export type BackendOpts = {
  backend?: string;
  byokUrl?: string;
  byokKey?: string;
  byokModel?: string;
};

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

export const api = {
  tasks: () => fetch("/api/tasks").then((r) => r.json()),
  backends: () => fetch("/api/backends").then((r) => r.json()),
  health: () => fetch("/api/health").then((r) => r.json()),
  analyse: (text: string, task: string, opts: BackendOpts = {}) =>
    post("/api/analyse", { text, task, ...opts }),
  custom: (state: string, questions: unknown, opts: BackendOpts = {}) =>
    post("/api/custom", { state, questions, ...opts }),
  rpa: (body: unknown) => post("/api/rpa", body),
};
