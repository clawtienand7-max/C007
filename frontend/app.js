// TFNK Agent OS frontend controller.
// Core rule enforced here: every button is bound to a registry action via
// data-action. On load we fetch /api/actions and disable any control whose
// action is not actually live (status !== connected/permission_required).
// Nothing in this UI pretends to work when its backend is missing.

const api = (path, opts = {}) =>
  fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  }).then(async (r) => ({ ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) }));

const $ = (sel) => document.querySelector(sel);
const state = { session: null, plan: null, stepCursor: 0, actions: {} };

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}

function mind(msg) {
  $("#agent_mind").textContent = msg;
}

function addTimeline(title, meta, cls = "") {
  const li = document.createElement("li");
  li.className = cls;
  li.innerHTML = `<div>${title}</div><div class="meta">${meta}</div>`;
  $("#timeline").prepend(li);
}

// --- bootstrap: wire buttons to real action status --------------------------
async function bootstrap() {
  const { data } = await api("/api/actions");
  for (const a of data.actions || []) state.actions[a.id] = a;

  document.querySelectorAll("[data-action]").forEach((btn) => {
    const action = state.actions[btn.dataset.action];
    const status = action ? action.status : "fake_or_unmapped";
    btn.dataset.status = status;
    if (status === "backend_missing" || status === "fake_or_unmapped") {
      btn.disabled = true;
      btn.title = `Disabled: action "${btn.dataset.action}" has no live backend (${status}).`;
    } else {
      btn.title = `${action.method} ${action.api} — risk:${action.risk}`;
    }
  });

  // health + loop pills
  const h = await api("/api/health");
  $("#pill_health").textContent = h.ok ? "backend ●" : "backend ✕";
  $("#pill_health").style.color = h.ok ? "var(--green)" : "var(--red)";
  refreshLoopStatus();
  refreshLogs();
  loadAudit();
  loadTestsInventory();
  loadPermissions();
}

// --- handlers ---------------------------------------------------------------
const handlers = {
  "agent.session.create": async () => {
    const goal = $("#goal_input").value || "Audit and repair fake UI in TFNK";
    const { data } = await api("/api/agent/session", { method: "POST", body: { goal } });
    state.session = data.session;
    state.plan = null;
    state.stepCursor = 0;
    mind(`Session ${data.session.session_id}\nIntent: ${data.intent.task_type} (risk ${data.intent.risk_level})\nTarget: ${data.intent.target}`);
    addTimeline(`Session created: ${data.session.session_id}`, `intent=${data.intent.task_type}`);
    toast("Session created");
  },
  "agent.plan": async () => {
    if (!state.session) return toast("Create a session first");
    const { data } = await api("/api/agent/plan", { method: "POST", body: { session_id: state.session.session_id, intent: state.session.intent } });
    state.plan = data.plan;
    state.stepCursor = 0;
    mind(`Plan ${data.plan.plan_id}: ${data.plan.steps.length} steps\n` + data.plan.steps.map((s, i) => `${i + 1}. ${s.name} [${s.agent}]`).join("\n"));
    addTimeline(`Plan generated`, `${data.plan.steps.length} steps`);
    toast("Plan generated");
  },
  "agent.step.run": async () => {
    if (!state.plan) return toast("Generate a plan first");
    const step = state.plan.steps[state.stepCursor];
    if (!step) return toast("All steps done");
    const { data } = await api("/api/agent/step/run", { method: "POST", body: { session_id: state.session?.session_id, step } });
    const v = data.step.verification;
    addTimeline(`Step ${state.stepCursor + 1}: ${step.name}`, `tool=${step.tool} • verify=${v} • ${data.step.duration_ms}ms`, v === "passed" ? "passed" : v === "failed" ? "failed" : "");
    state.stepCursor++;
    refreshLogs();
  },
  "agent.verify": async () => {
    const task_type = state.session?.intent?.task_type || "ui_audit";
    const { data } = await api("/api/agent/verify", { method: "POST", body: { task_type } });
    addTimeline(`Verify: ${data.verified ? "PASSED" : "FAILED"}`, `${data.method} • evidence: ${data.evidence.join("; ")}`, data.verified ? "passed" : "failed");
    toast(data.verified ? "Verified ✓" : "Not verified");
  },
  "ui.audit": async () => {
    await loadAudit();
    switchTab("audit");
    toast("UI audit complete");
  },
  "agent.repair": async () => {
    const { data } = await api("/api/agent/repair", { method: "POST", body: { session_id: state.session?.session_id } });
    if (data.requires_permission) {
      addTimeline("Repair proposed — permission required", `permission ${data.permission_id} • risk ${data.risk_level}`);
      switchTab("permissions");
      loadPermissions();
      toast("Repair needs approval — see Permission Queue");
    } else {
      addTimeline("Repair", data.repair_result, data.repair_result === "passed" ? "passed" : "");
      toast(data.notes?.[0] || "Nothing to repair");
    }
    refreshLogs();
  },
  "loop.start": async () => {
    const { data } = await api("/api/loop/run", { method: "POST", body: { max_iterations: 5, goal: state.session?.goal } });
    if (!data.ok) toast(data.error || "Could not start");
    else addTimeline("LOOP started", `run ${data.status.run_id}`);
    pollLoop();
  },
  "loop.stop": async () => {
    const { data } = await api("/api/loop/stop", { method: "POST" });
    toast(data.ok ? "LOOP stopped" : data.error);
    refreshLoopStatus();
  },
  "loop.status": refreshLoopStatus,
  "emergency.stop": async () => {
    await api("/api/emergency-stop", { method: "POST" });
    addTimeline("EMERGENCY STOP engaged", new Date().toLocaleTimeString(), "failed");
    toast("Emergency stop engaged");
    refreshLoopStatus();
  },
  "tests.run": async () => {
    switchTab("tests");
    $("#tests_summary").innerHTML = `<div class="stat"><b>…</b><span>running real test suite</span></div>`;
    const { data } = await api("/api/tests/run", { method: "POST" });
    const r = data.result;
    $("#tests_summary").innerHTML = `
      <div class="stat"><b>${r.summary.pass ?? "?"}</b><span>passed</span></div>
      <div class="stat"><b>${r.summary.fail ?? "?"}</b><span>failed</span></div>
      <div class="stat"><b>${r.result}</b><span>exit ${r.exit_code}</span></div>`;
    $("#tests_output").textContent = r.stdout_tail + "\n" + (r.stderr_tail || "");
    addTimeline("Tests run", `${r.result} (pass ${r.summary.pass}, fail ${r.summary.fail})`, r.result === "passed" ? "passed" : "failed");
  },
};

document.querySelectorAll("[data-action]").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.disabled) return;
    const h = handlers[btn.dataset.action];
    if (h) h();
    else toast(`No handler for ${btn.dataset.action}`);
  });
});

// --- loaders ----------------------------------------------------------------
async function loadAudit() {
  const { data } = await api("/api/agent/audit", { method: "POST" });
  const r = data.report;
  $("#audit_summary").innerHTML = `
    <div class="stat"><b>${r.total_elements}</b><span>elements</span></div>
    <div class="stat"><b>${r.connected}</b><span>connected</span></div>
    <div class="stat"><b>${r.fake_or_incomplete}</b><span>incomplete</span></div>`;
  const tbody = $("#audit_table tbody");
  tbody.innerHTML = "";
  for (const i of r.items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${i.ui_id || "—"}</td><td>${i.action_id || "—"}</td>
      <td><span class="badge ${i.status}">${i.status}</span></td><td>${i.reason || ""}</td>`;
    tbody.appendChild(tr);
  }
}

async function loadTestsInventory() {
  const { data } = await api("/api/tests");
  $("#tests_summary").innerHTML = `
    <div class="stat"><b>${data.coverage.total}</b><span>actions</span></div>
    <div class="stat"><b>${data.coverage.with_test}</b><span>with test</span></div>
    <div class="stat"><b>${data.test_files.length}</b><span>test files</span></div>`;
}

async function loadPermissions() {
  const { data } = await api("/api/permissions");
  const box = $("#permissions_list");
  const pending = (data.permissions || []).filter((p) => p.status === "pending");
  if (!pending.length) {
    box.innerHTML = `<p class="hint">No pending permission requests.</p>`;
    return;
  }
  box.innerHTML = "";
  for (const p of pending) {
    const div = document.createElement("div");
    div.className = "perm";
    div.innerHTML = `<b>${p.action_id}</b> <span class="badge permission_required">${p.risk}</span>
      <div>${p.reason}</div><div class="hint">files: ${(p.files || []).join(", ")}</div>
      <div class="row">
        <button class="approve" data-pid="${p.permission_id}" data-decision="approve">Approve</button>
        <button class="deny" data-pid="${p.permission_id}" data-decision="deny">Deny</button>
      </div>`;
    box.appendChild(div);
  }
  box.querySelectorAll("button[data-pid]").forEach((b) =>
    b.addEventListener("click", async () => {
      const { data } = await api("/api/permissions/decide", { method: "POST", body: { permission_id: b.dataset.pid, decision: b.dataset.decision } });
      addTimeline(`Permission ${data.permission?.status}`, b.dataset.pid);
      loadPermissions();
      refreshLogs();
    }),
  );
}

async function refreshLoopStatus() {
  const { data } = await api("/api/loop/status");
  const s = data.status;
  $("#pill_loop").textContent = `loop: ${s.status}${s.iteration ? " #" + s.iteration : ""}`;
  $("#pill_loop").style.color = s.status === "running" ? "var(--amber)" : s.status === "completed" ? "var(--green)" : "var(--muted)";
  return s;
}

let pollTimer = null;
async function pollLoop() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const s = await refreshLoopStatus();
    if (s.status !== "running") {
      clearInterval(pollTimer);
      addTimeline(`LOOP ${s.status}`, `${s.iteration} iterations`);
      refreshLogs();
    }
  }, 300);
}

async function refreshLogs() {
  const { data } = await api("/api/logs?limit=60");
  $("#logs").textContent = (data.logs || [])
    .slice()
    .reverse()
    .map((l) => `${l.ts.slice(11, 19)} [${l.agent || "?"}] ${l.event}`)
    .join("\n");
}

// --- tabs -------------------------------------------------------------------
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab_${name}`));
}
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
$("#btn_refresh_logs").addEventListener("click", refreshLogs);

bootstrap();
