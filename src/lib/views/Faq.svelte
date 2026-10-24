<script lang="ts">
  import View from "$lib/View.svelte";
  import { MEASURED } from "$lib/measured";

  // Grouped so a beginner can read top to bottom, and a specific question can be found.
  const GROUPS: [string, [string, string][]][] = [
    ["The basics", [
      ["What is Laya?",
       "A model that labels or scores text. You give it a piece of text and typed questions; it returns a choice, a score, or a yes/no probability. It is not a chatbot and cannot write prose — which is the point, because there is nothing to parse and nothing to hallucinate."],
      ["What is Jev?",
       "Jev System One is the request and response format used to ask those questions: a state, a set of typed questions, and typed answers back. Laya is the model; Jev is the wire format. This app speaks Jev, so any Jev client can talk to it."],
      ["What is an NPU?",
       "A small chip for one job: running a fixed model over a fixed input, once, at low power. A CPU runs anything; a GPU runs many things in parallel; an NPU does one narrow thing efficiently. That makes it excellent for decisions and speech, and poor for chat, which is sequential by nature."],
      ["Is this a driver or an application?",
       "An application. Four pieces stack: the Intel NPU driver (from Intel, needs admin and a reboot), OpenVINO (the runtime that talks to the driver), the model weights (Laya and Whisper), and this app. Only the driver needs administrator rights."],
      ["What do choice, score and noul mean?",
       "The three question types. choice picks one from options you define and returns a probability per option. score places the text on an ordered scale and returns a position plus a distribution. noul asks a yes/no question and returns P(yes)."],
    ]],
    ["Hardware", [
      ["Does my computer have a supported NPU?",
       "Only Intel Core Ultra (Meteor Lake, Lunar Lake, Arrow Lake, Panther Lake) has one. Open the Setup check page in this app: it reads the device from Windows directly instead of guessing. On anything else the app runs on the GPU or CPU."],
      ["I have an NPU but do not know the driver state. Where do I start?",
       "Setup check, row four. It shows the installed driver version and what Intel currently publishes. If the row is red, the page links the exact download."],
      ["Should I install Intel's driver or my laptop maker's?",
       "Start with your vendor's, because that build is what the laptop was tested with. Use Intel's generic build when the vendor is behind by several months, or when the version is on OpenVINO's known-bad list. Either way it needs administrator rights and a reboot."],
      ["What if the NPU is never detected?",
       "Check BIOS first — some laptops ship with it disabled. Then install the driver and reboot. If it still does not appear, the machine may not have one. The app falls back to the GPU, then the CPU, and the answers are identical."],
      ["Does the NPU work in Linux, WSL, a VM or on a Mac?",
       "No. The NPU is not passed through to a VM or WSL, so inside WSL OpenVINO sees CPU only. The installer detects WSL and starts the Windows-side app instead. Linux runs CPU and BYOK. Mac has no Intel NPU at all."],
    ]],
    ["Privacy", [
      ["Is my text, documents, audio or prompts sent to a cloud?",
       "No, unless you configure BYOK. Local mode keeps everything in the OpenVINO runtime on this machine. Open Corpus reads files you point it at, locally. Audio is decoded locally. The only outbound traffic is the optional device heartbeat."],
      ["What does the heartbeat send, and how do I turn it off?",
       "The device ID, the OS name, the architecture, the app version, and which backends compiled. No text, no prompts, no file paths, no keys. It goes out every five minutes only when LAYA_PORTAL is set. To disable it, remove that line from .env and restart."],
      ["What is the device ID, and how do I delete it?",
       "A hash of a machine identifier, shown in Compute, like NPU-7K3M-2QXV. It is stable across reinstalls so the registry does not fill with duplicates. To remove a machine, ask the registry owner; the portal exposes an admin prune that deletes records older than a number of days."],
    ]],
    ["Using it", [
      ["What is it good for, and what is it not?",
       "Good: ticket routing, prompt guardrails, document classification, speech to text. Not good: writing replies, summarising, translating, arithmetic over fields. It also should not be trusted for security decisions — the shell-command gating task in this repo scores only 12/18 and is deliberately not exposed as a feature."],
      ["How accurate is it, and what does probability mean?",
       "On the tests shipped here: document type 12/12, issue triage 10/10, email routing 6/6, guardrail 4/4, spam 9/10. The number next to each answer is the model's own confidence, not a guarantee — it is calibrated on the training distribution, not on your data. Validate on a sample of your own traffic before automating anything."],
      ["Which languages and inputs are supported?",
       "English only. The shipped checkpoint scores near zero on non-Latin scripts while still reporting high confidence, so it is not offered. State is capped at 256 tokens. Audio accepts wav, mp3, m4a, aac, ogg, opus, flac, webm, mp4, mov, amr and wma, up to 60 MB and 300 seconds."],
      ["How do I use BYOK?",
       "Compute → Bring your own key. Point it at any server that speaks Jev System One, give it a model name and a key. The key is forwarded in an Authorization header, never written to disk and never echoed back. Private and loopback targets are refused unless you set LAYA_ALLOW_PRIVATE_URL=1 yourself."],
      ["Does the RPA tab actually execute refunds or create invoices?",
       "No. It shows the decision, the rule that fired, and the payload that would be handed to a robot. Nothing is dispatched. Wiring it to a real system means building that yourself and gating it properly — a model choosing a workflow is not authorisation to run it."],
      ["Does the app read my files? Which folders?",
       "Only when you use Open Corpus, and only a directory you type. Reads are restricted to an allowlist of roots, files over 2 MB are capped, a scan stops at 200 entries. Nothing is indexed or uploaded."],
    ]],
    ["When something breaks", [
      ["Installation failed. What now?",
       "Read the last few lines of the installer output. The usual causes are no Python, no npm, or a stale node_modules. The API runs without a UI, so a failed frontend build is not fatal. Re-running the installer skips finished steps."],
      ["It is slow. Where is the time going?",
       `The first request after a restart compiles the graph: about ${MEASURED.decision.NPU.compile_s} s on the NPU, ${MEASURED.decision.GPU.compile_s} s on the GPU. After that a decision costs about ${MEASURED.decision.NPU.ms} ms. Cached kernels live in models/.ovcache, so a warm restart is fast too.`],
      ["The output looks wrong. How do I debug it?",
       "Check the device first — Setup check tells you what actually ran. Then run the same input twice: a large difference means the input is near a decision boundary. The Playground shows every probability, not just the winner, which is usually enough to see why."],
      ["Where are the logs, and how do I report a problem?",
       "The installer prints to the console; the app prints to the window it was started in. Do not paste model input or keys into an issue. The repo has no SECURITY.md yet, so report privately to the maintainer rather than in a public issue."],
    ]],
  ];

  let open = $state<string>("What is Laya?");
  let filter = $state("");

  let flat = $derived(
    GROUPS.flatMap(([g, rows]) => rows.map(([q, a]) => ({ g, q, a }))).filter(
      (r) =>
        !filter ||
        r.q.toLowerCase().includes(filter.toLowerCase()) ||
        r.a.toLowerCase().includes(filter.toLowerCase()),
    ),
  );
</script>

<View
  title="FAQ"
  icon="help"
  subtitle="Twenty questions, grouped. The last group is what to do when something breaks."
>
  {#snippet actions()}
    <input class="field h-7 w-[220px] text-[11.5px]" bind:value={filter} placeholder="Search the FAQ" />
  {/snippet}

  {#if filter}
    <div class="card overflow-hidden">
      {#each flat as r, i}
        <button
          class="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-[12px] hover:bg-hover {i > 0 ? 'border-t border-line' : ''}"
          onclick={() => (open = open === r.q ? "" : r.q)}
        >
          <span class="text-ink-2">{r.q}</span>
          <span class="mono text-[10px] text-ink-3">{open === r.q ? "−" : "+"}</span>
        </button>
        {#if open === r.q}
          <div class="px-4 pb-3 text-[11.5px] leading-relaxed text-ink-3">{r.a}</div>
        {/if}
      {/each}
      {#if !flat.length}
        <p class="px-4 py-6 text-center text-[12px] text-ink-3">Nothing matches that.</p>
      {/if}
    </div>
  {:else}
    {#each GROUPS as [group, rows]}
      <span class="label mb-1.5 block">{group}</span>
      <div class="card mb-4 overflow-hidden">
        {#each rows as [q, a], i}
          <button
            class="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-[12px] hover:bg-hover {i > 0 ? 'border-t border-line' : ''}"
            onclick={() => (open = open === q ? "" : q)}
          >
            <span class="text-ink-2">{q}</span>
            <span class="mono text-[10px] text-ink-3">{open === q ? "−" : "+"}</span>
          </button>
          {#if open === q}
            <div class="px-4 pb-3 text-[11.5px] leading-relaxed text-ink-3">{a}</div>
          {/if}
        {/each}
      </div>
    {/each}
  {/if}
</View>
