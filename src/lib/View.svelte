<script lang="ts">
  import Icon from "$lib/Icon.svelte";
  import type { Snippet } from "svelte";

  type Props = {
    title: string;
    icon?: string;
    subtitle?: string;
    actions?: Snippet;
    children: Snippet;
  };
  let { title, icon = "circle", subtitle = "", actions, children }: Props = $props();
</script>

<div class="flex h-full min-h-0 flex-col px-7 py-6">
  <div
    class="mb-4 flex shrink-0 flex-wrap items-start justify-between gap-4 border-b border-line pb-3.5"
  >
    <div class="min-w-0">
      <h2 class="flex items-center gap-2 text-[17px] font-semibold">
        <span class="text-ink-3"><Icon name={icon} size={15} /></span>
        {title}
      </h2>
      {#if subtitle}
        <p class="mt-1 max-w-[680px] text-[12px] leading-relaxed text-ink-2">{subtitle}</p>
      {/if}
    </div>
    {#if actions}
      <div class="flex flex-wrap items-center gap-1.5">{@render actions()}</div>
    {/if}
  </div>

  <div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
    {@render children()}
  </div>
</div>
