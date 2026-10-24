export type Backend = {
  id: string;
  device: string;
  label: string;
  kind: "local" | "byok";
  present: boolean;
  ready: boolean;
  reason: string | null;
  latency_ms: number | null;
  compile_s: number | null;
  description: string;
  url?: string | null;
  model?: string | null;
};

export const SECTIONS = [
  { id: "overview", label: "Overview", icon: "sparkles", group: "Start" },
  { id: "setup", label: "Setup check", icon: "check", group: "Start" },
  { id: "playground", label: "Playground", icon: "play", group: "Model" },
  { id: "backends", label: "Compute", icon: "cpu", group: "Model" },
  { id: "providers", label: "Providers", icon: "server", group: "Model" },
  { id: "pricing", label: "Pricing", icon: "tag", group: "Model" },
  { id: "performance", label: "Performance", icon: "gauge", group: "Model" },
  { id: "voice", label: "Voice", icon: "mic", group: "Tools" },
  { id: "transcribe", label: "Transcribe", icon: "mic", group: "Tools" },
  { id: "corpus", label: "Open Corpus", icon: "folder", group: "Tools" },
  { id: "schema", label: "Schema", icon: "code", group: "Tools" },
  { id: "apps", label: "Apps", icon: "grid", group: "Usage" },
  { id: "parameters", label: "Parameters", icon: "sliders", group: "Reference" },
  { id: "faq", label: "FAQ", icon: "help", group: "Reference" },
] as const;

export type SectionId = (typeof SECTIONS)[number]["id"];

export const GROUPS = [...new Set(SECTIONS.map((s) => s.group))];

export const PROJECT = {
  name: "laya-npu",
  tagline: "Typed decisions and local speech, on the NPU you already own.",
  description:
    "Route tickets, gate prompts and transcribe audio on the Intel NPU inside your " +
    "laptop. No cloud, no API keys, no per-token bill.",
  portal: "https://manef.dev",
  author: "https://rahmanef.com",
  repo: "https://github.com/rahmanef63/laya-npu",
  collaborators: ["rahmanef63", "official-manef", "ManefDev"],
};
