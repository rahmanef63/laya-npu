<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";
  import { get, post, postAudio } from "$lib/http";

  type Props = { backend?: string };
  let { backend = "" }: Props = $props();

  let meta = $state<any>(null);
  let result = $state<any>(null);
  let busy = $state(false);
  let error = $state("");
  let dragging = $state(false);
  let fileName = $state("");
  let task = $state("triage");

  const device = $derived(
    backend.startsWith("local:") ? backend.split(":")[1].toUpperCase() : "NPU",
  );

  $effect(() => {
    get("/api/pipeline").then((r) => r.json()).then((d) => (meta = d)).catch(() => {});
  });

  async function upload(file: File) {
    if (!file) return;
    busy = true;
    error = "";
    result = null;
    fileName = file.name;
    try {
      const buf = await file.arrayBuffer();
      const r = await postAudio("/api/voice", buf, {
          "Content-Type": "application/octet-stream",
          "X-Device": device,
          "X-Task": task,
        });
      const d = await r.json();
      if (d.error) throw new Error(d.error);
      result = d;
    } catch (e: any) {
      error = String(e.message ?? e);
    } finally {
      busy = false;
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    const f = e.dataTransfer?.files?.[0];
    if (f) upload(f);
  }

  function onPick(e: Event) {
    const f = (e.currentTarget as HTMLInputElement).files?.[0];
    if (f) upload(f);
  }
</script>

<View
  title="Voice"
  icon="mic"
  subtitle="Any audio file in, one decision out. Whisper transcribes, Laya decides, a Python rule table picks the action. Nothing leaves the machine."
>
  {#snippet actions()}
    <select class="field h-7 w-auto text-[11.5px]" bind:value={task}>
      {#each meta?.tasks ?? [] as t}
        <option value={t.id}>{t.label}</option>
      {/each}
    </select>
    <span class="chip mono">{device}</span>
  {/snippet}

  <div class="mb-3 flex shrink-0 flex-wrap items-center gap-1.5">
    {#each ["whisper", "laya", "policy"] as stage, i}
      <span class="chip mono">{i + 1}. {stage}</span>
      {#if i < 2}<span class="text-[10px] text-ink-3">→</span>{/if}
    {/each}
    <span class="chip ml-auto">all local</span>
  </div>

  <div class="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-2">
    <div
      class="card flex min-h-[240px] flex-col items-center justify-center p-6 text-center transition-colors
        {dragging ? 'border-ink/50 bg-panel-2' : ''}"
      ondragover={(e) => { e.preventDefault(); dragging = true; }}
      ondragleave={() => (dragging = false)}
      ondrop={onDrop}
      role="button"
      tabindex="0"
    >
      {#if busy}
        <Icon name="mic" size={24} />
        <p class="mt-3 text-[13px]">Working on {fileName}…</p>
        <p class="mt-1 text-[11.5px] text-ink-3">transcribe, then decide</p>
      {:else if result}
        <div class="w-full text-left">
          <div class="mb-2 flex flex-wrap gap-1.5">
            <span class="chip mono">{result.transcript.seconds}s audio</span>
            <span class="chip mono">{result.timings.total_s}s total</span>
            <span class="chip mono">{result.realtime}x realtime</span>
          </div>
          <span class="label">Transcript</span>
          <p class="mt-1 text-[12.5px] leading-relaxed">{result.transcript.text}</p>
          <button class="btn mt-3 h-6 text-[10.5px]" onclick={() => { result = null; error = ""; }}>
            New file
          </button>
        </div>
      {:else}
        <Icon name="mic" size={24} />
        <p class="mt-3 text-[13px]">Drop a voice note</p>
        <p class="mt-1 text-[11.5px] text-ink-3">mp3, m4a, wav, ogg, flac, webm — 45 s takes under a second</p>
        <label class="btn btn-solid mt-4 h-8 cursor-pointer">
          Choose file
          <input type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.webm,.mp4" onchange={onPick} class="hidden" />
        </label>
      {/if}
    </div>

    <div class="flex min-h-0 flex-col gap-3">
      {#if error}
        <div class="rounded-card border border-[#3b1c1c] bg-[#140a0a] p-2.5 text-[11.5px] text-[#f43e64]">{error}</div>
      {:else if !result}
        <div class="card flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-ink-3">
          <Icon name="sparkles" size={22} />
          <p class="max-w-[260px] text-[12px]">The decision appears here with every answer and the rule that produced the action.</p>
        </div>
      {:else}
        <div class="min-h-0 flex-1 overflow-y-auto rounded-card border border-line bg-[#030303] p-3.5">
          <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span class="text-[17px] font-semibold">{result.action_label}</span>
            <div class="flex gap-1.5">
              <span class="chip mono">{result.timings.asr_s}s asr</span>
              <span class="chip mono">{result.timings.decision_s}s decide</span>
              {#if result.review}<span class="chip" style="color:#e9c93a">review</span>{/if}
            </div>
          </div>

          <div class="mb-3 rounded-card border border-line-2 bg-panel-2 p-2.5">
            {#each result.reasons as r}
              <p class="mono text-[10.5px] leading-relaxed text-ink-3">· {r}</p>
            {/each}
          </div>

          {#each result.decision.answers ?? [] as a}
            <div class="mb-2 rounded-card border border-line-2 bg-panel-2 p-2.5">
              <div class="mb-1.5 flex items-baseline justify-between gap-2">
                <span class="label">{a.label}</span>
                <span class="text-[12px] font-semibold">
                  {a.type === "noul" ? (a.value ? "yes" : "no") : a.value}
                  <span class="mono ml-1 text-[10px] text-ink-3">p={a.probability.toFixed(2)}</span>
                </span>
              </div>
              {#if a.ranked}
                {#each a.ranked as r}
                  <div class="grid grid-cols-[1fr_80px_40px] items-center gap-2 text-[11px]">
                    <span class={r.name === a.value ? "font-semibold text-ink" : "text-ink-3"}>{r.name}</span>
                    <div class="h-1 overflow-hidden rounded bg-line"><div class="h-full rounded bg-ink-2" style="width:{r.p * 100}%"></div></div>
                    <span class="mono text-right text-[9.5px] text-ink-3">{r.p.toFixed(2)}</span>
                  </div>
                {/each}
              {:else if a.type === "score"}
                <div class="flex gap-1">
                  {#each a.scale as lv, i}
                    <span class="mono grid size-5 place-items-center rounded border text-[9px]
                      {i === Math.round(a.value) ? 'border-ink bg-ink font-bold text-black' : 'border-line text-ink-3'}">{i}</span>
                  {/each}
                </div>
              {:else}
                <div class="h-1 overflow-hidden rounded bg-line"><div class="h-full rounded bg-ink" style="width:{a.probability * 100}%"></div></div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</View>
