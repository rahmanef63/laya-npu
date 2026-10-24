// Portal page script. No framework: the page is static, the data is three fetches.

const $ = (id) => document.getElementById(id);

function ago(seconds) {
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

async function loadRegistry() {
  try {
    const r = await fetch("/api/summary");
    const d = await r.json();
    $("r-total").textContent = d.total ?? 0;
    $("r-online").textContent = d.online ?? 0;
    $("r-npu").textContent = d.by_device?.NPU ?? 0;
    $("r-byok").textContent = d.byok ?? 0;
    $("n-total").textContent = d.total ?? 0;
    $("n-online").textContent = d.online ?? 0;
    $("n-npu").textContent = d.by_device?.NPU ?? 0;
    $("n-byok").textContent = d.byok ?? 0;

    const pill = $("live-pill");
    pill.innerHTML =
      d.total > 0
        ? `<span class="dot on"></span> ${d.total} install${d.total === 1 ? "" : "s"} registered`
        : `<span class="dot"></span> registry empty — install to be the first`;

    // Aggregate bars, no per-machine detail
    const rows = Object.entries(d.by_device ?? {});
    const max = Math.max(1, ...rows.map(([, n]) => n));
    $("r-bars").innerHTML = rows
      .map(
        ([name, n]) => `<div class="brow">
          <span class="bname mono">${esc(name)}</span>
          <div class="btrack"><div class="bfill" style="width:${(n / max) * 100}%"></div></div>
          <span class="bnum mono">${n}</span>
        </div>`,
      )
      .join("");
  } catch {
    $("live-pill").innerHTML = `<span class="dot"></span> registry unreachable`;
  }
}

// A browser cannot see the NPU; WebGPU presence is the closest honest signal.
async function detectHardware() {
  const gpu = $("d-webgpu");
  if (!("gpu" in navigator)) {
    gpu.textContent = "not available in this browser";
    gpu.className = "dv muted";
  } else {
    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) {
        gpu.textContent = "no adapter (software rendering?)";
        gpu.className = "dv bad";
      } else {
        const info = adapter.info ?? {};
        const name = info.description || info.device || "adapter present";
        gpu.textContent = name;
        gpu.className = "dv ok";
      }
    } catch {
      gpu.textContent = "blocked";
      gpu.className = "dv muted";
    }
  }

  const hints = $("d-hints");
  const bits = [];
  if (navigator.hardwareConcurrency) bits.push(`${navigator.hardwareConcurrency} threads`);
  if (navigator.userAgentData?.platform) bits.push(navigator.userAgentData.platform);
  else if (navigator.platform) bits.push(navigator.platform);
  hints.textContent = bits.join(" · ") || "nothing reported";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

async function checkDevice() {
  const out = $("link-result");
  const verdict = $("d-verdict");
  const id = $("link-input").value.trim().toUpperCase();
  if (!/^NPU-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(id)) {
    out.className = "result bad";
    out.textContent = "Expected a device ID like NPU-7K3M-2QXV.";
    return;
  }
  out.className = "result";
  out.textContent = "checking…";
  try {
    const r = await fetch("/api/device/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    const d = await r.json();
    if (!d.found) {
      out.className = "result bad";
      out.textContent = "Not registered. Run the installer, then look in Setup check.";
      if (verdict) {
        verdict.textContent = "not in the registry";
        verdict.className = "dv mono bad";
      }
      return;
    }
    out.className = "result ok";
    out.textContent = `Registered — ${d.state}.`;
    if (verdict) {
      verdict.textContent = `registered · ${d.state}`;
      verdict.className = "dv mono ok";
    }
  } catch {
    out.className = "result bad";
    out.textContent = "Registry unreachable.";
  }
}

$("link-input")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") checkDevice();
});

loadRegistry();
detectHardware();
setInterval(loadRegistry, 60000);
