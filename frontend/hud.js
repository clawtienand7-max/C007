// TFNK OM HUD controller. Same no-fake-UI rule as the Command Center: every
// data-action button is enabled only if /api/actions says it is live. All data
// comes from real APIs; unavailable telemetry/weather is shown as such.

const api = (p, opts = {}) =>
  fetch(p, { headers: { "Content-Type": "application/json" }, ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined })
    .then(async (r) => ({ ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) }));
const $ = (s) => document.querySelector(s);
const state = { actions: {}, chatSession: null, agent: "tfnk", telemetryTimer: null };

function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2400); }

const handlers = {
  "hud.telemetry.refresh": async () => { await loadTelemetry(true); toast("Telemetry refreshed"); },
  "om.graph.load": async () => { await loadGraph(); toast("OM graph reloaded"); },
  "weather.hk.refresh": async () => { await loadWeather(); toast("Weather refreshed"); },
  "hud.toggle_animation": async () => {
    const { data } = await api("/api/hud/animation/toggle", { method: "POST", body: {} });
    document.body.classList.toggle("no-anim", !data.animation);
    toast(`Animation ${data.animation ? "on" : "off"}`);
  },
  "hud.layout.save": async () => { await api("/api/hud/layout/save", { method: "POST", body: { layout: { savedAt: Date.now() } } }); toast("Layout saved"); },
  "chat.new": async () => {
    const { data } = await api("/api/chat/session/new", { method: "POST", body: { agent: state.agent } });
    state.chatSession = data.session.session_id;
    $("#chat_log").innerHTML = `<div class="hint">New ${state.agent} session ${data.session.session_id}.</div>`;
    loadSessions();
    toast("New chat");
  },
  "chat.message.send": sendMessage,
  "emergency.stop": async () => {
    await api("/api/emergency-stop", { method: "POST", body: {} });
    toast("EMERGENCY STOP engaged");
    loadTopbar();
  },
};

async function bootstrap() {
  const { data } = await api("/api/actions");
  for (const a of data.actions || []) state.actions[a.id] = a;
  document.querySelectorAll("[data-action]").forEach((btn) => {
    const a = state.actions[btn.dataset.action];
    const status = a ? a.status : "fake_or_unmapped";
    if (status === "backend_missing" || status === "fake_or_unmapped") { btn.disabled = true; btn.title = `disabled (${status})`; }
    btn.addEventListener("click", () => { if (btn.disabled) return; const h = handlers[btn.dataset.action]; if (h) h(); });
  });
  // animation state
  const hud = await api("/api/hud/state").then((r) => r.data.hud);
  document.body.classList.toggle("no-anim", hud && hud.animation === false);

  // chat tabs (client-only)
  document.querySelectorAll("#chat_tabs button").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll("#chat_tabs button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active"); state.agent = b.dataset.tab;
    }));
  $("#chat_collapse").addEventListener("click", () => $("#chat_table").classList.toggle("collapsed"));
  $("#chat_text").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } });

  loadTopbar(); loadTelemetry(); loadGraph(); loadWeather(); loadSessions();
  state.telemetryTimer = setInterval(loadTelemetry, (hud && hud.telemetry_interval_ms) || 4000);
  setInterval(loadTopbar, 5000);
}

async function loadTopbar() {
  const loop = await api("/api/loop/status").then((r) => r.data.status).catch(() => null);
  if (loop) $("#t_loop").textContent = loop.status;
  const dev = await api("/api/devices").then((r) => r.data).catch(() => null);
  if (dev) $("#t_peers").textContent = dev.peers.length;
}

function fmt(v, unit = "") { return v === null || v === undefined ? null : `${v}${unit}`; }
function setMetric(id, val) { const el = $(id); if (val === null) { el.textContent = "unavailable"; el.classList.add("na"); } else { el.textContent = val; el.classList.remove("na"); } }

async function loadTelemetry(refresh) {
  const { data } = refresh ? await api("/api/telemetry/refresh", { method: "POST", body: {} }) : await api("/api/telemetry/system");
  if (!data || !data.cpu) return;
  setMetric("#m_cpu", fmt(data.cpu.usage, "%"));
  setMetric("#m_ram", `${data.memory.used} / ${data.memory.total} GB (${data.memory.percent}%)`);
  setMetric("#m_gpu", data.gpu.available ? fmt(data.gpu.usage, "%") : null);
  setMetric("#m_gputemp", data.gpu.available ? fmt(data.gpu.temperature, "°C") : null);
  setMetric("#m_vram", data.gpu.available ? `${data.gpu.vramUsed?.toFixed?.(1)} / ${data.gpu.vramTotal?.toFixed?.(1)} GB` : null);
  setMetric("#m_net", data.network.downloadMbps === null ? `${data.network.interfaces.length} iface` : `↓${data.network.downloadMbps} ↑${data.network.uploadMbps}`);
  setMetric("#m_disk", data.disk.available ? `${data.disk.freeGB} GB free` : null);
  setMetric("#m_peers", String(data.network.lanPeers));
}

async function loadGraph() {
  const g = await api("/api/om/graph").then((r) => r.data);
  const cx = 200, cy = 200, R = 78;
  const others = g.nodes.filter((n) => n.id !== "om_core");
  const pos = { om_core: { x: cx, y: cy } };
  others.forEach((n, i) => { const a = (i / others.length) * Math.PI * 2 - Math.PI / 2; pos[n.id] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R }; });
  let svg = "";
  for (const e of g.edges) { const s = pos[e.source], t = pos[e.target]; if (s && t) svg += `<line class="edge" x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" />`; }
  for (const n of g.nodes) { const p = pos[n.id]; const r = n.type === "core" ? 12 : 6; svg += `<g class="node ${n.type === "core" ? "core" : ""}"><circle cx="${p.x}" cy="${p.y}" r="${r}" /><text x="${p.x}" y="${p.y + r + 9}">${n.label}</text></g>`; }
  $("#om_graph").innerHTML = svg;
  $("#om_core_small").textContent = `${g.nodes.length} nodes · ${g.memory_link_count} links`;
}

async function loadWeather() {
  const w = await api("/api/weather/hong-kong").then((r) => r.data);
  const box = $("#weatherbox");
  if (!w.available) {
    box.innerHTML = `<div class="na">Weather unavailable</div><div class="hint">${w.error || ""}</div><div class="hint">source: ${w.source}</div>`;
    $("#t_weather").textContent = "n/a";
    return;
  }
  box.innerHTML = `<div class="temp">${w.temperature_c ?? "—"}°C</div>
    <div class="hint">Humidity ${w.humidity_percent ?? "—"}% · Rain max ${w.rainfall_mm_max ?? 0} mm</div>
    <div class="hint">Warnings: ${(w.warnings && w.warnings.length) ? w.warnings.join("; ") : "none"}</div>
    <div class="hint">source: ${w.source} · ${w.observed || ""}</div>`;
  $("#t_weather").textContent = `${w.temperature_c ?? "—"}°C`;
}

async function loadSessions() {
  const s = await api("/api/chat/sessions").then((r) => r.data.sessions || []);
  $("#chat_sessions").innerHTML = s.length
    ? s.map((x) => `<div class="hint">• ${x.title} [${x.agent}] (${x.message_count} msg)</div>`).join("")
    : `<div class="hint">no sessions</div>`;
}

async function sendMessage() {
  const text = $("#chat_text").value.trim();
  if (!text) return;
  const table = $("#chat_table"); table.classList.add("sending"); table.classList.remove("error");
  appendMsg("user", text);
  $("#chat_text").value = "";
  const { ok, data } = await api("/api/chat/message", { method: "POST", body: { session_id: state.chatSession, text } });
  table.classList.remove("sending");
  if (!ok || data.error) { table.classList.add("error"); toast(data.error || "send failed"); return; }
  state.chatSession = data.session_id;
  appendMsg("tfnk", data.reply.text);
  loadSessions();
}
function appendMsg(role, text) {
  const log = $("#chat_log");
  if (log.querySelector(".hint")) log.innerHTML = "";
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `<span class="who">${role === "user" ? "you" : "TFNK"}</span>${text}`;
  log.appendChild(div); log.scrollTop = log.scrollHeight;
}

bootstrap();
