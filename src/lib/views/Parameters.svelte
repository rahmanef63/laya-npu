<script lang="ts">
  import View from "$lib/View.svelte";

  const GROUPS = [
    {
      title: "Wire format",
      rows: [
        ["state", "object | string", "Text or structured fields to decide on. Serialised before inference."],
        ["questions", "object", "Map of id → question. Each question is choice, score or noul."],
        ["model", "string", "Endpoint-specific model name. Optional for the local backend."],
      ],
    },
    {
      title: "Per question",
      rows: [
        ["type", "choice | score | noul", "The primitive. choice picks one label, score places an ordinal, noul gives P(yes)."],
        ["instructions", "string", "The question, ≤600 chars. Name the field in backticks, e.g. `message`."],
        ["criteria", "object | array", "choice: {value: when-to-choose}. score: ordered level strings. noul: {true, false}."],
      ],
    },
    {
      title: "Response",
      rows: [
        ["answers[id].choice", "string", "The selected option, with a full probability map."],
        ["answers[id].score", "number", "Ordinal position; may sit between levels."],
        ["answers[id].noul", "number", "P(yes) in [0,1]."],
        ["answer_confidence", "number", "Mass on the reported answer. This is what a temperature fit targets."],
        ["confidence", "number", "Normalised entropy for choice and score. Not the same quantity."],
      ],
    },
  ];

  const PARAMS = [
    "state", "questions", "model", "task", "lang", "lang_guess",
    "max_len", "head_max_len", "min_confidence",
    "type", "instructions", "criteria",
    "choice", "score", "noul",
    "answer_confidence", "x_jev_confidence", "legend", "usage",
  ];
</script>

<View
  title="Parameters"
  icon="sliders"
  subtitle="The full request surface. There are no sampling parameters because the model does not sample — it scores typed options in one pass."
>
  <div class="mb-5 flex flex-wrap gap-1.5">
    {#each PARAMS as p}
      <span class="chip mono">{p}</span>
    {/each}
  </div>

  {#each GROUPS as g}
    <span class="label mb-1.5 block">{g.title}</span>
    <div class="card mb-4 overflow-hidden">
      {#each g.rows as [name, type, desc], i}
        <div class="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[1.1fr_1fr_2fr] sm:items-baseline sm:gap-3 {i > 0 ? 'border-t border-line' : ''}">
          <span class="mono text-[11.5px] text-ink">{name}</span>
          <span class="mono text-[10.5px] text-ink-3">{type}</span>
          <span class="text-[11.5px] leading-relaxed text-ink-2">{desc}</span>
        </div>
      {/each}
    </div>
  {/each}
</View>
