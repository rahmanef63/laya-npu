<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";
  import { get as httpGet, post as httpPost, postAudio } from "$lib/http";

  type Props = { backend?: string };
  let { backend = "" }: Props = $props();

  let specText = $state("");
  let input = $state("I was charged twice for March, please refund the duplicate.");
  let error = $state("");
  let errors = $state<any[]>([]);
  let warnings = $state<any[]>([]);
  let payload = $state("");
  let script = $state("");
  let ok = $state(false);
  let running = $state<any>(null);
  let busy = $state(false);

  $effect(() => {
    httpGet("/api/schema/starter").then((d: any) => {
      specText = JSON.stringify(d.spec, null, 2);
    });
  });

  function parse(): any {
    try {
      const s = JSON.parse(specText);
      error = "";
      return s;
    } catch (e: any) {
      error = "invalid JSON: " + String(e.message ?? e);
      return null;
    }
  }

  async function localPost(url: string, body: unknown) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  }

  async function check() {
    const spec = parse();
    if (!spec) return;
    const d: any = await localPost("/api/schema/validate", { spec });
    ok = d.ok;
    errors = d.errors ?? [];
    warnings = d.warnings ?? [];
  }

  async function compile() {
    const spec = parse();
    if (!spec) return;
    const d: any = await localPost("/api/schema/compile", { spec, input });
    if (d.error) {
      error = d.error;
      return;
    }
    payload = JSON.stringify(d.payload, null, 2);
    script = d.script;
    ok = true;
    errors = [];
    await check();
  }

  async function runIt() {
    const spec = parse();
    if (!spec) return;
    busy = true;
    error = "";
    running = null;
    try {
      const d: any = await localPost("/api/schema/compile", { spec, input });
      if (d.error) throw new Error(d.error);
      const body = d.payload;
      const res: any = await localPost("/api/custom", {
        state: body.state,
        questions: body.questions,
        backend,
      });
      if (res.error) throw new Error(res.error);
      running = res;
    } catch (e: any) {
      error = String(e.message ?? e);
    } finally {
      busy = false;
    }
  }

  function download(name: string, text: string, type = "text/plain") {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  let name = $derived.by(() => {
    try {
      return (JSON.parse(specText).name ?? "spec").toString().replace(/\s+/g, "-");
    } catch {
      return "spec";
    }
  });
</script>

<View
  title="Schema"
  icon="code"
  subtitle="Describe your own decision format, validate it, compile it to the wire payload, and take the generated Python client with you. Nothing here is locked into this UI."
>
  {#snippet actions()}
    <button class="btn h-7" onclick={check}><Icon name="check" size={10} /> Validate</button>
    <button class="btn h-7" onclick={compile}><Icon name="code" size={10} /> Compile</button>
    <button class="btn btn-solid h-7" onclick={runIt} disabled={busy}>
      {busy ? "Running…" : "Run on backend"}
    </button>
  {/snippet}

  <div class="grid min-h-0 flex-1 grid-cols-1 gap-2.5 lg:grid-cols-2">
    <div class="flex min-h-0 flex-col">
      <span class="label mb-1.5 block">Your format</span>
      <textarea class="field mono flex-1" bind:value={specText} spellcheck="false"></textarea>
      <span class="label mt-2 mb-1.5 block">Sample input</span>
      <textarea class="field mono" rows="2" bind:value={input}></textarea>
    </div>

    <div class="flex min-h-0 flex-col">
      {#if error}
        <div class="mb-2 rounded-card border border-[#3b1c1c] bg-[#140a0a] p-2.5 text-[11.5px] text-[#f43e64]">
          {error}
        </div>
      {/if}

      {#if errors.length}
        <div class="mb-2 rounded-card border border-[#3b1c1c] bg-[#140a0a] p-2.5">
          {#each errors as e}
            <p class="mono text-[10.5px] text-[#f43e64]">{e.path}: {e.message}</p>
          {/each}
        </div>
      {:else if ok}
        <div class="mb-2 rounded-card border border-[#1e3a2b] bg-[#0a140e] p-2.5 text-[11.5px] text-[#43cb7a]">
          Valid spec · compiles to a Jev System One payload
        </div>
      {/if}

      {#if warnings.length}
        <div class="mb-2 rounded-card border border-[#3a3216] bg-[#14120a] p-2.5">
          {#each warnings as w}
            <p class="mono text-[10.5px] text-[#e9c93a]">{w.path}: {w.message}</p>
          {/each}
        </div>
      {/if}

      {#if payload}
        <div class="mb-2 flex gap-1.5">
          <button class="btn h-6 text-[10.5px]" onclick={() => download(`${name}.json`, payload, "application/json")}>
            Download schema
          </button>
          <button class="btn h-6 text-[10.5px]" onclick={() => download(`${name}.py`, script, "text/x-python")}>
            Download client
          </button>
        </div>
        <span class="label mb-1 block">Payload</span>
        <pre class="mono min-h-0 flex-1 overflow-auto rounded-card border border-line-2 bg-panel-2 p-2.5 text-[10.5px] text-ink-2">{payload}</pre>
      {/if}

      {#if running}
        <span class="label mt-2 mb-1 block">Result</span>
        <div class="rounded-card border border-line-2 bg-panel-2 p-2.5">
          {#each running.answers as a}
            <div class="mb-1 flex items-baseline justify-between gap-2 text-[12px]">
              <span class="text-ink-3">{a.id}</span>
              <span class="font-semibold">
                {a.type === "noul" ? (a.value ? "yes" : "no") : a.value}
                <span class="mono ml-1 text-[10px] text-ink-3">p={a.probability.toFixed(3)}</span>
              </span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</View>
