<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";

  type Props = { backend?: string; backends?: any[]; onPick?: (id: string) => void };
  let { backend = "", backends = [], onPick = () => {} }: Props = $props();

  const APPS = [
    { name: "Inbox triage", sub: "routes mail by team", uses: "email", pct: 38 },
    { name: "Ticket router", sub: "support queue", uses: "triage", pct: 24 },
    { name: "Prompt guard", sub: "gate before a model", uses: "guard", pct: 17 },
    { name: "Model router", sub: "picks a model per call", uses: "router", pct: 11 },
    { name: "Moderation", sub: "community posts", uses: "moderation", pct: 10 },
  ];
</script>

<View
  title="Apps"
  icon="grid"
  subtitle="Recipes that ship with this app. Each one is a preset plus a policy layer; click through to run it in the playground."
>
  <div class="card shrink-0 overflow-hidden">
    {#each APPS as a, i}
      <div class="grid grid-cols-[24px_1fr_1fr_auto] items-center gap-3 px-4 py-3 {i > 0 ? 'border-t border-line' : ''}">
        <span class="mono text-[10.5px] text-ink-3">{i + 1}</span>
        <span class="flex flex-col">
          <span class="text-[12.5px] text-ink">{a.name}</span>
          <span class="text-[10.5px] text-ink-3">{a.sub}</span>
        </span>
        <span class="chip mono w-fit">{a.uses}</span>
        <div class="flex items-center gap-2">
          <div class="h-1 w-20 overflow-hidden rounded bg-line">
            <div class="h-full rounded bg-ink-2" style="width:{a.pct * 2.4}%"></div>
          </div>
          <span class="mono w-8 text-right text-[10.5px] text-ink-3">{a.pct}%</span>
        </div>
      </div>
    {/each}
  </div>

  <div class="card mt-4 p-4">
    <span class="label">Shares are illustrative</span>
    <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
      This deployment has no traffic of its own, so the percentages show the intended
      mix rather than measured load. Everything else on this page is real.
    </p>
  </div>
</View>
