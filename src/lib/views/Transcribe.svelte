<script lang="ts">
  import View from "$lib/View.svelte";
  import Icon from "$lib/Icon.svelte";
  import { get, post, postAudio } from "$lib/http";

  type Props = { backend?: string };
  let { backend = "" }: Props = $props();

  let available = $state<any>(null);
  let result = $state<any>(null);
  let busy = $state(false);
  let error = $state("");
  let dragging = $state(false);
  let fileName = $state("");

  const device = $derived(
    backend.startsWith("local:") ? backend.split(":")[1].toUpperCase() : "NPU",
  );

  $effect(() => {
    get("/api/asr").then((r) => r.json()).then((d) => (available = d)).catch(() => {});
  });

  async function upload(file: File) {
    if (!file) return;
    busy = true;
    error = "";
    result = null;
    fileName = file.name;
    try {
      const buf = await file.arrayBuffer();
      const r = await postAudio("/api/asr", buf, { "X-Device": device, "Content-Type": "application/octet-stream" });
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

  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([result.text], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName.replace(/\.[^.]+$/, "") + ".txt";
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<View
  title="Transcribe"
  icon="mic"
  subtitle="Whisper int8, running locally. No API key, no per-minute cost, nothing leaves the machine. Feed it wav, mp3, m4a, ogg, flac or webm — the converter ships with the app."
>
  {#snippet actions()}
    {#if available}<span class="chip mono">{available.model ? "model ready" : "no model"}</span>{/if}
    <span class="chip mono">{device}</span>
  {/snippet}

  {#if available && !available.present}
    <div class="card mb-3 p-4">
      <span class="label">No transcription model installed</span>
      <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
        Download whisper-base int8 (85 MB) and point the app at it:
      </p>
      <pre class="mono mt-2 overflow-auto rounded border border-line-2 bg-panel-2 p-2.5 text-[10.5px] text-ink-2">python -c "from huggingface_hub import snapshot_download; snapshot_download('OpenVINO/whisper-base-int8-ov', local_dir=r'C:\Users\you\models\whisper-base-int8')"</pre>
      <p class="mt-2 text-[11px] text-ink-3">
        Then add <code class="mono">WHISPER_MODEL</code> to <code class="mono">.env</code> and restart.
      </p>
    </div>
  {/if}

  <div
    class="card flex flex-1 flex-col items-center justify-center p-8 text-center transition-colors
      {dragging ? 'border-ink/50 bg-panel-2' : ''}"
    ondragover={(e) => { e.preventDefault(); dragging = true; }}
    ondragleave={() => (dragging = false)}
    ondrop={onDrop}
    role="button"
    tabindex="0"
  >
    {#if busy}
      <Icon name="mic" size={26} />
      <p class="mt-3 text-[13px]">Transcribing {fileName}…</p>
      <p class="mt-1 text-[11.5px] text-ink-3">the NPU does about 57x realtime</p>
    {:else if result}
      <div class="w-full max-w-[720px] text-left">
        <div class="mb-3 flex flex-wrap items-center gap-1.5">
          <span class="chip mono">{result.seconds}s audio</span>
          <span class="chip mono">{result.infer_s}s infer</span>
          <span class="chip mono">{result.speedup}x realtime</span>
          <span class="chip mono">{result.device}</span>
          <button class="btn ml-auto h-6 text-[10.5px]" onclick={download}>Download .txt</button>
        </div>
        <p class="whitespace-pre-wrap text-[13.5px] leading-relaxed">{result.text}</p>
      </div>
    {:else}
      <Icon name="mic" size={26} />
      <p class="mt-3 text-[13px]">Drop an audio file here</p>
      <p class="mt-1 text-[11.5px] text-ink-3">or pick one</p>
      <label class="btn btn-solid mt-4 h-8 cursor-pointer">
        Choose file
        <input type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.webm,.mp4" onchange={onPick} class="hidden" />
      </label>
    {/if}
  </div>

  {#if error}
    <div class="mt-3 rounded-card border border-[#3b1c1c] bg-[#140a0a] p-2.5 text-[11.5px] text-[#f43e64]">
      {error}
    </div>
  {/if}

  <div class="card mt-3 p-4">
    <span class="label">Measured here</span>
    <p class="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
      45 s of speech, whisper-base int8: NPU 0.79 s (57x realtime), CPU 1.74 s, GPU 2.49 s.
      The NPU beats the GPU by 3x on audio — the opposite of the decision model, because
      transcription is one forward pass over a fixed window rather than an autoregressive
      decode loop.
    </p>
  </div>
</View>
