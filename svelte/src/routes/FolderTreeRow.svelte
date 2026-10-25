<script lang="ts">
  import { t } from 'svelte-i18n';
  import type { TreeRow } from './folderTree';

  export let row: TreeRow;
  export let selected: boolean;
  export let pinned: boolean;
  export let renaming: boolean;
  export let onSelect: Function;
  export let onToggle: Function;
  export let onPin: Function;
  export let onStartRename: Function;
  export let onRename: Function;
  export let onDelete: Function;

  let newName = '';

  $: tt = function(key: string) {
    return $t('outputsBrowser.' + key);
  }

  $: node = row.node;
  $: label = node.name || tt('Output folder');
  $: modified = node.modified_at
    ? new Date(node.modified_at * 1000).toLocaleString()
    : '';
  function focusInput(el: HTMLInputElement) {
    newName = node.name;
    el.value = newName;
    el.focus();
    el.select();
  }

  function onRenameKeydown(e: KeyboardEvent) {
    e.stopPropagation();
    if (e.key === 'Enter') {
      onRename(node, newName);
    } else if (e.key === 'Escape') {
      onRename(node, null);
    }
  }
</script>

<li
  id={'tree-row-' + encodeURIComponent(node.path)}
  role="treeitem"
  aria-selected={selected}
  aria-expanded={node.children.length > 0 ? row.open : undefined}
  aria-level={row.depth + 1}
>
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div
    class="group flex items-center h-7 pr-1 cursor-pointer select-none rounded
      {selected ? 'bg-primary/25 font-semibold' : 'hover:bg-base-300'}"
    style="padding-left: {row.depth * 14 + 4}px"
    data-path={node.path}
    title={modified ? `${label}\n${tt('Last changed')}: ${modified}` : label}
    on:click={() => onSelect(node.path)}
  >
    {#if node.children.length > 0}
      <button
        class="w-5 h-5 shrink-0 flex items-center justify-center opacity-70 hover:opacity-100"
        tabindex="-1"
        aria-label={row.open ? tt('Collapse') : tt('Expand')}
        on:click|stopPropagation={() => onToggle(node.path)}
      >
        <svg class="w-3 h-3 transition-transform {row.open ? 'rotate-90' : ''}" viewBox="0 0 20 20" fill="currentColor">
          <path d="M7 4l6 6-6 6V4z" />
        </svg>
      </button>
    {:else}
      <span class="w-5 shrink-0"></span>
    {/if}

    <svg class="w-4 h-4 shrink-0 mr-1.5 {selected ? 'text-primary' : 'opacity-60'}" viewBox="0 0 24 24" fill="currentColor">
      {#if row.open}
        <path d="M19.906 9c.382 0 .749.057 1.094.162V9a3 3 0 00-3-3h-3.879a.75.75 0 01-.53-.22L11.47 3.66A2.25 2.25 0 009.879 3H6a3 3 0 00-3 3v3.162A3.756 3.756 0 014.094 9h15.812zM4.094 10.5a2.25 2.25 0 00-2.227 2.568l.857 6A2.25 2.25 0 004.951 21H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-2.227-2.568H4.094z" />
      {:else}
        <path d="M19.5 21a3 3 0 003-3v-4.5a3 3 0 00-3-3h-15a3 3 0 00-3 3V18a3 3 0 003 3h15zM1.5 10.146V6a3 3 0 013-3h5.379a2.25 2.25 0 011.59.659l2.122 2.121c.14.141.331.22.53.22H19.5a3 3 0 013 3v1.146A4.483 4.483 0 0019.5 9h-15a4.483 4.483 0 00-3 1.146z" />
      {/if}
    </svg>

    {#if renaming}
      <input
        class="input input-bordered input-xs flex-1 min-w-0 rounded font-normal"
        bind:value={newName}
        use:focusInput
        on:click|stopPropagation
        on:keydown={onRenameKeydown}
        on:blur={() => onRename(node, null)}
      />
    {:else}
      <span class="truncate flex-1 text-sm">{label}</span>

      {#if pinned}
        <svg class="w-3 h-3 shrink-0 ml-1 text-warning group-hover:hidden" viewBox="0 0 20 20" fill="currentColor" aria-label={tt('Pinned')}>
          <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
        </svg>
      {/if}

      {#if node.path}
        <span class="hidden group-hover:flex shrink-0 items-center gap-0.5 ml-1">
          <button
            class="p-0.5 rounded hover:bg-base-100 {pinned ? 'text-warning' : ''}"
            tabindex="-1"
            title={pinned ? tt('Unpin') : tt('Pin')}
            aria-label={pinned ? tt('Unpin') : tt('Pin')}
            on:click|stopPropagation={() => onPin(node.path)}
          >
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill={pinned ? 'currentColor' : 'none'}>
              <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
            </svg>
          </button>
          <button
            class="p-0.5 rounded hover:bg-base-100"
            tabindex="-1"
            title={tt('Rename') + ' (F2)'}
            aria-label={tt('Rename')}
            on:click|stopPropagation={() => onStartRename(node.path)}
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487z" />
            </svg>
          </button>
          <button
            class="p-0.5 rounded hover:bg-base-100 text-error"
            tabindex="-1"
            title={$t('common.btn.delete')}
            aria-label={$t('common.btn.delete')}
            on:click|stopPropagation={() => onDelete(node)}
          >
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16 2v4h6v2h-2v14H4V8H2V6h6V2h8zm-2 2h-4v2h4V4zm0 4H6v12h12V8h-4zm-5 2h2v8H9v-8zm6 0h-2v8h2v-8z" />
            </svg>
          </button>
        </span>
      {/if}

      {#if node.media_count > 0}
        <span class="shrink-0 ml-1 text-xs tabular-nums opacity-60 {node.path ? 'group-hover:hidden' : ''}">{node.media_count}</span>
      {/if}
    {/if}
  </div>
</li>
