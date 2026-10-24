// The single source of truth for every number the UI shows.
//
// The review found README saying NPU 66 ms / GPU 43 ms / CPU 443 ms while the views said
// 29.3 / 34.7 / 404. Both were measured, at different times and with different padding.
// These are the current figures, re-measured on the same graph, 256-token window, 40
// iterations after warmup, and every surface now reads from here.
//
// Re-measure with:  python tests/bench_backends.py

export const MEASURED = {
  date: "2026-10-24",
  machine: "Intel Core Ultra 9 386H",
  runtime: "OpenVINO 2026.4.1, INT8",
  window: "256 tokens, 1 question per request",

  // Decision model (Laya), milliseconds per question.
  decision: {
    NPU: { ms: 26.5, compile_s: 17.6 },
    GPU: { ms: 32.5, compile_s: 3.7 },
    CPU: { ms: 182.3, compile_s: 3.3 },
  },

  // Whisper (speech), seconds for 45.3 s of audio.
  asr: {
    NPU: { s: 0.79, realtime: 57 },
    CPU: { s: 1.74, realtime: 26 },
    GPU: { s: 2.49, realtime: 18 },
  },

  // Headline figures used on the Overview and in the social card.
  headline: {
    perDecisionMs: 27,
    asrRealtime: 57,
    whisperSizeMb: 85,
    costPerRequest: "$0",
  },
};

export function decisionMs(device: string): number | null {
  const row = MEASURED.decision[device.toUpperCase() as keyof typeof MEASURED.decision];
  return row ? row.ms : null;
}
