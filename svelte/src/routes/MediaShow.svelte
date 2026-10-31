<script lang="ts">
  export let file: any;
  export let styleClass: string;
  export let onClickDir: Function;
  export let onOpen: Function | undefined = undefined;
  // 'play' loops on its own, 'hover' plays while the mouse is over it,
  // 'still' only shows the first frame.
  export let videoMode: 'play' | 'hover' | 'still' = 'play';

  // Without autoplay, Safari leaves the frame blank unless the URL asks
  // for a start time, so seek just past zero to show the first frame.
  $: videoSrc = videoMode === 'play' ? file.previewUrl : `${file.previewUrl}#t=0.001`;

  function onVideoEnter(e: MouseEvent) {
    if (videoMode !== 'hover') return;
    const video = e.currentTarget as HTMLVideoElement;
    video.play().catch(() => {});
  }

  function onVideoLeave(e: MouseEvent) {
    if (videoMode !== 'hover') return;
    const video = e.currentTarget as HTMLVideoElement;
    video.pause();
    video.currentTime = 0.001;
  }

  function onClickFile(e: MouseEvent) {
    if (!onOpen || !['image', 'video'].includes(file.fileType)) {
      return;
    }
    // Keep ctrl/cmd/shift-click opening the raw file in a new tab.
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) {
      return;
    }
    e.preventDefault();
    onOpen(file);
  }
</script>


<div class={styleClass}>
  {#if file.type === 'dir'}
    <button
      class="w-full h-full flex items-center justify-center"
      on:click={() => onClickDir(file)}
    >
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-16 h-16">
        <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
      </svg>
    </button>
  {:else}
    <a
      href={file.url}
      target="_blank"
      on:click={onClickFile}
      style="height: inherit; width: inherit;"
    >
      {#if file.fileType === 'json'}
        <div class="w-full h-full flex items-center justify-center">
          <span class="font-bold text-xl">
            JSON
          </span>
        </div>
      {/if}
      {#if file.fileType === 'html'}
        <div class="w-full h-full flex items-center justify-center">
          <span class="font-bold text-xl">
            HTML
          </span>
        </div>
      {/if}
      {#if file.fileType === 'image'}
        <img
          class="h-full w-full object-contain"
          loading="lazy"
          src={file.previewUrl}
          alt={file.name} />
      {/if}
      {#if file.fileType === 'video'}
        {#key videoMode}
          <video
            class="h-full w-full object-contain pb-0.5 border-0.5 border-black"
            src={videoSrc}
            loop={true}
            autoplay={videoMode === 'play'}
            muted={true}
            playsinline
            preload={videoMode === 'play' ? 'auto' : 'metadata'}
            on:mouseenter={onVideoEnter}
            on:mouseleave={onVideoLeave}
          >
            <track kind="captions" />
          </video>
        {/key}
      {/if}
    </a>
  {/if}
</div>
