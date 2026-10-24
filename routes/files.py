from aiohttp import web
import json
from os import path
import os
import shutil

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

    if path.splitext(filename)[1].lower() in image_extensions:
        try:
            with Image.open(file_path) as img:
                metadata["width"], metadata["height"] = img.size
                metadata["format"] = (img.format or metadata["format"]).lower()
                info = img.info or {}
                metadata["workflow"] = parse_json_or_none(info.get("workflow"))
                metadata["prompt"] = parse_json_or_none(info.get("prompt"))
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
        except Exception as e:
            print(f'[comfyui-browser] failed to read metadata of {file_path}: {e}')

    if not metadata["workflow"]:
        json_path = path.splitext(file_path)[0] + '.json'
        if path.isfile(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                metadata["workflow"] = parse_json_or_none(f.read())

    return web.json_response(metadata)
