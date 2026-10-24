<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";
  import { get as httpGet, post as httpPost, postAudio } from "$lib/http";

  type Props = { backend?: string };
  let { backend = "" }: Props = $props();

  let dir = $state("");
  let roots = $state<string[]>([]);
  let files = $state<any[]>([]);
  let results = $state<any[]>([]);
  let task = $state("doc_type");
  let busy = $state(false);
  let error = $state("");
  let scanned = $state(false);

  const TASKS = [
    ["doc_type", "Document type"],
    ["email", "Inbound email"],
    ["triage", "Support ticket"],
  ];

  $effect(() => {
    httpGet("/api/corpus/roots").then((d: any) => (roots = d.roots ?? []));
  });

  async function localPost(url: string, body: unknown) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  }

  async function list() {
    busy = true;
    error = "";
    results = [];
    try {
      const d: any = await localPost("/api/corpus/list", { dir });
      if (d.error) throw new Error(d.error);
      files = d.files ?? [];
      dir = d.dir ?? dir;
      scanned = true;
    } catch (e: any) {
      error = String(e.message ?? e);
    } finally {
      busy = false;
    }
  }

  async function classify() {
    busy = true;
    error = "";
    try {
      const d: any = await localPost("/api/corpus/classify", { dir, task, backend });
      if (d.error) throw new Error(d.error);
      results = d.results ?? [];
    } catch (e: any) {
      error = String(e.message ?? e);
    } finally {
      busy = false;
    }
  }

  function kb(n: number | null) {
    if (n == null) return "—";
    return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(0)} KB`;
  }
</script>

<View
  title="Open Corpus"
  icon="folder"
  subtitle="Point at a directory on this machine. Every supported file is read, its text extracted, and each one classified. PDFs go through pypdf; scans and images are skipped because there is no vision tower."
>
  <div class="card shrink-0 p-4">
    <span class="label mb-1.5 block">Directory</span>
    <div class="flex flex-wrap gap-2">
      <input
        class="field mono flex-1 min-w-[260px]"
        bind:value={dir}
        placeholder="C:\Users\you\Documents\invoices"
      />
      <select class="field w-auto" bind:value={task}>
        {#each TASKS as [id, label]}
          <option value={id}>{label}</option>
        {/each}
      </select>
      <button class="btn h-[34px]" onclick={list} disabled={busy || !dir.trim()}>
        <Icon name="search" size={11} /> Scan
      </button>
      <button
        class="btn btn-solid h-[34px]"
        onclick={classify}
        disabled={busy || !dir.trim()}
      >
        {busy ? "Working…" : "Classify all"}
      </button>
    </div>

    <p class="mt-2 text-[11px] leading-relaxed text-ink-3">
      Allowed roots: {roots.join(", ") || "—"}. Anything outside them is refused.
    </p>
  </div>

  {#if error}
    <div class="mt-3 rounded-card border border-[#3b1c1c] bg-[#140a0a] p-2.5 text-[11.5px] text-[#f43e64]">
      {error}
    </div>
  {/if}

  {#if results.length}
    <span class="label mt-4 mb-2 block">Results · {results.length} files</span>
    <div class="card overflow-hidden">
      {#each results as r, i}
        <div class="grid grid-cols-[1.4fr_1fr_70px] items-center gap-3 px-4 py-2.5 text-[12px] {i > 0 ? 'border-t border-line' : ''}">
          <span class="flex items-center gap-2 truncate">
            <span class="mono text-[9.5px] text-ink-3">{r.kind}</span>
            <span class="truncate text-ink-2">{r.name}</span>
          </span>
          <span class="truncate">
            {#if r.error}
              <span class="text-[#f43e64]">{r.error}</span>
            {:else}
              <span class="font-semibold">{r.action_label ?? r.answers?.[0]?.value}</span>
              {#if r.answers?.[0]?.probability}
                <span class="mono ml-1.5 text-[10px] text-ink-3">p={r.answers[0].probability.toFixed(2)}</span>
              {/if}
            {/if}
          </span>
          <span class="mono text-right text-[10.5px] text-ink-3">{r.ms ? r.ms + " ms" : "—"}</span>
        </div>
      {/each}
    </div>
  {:else if scanned && files.length}
    <span class="label mt-4 mb-2 block">Found · {files.length} entries</span>
    <div class="card overflow-hidden">
      {#each files as f, i}
        <div class="grid grid-cols-[1.6fr_90px_70px] items-center gap-3 px-4 py-2 text-[12px] {i > 0 ? 'border-t border-line' : ''}">
          <span class="truncate text-ink-2">{f.name}</span>
          <span class="mono text-[9.5px] {f.kind === 'unsupported' ? 'text-ink-3' : 'text-ink'}">{f.kind}</span>
          <span class="mono text-right text-[10.5px] text-ink-3">{kb(f.size)}</span>
        </div>
      {/each}
    </div>
  {:else if scanned}
    <p class="mt-4 text-[12px] text-ink-3">No files in that directory.</p>
  {/if}
</View>
