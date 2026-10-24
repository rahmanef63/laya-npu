<script lang="ts">
  import { api } from "$lib/api";
  import SiteHeader from "$lib/SiteHeader.svelte";
  import SectionNav from "$lib/SectionNav.svelte";
  import Overview from "$lib/views/Overview.svelte";
  import Setup from "$lib/views/Setup.svelte";
  import Playground from "$lib/views/Playground.svelte";
  import Compute from "$lib/views/Compute.svelte";
  import Providers from "$lib/views/Providers.svelte";
  import Pricing from "$lib/views/Pricing.svelte";
  import Performance from "$lib/views/Performance.svelte";
  import Voice from "$lib/views/Voice.svelte";
  import Transcribe from "$lib/views/Transcribe.svelte";
  import Corpus from "$lib/views/Corpus.svelte";
  import Schema from "$lib/views/Schema.svelte";
  import Apps from "$lib/views/Apps.svelte";
  import Parameters from "$lib/views/Parameters.svelte";
  import Faq from "$lib/views/Faq.svelte";
  import { SECTIONS, PROJECT, type SectionId } from "$lib/registry";

  // Registry entry -> component. A section without an entry here is a bug, and the
  // page says so instead of silently rendering the wrong view.
  const VIEWS: Record<string, any> = {
    overview: Overview,
    setup: Setup,
    playground: Playground,
    backends: Compute,
    providers: Providers,
    pricing: Pricing,
    performance: Performance,
    voice: Voice,
    transcribe: Transcribe,
    corpus: Corpus,
    schema: Schema,
    apps: Apps,
    parameters: Parameters,
    faq: Faq,
  };

  let active = $state<SectionId>("overview");
  let backends = $state<any[]>([]);
  let backend = $state("");

  let meta = $derived(SECTIONS.find((s) => s.id === active));
  let View = $derived(VIEWS[active]);

  $effect(() => {
    api
      .backends()
      .then((d: any) => {
        backends = d.backends ?? [];
        const ready = backends.filter((b: any) => b.ready);
        backend = ready[0]?.id ?? backends[0]?.id ?? "";
      })
      .catch(() => {});
  });

  $effect(() => {
    if (typeof window === "undefined") return;
    const id = window.location.hash.slice(1) as SectionId;
    if (id && SECTIONS.some((s) => s.id === id)) active = id;
  });

  function go(id: SectionId) {
    active = id;
    if (typeof window !== "undefined") history.replaceState(null, "", `#${id}`);
  }

  function onKey(e: KeyboardEvent) {
    const t = e.target as HTMLElement;
    if (t?.matches?.("input, textarea, select")) return;
    const i = SECTIONS.findIndex((s) => s.id === active);
    if (e.key === "j" || e.key === "ArrowDown") {
      e.preventDefault();
      go(SECTIONS[Math.min(i + 1, SECTIONS.length - 1)].id);
    }
    if (e.key === "k" || e.key === "ArrowUp") {
      e.preventDefault();
      go(SECTIONS[Math.max(i - 1, 0)].id);
    }
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="flex h-dvh flex-col">
  <SiteHeader {backends} {backend} onPick={(id) => (backend = id)} />

  <div class="grid min-h-0 flex-1 grid-cols-[210px_1fr] max-[860px]:grid-cols-[56px_1fr]">
    <aside class="min-h-0 overflow-hidden">
      <SectionNav {active} onPick={go} />
    </aside>

    <main class="flex min-h-0 min-w-0 flex-col">
      <div class="flex shrink-0 items-center gap-2 border-b border-line px-7 py-2.5 text-[11px] text-ink-2">
        <span class="text-ink-3">{meta?.group}</span>
        <span class="text-line">/</span>
        <span>{meta?.label}</span>
        <span class="ml-auto text-ink-3">
          j / k to move ·
          <a class="hover:text-ink-2" href={PROJECT.author} target="_blank" rel="noreferrer">rahmanef.com</a>
        </span>
      </div>

      <div class="flex min-h-0 flex-1 flex-col">
        {#if View}
          <View {backend} {backends} onPick={(id: string) => (backend = id)} />
        {:else}
          <div class="p-7 text-[12.5px] text-[#f43e64]">
            No view registered for “{active}”. Add it to VIEWS in +page.svelte.
          </div>
        {/if}
      </div>
    </main>
  </div>
</div>
