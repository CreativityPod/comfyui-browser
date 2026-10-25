<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { t } from 'svelte-i18n';
  import { onLoadWorkflow } from './utils';
  import type { FOLDER_TYPES } from './utils';
  import { fetchMetadata, summarizePrompt, copyText, downloadJson, describeResolution } from './metadata';
  import type { FileMetadata, GenerationSummary } from './metadata';
  import type Toast from './Toast.svelte';

  export let files: Array<any>;
  export let index: number;
  export let comfyUrl: string;
  export let folderType: FOLDER_TYPES;
  export let comfyApp: any;
  export let toast: Toast;
  export let onClose: Function;

  const localStorageKey = 'comfyui-browser-viewer-panel';

  let metadata: FileMetadata | null = null;
  let summary: GenerationSummary | null = null;
  let metadataLoading = false;
  let showPanel = true;
  let showWorkflow = false;
  let showPrompt = false;
  let requestId = 0;

  $: tt = function(key: string) {
    return $t('viewer.' + key);
  }

  $: file = files[index];
  // Videos get their size from the player once it has loaded.
  let videoWidth = 0;
  let videoHeight = 0;
  $: resolution = describeResolution(metadata?.width || videoWidth, metadata?.height || videoHeight);
  $: hasPrev = index > 0;
  $: hasNext = index < files.length - 1;
  $: if (file) {
    copiedKey = '';
    loadMetadata(file);
    preloadNeighbours(index);
  }

  async function loadMetadata(f: any) {
    const id = ++requestId;
    metadataLoading = true;
    let data: FileMetadata | null = null;
    try {
      data = await fetchMetadata(comfyUrl, folderType, f);
    } catch {
      data = null;
    }
    if (id !== requestId) {
      return;
    }
    metadata = data;
    summary = summarizePrompt(data?.prompt);
    metadataLoading = false;
  }

  function preloadNeighbours(i: number) {
    for (const f of [files[i - 1], files[i + 1]]) {
      if (f && f.fileType === 'image') {
        new Image().src = f.previewUrl;
      }
    }
  }

  function prev() {
    if (hasPrev) index -= 1;
  }

  function next() {
    if (hasNext) index += 1;
  }

  function togglePanel() {
    showPanel = !showPanel;
    try {
      localStorage.setItem(localStorageKey, showPanel ? '1' : '0');
    } catch {}
  }

  function onKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement;
    if (['INPUT', 'TEXTAREA'].includes(target?.tagName)) {
      return;
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      prev();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      next();
    } else if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'i' || e.key === 'I') {
      togglePanel();
    }
  }

  // Which copy button just succeeded, so its label can read "Copied" for a moment.
  let copiedKey = '';
  let copiedTimer: ReturnType<typeof setTimeout> | undefined;

  async function onCopy(text: any, key: string) {
    const str = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
    const ok = await copyText(str);
    if (!ok) {
      toast.show(false, '', tt('Failed to copy'));
      return;
    }
    copiedKey = key;
    clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => copiedKey = '', 1500);
  }

  function baseName(name: string) {
    return name.replace(/\.[^.]+$/, '');
  }

  function formatValue(v: any) {
    if (v === undefined || v === null) return '';
    if (typeof v === 'number' && !Number.isInteger(v)) return String(Math.round(v * 1000) / 1000);
    return String(v);
  }

  onMount(() => {
    try {
      showPanel = localStorage.getItem(localStorageKey) !== '0';
    } catch {}
    document.body.style.overflow = 'hidden';
  });

  onDestroy(() => {
    document.body.style.overflow = '';
  });
</script>

<svelte:window on:keydown={onKeydown} />

{#if file}
<div class="fixed inset-0 z-50 flex bg-black/95">
  <div class="relative flex flex-col flex-1 min-w-0">
    <div class="flex items-center gap-2 px-3 py-2 text-sm text-gray-200 bg-black/60">
      <span class="font-bold truncate" title={file.name}>{file.name}</span>
      <span class="text-gray-400 shrink-0">{index + 1} / {files.length}</span>
      <div class="flex-1"></div>
      <a class="btn btn-ghost btn-xs" href={file.previewUrl} target="_blank">{tt('Open original')}</a>
      <button class="btn btn-ghost btn-xs" on:click={togglePanel} title="I">
        {showPanel ? tt('Hide info') : tt('Show info')}
      </button>
      <button
        class="btn btn-sm btn-circle no-animation ml-2 bg-gray-100 border-0 text-black hover:bg-error hover:text-white"
        on:click={() => onClose()}
        aria-label="Close"
        title="Esc"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <div class="relative flex-1 min-h-0 flex items-center justify-center p-2">
      {#if file.fileType === 'video'}
        {#key file.previewUrl}
          <video
            class="max-h-full max-w-full object-contain"
            src={file.previewUrl}
            bind:videoWidth
            bind:videoHeight
            controls
            autoplay
            loop
          >
            <track kind="captions" />
          </video>
        {/key}
      {:else}
        <img class="max-h-full max-w-full object-contain" src={file.previewUrl} alt={file.name} />
      {/if}

      <button
        class="btn btn-circle no-animation absolute left-3 inset-y-0 my-auto bg-black/50 border-0 text-white hover:bg-black/80"
        disabled={!hasPrev}
        on:click={prev}
        aria-label="Previous"
        title="←"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
      </button>
      <button
        class="btn btn-circle no-animation absolute right-3 inset-y-0 my-auto bg-black/50 border-0 text-white hover:bg-black/80"
        disabled={!hasNext}
        on:click={next}
        aria-label="Next"
        title="→"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
          <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
      </button>
    </div>
  </div>

  {#if showPanel}
    <aside class="w-80 lg:w-96 shrink-0 h-full overflow-y-auto bg-base-200 p-4 space-y-4 text-sm">
      <section>
        <h3 class="font-bold mb-1">{tt('File')}</h3>
        <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          {#if resolution && !summary}
            <dt class="text-gray-400">{tt('Resolution')}</dt>
            <dd>{resolution.dimensions}</dd>
            <dt class="text-gray-400">{tt('Megapixels')}</dt>
            <dd>{resolution.megapixels}</dd>
            <dt class="text-gray-400">{tt('Aspect ratio')}</dt>
            <dd>{resolution.aspect}</dd>
          {/if}
          <dt class="text-gray-400">{tt('File size')}</dt>
          <dd>{file.formattedSize}</dd>
          <dt class="text-gray-400">{tt('Created')}</dt>
          <dd>{file.formattedDatetime}</dd>
          {#if metadata?.format}
            <dt class="text-gray-400">{tt('Format')}</dt>
            <dd class="uppercase">{metadata.format}</dd>
          {/if}
        </dl>
      </section>

      {#if metadataLoading && !metadata}
        <p class="text-gray-400">{$t('common.loading')}</p>
      {/if}

      {#if summary}
        <section class="space-y-2">
          <h3 class="font-bold">{tt('Generation')}</h3>
          {#each summary.models as model}
            <div>
              <span class="text-gray-400">{tt('Model')}</span>
              <span class="break-all">{model}</span>
            </div>
          {/each}
          {#each summary.loras as lora}
            <div>
              <span class="text-gray-400">LoRA</span>
              <span class="break-all">{lora.name}</span>
              <span class="text-gray-400">
                {formatValue(lora.strengthModel)}{lora.strengthClip !== undefined ? ' / ' + formatValue(lora.strengthClip) : ''}
              </span>
            </div>
          {/each}
          {#each summary.samplers as s, i}
            <div class="space-y-2 {i > 0 ? 'border-t border-base-300 pt-2' : ''}">
              {#if summary.samplers.length > 1}
                <div class="text-gray-400 text-xs">{s.type}</div>
              {/if}
              {#if s.positive}
                <div>
                  <div class="flex items-center justify-between">
                    <span class="text-gray-400">{tt('Positive')}</span>
                    <button class="btn btn-link btn-xs p-0 no-underline {copiedKey === `pos-${i}` ? 'text-success' : 'text-accent'}" on:click={() => onCopy(s.positive, `pos-${i}`)}>{copiedKey === `pos-${i}` ? '✓ ' + tt('Copied') : tt('Copy')}</button>
                  </div>
                  {#if s.positiveGenerated}
                    <p class="italic text-gray-400 text-xs mb-1">{tt('llmInputPrompt')}</p>
                  {/if}
                  <p class="whitespace-pre-wrap break-words bg-base-100 rounded p-2">{s.positive}</p>
                </div>
              {:else if s.positiveGenerated}
                <div>
                  <span class="text-gray-400">{tt('Positive')}</span>
                  <p class="italic text-gray-400 bg-base-100 rounded p-2">{tt('generatedPrompt')}</p>
                </div>
              {/if}
              {#if s.negative}
                <div>
                  <div class="flex items-center justify-between">
                    <span class="text-gray-400">{tt('Negative')}</span>
                    <button class="btn btn-link btn-xs p-0 no-underline {copiedKey === `neg-${i}` ? 'text-success' : 'text-accent'}" on:click={() => onCopy(s.negative, `neg-${i}`)}>{copiedKey === `neg-${i}` ? '✓ ' + tt('Copied') : tt('Copy')}</button>
                  </div>
                  {#if s.negativeGenerated}
                    <p class="italic text-gray-400 text-xs mb-1">{tt('llmInputPrompt')}</p>
                  {/if}
                  <p class="whitespace-pre-wrap break-words bg-base-100 rounded p-2">{s.negative}</p>
                </div>
              {:else if s.negativeGenerated}
                <div>
                  <span class="text-gray-400">{tt('Negative')}</span>
                  <p class="italic text-gray-400 bg-base-100 rounded p-2">{tt('generatedPrompt')}</p>
                </div>
              {/if}
              <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
                {#each [['Seed', s.seed], ['Steps', s.steps], ['CFG', s.cfg], ['Sampler', s.sampler], ['Scheduler', s.scheduler], ['Denoise', s.denoise]] as [label, value]}
                  {#if value !== undefined && value !== null}
                    <dt class="text-gray-400">{tt(label)}</dt>
                    <dd class="break-all">{formatValue(value)}</dd>
                  {/if}
                {/each}
                {#if resolution && i === summary.samplers.length - 1}
                <dt class="text-gray-400">{tt('Resolution')}</dt>
                <dd>{resolution.dimensions}</dd>
                <dt class="text-gray-400">{tt('Megapixels')}</dt>
                <dd>{resolution.megapixels}</dd>
                <dt class="text-gray-400">{tt('Aspect ratio')}</dt>
                <dd>{resolution.aspect}</dd>
                {/if}
              </dl>
            </div>
          {/each}
          {#if resolution && summary.samplers.length === 0}
            <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
              <dt class="text-gray-400">{tt('Resolution')}</dt>
              <dd>{resolution.dimensions}</dd>
              <dt class="text-gray-400">{tt('Megapixels')}</dt>
              <dd>{resolution.megapixels}</dd>
              <dt class="text-gray-400">{tt('Aspect ratio')}</dt>
              <dd>{resolution.aspect}</dd>
            </dl>
          {/if}
        </section>
      {/if}

      {#if metadata?.parameters}
        <section>
          <div class="flex items-center justify-between">
            <h3 class="font-bold">{tt('Parameters')}</h3>
            <button class="btn btn-link btn-xs p-0 no-underline {copiedKey === 'params' ? 'text-success' : 'text-accent'}" on:click={() => onCopy(metadata?.parameters, 'params')}>{copiedKey === 'params' ? '✓ ' + tt('Copied') : tt('Copy')}</button>
          </div>
          <p class="whitespace-pre-wrap break-words bg-base-100 rounded p-2">{metadata.parameters}</p>
        </section>
      {/if}

      {#if metadata?.workflow || metadata?.prompt}
        <section class="space-y-2">
          <h3 class="font-bold">{tt('Workflow')}</h3>
          <div class="flex flex-wrap gap-2">
            {#if comfyApp}
              <button class="btn btn-accent btn-sm" on:click={async () => await onLoadWorkflow(file, comfyApp, toast)}>
                {tt('Load into ComfyUI')}
              </button>
            {/if}
            {#if metadata.workflow}
              <button class="btn btn-outline btn-sm" on:click={() => onCopy(metadata?.workflow, 'workflow')}>{copiedKey === 'workflow' ? '✓ ' + tt('Copied') : tt('Copy workflow')}</button>
              <button class="btn btn-outline btn-sm" on:click={() => downloadJson(metadata?.workflow, baseName(file.name) + '.json')}>
                {tt('Download .json')}
              </button>
            {/if}
          </div>
          {#if metadata.workflow}
            <details bind:open={showWorkflow}>
              <summary class="cursor-pointer text-gray-400" title={tt('workflowHint')}>{tt('Workflow JSON (editor graph)')}</summary>
              {#if showWorkflow}
                <pre class="text-xs bg-base-100 rounded p-2 overflow-auto max-h-96">{JSON.stringify(metadata.workflow, null, 2)}</pre>
              {/if}
            </details>
          {/if}
          {#if metadata.prompt}
            <details bind:open={showPrompt}>
              <summary class="cursor-pointer text-gray-400" title={tt('promptHint')}>{tt('API prompt JSON (what was executed)')}</summary>
              {#if showPrompt}
                <pre class="text-xs bg-base-100 rounded p-2 overflow-auto max-h-96">{JSON.stringify(metadata.prompt, null, 2)}</pre>
              {/if}
            </details>
          {/if}
        </section>
      {:else if metadata && !metadata.parameters}
        <p class="text-gray-400">{tt('No workflow found in this file')}</p>
      {/if}
    </aside>
  {/if}
</div>
{/if}
