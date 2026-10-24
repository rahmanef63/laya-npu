<script lang="ts">
  import View from "$lib/View.svelte";

  import { MEASURED } from "$lib/measured";
  const ROWS = Object.entries(MEASURED.decision).map(([label, v]) => ({
    label, ms: v.ms, compile: v.compile_s,
  }));

  const MAX = Math.max(...ROWS.map((r) => r.ms));
</script>

<View title="Performance" icon="gauge" subtitle={`Measured ${MEASURED.date} on ${MEASURED.machine}: ${MEASURED.runtime}, ${MEASURED.window}.`}>
  <div class="flex flex-col gap-2.5">
    {#each ROWS as r}
      <div class="card p-4">
        <div class="mb-2 flex items-baseline justify-between gap-3">
          <span class="text-[13px] font-semibold">{r.label}</span>
          <span class="mono text-[13px]">{r.ms.toFixed(1)} ms</span>
        </div>
        <div class="h-1.5 overflow-hidden rounded bg-line">
          <div class="h-full rounded bg-ink" style="width:{(r.ms / MAX) * 100}%"></div>
        </div>
        <div class="mt-1.5 flex gap-1.5">
          <span class="chip mono">compile {r.compile}s</span>
          <span class="chip mono">{(1000 / r.ms).toFixed(1)} req/s</span>
        </div>
      </div>
    {/each}
  </div>

  <div class="card mt-4 p-4">
    <span class="label">Reading this</span>
    <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
      NPU and GPU land within 20% of each other; CPU is 13× slower because it executes
      the same INT8 graph without the matrix engine. Compile time inverts the ranking:
      the NPU needs a long one-off build, the CPU barely any. For a single request the
      CPU is cheaper end to end; for a hundred the NPU wins.
    </p>
  </div>
</View>
