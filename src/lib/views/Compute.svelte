<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";
  import { get, post, postAudio } from "$lib/http";
  import { MEASURED } from "$lib/measured";

  type Props = { backends?: any[]; backend?: string; onPick?: (id: string) => void };
  let { backends = [], backend = "", onPick = () => {} }: Props = $props();

  let local = $derived(backends.filter((b) => b.kind === "local"));
  let hosted = $derived(backends.filter((b) => b.kind === "byok"));

  let byokUrl = $state("");
  let byokKey = $state("");
  let byokModel = $state("jev");

  // ---- NPU driver ----
  let drv = $state<any>(null);
  $effect(() => {
    get("/api/driver").then((r) => r.json()).then((d) => (drv = d)).catch(() => {});
  });

  // ---- device identity ----
  let dev = $state<any>(null);
  let portal = $state("https://manef.dev");
  let linkMsg = $state("");
  let copied = $state(false);

  $effect(() => {
    get("/api/device")
      .then((r) => r.json())
      .then((d) => {
        dev = d;
        if (d?.portal) portal = d.portal;
      })
      .catch(() => {});
  });

  async function copyId() {
    try {
      await navigator.clipboard.writeText(dev?.id ?? "");
      copied = true;
      setTimeout(() => (copied = false), 1400);
    } catch {}
  }

  async function link() {
    linkMsg = "linking…";
    try {
      const r = await post("/api/device/link", { portal });
      const d = await r.json();
      if (d.error) throw new Error(d.error);
      linkMsg = d.heartbeat?.ok
        ? `linked · ${d.heartbeat.detail}`
        : `saved locally · heartbeat: ${d.heartbeat?.detail ?? "not sent"}`;
      dev = await get("/api/device").then((x) => x.json());
    } catch (e: any) {
      linkMsg = String(e.message ?? e);
    }
  }
</script>

<View
  title="Compute"
  icon="cpu"
  subtitle="The same decision head, four ways to run it. Pick where the forward pass happens: on this machine's NPU, GPU or CPU, or on an endpoint you already pay for."
>
  <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
    {#each local as b}
      <button
        class="card p-4 text-left transition-colors
          {backend === b.id ? 'border-ink/40 bg-panel-2' : 'hover:bg-hover'}"
        onclick={() => onPick(b.id)}
        disabled={!b.present}
      >
        <div class="flex items-center justify-between gap-2">
          <span class="flex items-center gap-2 text-[13px] font-semibold">
            <span
              class="size-1.5 rounded-full {b.ready
                ? 'bg-[#43cb7a]'
                : b.present
                  ? 'bg-[#e9c93a]'
                  : 'bg-ink-3'}"
            ></span>
            {b.label}
          </span>
          {#if backend === b.id}
            <span class="chip mono">selected</span>
          {:else if !b.present}
            <span class="chip">absent</span>
          {/if}
        </div>

        <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-3">{b.description}</p>

        <div class="mt-3 flex flex-wrap gap-1.5">
          {#if b.latency_ms}
            <span class="chip mono">{b.latency_ms} ms</span>
          {/if}
          {#if b.compile_s}
            <span class="chip mono">compile {b.compile_s}s</span>
          {/if}
          <span class="chip mono">{b.device}</span>
        </div>
      </button>
    {/each}
  </div>

  <span class="label mt-6 mb-2 block">Bring your own key</span>

  {#each hosted as b}
    <div class="card p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="flex items-center gap-2 text-[13px] font-semibold">
          <span
            class="size-1.5 rounded-full {b.ready ? 'bg-[#43cb7a]' : 'bg-ink-3'}"
          ></span>
          {b.label}
        </span>
        {#if backend === "byok"}
          <span class="chip mono">selected</span>
        {/if}
      </div>

      <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-3">{b.description}</p>

      <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <label class="flex flex-col gap-1">
          <span class="label">Endpoint</span>
          <input class="field mono" bind:value={byokUrl} placeholder="https://api.example.com" />
        </label>
        <label class="flex flex-col gap-1">
          <span class="label">Model</span>
          <input class="field mono" bind:value={byokModel} placeholder="jev" />
        </label>
        <label class="flex flex-col gap-1">
          <span class="label">Key</span>
          <input
            class="field mono"
            type="password"
            bind:value={byokKey}
            placeholder="sk-..."
          />
        </label>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-2">
        <button
          class="btn btn-solid h-7"
          onclick={() => onPick("byok")}
          disabled={!byokUrl.trim()}
        >
          Use this endpoint
        </button>
        <span class="text-[11px] text-ink-3">
          The key is forwarded server-side and never written to disk or echoed back.
        </span>
      </div>
    </div>
  {/each}

  <span class="label mt-6 mb-2 block">NPU driver</span>

  <div class="card p-4">
    {#if !drv}
      <p class="text-[11.5px] text-ink-3">checking…</p>
    {:else if !drv.present}
      <div class="flex items-center gap-2">
        <span class="size-1.5 rounded-full bg-ink-3"></span>
        <span class="text-[12.5px]">No Intel NPU detected</span>
      </div>
      <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-3">
        {drv.reason ?? "The app runs on GPU or CPU instead."}
      </p>
    {:else}
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="flex items-center gap-2 text-[12.5px] font-semibold">
          <span
            class="size-1.5 rounded-full {drv.action === "none"
              ? "bg-[#43cb7a]"
              : drv.action === "update"
                ? "bg-[#f43e64]"
                : "bg-[#e9c93a]"}"
          ></span>
          {drv.current}
        </span>
        <span class="chip mono">{drv.verdict ?? "unknown"}</span>
      </div>

      <div class="mt-2 flex flex-wrap gap-1.5">
        {#if drv.latest}<span class="chip mono">latest {drv.latest}</span>{/if}
        {#if drv.date}<span class="chip mono">{drv.date}</span>{/if}
        {#if drv.provider}<span class="chip mono">{drv.provider}</span>{/if}
      </div>

      <p class="mt-2 text-[11.5px] leading-relaxed text-ink-3">{drv.message}</p>

      {#if drv.action !== "none"}
        <a class="btn mt-2 h-7" href={drv.url} target="_blank" rel="noreferrer">
          Download driver
        </a>
        <p class="mt-1.5 text-[10.5px] leading-relaxed text-ink-3">
          Installs with administrator rights and needs a reboot. On an OEM laptop the
          vendor build is often the tested one — that is why this is a link, not an
          automatic download.
        </p>
      {/if}
    {/if}
  </div>

  <span class="label mt-6 mb-2 block">This device</span>

  <div class="card p-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <span class="mono text-[15px] font-semibold">{dev?.id ?? "—"}</span>
      <div class="flex gap-1.5">
        <button class="btn h-6 text-[10.5px]" onclick={copyId}>
          {copied ? "copied" : "copy id"}
        </button>
        {#if dev?.linked_at}
          <span class="chip mono">linked</span>
        {/if}
      </div>
    </div>

    <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-3">
      Paste this ID into the portal to make this machine visible in the registry.
      It is a hash of a machine identifier — no name, no path, no key.
    </p>

    <div class="mt-3 flex flex-wrap items-end gap-2">
      <label class="flex min-w-[240px] flex-1 flex-col gap-1">
        <span class="label">Portal</span>
        <input class="field mono" bind:value={portal} placeholder="https://manef.dev" />
      </label>
      <button class="btn btn-solid h-[34px]" onclick={link} disabled={!portal.trim()}>
        Link device
      </button>
    </div>

    {#if linkMsg}
      <p class="mono mt-2 text-[10.5px] text-ink-3">{linkMsg}</p>
    {/if}

    {#if dev?.heartbeat?.at}
      <p class="mono mt-1 text-[10.5px] text-ink-3">
        last heartbeat {dev.heartbeat.at} · {dev.heartbeat.detail}
      </p>
    {/if}
  </div>

  <div class="card mt-4 p-4">
    <span class="label">Measured on this machine · {MEASURED.date}</span>
    <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
      {MEASURED.machine}, {MEASURED.runtime}, {MEASURED.window}.
      NPU {MEASURED.decision.NPU.ms} ms · GPU {MEASURED.decision.GPU.ms} ms ·
      CPU {MEASURED.decision.CPU.ms} ms. The NPU is slowest to compile
      ({MEASURED.decision.NPU.compile_s}s) and fastest to run; the CPU needs no driver,
      which is why it is the fallback.
    </p>
  </div>
</View>
