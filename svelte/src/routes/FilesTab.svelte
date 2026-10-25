<script lang="ts">
  import Toast from './Toast.svelte';
  import OutputsBrowser from './OutputsBrowser.svelte';

  export let comfyUrl: string;

  let toast: Toast;
</script>

<OutputsBrowser folderType="outputs" {comfyUrl} {toast} />

<Toast bind:this={toast} />
