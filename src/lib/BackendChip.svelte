<script lang="ts">
  type Props = {
    backend?: string;
    onPick?: (id: string) => void;
    backends?: any[];
  };
  let { backend = "", onPick = () => {}, backends = [] }: Props = $props();

  let current = $derived(backends.find((b) => b.id === backend));

  let dot = $derived(
    current?.ready ? "bg-[#43cb7a]" : current?.present ? "bg-[#e9c93a]" : "bg-ink-3"
  );
</script>

<button
  class="btn h-7 gap-2"
  onclick={() => {
    const ready = backends.filter((b) => b.ready);
    if (!ready.length) return;
    const i = ready.findIndex((b) => b.id === backend);
    onPick(ready[(i + 1) % ready.length].id);
  }}
  title="Cycle the compute backend"
>
  <span class="size-1.5 rounded-full {dot}"></span>
  <span class="mono text-[11px]">{current?.device ?? "—"}</span>
</button>
