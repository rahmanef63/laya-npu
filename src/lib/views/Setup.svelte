<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";
  import { get, post, postAudio } from "$lib/http";

  type Props = { backends?: any[]; backend?: string; onPick?: (id: string) => void };
  let { backends = [], backend = "", onPick = () => {} }: Props = $props();

  let driver = $state<any>(null);
  let health = $state<any>(null);
  let loading = $state(true);

  $effect(() => {
    Promise.all([
      get("/api/driver").then((r) => r.json()).catch(() => null),
      get("/api/health").then((r) => r.json()).catch(() => null),
    ]).then(([d, h]) => {
      driver = d;
      health = h;
      loading = false;
    });
  });

  // Four checks, in the order a person should care about them.
  let checks = $derived.by(() => {
    const ready = backends.filter((b) => b.ready);
    const hasNpu = backends.some((b) => b.device === "NPU" && b.ready);
    return [
      {
        id: "app",
        label: "App running",
        ok: !!health?.ok,
        detail: health?.ok
          ? "The server is answering on this machine."
          : "The server is not answering. Start it with laya-npu.cmd or ./start.sh.",
      },
      {
        id: "hw",
        label: "Hardware detected",
        ok: ready.length > 0,
        detail: ready.length
          ? `${ready.map((b) => b.device).join(", ")} compiled successfully.`
          : "No backend compiled. The model or OpenVINO install is broken.",
      },
      {
        id: "npu",
        label: "NPU available",
        ok: hasNpu,
        detail: hasNpu
          ? "The Intel NPU is usable. This is the fast, low-power path."
          : "No NPU. Everything still works on the GPU or CPU — 2 to 7 times slower.",
      },
      {
        id: "driver",
        label: "Driver current",
        ok: driver?.present ? driver.action === "none" : false,
        detail: !driver?.present
          ? (driver?.reason ?? "No Intel NPU device found.")
          : driver.action === "none"
            ? `Driver ${driver.current} is current.`
            : `Driver ${driver.current} → ${driver.latest} available. Download from Intel.`,
      },
    ];
  });

  let done = $derived(checks.filter((c) => c.ok).length);
</script>

<View
  title="Setup check"
  icon="check"
  subtitle="Four things to confirm before using anything else. If a row is red, the fix is written next to it."
>
  {#snippet actions()}
    <span class="chip mono">{done}/4 ready</span>
  {/snippet}

  {#if loading}
    <p class="text-[12px] text-ink-3">Checking…</p>
  {:else}
    <div class="card mb-5 shrink-0 overflow-hidden">
      {#each checks as c, i}
        <div class="flex items-start gap-3 px-4 py-3 {i > 0 ? 'border-t border-line' : ''}">
          <span
            class="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold
              {c.ok ? 'bg-[#43cb7a] text-black' : 'bg-[#f43e64] text-black'}"
          >{c.ok ? "✓" : "!"}</span>
          <span class="min-w-0">
            <span class="block text-[12.5px] font-semibold">{c.label}</span>
            <span class="block text-[11.5px] leading-relaxed text-ink-2">{c.detail}</span>
          </span>
        </div>
      {/each}
    </div>

    {#if !checks[2].ok && driver?.present}
      <div class="card mb-4 p-4">
        <span class="label">NPU present but not compiled</span>
        <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
          The hardware exists and the driver is installed, but OpenVINO could not build a
          graph for it. Usually the driver is older than the runtime. Update it, reboot,
          then reload this page.
        </p>
        <a class="btn mt-2 h-7" href={driver.url} target="_blank" rel="noreferrer">
          Intel NPU driver download
        </a>
      </div>
    {/if}

    {#if !checks[2].ok && !driver?.present}
      <div class="card mb-4 p-4">
        <span class="label">No NPU — what now</span>
        <ol class="mt-1.5 flex list-decimal flex-col gap-1 pl-4 text-[11.5px] leading-relaxed text-ink-2">
          <li>Check it is enabled in BIOS. Some laptops ship with it off.</li>
          <li>Install the Intel NPU driver, reboot.</li>
          <li>If it still does not appear, the machine may not have one. Everything
            still runs on the GPU or CPU.</li>
        </ol>
      </div>
    {/if}

    <span class="label mb-2 block">Choose what to run on</span>
    <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {#each backends.filter((b) => b.kind === "local") as b}
        <button
          class="card p-3 text-left transition-colors {backend === b.id ? 'border-ink/40 bg-panel-2' : 'hover:bg-hover'}"
          onclick={() => onPick(b.id)}
          disabled={!b.ready}
        >
          <span class="flex items-center gap-2 text-[12.5px] font-semibold">
            <span class="size-1.5 rounded-full {b.ready ? 'bg-[#43cb7a]' : 'bg-ink-3'}"></span>
            {b.device}
          </span>
          <span class="mt-1 block text-[10.5px] text-ink-3">
            {b.ready ? "ready" : (b.reason ?? "unavailable")}
          </span>
        </button>
      {/each}
    </div>

    <div class="card mt-4 p-4">
      <span class="label">What you are running</span>
      <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
        <b>Laya</b> is a decision model: you give it text and typed questions, it returns a
        label or a score with a probability. It does not write prose. <b>Jev System One</b>
        is the request format used to ask those questions. <b>NPU</b> is a small chip for
        exactly this kind of work: one pass over a fixed input, at low power. OpenVINO is
        the runtime that drives it, and the Intel driver sits underneath.
      </p>
    </div>
  {/if}
</View>
