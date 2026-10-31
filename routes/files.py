from aiohttp import web
import json
from os import path
import os
import shutil
import time

from PIL import Image

from ..utils import get_target_folder_files, get_parent_path, get_info_filename, \
    image_extensions, video_extensions

# folder_path, folder_type
async def api_get_files(request):
    folder_path = request.query.get('folder_path', '')
    folder_type = request.query.get('folder_type', 'outputs')
    files = get_target_folder_files(folder_path, folder_type=folder_type)

    if files == None:
        return web.Response(status=404)

    return web.json_response({
        'files': files
    })


def build_folder_tree(dir_path: str, rel_path: str, deadline: float):
    node = {
        "name": path.basename(dir_path) if rel_path else "",
        "path": rel_path,
        "media_count": 0,
        "modified_at": 0,
        "created_at": 0,
        "children": [],
        "truncated": False,
    }
    try:
        stat = os.stat(dir_path)
        node["created_at"] = stat.st_ctime
        node["modified_at"] = stat.st_mtime
        entries = list(os.scandir(dir_path))
    except OSError:
        return node

    for entry in entries:
        name = entry.name
        if name.startswith('.'):
            continue
        try:
            if entry.is_dir(follow_symlinks=False):
                if time.monotonic() > deadline:
                    node["truncated"] = True
                    continue
                child_rel = f'{rel_path}/{name}' if rel_path else name
                node["children"].append(build_folder_tree(entry.path, child_rel, deadline))
            elif entry.is_file():
                ext = path.splitext(name)[1].lower()
                if ext in image_extensions or ext in video_extensions:
                    node["media_count"] += 1
                    node["modified_at"] = max(node["modified_at"], entry.stat().st_mtime)
        except OSError:
            continue

    # A folder counts as recently active when anything below it changed.
    for child in node["children"]:
        node["modified_at"] = max(node["modified_at"], child["modified_at"])

    return node


# folder_type
async def api_get_folder_tree(request):
    folder_type = request.query.get('folder_type', 'outputs')
    parent_path = get_parent_path(folder_type)
    if not path.isdir(parent_path):
        return web.json_response({'tree': None}, status=404)

    # Very large trees are cut off after a few seconds rather than hanging the UI.
    tree = build_folder_tree(parent_path, '', time.monotonic() + 5)
    return web.json_response({'tree': tree})


# filename, folder_path, folder_type
async def api_delete_file(request):
    json_data = await request.json()
    filename = json_data['filename']
    folder_path = json_data.get('folder_path', '')
    folder_type = json_data.get('folder_type', 'outputs')

    parent_path = get_parent_path(folder_type)
    target_path = path.join(parent_path, folder_path, filename)
    if not path.exists(target_path):
        return web.json_response(status=404)

    if path.isdir(target_path):
        shutil.rmtree(target_path)
    else:
        os.remove(target_path)
    info_file_path = get_info_filename(target_path)
    if path.exists(info_file_path):
        os.remove(info_file_path)

    return web.Response(status=201)


# filename, folder_path, folder_type, new_data: {}
async def api_update_file(request):
    json_data = await request.json()
    filename = json_data['filename']
    folder_path = json_data.get('folder_path', '')
    folder_type = json_data.get('folder_type', 'outputs')
    parent_path = get_parent_path(folder_type)

    new_data = json_data.get('new_data', None)
    if not new_data:
        return web.Response(status=400)

    new_filename = new_data['filename']
    notes = new_data['notes']

    old_file_path = path.join(parent_path, folder_path, filename)
    new_file_path = path.join(parent_path, folder_path, new_filename)

    if not path.exists(old_file_path):
        return web.Response(status=404)

    if new_filename and filename != new_filename:
        shutil.move(
            old_file_path,
            new_file_path
        )
        old_info_file_path = get_info_filename(old_file_path)
        if path.exists(old_info_file_path):
            new_info_file_path = get_info_filename(new_file_path)
            shutil.move(
                old_info_file_path,
                new_info_file_path
            )

    if notes:
        extra = {
            "notes": notes
        }
        info_file_path = get_info_filename(new_file_path)
        with open(info_file_path, "w", encoding="utf-8") as outfile:
            json.dump(extra, outfile)

    return web.Response(status=201)

def is_safe_name(name: str):
    return bool(name) and name not in ('.', '..') and not name.startswith('.') \
        and '/' not in name and '\\' not in name and '\0' not in name


# folder_path, folder_type, filename, new_name
async def api_rename_folder(request):
    json_data = await request.json()
    folder_path = json_data.get('folder_path', '')
    folder_type = json_data.get('folder_type', 'outputs')
    filename = json_data.get('filename', '')
    new_name = (json_data.get('new_name') or '').strip()

    if '..' in folder_path.split('/') or not is_safe_name(filename):
        return web.json_response({'message': 'Invalid folder'}, status=400)
    if not is_safe_name(new_name):
        return web.json_response({'message': 'Invalid name'}, status=400)

    parent_path = path.join(get_parent_path(folder_type), folder_path)
    old_path = path.join(parent_path, filename)
    new_path = path.join(parent_path, new_name)
    if not path.isdir(old_path):
        return web.json_response({'message': 'Folder not found'}, status=404)
    # A case-only rename on macOS points at the same folder, so allow that one.
    if path.exists(new_path) and not path.samefile(old_path, new_path):
        return web.json_response({'message': 'A folder with that name already exists'}, status=409)

    os.rename(old_path, new_path)
    return web.json_response({'path': f'{folder_path}/{new_name}' if folder_path else new_name})


# filename, folder_path, folder_type
async def api_view_file(request):
    folder_type = request.query.get("folder_type", "outputs")
    folder_path = request.query.get("folder_path", "")
    filename = request.query.get("filename", None)
    if not filename:
        return web.Response(status=404)

    parent_path = get_parent_path(folder_type)
    file_path = path.join(parent_path, folder_path, filename)

    if not path.exists(file_path):
        return web.Response(status=404)

    with open(file_path, 'rb') as f:
        media_file = f.read()

    content_type = 'application/json'
    file_extension = path.splitext(filename)[1].lower()
    if file_extension in image_extensions:
        content_type = f'image/{file_extension[1:]}'
    if file_extension in video_extensions:
        content_type = f'video/{file_extension[1:]}'

    return web.Response(
        body=media_file,
        content_type=content_type,
        headers={"Content-Disposition": f"filename=\"{filename}\""}
    )


def parse_json_or_none(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def read_image_generation_info(img, metadata):
    info = img.info or {}
    metadata["workflow"] = metadata["workflow"] or parse_json_or_none(info.get("workflow"))
    metadata["prompt"] = metadata["prompt"] or parse_json_or_none(info.get("prompt"))
    if isinstance(info.get("parameters"), str):
        metadata["parameters"] = info["parameters"]

    # SaveAnimatedWEBP stores them in EXIF: Make (0x010F) = "workflow:{...}",
    # Model (0x0110) = "prompt:{...}"
    for tag_value in img.getexif().values():
        if not isinstance(tag_value, str):
            continue
        key, sep, value = tag_value.partition(':')
        if sep and key in ("workflow", "prompt") and not metadata[key]:
            metadata[key] = parse_json_or_none(value)


def read_video_metadata(file_path, metadata):
    # PyAV is a ComfyUI dependency; imported here so the plugin still loads without it.
    import av

    with av.open(file_path) as container:
        tags = {key.lower(): value for key, value in container.metadata.items()}
        if container.streams.video:
            codec = container.streams.video[0].codec_context
            metadata["width"], metadata["height"] = codec.width or None, codec.height or None

    # VideoHelperSuite and ComfyUI's SaveVideo / SaveWEBM write "prompt" and "workflow" tags.
    metadata["workflow"] = parse_json_or_none(tags.get("workflow"))
    metadata["prompt"] = parse_json_or_none(tags.get("prompt"))

    # Older VideoHelperSuite versions put both into one "comment" tag:
    # {"prompt": "<json string>", "workflow": {...}}
    comment = parse_json_or_none(tags.get("comment"))
    if isinstance(comment, dict):
        for key in ("workflow", "prompt"):
            value = comment.get(key)
            if not metadata[key] and value:
                metadata[key] = value if isinstance(value, (dict, list)) else parse_json_or_none(value)

# filename, folder_path, folder_type
async def api_get_file_metadata(request):
    folder_type = request.query.get("folder_type", "outputs")
    folder_path = request.query.get("folder_path", "")
    filename = request.query.get("filename", None)
    if not filename or '..' in folder_path or '..' in filename:
        return web.Response(status=404)

    parent_path = get_parent_path(folder_type)
    file_path = path.join(parent_path, folder_path, filename)
    if not path.isfile(file_path):
        return web.Response(status=404)

    metadata = {
        "width": None,
        "height": None,
        "format": path.splitext(filename)[1][1:].lower(),
        "workflow": None,
        "prompt": None,
        "parameters": None,
    }

    extension = path.splitext(filename)[1].lower()
    if extension in image_extensions:
        try:
            with Image.open(file_path) as img:
                metadata["width"], metadata["height"] = img.size
                metadata["format"] = (img.format or metadata["format"]).lower()
                read_image_generation_info(img, metadata)
        except Exception as e:
            print(f'[comfyui-browser] failed to read metadata of {file_path}: {e}')
    elif extension in video_extensions:
        try:
            read_video_metadata(file_path, metadata)
        except Exception as e:
            print(f'[comfyui-browser] failed to read metadata of {file_path}: {e}')

        # VideoHelperSuite also saves the first frame as a PNG with the same metadata.
        if not metadata["workflow"] and not metadata["prompt"]:
            stem = path.splitext(file_path)[0]
            for png_path in (stem + '.png', stem.removesuffix('-audio') + '.png'):
                if not path.isfile(png_path):
                    continue
                try:
                    with Image.open(png_path) as img:
                        read_image_generation_info(img, metadata)
                except Exception as e:
                    print(f'[comfyui-browser] failed to read metadata of {png_path}: {e}')
                break

    if not metadata["workflow"]:
        json_path = path.splitext(file_path)[0] + '.json'
        if path.isfile(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                metadata["workflow"] = parse_json_or_none(f.read())

    return web.json_response(metadata)
