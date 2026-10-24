<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";
  import { PROJECT } from "$lib/registry";

  type Props = { backends?: any[] };
  let { backends = [] }: Props = $props();

  const WHY = [
    {
      icon: "cpu",
      title: "Your NPU is idle",
      body: "Every Core Ultra ships a neural processor. Windows uses it for background blur and live captions, then leaves it alone. This is software that actually runs on it.",
    },
    {
      icon: "tag",
      title: "Decisions cost money today",
      body: "Routing a ticket, gating a prompt, labelling an issue — each is a metered API call. A 421M model on hardware you own makes them free.",
    },
    {
      icon: "check",
      title: "No text, no hallucination",
      body: "It does not generate prose. It returns a probability for each option you define. Nothing to parse, nothing to retry, no malformed JSON.",
    },
    {
      icon: "pulse",
      title: "Fast where it counts",
      body: "About 29 ms per question, and 57x realtime for speech. Audio never leaves the machine, which is the part people actually ask about.",
    },
  ];

  const USE_CASES = [
    {
      title: "Voice note to routed ticket",
      detail: "A customer leaves a voice note. Whisper transcribes it, Laya reads the intent and churn risk, a rule table picks the action. Under a second, offline.",
      chips: ["whisper", "triage", "0.9 s"],
      section: "voice",
    },
    {
      title: "Inbox triage",
      detail: "Every inbound email: which team, is it spam, is it phishing, how urgent. Measured 6/6 on the checks that matter, with a 0.999 on legitimate invoices.",
      chips: ["email", "6/6"],
      section: "playground",
    },
    {
      title: "Guardrail before the LLM",
      detail: "Jailbreak 0.998, prompt injection 1.000. A 29 ms gate in front of a 3 s cloud call is 1% overhead that blocks the expensive mistakes.",
      chips: ["guard", "4/4"],
      section: "playground",
    },
    {
      title: "Document routing",
      detail: "Point it at a folder. It reads PDFs and text, extracts, classifies. Invoice to approval, receipt to filing, support to a reply.",
      chips: ["corpus", "pdf"],
      section: "corpus",
    },
    {
      title: "Bring your own model",
      detail: "Write your decision format as JSON, validate it, compile it to the wire payload, and download a standalone Python client. Nothing is locked in here.",
      chips: ["schema", "portable"],
      section: "schema",
    },
    {
      title: "Your own endpoint",
      detail: "Already paying for a decision model? Point the app at any server speaking the same protocol. The key stays server-side.",
      chips: ["byok"],
      section: "backends",
    },
  ];

  const LIMITS = [
    ["English only", "The shipped checkpoint is English. Non-Latin scripts score near zero while still reporting high confidence — a silent failure, so it is not offered."],
    ["256 tokens", "State longer than that is truncated before inference."],
    ["One request at a time", "A single NPU infer request per device. Concurrency is serialised."],
    ["Windows for the NPU", "The NPU is not reachable from WSL or a VM. Linux and WSL get CPU and BYOK."],
  ];
</script>

<View
  title="Overview"
  icon="sparkles"
  subtitle="Typed decisions and speech recognition on the hardware already in your laptop. No cloud, no API keys, no per-token bill."
>
  {#snippet actions()}
    <span class="chip mono">{backends.filter((b) => b.ready).length} backends ready</span>
    <a class="btn h-7" href={PROJECT.repo} target="_blank" rel="noreferrer">Source</a>
  {/snippet}

  <div class="mb-6 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
    {#each WHY as w}
      <div class="card p-4">
        <span class="flex items-center gap-2 text-[13px] font-semibold">
          <span class="text-ink-3"><Icon name={w.icon} size={13} /></span>
          {w.title}
        </span>
        <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">{w.body}</p>
      </div>
    {/each}
  </div>

  <div class="mb-6 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
    {#each [
      ["29 ms", "per decision"],
      ["57x", "realtime audio"],
      ["85 MB", "whisper model"],
      ["$0", "per request"],
    ] as [big, small]}
      <div class="card p-3.5">
        <div class="mono text-[20px] font-semibold tracking-tight">{big}</div>
        <div class="text-[10.5px] text-ink-3">{small}</div>
      </div>
    {/each}
  </div>

  <span class="label mb-2 block">What people do with it</span>
  <div class="mb-6 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
    {#each USE_CASES as u}
      <a class="card p-4 transition-colors hover:bg-hover" href="#{u.section}">
        <span class="text-[13px] font-semibold">{u.title}</span>
        <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">{u.detail}</p>
        <div class="mt-2.5 flex flex-wrap gap-1.5">
          {#each u.chips as c}<span class="chip mono">{c}</span>{/each}
        </div>
      </a>
    {/each}
  </div>

  <span class="label mb-2 block">What it will not do</span>
  <div class="card mb-6 overflow-hidden">
    {#each LIMITS as [k, v], i}
      <div class="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[160px_1fr] sm:items-baseline sm:gap-3 {i > 0 ? 'border-t border-line' : ''}">
        <span class="text-[11.5px] font-semibold text-ink">{k}</span>
        <span class="text-[11.5px] leading-relaxed text-ink-2">{v}</span>
      </div>
    {/each}
  </div>

  <div class="card p-4">
    <span class="label">Where the numbers come from</span>
    <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
      All timings are measured on this machine — Intel Core Ultra 9 386H, OpenVINO
      2026.4.1, INT8. Accuracy figures come from the harnesses in <code class="mono">tests/</code>,
      including the tasks that failed: shell-command gating scores 12/18 and is
      deliberately not offered as a feature. Speech to text runs on the NPU at three
      times the GPU's speed; the decision model is slightly faster on the GPU. Both
      statements are in the repo, not just on this page.
    </p>
  </div>
</View>
