<script lang="ts">
  import View from "$lib/View.svelte";

  const PARAMS = [
    "state", "questions", "max_len", "head_max_len", "min_confidence",
    "model", "task", "lang", "lang_guess", "criteria", "instructions",
    "abstention", "answer_confidence", "x_jev_confidence", "legend", "usage",
  ];

  const FAQ: [string, string][] = [
    ["What is this?", "A non-autoregressive decision model: ModernBERT-large with a decision head, 421M parameters, quantised to INT8 and running through OpenVINO."],
    ["Which compute should I pick?", "NPU when you care about power or steady load. GPU when you want a fast first compile. CPU when nothing else is available — it needs no driver and works everywhere."],
    ["What is BYOK here?", "Bring your own endpoint. Point the app at any server that speaks the Jev System One protocol with your own key. The key stays server-side."],
    ["Context window?", "256 tokens of state. Longer input is truncated before inference."],
    ["Cost?", "Zero per token on local devices. BYOK depends on your provider."],
    ["Other languages?", "No. The shipped checkpoint is English and scores near zero on non-Latin scripts while still reporting high confidence."],
  ];

  let open = $state(0);
</script>

<View
  title="Parameters and FAQ"
  icon="sliders"
  subtitle="Request fields the endpoint accepts, and the questions people ask first."
>
  <div class="mb-5 flex flex-wrap gap-1.5">
    {#each PARAMS as p}
      <span class="chip mono">{p}</span>
    {/each}
  </div>

  <div class="card overflow-hidden">
    {#each FAQ as [q, a], i}
      <button
        class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-[12.5px] hover:bg-hover"
        onclick={() => (open = open === i ? -1 : i)}
      >
        <span class="text-ink-2">{q}</span>
        <span class="text-ink-3">{open === i ? "close" : "open"}</span>
      </button>
      {#if open === i}
        <div class="px-4 pb-3.5 text-[12px] leading-relaxed text-ink-3">{a}</div>
      {/if}
    {/each}
  </div>
</View>
