<script lang="ts">
  // Thin outline icons, Lucide-style paths, one component keyed by name.
  type Props = { name?: string; size?: number; stroke?: number };
  let { name = "circle", size = 14, stroke = 1.6 }: Props = $props();

  const PATHS: Record<string, string> = {
    play: "M6 4l14 8-14 8z",
    cpu: "M6 6h12v12H6z M10 10h4v4h-4z M9 2v4 M15 2v4 M9 18v4 M15 18v4 M2 9h4 M2 15h4 M18 9h4 M18 15h4",
    server: "M4 5h16v6H4z M4 13h16v6H4z M7 8h.01 M7 16h.01",
    tag: "M3 3h8l10 10-8 8L3 11z M7 7h.01",
    gauge: "M12 21a9 9 0 1 1 9-9 M12 12l4-4",
    grid: "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
    sliders: "M4 6h16 M4 12h16 M4 18h16 M9 3v6 M15 9v6 M7 15v6",
    help: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7 M12 17h.01",
    x: "M6 6l12 12 M18 6L6 18",
    copy: "M9 9h10v10H9z M5 15V5h10",
    check: "M4 12l5 5L20 6",
    chevron: "M6 9l6 6 6-6",
    arrowUpRight: "M7 17L17 7 M9 7h8v8",
    circle: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0",
    sparkles: "M12 3l1.9 4.8L18.7 9.7l-4.8 1.9L12 16.4l-1.9-4.8L5.3 9.7l4.8-1.9z",
    plus: "M12 5v14 M5 12h14",
    layers: "M12 3l9 5-9 5-9-5z M3 13l9 5 9-5",
    folder: "M3 7h6l2 2h10v10H3z",
    mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z M5 11a7 7 0 0 0 14 0 M12 18v3",
    search: "M11 11m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0 M21 21l-4.3-4.3",
    code: "M8 8l-4 4 4 4 M16 8l4 4-4 4",
  };
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width={stroke}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  <path d={PATHS[name] ?? PATHS.circle} />
</svg>
