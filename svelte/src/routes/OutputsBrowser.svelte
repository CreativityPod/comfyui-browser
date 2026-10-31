<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { t } from 'svelte-i18n';
  import { onLoadWorkflow, fetchFiles, getLocalConfig, setLocalConfig } from './utils';
  import type { FOLDER_TYPES } from './utils';
  import {
    fetchFolderTree, findFolder, ancestorPaths, matchingPaths, sortFolders, flattenTree, movePath,
  } from './folderTree';
  import type { FolderNode, FolderSort } from './folderTree';
  import FolderTreeRow from './FolderTreeRow.svelte';
  import MediaShow from './MediaShow.svelte';
  import ImageViewer from './ImageViewer.svelte';
  import type Toast from './Toast.svelte';

  export let comfyUrl: string;
  export let folderType: FOLDER_TYPES = 'outputs';
  export let toast: Toast;

  type FileSort = 'newest' | 'oldest' | 'name';
  type ThumbSize = 's' | 'm' | 'l';
  type VideoMode = 'play' | 'hover' | 'still';

  const configKey = 'outputsBrowser';
  const thumbWidths: Record<ThumbSize, number> = { s: 120, m: 180, l: 280 };
  const thumbSizes: Array<ThumbSize> = ['s', 'm', 'l'];
  const videoModes: Array<VideoMode> = ['play', 'hover', 'still'];
  const videoModeLabels: Record<VideoMode, string> = {
    play: 'Play video thumbnails',
    hover: 'Play video thumbnails on hover',
    still: 'Show video thumbnails as still frames',
  };
  const pageSize = 40;
  const subfolderPreview = 12;
  const maxRecent = 6;
  // A folder only counts as viewed once it has stayed open this long, so
  // arrowing through the tree doesn't flood the recent list.
  const recentDelay = 1000;

  let comfyApp: any;
  let tree: FolderNode | null = null;
  let treeError = false;
  let folderPath = '';
  let expanded = new Set<string>(['']);
  let recent: Array<string> = [];
  let pinned: Array<string> = [];
  let pinnedOpen = true;
  let recentOpen = true;
  let folderSort: FolderSort = 'recent';
  let fileSort: FileSort = 'newest';
  let thumbSize: ThumbSize = 'm';
  let videoMode: VideoMode = 'play';
  let videoAudio = true;
  let panelWidth = 260;
  let panelOpen = true;
  // Settings are read from localStorage on mount; nothing is saved before that.
  let restored = false;

  let files: Array<any> = [];
  let loaded = false;
  let showCursor = pageSize;
  let searchQuery = '';
  let folderQuery = '';
  let viewerIndex = -1;
  let loadId = 0;
  let showAllSubfolders = false;
  let renamingPath: string | null = null;
  let recentTimer: ReturnType<typeof setTimeout> | undefined;
  let filesTimer: ReturnType<typeof setTimeout> | undefined;

  let rootEl: HTMLElement;
  let mainEl: HTMLElement;
  let treeEl: HTMLElement;
  let treeListEl: HTMLElement;
  let layoutHeight = 600;
  let mainScrollTop = 0;

  $: tt = function(key: string) {
    return $t('outputsBrowser.' + key);
  }

  $: searchRegex = toRegex(searchQuery);
  $: currentNode = findFolder(tree, folderPath);
  // Without the tree endpoint (ComfyUI not restarted yet) fall back to the folder listing.
  $: subfolders = currentNode
    ? sortFolders(currentNode.children, folderSort)
    : files.filter((f) => f.type === 'dir').map((d) => ({
      name: d.name, path: d.path, media_count: -1, modified_at: d.created_at,
      created_at: d.created_at, children: [], truncated: false,
    }));
  $: shownSubfolders = subfolders.filter((d) => searchRegex.test(d.name.toLowerCase()));
  $: fileItems = sortFiles(
    files.filter((f) => f.type !== 'dir' && searchRegex.test(f.name.toLowerCase())),
    fileSort,
  );
  $: mediaFiles = fileItems.filter((f) => ['image', 'video'].includes(f.fileType));
  $: visible = tree && folderQuery.trim() ? matchingPaths(tree, folderQuery.trim()) : null;
  $: recentNodes = recent
    .filter((p) => p !== folderPath)
    .map((p) => findFolder(tree, p))
    .filter((n) => n) as Array<FolderNode>;
  $: pinnedNodes = pinned
    .map((p) => findFolder(tree, p))
    .filter((n) => n) as Array<FolderNode>;
  $: rows = tree ? flattenTree(tree, expanded, folderSort, visible) : [];
  $: breadcrumbs = folderPath ? folderPath.split('/') : [];
  $: gridStyle = `grid-template-columns: repeat(auto-fill, minmax(${thumbWidths[thumbSize]}px, 1fr));`;

  $: persist({
    folderPath, recent, pinned, pinnedOpen, recentOpen,
    folderSort, fileSort, thumbSize, panelWidth, panelOpen, expanded,
    videoMode, videoAudio,
  });

  function persist(state: any) {
    if (!restored) return;
    setLocalConfig(configKey, { ...state, expanded: [...state.expanded] });
  }

  function toRegex(query: string) {
    try {
      return new RegExp(query.toLowerCase());
    } catch {
      return new RegExp('');
    }
  }

  function sortFiles(list: Array<any>, mode: FileSort) {
    const sorted = [...list];
    if (mode === 'name') {
      const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
      sorted.sort((a, b) => collator.compare(a.name, b.name));
    } else if (mode === 'oldest') {
      sorted.sort((a, b) => a.created_at - b.created_at);
    } else {
      sorted.sort((a, b) => b.created_at - a.created_at);
    }
    return sorted;
  }

  async function loadTree() {
    try {
      tree = await fetchFolderTree(comfyUrl, folderType);
      treeError = false;
    } catch (e) {
      console.error('[comfyui-browser]', e);
      treeError = true;
    }
    // The remembered folder may have been deleted or renamed outside the browser.
    if (tree && !findFolder(tree, folderPath)) {
      await openFolder('');
    }
    recent = recent.filter((p) => !tree || findFolder(tree, p));
    pinned = pinned.filter((p) => !tree || findFolder(tree, p));
  }

  async function loadFiles() {
    const id = ++loadId;
    loaded = false;
    let list: Array<any> = [];
    try {
      list = await fetchFiles(folderType, comfyUrl, folderPath);
    } catch (e) {
      console.error('[comfyui-browser]', e);
    }
    if (id !== loadId) {
      return;
    }
    files = list;
    loaded = true;
  }

  export async function refresh() {
    await Promise.all([loadTree(), loadFiles()]);
  }

  // fromKeyboard: keep the folder collapsed and wait a moment before loading,
  // so holding an arrow key doesn't fire a request for every folder passed.
  async function openFolder(path: string, fromKeyboard = false) {
    const changed = path !== folderPath;
    folderPath = path;
    viewerIndex = -1;
    showCursor = pageSize;
    if (changed) showAllSubfolders = false;
    clearTimeout(recentTimer);
    if (path) {
      recentTimer = setTimeout(() => {
        if (folderPath === path) {
          recent = [path, ...recent.filter((p) => p !== path)].slice(0, maxRecent);
        }
      }, recentDelay);
    }
    for (const p of fromKeyboard ? ancestorPaths(path) : [...ancestorPaths(path), path]) {
      expanded.add(p);
    }
    expanded = expanded;
    if (changed) {
      files = [];
      loaded = false;
      if (mainEl) mainEl.scrollTop = 0;
    }
    clearTimeout(filesTimer);
    if (fromKeyboard) {
      filesTimer = setTimeout(loadFiles, 150);
    } else {
      loadFiles();
    }
    await tick();
    revealInTree(path);
  }

  function revealInTree(path: string) {
    const row = treeEl?.querySelector(`[data-path="${CSS.escape(path)}"]`);
    row?.scrollIntoView({ block: 'nearest' });
  }

  function onSelectFolder(path: string) {
    if (path === folderPath && path !== '') {
      onToggleFolder(path);
      return;
    }
    openFolder(path);
  }

  function onToggleFolder(path: string) {
    if (expanded.has(path)) {
      expanded.delete(path);
    } else {
      expanded.add(path);
    }
    expanded = expanded;
  }

  function onTreeKeydown(e: KeyboardEvent) {
    if (viewerIndex >= 0 || renamingPath !== null || rows.length === 0) {
      return;
    }
    const i = rows.findIndex((r) => r.node.path === folderPath);
    const row = rows[i];
    let target: string | undefined;

    switch (e.key) {
      case 'ArrowDown':
        target = rows[i < 0 ? 0 : Math.min(i + 1, rows.length - 1)].node.path;
        break;
      case 'ArrowUp':
        target = rows[i < 0 ? 0 : Math.max(i - 1, 0)].node.path;
        break;
      case 'Home':
        target = rows[0].node.path;
        break;
      case 'End':
        target = rows[rows.length - 1].node.path;
        break;
      case 'ArrowRight':
        if (row && row.node.children.length > 0) {
          if (row.open) {
            target = rows[i + 1]?.node.path;
          } else {
            onToggleFolder(row.node.path);
          }
        }
        break;
      case 'ArrowLeft':
        if (row?.open && !visible) {
          onToggleFolder(row.node.path);
        } else if (row && row.parent !== null) {
          target = row.parent;
        }
        break;
      case 'Enter':
      case ' ':
        if (row && row.node.children.length > 0 && !visible) {
          onToggleFolder(row.node.path);
        }
        break;
      case 'F2':
        if (folderPath) startRename(folderPath);
        break;
      case 'Delete':
      case 'Backspace':
        if (e.key === 'Backspace' && !(e.metaKey || e.ctrlKey)) return;
        if (row && row.node.path) onDeleteFolder(row.node);
        break;
      default:
        return;
    }
    e.preventDefault();
    if (target !== undefined && target !== folderPath) {
      openFolder(target, true);
    }
  }

  function togglePin(path: string) {
    pinned = pinned.includes(path)
      ? pinned.filter((p) => p !== path)
      : [...pinned, path];
  }

  async function startRename(path: string) {
    if (!path) return;
    panelOpen = true;
    folderQuery = '';
    for (const p of ancestorPaths(path)) {
      expanded.add(p);
    }
    expanded = expanded;
    renamingPath = path;
    await tick();
    revealInTree(path);
  }

  async function onRename(node: FolderNode, newName: string | null) {
    // Enter commits, and the input then blurs and calls this again; ignore that.
    if (renamingPath !== node.path) return;
    renamingPath = null;
    newName = (newName || '').trim();
    if (!newName || newName === node.name) {
      treeListEl?.focus();
      return;
    }

    const parent = parentOf(node.path);
    const res = await fetch(comfyUrl + '/browser/files/rename', {
      method: 'POST',
      body: JSON.stringify({
        folder_type: folderType,
        folder_path: parent,
        filename: node.name,
        new_name: newName,
      }),
    });
    let message = '';
    try {
      message = (await res.json()).message || '';
    } catch {}
    toast.show(
      res.ok,
      tt('Renamed to') + ' ' + newName,
      tt('Failed to rename') + (message ? ': ' + message : ''),
    );
    if (!res.ok) {
      treeListEl?.focus();
      return;
    }

    const to = parent ? `${parent}/${newName}` : newName;
    const move = (p: string) => movePath(p, node.path, to);
    recent = recent.map(move);
    pinned = pinned.map(move);
    expanded = new Set([...expanded].map(move));
    const newFolderPath = move(folderPath);
    await loadTree();
    await openFolder(newFolderPath, true);
    treeListEl?.focus();
  }

  function collapseAll() {
    expanded = new Set(ancestorPaths(folderPath));
  }

  function parentOf(path: string) {
    return path.split('/').slice(0, -1).join('/');
  }

  async function collect(filename: string, parentPath: string) {
    const res = await fetch(comfyUrl + '/browser/collections', {
      method: 'POST',
      body: JSON.stringify({
        filename,
        folder_path: parentPath,
        folder_type: folderType,
      }),
    });
    toast.show(
      res.ok,
      $t('filesList.Added to Saves'),
      $t('filesList.Failed to add to Saves'),
    );
  }

  async function remove(filename: string, parentPath: string) {
    const res = await fetch(comfyUrl + '/browser/files', {
      method: 'DELETE',
      body: JSON.stringify({
        folder_type: folderType,
        filename,
        folder_path: parentPath,
      }),
    });
    toast.show(
      res.ok,
      $t('filesList.Deleted the file') + filename,
      $t('filesList.Failed to delete the file'),
    );
    return res.ok;
  }

  async function onDeleteFolder(node: FolderNode) {
    if (!confirm(tt('Delete this folder and everything in it?') + '\n' + node.path)) {
      return;
    }
    const ok = await remove(node.name, parentOf(node.path));
    if (!ok) {
      return;
    }
    const gone = (p: string) => p === node.path || p.startsWith(node.path + '/');
    recent = recent.filter((p) => !gone(p));
    pinned = pinned.filter((p) => !gone(p));
    if (folderPath === node.path || folderPath.startsWith(node.path + '/')) {
      await openFolder(parentOf(node.path));
    }
    await refresh();
  }

  async function onCollectFile(file: any) {
    await collect(file.name, file.folder_path);
  }

  async function onDeleteFile(file: any) {
    if (!confirm($t('filesList.You want to delete this file?') + ' ' + file.name)) {
      return;
    }
    if (await remove(file.name, file.folder_path)) {
      files = files.filter((f) => f !== file);
      loadTree();
    }
  }

  function onOpenFile(file: any) {
    viewerIndex = mediaFiles.indexOf(file);
  }

  function onMainScroll() {
    mainScrollTop = mainEl.scrollTop;
    if (showCursor < fileItems.length
      && mainEl.scrollTop + mainEl.clientHeight >= mainEl.scrollHeight - 400) {
      showCursor += pageSize;
    }
  }

  function updateLayoutHeight() {
    if (!rootEl) return;
    const top = rootEl.getBoundingClientRect().top + window.scrollY;
    layoutHeight = Math.max(300, window.innerHeight - top);
  }

  function startResize(e: PointerEvent) {
    const startX = e.clientX;
    const startWidth = panelWidth;
    const move = (ev: PointerEvent) => {
      panelWidth = Math.min(600, Math.max(160, startWidth + ev.clientX - startX));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  const onBrowserShow = () => refresh();

  onMount(async () => {
    //@ts-ignore
    comfyApp = window.top.app;
    //@ts-ignore
    window.top.addEventListener('comfyuiBrowserShow', onBrowserShow);

    const saved = getLocalConfig()[configKey] || {};
    folderPath = saved.folderPath || '';
    expanded = new Set<string>(saved.expanded || ['']);
    recent = saved.recent || [];
    pinned = saved.pinned || [];
    pinnedOpen = saved.pinnedOpen ?? true;
    recentOpen = saved.recentOpen ?? true;
    folderSort = saved.folderSort || folderSort;
    fileSort = saved.fileSort || fileSort;
    thumbSize = saved.thumbSize || thumbSize;
    videoMode = videoModes.includes(saved.videoMode) ? saved.videoMode : videoMode;
    videoAudio = saved.videoAudio ?? videoAudio;
    panelWidth = saved.panelWidth || panelWidth;
    panelOpen = saved.panelOpen ?? window.innerWidth >= 640;
    restored = true;
    updateLayoutHeight();
    await openFolder(folderPath);
    await loadTree();
    await tick();
    revealInTree(folderPath);
  });

  onDestroy(() => {
    if (typeof window === 'undefined') return;
    //@ts-ignore
    window.top?.removeEventListener('comfyuiBrowserShow', onBrowserShow);
  });
</script>

<svelte:window on:resize={updateLayoutHeight} />

<div bind:this={rootEl} class="flex w-full overflow-hidden" style="height: {layoutHeight}px">
  {#if panelOpen}
    <!-- Folder tree -->
    <aside
      class="flex flex-col shrink-0 bg-base-200 border-r border-base-300"
      style="width: {panelWidth}px"
    >
      <div class="flex items-center gap-1 p-2 border-b border-base-300">
        <input
          type="text"
          placeholder={tt('Find folder')}
          bind:value={folderQuery}
          class="input input-bordered input-sm w-full min-w-0 rounded"
        />
        <div class="join shrink-0">
          <button
            class="btn btn-xs join-item {folderSort === 'recent' ? 'btn-active' : 'btn-ghost'}"
            title={tt('Recently changed first')}
            on:click={() => folderSort = 'recent'}
          >{tt('Recent')}</button>
          <button
            class="btn btn-xs join-item {folderSort === 'name' ? 'btn-active' : 'btn-ghost'}"
            title={tt('Sort by name')}
            on:click={() => folderSort = 'name'}
          >A–Z</button>
        </div>
      </div>

      <div bind:this={treeEl} class="flex-1 overflow-auto p-1">
        {#if !folderQuery}
          {#each [
            { key: 'pinned', label: tt('Pinned'), nodes: pinnedNodes, open: pinnedOpen },
            { key: 'recent', label: tt('Recently viewed'), nodes: recentNodes, open: recentOpen },
          ] as section (section.key)}
            {#if section.nodes.length > 0}
              <button
                class="w-full flex items-center gap-1 px-2 pt-1 pb-0.5 text-xs uppercase tracking-wide opacity-50 hover:opacity-80"
                aria-expanded={section.open}
                on:click={() => section.key === 'pinned' ? pinnedOpen = !pinnedOpen : recentOpen = !recentOpen}
              >
                <svg class="w-2.5 h-2.5 transition-transform {section.open ? 'rotate-90' : ''}" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M7 4l6 6-6 6V4z" />
                </svg>
                <span class="flex-1 text-left">{section.label}</span>
                {#if !section.open}<span class="normal-case tracking-normal">{section.nodes.length}</span>{/if}
              </button>
              {#if section.open}
                <ul class="mb-2">
                  {#each section.nodes as node (node.path)}
                    <li class="group flex items-center h-7 rounded hover:bg-base-300 {node.path === folderPath ? 'bg-primary/10' : ''}">
                      <button
                        class="flex-1 min-w-0 flex items-center h-full pl-2 pr-1 text-sm text-left"
                        title={node.path}
                        on:click={() => openFolder(node.path)}
                      >
                        {#if section.key === 'pinned'}
                          <svg class="w-3.5 h-3.5 mr-1.5 shrink-0 text-warning" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
                          </svg>
                        {:else}
                          <svg class="w-3.5 h-3.5 mr-1.5 shrink-0 opacity-50" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z" clip-rule="evenodd" />
                          </svg>
                        {/if}
                        <span class="truncate flex-1">{node.name}</span>
                        {#if node.path.includes('/')}
                          <span class="truncate max-w-[45%] ml-1 text-xs opacity-40">{parentOf(node.path)}</span>
                        {/if}
                      </button>
                      {#if section.key === 'pinned'}
                        <button
                          class="hidden group-hover:block shrink-0 p-0.5 mr-1 rounded hover:bg-base-100 opacity-70"
                          title={tt('Unpin')}
                          aria-label={tt('Unpin')}
                          on:click={() => togglePin(node.path)}
                        >
                          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      {/if}
                    </li>
                  {/each}
                </ul>
              {/if}
            {/if}
          {/each}

          <div class="px-2 pb-0.5 text-xs uppercase tracking-wide opacity-50 flex items-center">
            <span class="flex-1">{tt('Folders')}</span>
            <button class="normal-case tracking-normal hover:opacity-100 opacity-80" on:click={collapseAll}>{tt('Collapse all')}</button>
          </div>
        {/if}

        {#if tree}
          <!-- svelte-ignore a11y-no-noninteractive-tabindex a11y-no-noninteractive-element-interactions -->
          <ul
            bind:this={treeListEl}
            role="tree"
            tabindex="0"
            aria-label={tt('Folders')}
            aria-activedescendant={'tree-row-' + encodeURIComponent(folderPath)}
            class="rounded outline-none focus-visible:ring-1 focus-visible:ring-primary/60"
            on:keydown={onTreeKeydown}
          >
            {#each rows as row (row.node.path)}
              <FolderTreeRow
                {row}
                selected={row.node.path === folderPath}
                pinned={pinned.includes(row.node.path)}
                renaming={renamingPath === row.node.path}
                onSelect={onSelectFolder}
                onToggle={onToggleFolder}
                onPin={togglePin}
                onStartRename={startRename}
                {onRename}
                onDelete={onDeleteFolder}
              />
            {/each}
          </ul>
          {#if visible && visible.size === 0}
            <p class="px-2 py-3 text-sm opacity-60">{tt('No folders match')}</p>
          {/if}
          {#if tree.truncated}
            <p class="px-2 py-2 text-xs opacity-50">{tt('Tree truncated')}</p>
          {/if}
        {:else if treeError}
          <p class="px-2 py-3 text-sm opacity-70">{tt('Tree unavailable')}</p>
        {:else}
          <p class="px-2 py-3 text-sm opacity-60">{$t('common.loading')}</p>
        {/if}
      </div>
    </aside>

    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div
      class="w-1 shrink-0 cursor-col-resize hover:bg-primary/40 active:bg-primary/60"
      title={tt('Drag to resize')}
      on:pointerdown|preventDefault={startResize}
    ></div>
  {/if}

  <!-- Thumbnails -->
  <section
    bind:this={mainEl}
    on:scroll={onMainScroll}
    class="flex-1 min-w-0 overflow-auto"
  >
    <div class="sticky top-0 z-10 bg-base-100/95 backdrop-blur border-b border-base-300 px-3 py-2 flex flex-wrap items-center gap-2">
      <button
        class="btn btn-ghost btn-sm btn-square"
        title={panelOpen ? tt('Hide folders') : tt('Show folders')}
        aria-label={panelOpen ? tt('Hide folders') : tt('Show folders')}
        on:click={() => panelOpen = !panelOpen}
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      <div class="text-sm breadcrumbs py-0 flex-1 min-w-[10rem]">
        <ul>
          <li><button class="hover:underline" on:click={() => openFolder('')}>{tt('Output folder')}</button></li>
          {#each breadcrumbs as part, index}
            <li>
              <button
                class="hover:underline {index === breadcrumbs.length - 1 ? 'font-semibold' : ''}"
                on:click={() => openFolder(breadcrumbs.slice(0, index + 1).join('/'))}
              >{part}</button>
            </li>
          {/each}
        </ul>
      </div>

      <input
        type="text"
        placeholder={$t('filesList.searchInput.placeholder')}
        bind:value={searchQuery}
        class="input input-bordered input-sm w-40 lg:w-56 rounded"
      />

      <select bind:value={fileSort} class="select select-bordered select-sm rounded" aria-label={tt('Sort files')}>
        <option value="newest">{tt('Newest first')}</option>
        <option value="oldest">{tt('Oldest first')}</option>
        <option value="name">{tt('Name')}</option>
      </select>

      <div class="join" role="group" aria-label={tt('Thumbnail size')}>
        {#each thumbSizes as size}
          <button
            class="btn btn-sm join-item {thumbSize === size ? 'btn-active' : 'btn-ghost'}"
            title={tt('Thumbnail size')}
            on:click={() => thumbSize = size}
          >{size.toUpperCase()}</button>
        {/each}
      </div>

      <div class="flex items-center gap-0.5 p-0.5 rounded-lg border border-base-content/30" role="group" aria-label={tt('Video thumbnails')}>
        {#each videoModes as mode}
          <button
            class="btn btn-square h-7 w-7 min-h-0 rounded-md {videoMode === mode ? 'btn-primary' : 'btn-ghost opacity-60 hover:opacity-100'}"
            title={tt(videoModeLabels[mode])}
            aria-label={tt(videoModeLabels[mode])}
            aria-pressed={videoMode === mode}
            on:click={() => videoMode = mode}
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
              {#if mode === 'play'}
                <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
              {:else if mode === 'hover'}
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.042 21.672L13.684 16.6m0 0l-2.51 2.225.569-9.47 5.227 7.917-3.286-.672zM12 2.25V4.5m5.834.166l-1.591 1.591M20.25 10.5H18M7.757 14.743l-1.59 1.59M6 10.5H3.75m4.007-4.243l-1.59-1.59" />
              {:else}
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
              {/if}
            </svg>
          </button>
        {/each}
      </div>

      <button
        class="btn btn-sm btn-square {videoAudio ? 'btn-active' : 'btn-ghost'}"
        title={tt(videoAudio ? 'Viewer audio on' : 'Viewer audio off')}
        aria-label={tt('Viewer audio')}
        aria-pressed={videoAudio}
        on:click={() => videoAudio = !videoAudio}
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
          {#if videoAudio}
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
          {:else}
            <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 9.75L19.5 12m0 0l2.25 2.25M19.5 12l2.25-2.25M19.5 12l-2.25 2.25m-10.5-6l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
          {/if}
        </svg>
      </button>

      <button class="btn btn-ghost btn-sm btn-square" title={$t('common.btn.refresh')} aria-label={$t('common.btn.refresh')} on:click={refresh}>
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
        </svg>
      </button>
    </div>

    <div class="p-3">
      {#if shownSubfolders.length > 0}
        <div class="mb-4">
          <div class="text-xs uppercase tracking-wide opacity-50 mb-1.5">{tt('Subfolders')} · {shownSubfolders.length}</div>
          <div class="grid gap-2" style="grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));">
            {#each showAllSubfolders ? shownSubfolders : shownSubfolders.slice(0, subfolderPreview) as dir (dir.path)}
              <div class="group flex items-center gap-2 px-2 py-1.5 rounded bg-base-200 hover:bg-base-300">
                <button class="flex items-center gap-2 flex-1 min-w-0 text-left" on:click={() => openFolder(dir.path)} title={dir.path}>
                  <svg class="w-6 h-6 shrink-0 text-primary/80" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19.5 21a3 3 0 003-3v-4.5a3 3 0 00-3-3h-15a3 3 0 00-3 3V18a3 3 0 003 3h15zM1.5 10.146V6a3 3 0 013-3h5.379a2.25 2.25 0 011.59.659l2.122 2.121c.14.141.331.22.53.22H19.5a3 3 0 013 3v1.146A4.483 4.483 0 0019.5 9h-15a4.483 4.483 0 00-3 1.146z" />
                  </svg>
                  <span class="min-w-0">
                    <span class="block truncate text-sm font-semibold">{dir.name}</span>
                    {#if dir.media_count >= 0}
                      <span class="block truncate text-xs opacity-50">
                        {dir.media_count} {tt('items')}{dir.children.length ? ` · ${dir.children.length} ${tt('folders')}` : ''}
                      </span>
                    {/if}
                  </span>
                </button>
                <span class="hidden shrink-0 group-hover:flex focus-within:flex">
                  {#if dir.media_count >= 0}
                    <button class="btn btn-ghost btn-xs px-1 {pinned.includes(dir.path) ? 'text-warning' : ''}" on:click={() => togglePin(dir.path)}>
                      {pinned.includes(dir.path) ? tt('Unpin') : tt('Pin')}
                    </button>
                    <button class="btn btn-ghost btn-xs px-1" on:click={() => startRename(dir.path)}>{tt('Rename')}</button>
                  {/if}
                  <button class="btn btn-ghost btn-xs px-1 text-error" on:click={() => onDeleteFolder(dir)}>{$t('common.btn.delete')}</button>
                </span>
              </div>
            {/each}
          </div>
          {#if shownSubfolders.length > subfolderPreview}
            <button class="btn btn-ghost btn-xs mt-1" on:click={() => showAllSubfolders = !showAllSubfolders}>
              {showAllSubfolders ? tt('Show fewer') : `${tt('Show all')} (${shownSubfolders.length})`}
            </button>
          {/if}
        </div>
      {/if}

      {#if fileItems.length > 0}
        <div class="grid gap-2" style={gridStyle}>
          {#each fileItems.slice(0, showCursor) as file (file.name)}
            <div class="p-2 bg-info-content rounded flex flex-col min-w-0">
              <MediaShow {file} {videoMode} styleClass="w-full aspect-square flex items-center justify-center" onClickDir={() => {}} onOpen={onOpenFile} />

              <p class="font-bold text-sm leading-5 mt-1 truncate" title={file.name}>{file.name}</p>
              {#if thumbSize !== 's'}
                <p class="text-gray-500 text-xs truncate">{file.formattedDatetime} · {file.formattedSize}</p>
              {/if}

              <div class="flex items-center mt-auto pt-0.5">
                {#if comfyApp}
                  <button
                    class="btn btn-link btn-sm p-0 min-h-0 h-6 no-underline text-accent mr-2"
                    on:click={async () => await onLoadWorkflow(file, comfyApp, toast)}
                  >{$t('common.btn.load')}</button>
                {/if}
                <button
                  class="btn btn-link btn-sm p-0 min-h-0 h-6 no-underline text-accent"
                  on:click={async () => await onCollectFile(file)}
                >{$t('common.btn.save')}</button>
                <button
                  class="btn btn-link btn-sm p-0 min-h-0 h-6 no-underline text-error ml-auto"
                  title={$t('common.btn.delete')}
                  on:click={async () => await onDeleteFile(file)}
                >
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M16 2v4h6v2h-2v14H4V8H2V6h6V2h8zm-2 2h-4v2h4V4zm0 4H6v12h12V8h-4zm-5 2h2v8H9v-8zm6 0h-2v8h2v-8z" fill="#f77"/>
                  </svg>
                  {#if thumbSize !== 's'}{$t('common.btn.delete')}{/if}
                </button>
              </div>
            </div>
          {/each}
        </div>

        {#if fileItems.length > showCursor}
          <div class="flex justify-center py-4">
            <button on:click={() => showCursor += pageSize} class="btn btn-neutral btn-outline btn-sm">
              {tt('Load more')} ({fileItems.length - showCursor})
            </button>
          </div>
        {/if}
      {:else if shownSubfolders.length === 0}
        <div class="w-full py-24 flex items-center justify-center">
          <span class="font-bold text-2xl opacity-60">
            {loaded ? $t('common.emptyList') : $t('common.loading')}
          </span>
        </div>
      {/if}
    </div>
  </section>
</div>

{#if mainScrollTop >= 300}
  <button
    class="fixed right-10 bottom-10 w-10 h-10 flex justify-center items-center rounded-full bg-slate-50"
    aria-label="Top"
    on:click={() => mainEl.scrollTo({ top: 0 })}
  >
    <svg class="w-5 h-5 icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
      <path fill="#333333" d="M572.235 205.282v600.365a30.118 30.118 0 11-60.235 0V205.282L292.382 438.633a28.913 28.913 0 01-42.646 0 33.43 33.43 0 010-45.236l271.058-288.045a28.913 28.913 0 0142.647 0L834.5 393.397a33.43 33.43 0 010 45.176 28.913 28.913 0 01-42.647 0l-219.618-233.23z"/>
    </svg>
  </button>
{/if}

{#if viewerIndex >= 0 && mediaFiles[viewerIndex]}
  <ImageViewer
    files={mediaFiles}
    bind:index={viewerIndex}
    {comfyUrl}
    {folderType}
    {comfyApp}
    {toast}
    audio={videoAudio}
    onClose={() => viewerIndex = -1}
  />
{/if}
