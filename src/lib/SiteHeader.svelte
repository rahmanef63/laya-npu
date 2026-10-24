<script lang="ts">
  import { PROJECT } from "$lib/registry";
  import BackendChip from "$lib/BackendChip.svelte";

  type Props = { backends?: any[]; backend?: string; onPick?: (id: string) => void };
  let { backends = [], backend = "", onPick = () => {} }: Props = $props();
</script>

<header class="h-14 shrink-0 border-b border-line bg-page">
  <div class="mx-auto flex h-full max-w-[1400px] items-center gap-5 px-6">
    <a class="flex items-center gap-2" href={PROJECT.author} target="_blank" rel="noreferrer">
      <span class="size-3 rounded-[3px] bg-ink"></span>
      <span class="text-[14px] font-semibold tracking-tight">
        laya<span class="font-normal text-ink-3">npu</span>
      </span>
    </a>

    <span class="hidden text-[11px] text-ink-3 md:block">{PROJECT.tagline}</span>

    <div class="ml-auto flex items-center gap-2">
      <BackendChip {backends} {backend} {onPick} />
      <a class="btn h-7" href={PROJECT.repo} target="_blank" rel="noreferrer">GitHub</a>
      <a
        class="btn btn-solid h-7"
        href={PROJECT.portal}
        target="_blank"
        rel="noreferrer"
      >manef.dev</a>
    </div>
  </div>
</header>
