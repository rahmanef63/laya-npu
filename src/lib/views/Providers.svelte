<script lang="ts">
  import View from "$lib/View.svelte";

  type Props = { backends?: any[] };
  let { backends = [] }: Props = $props();
</script>

<View title="Providers" icon="server" subtitle="Every backend that can answer a request. Local devices are discovered at runtime; the hosted row appears once an endpoint is configured.">
  <div class="card shrink-0 overflow-hidden">
    <div class="grid grid-cols-[2fr_1fr_1fr_1fr] gap-3 border-b border-line bg-panel-2 px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-ink-3">
      <span>Provider</span><span>Device</span><span>Latency</span><span>Status</span>
    </div>
    {#each backends as b}
      <div class="grid grid-cols-[2fr_1fr_1fr_1fr] items-center gap-3 border-t border-line px-4 py-2.5 text-[12.5px]">
        <span class="flex items-center gap-2">
          <span class="size-3 rounded-[3px] bg-ink"></span>
          {b.label}
        </span>
        <span class="mono text-ink-2">{b.device}</span>
        <span class="mono text-ink-2">{b.latency_ms ? b.latency_ms + " ms" : "—"}</span>
        <span class="mono text-[11px] {b.ready ? 'text-[#43cb7a]' : 'text-ink-3'}">
          {b.ready ? "ready" : (b.reason ?? "idle")}
        </span>
      </div>
    {/each}
  </div>
</View>
