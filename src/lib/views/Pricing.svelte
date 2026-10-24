<script lang="ts">
  import View from "$lib/View.svelte";
  import { SECTIONS } from "$lib/registry";

  // Pricing is genuinely flat here: the model is self-hosted, so the honest table
  // is one row of zeros. Showing a fake metered curve would be worse than showing none.
  const ROWS = [
    ["Input", "$0.00000", "per 1M tokens"],
    ["Output", "$0", "no tokens generated"],
    ["Per request", "$0", "no metering"],
    ["NPU", "$0", "your hardware"],
    ["GPU", "$0", "your hardware"],
    ["BYOK", "provider price", "your contract"],
  ];

  const COMPARE = [
    { name: "Hosted decision API", price: "$0.042 / 1M input", note: "metered, per call" },
    { name: "Frontier chat model", price: "~$900 / 40k calls", note: "generates text" },
    { name: "laya-npu local", price: "$0", note: "one forward pass" },
  ];
</script>

<View
  title="Pricing"
  icon="tag"
  subtitle="Self-hosted, so there is no per-token charge. The only cost is the machine you already own, plus whatever a BYOK provider bills."
>
  <div class="card shrink-0 overflow-hidden">
    <div class="grid grid-cols-[1.2fr_1fr_1.4fr] gap-3 border-b border-line bg-panel-2 px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-ink-3">
      <span>Item</span><span>Price</span><span>Unit</span>
    </div>
    {#each ROWS as [k, v, u]}
      <div class="grid grid-cols-[1.2fr_1fr_1.4fr] items-center gap-3 border-t border-line px-4 py-2.5 text-[12.5px]">
        <span class="text-ink-2">{k}</span>
        <span class="mono">{v}</span>
        <span class="text-[11.5px] text-ink-3">{u}</span>
      </div>
    {/each}
  </div>

  <span class="label mt-5 mb-2 block">What this replaces</span>
  <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
    {#each COMPARE as c}
      <div class="card p-4">
        <span class="text-[12.5px] font-semibold">{c.name}</span>
        <p class="mono mt-1 text-[15px]">{c.price}</p>
        <p class="mt-1 text-[11px] text-ink-3">{c.note}</p>
      </div>
    {/each}
  </div>

  <p class="mt-4 text-[11px] leading-relaxed text-ink-3">
    No chart on this page on purpose. A time series would need real metered data, and
    this deployment has none — every request is free.
  </p>
</View>
