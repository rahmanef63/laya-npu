// One place that talks to the API, so the access token is applied once.
//
// The server inlines the token into the page as a meta tag only when LAYA_TOKEN is set
// (that is what happens when the app binds to a LAN address). On loopback there is no
// token and these headers are simply absent.

function token(): string {
  if (typeof document === "undefined") return "";
  const meta = document.querySelector('meta[name="laya-token"]');
  return meta?.getAttribute("content") ?? "";
}

export function headers(extra: Record<string, string> = {}): Record<string, string> {
  const t = token();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

async function parse<T>(r: Response): Promise<T> {
  const d = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok && !("error" in d)) return { error: `HTTP ${r.status}` } as T;
  return d as T;
}

export async function get<T = any>(path: string): Promise<T> {
  const r = await fetch(path, { headers: headers() });
  return parse<T>(r);
}

export async function post<T = any>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  return parse<T>(r);
}

export async function postAudio<T = any>(
  path: string,
  bytes: ArrayBuffer,
  extra: Record<string, string> = {},
): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: headers({ "Content-Type": "application/octet-stream", ...extra }),
    body: bytes,
  });
  return parse<T>(r);
}

export const api = {
  tasks: () => get("/api/tasks"),
  backends: () => get("/api/backends"),
  health: () => get("/api/health"),
  driver: () => get("/api/driver"),
  device: () => get("/api/device"),
  pipeline: () => get("/api/pipeline"),
  asr: () => get("/api/asr"),
  analyse: (text: string, task: string, opts: Record<string, unknown> = {}) =>
    post("/api/analyse", { text, task, ...opts }),
  custom: (state: string, questions: unknown, opts: Record<string, unknown> = {}) =>
    post("/api/custom", { state, questions, ...opts }),
  rpa: (body: unknown) => post("/api/rpa", body),
};
