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
  loadMemory();
  loadDevices();
  loadGestures();
  loadVision();
  loadScheduler();
  loadDelivery();
  loadSelfUpgrade();
  subscribeEvents();
}

// Live event stream (SSE) — updates the gesture timeline and loop pill as
// peer/vision events arrive.
function subscribeEvents() {
  try {
    const es = new EventSource("/api/events");
    es.onmessage = (m) => {
      const e = JSON.parse(m.data);
      if (e.event === "gesture.command.detected") {
        addTimeline(`Gesture: ${e.gesture}`, `→ ${e.mapped_action} (${e.verification_result})`, e.executed ? "passed" : "");
        loadVision();
      } else if (e.event === "peer.online") {
        loadDevices();
      }
    };
  } catch {
    /* EventSource unavailable; panels still work via manual refresh */
  }
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
  "agent.run": async () => {
    const goal = $("#goal_input").value || "Audit and repair fake UI in TFNK";
    mind("Running autonomously…");
    const { data } = await api("/api/agent/run", { method: "POST", body: { goal } });
    state.session = data.session;
    mind(data.report.markdown);
    addTimeline(`Autonomous run: ${data.session.status}`, `completed ${data.report.completed} • verified ${data.report.verified}`, data.report.verified ? "passed" : "");
    switchTab("timeline");
    refreshLogs();
    toast(`Autonomous run: ${data.session.status}`);
  },
  "memory.write": async () => {
    const text = $("#memory_input").value.trim();
    if (!text) return toast("Type something to remember");
    const { data } = await api("/api/memory/write", { method: "POST", body: { kind: "fact", text } });
    $("#memory_input").value = "";
    addTimeline("Memory saved", data.entry.id);
    loadMemory();
    switchTab("memory");
    toast("Saved to memory");
  },
  "memory.search": async () => {
    const q = $("#memory_input").value.trim();
    await loadMemory(q);
    switchTab("memory");
    toast("Memory searched");
  },
  "computer.screenshot": async () => {
    const { data } = await api("/api/computer/screenshot", { method: "POST" });
    $("#computer_view").textContent = JSON.stringify(data.snapshot, null, 2);
    switchTab("computer");
    addTimeline("Computer screenshot", `${data.snapshot.elements.length} elements seen`);
  },
  "computer.click": async () => {
    const ui_id = $("#click_input").value.trim() || "btn_loop_status";
    const { data } = await api("/api/computer/click", { method: "POST", body: { ui_id } });
    addTimeline(`Computer click: ${ui_id}`, `${data.verification} — ${data.reason}`, data.verification === "passed" ? "passed" : data.verification === "blocked" ? "failed" : "");
    switchTab("computer");
    handlers["computer.screenshot"]();
    toast(`click ${ui_id}: ${data.verification}`);
  },
  "computer.type": async () => {
    const text = $("#goal_input").value || "typed by computer use agent";
    const { data } = await api("/api/computer/type", { method: "POST", body: { ui_id: "goal_input", text } });
    addTimeline("Computer type → goal_input", `${data.verification} — ${data.reason}`, data.verification === "passed" ? "passed" : "");
    toast(`type: ${data.verification}`);
  },
  "devices.discover": async () => {
    const { data } = await api("/api/devices/discover", { method: "POST" });
    addTimeline("Device discovery", `${data.peers.length} peer(s) on LAN`);
    switchTab("devices");
    loadDevices();
    toast(`Discovery: ${data.peers.length} peer(s)`);
  },
  "devices.pair": async () => {
    const node_id = $("#pair_node_input").value.trim();
    if (!node_id) return toast("Enter a peer node_id");
    const { data } = await api("/api/devices/pair", { method: "POST", body: { node_id } });
    if (data.error) return toast(data.error);
    addTimeline(`Pairing started for ${node_id}`, `code ${data.pairing_code} (enter on the peer)`);
    toast(`Pairing code: ${data.pairing_code}`);
  },
  "camera.start": async () => {
    // Demo path: register the shipped sample replay source, then test it.
    const add = await api("/api/camera/source/add", { method: "POST", body: { type: "frames_jsonl", name: "Demo 360 replay", uri: "data/samples/gestures_demo.jsonl" } });
    state.camSource = add.data.source.source_id;
    const { data } = await api("/api/camera/start", { method: "POST", body: { source_id: state.camSource } });
    $("#cam_state").textContent = data.started ? "● live (replay)" : "● failed";
    addTimeline("Camera start", data.started ? `replay ${data.test.fps}fps ${data.test.resolution}` : data.test.error, data.started ? "passed" : "failed");
    switchTab("vision");
    toast(data.started ? "Camera ready (replay)" : "Camera failed");
  },
  "vision.start": async () => {
    await api("/api/vision/start", { method: "POST", body: {} });
    if (state.camSource) await api("/api/vision/replay", { method: "POST", body: { source_id: state.camSource } });
    switchTab("vision");
    await loadVision();
    addTimeline("Vision started", state.camSource ? "replayed demo gestures" : "ingest mode");
    toast("Vision running");
  },
  "vision.stop": async () => {
    await api("/api/vision/stop", { method: "POST" });
    $("#cam_state").textContent = "● idle";
    await loadVision();
    toast("Vision stopped");
  },
  "gesture.map_action": async () => {
    await loadGestures();
    switchTab("vision");
    toast("Gesture map reloaded");
  },
  "scheduler.task.create": async () => {
    const name = $("#sched_name_input").value.trim() || "每日 TFNK 健康檢查";
    const { data } = await api("/api/scheduler/tasks", { method: "POST", body: { name, task_type: "health_check", schedule_type: "interval", interval_seconds: 3600, risk_level: "low" } });
    state.schedTaskId = data.task.id;
    addTimeline("Scheduled task created", `${data.task.name} • next ${data.task.next_run_at || "—"}`);
    switchTab("scheduler");
    loadScheduler();
    toast("Task created");
  },
  "scheduler.task.run_now": async () => {
    if (!state.schedTaskId) return toast("Create a task first");
    const { data } = await api("/api/scheduler/tasks/run-now", { method: "POST", body: { id: state.schedTaskId } });
    addTimeline("Run now", `${data.run.status} • verify ${data.run.verification_result}`, data.run.verification_result === "passed" ? "passed" : "");
    loadScheduler();
    toast(`Run: ${data.run.status}`);
  },
  "contract.create": async () => {
    const { data } = await api("/api/contracts", { method: "POST", body: {
      user_goal: "讓 TFNK 可每日自動健康檢查並在 UI 查看結果",
      must_have: ["可建立 scheduled task", "可 Run Now", "task_run 記錄產生", "UI 顯示 status"],
      real_usage_scenario: [{ type: "api", action: "GET /api/health", expect: { status_code: 200, body_contains: ["ok"] } }],
      risk_level: "medium",
    } });
    state.contractId = data.contract.requirement_id;
    addTimeline("Requirement contract created", data.contract.requirement_id);
    toast("Contract created");
  },
  "delivery.intake": async () => {
    if (!state.contractId) await handlers["contract.create"]();
    const { data } = await api("/api/deliveries/intake", { method: "POST", body: {
      source_agent: "codex", source_type: "pr", requirement_id: state.contractId,
      branch: "codex/demo", changed_files: ["backend/lib/scheduler.js", "frontend/app.js"],
      report: "可建立 scheduled task、可 Run Now、task_run 記錄產生、UI 顯示 status",
    } });
    state.deliveryId = data.delivery_id;
    addTimeline("Delivery intake", `${data.delivery_id} from ${data.source_agent}`);
    switchTab("delivery");
    loadDelivery();
    toast("Delivery received");
  },
  "delivery.verify": async () => {
    if (!state.deliveryId) return toast("Intake a delivery first");
    toast("Verifying (running real tests)…");
    const data = await api("/api/deliveries/verify", { method: "POST", body: { id: state.deliveryId } }).then((r) => r.data);
    addTimeline(`Delivery verify: ${data.passed ? "PASSED" : "NOT ACCEPTED"}`, `rec=${data.recommendation} • real_usage=${data.real_usage_result}`, data.passed ? "passed" : "failed");
    loadDelivery();
    toast(data.recommendation);
  },
  "delivery.accept": async () => {
    if (!state.deliveryId) return toast("Intake a delivery first");
    const data = await api("/api/deliveries/accept", { method: "POST", body: { id: state.deliveryId } }).then((r) => r.data);
    if (data.error) return toast(data.error);
    addTimeline("Delivery accepted", state.deliveryId, "passed");
    loadDelivery();
    toast("Accepted");
  },
  "real_usage.run": async () => {
    const data = await api("/api/real-usage/run", { method: "POST", body: { scenario: { scenario_id: "demo", steps: [
      { type: "api", action: "GET /api/health", expect: { status_code: 200, body_contains: ["ok"] } },
      { type: "api", action: "GET /api/scheduler/runs", expect: { status_code: 200 } },
    ] } } }).then((r) => r.data);
    addTimeline(`Real usage: ${data.result.status}`, `usable=${data.result.usable_for_real_work}`, data.result.status === "passed" ? "passed" : "failed");
    toast(`Real usage: ${data.result.status}`);
  },
  "self.gaps.detect": async () => {
    const { data } = await api("/api/self/gaps/detect", { method: "POST" });
    if (data.gaps[0]) state.gapId = data.gaps[0].gap_id;
    addTimeline("Capability gaps detected", `${data.gaps.length} gap(s)`);
    switchTab("selfupgrade");
    loadSelfUpgrade();
    toast(`${data.gaps.length} gap(s) found`);
  },
  "self.research.run": async () => {
    if (!state.gapId) { await handlers["self.gaps.detect"](); }
    const { data } = await api("/api/self/research/run", { method: "POST", body: { gap_id: state.gapId } });
    addTimeline("Self research", `status=${data.report.honest_status} • ${data.report.queries.length} queries`, data.report.honest_status === "ready" ? "passed" : "");
    toast(`Research: ${data.report.honest_status}`);
  },
  "self.github.search": async () => {
    if (!state.gapId) { await handlers["self.gaps.detect"](); }
    // No network here: we score user-provided candidate metadata with the real rubric.
    const candidates = [
      { name: "pdf-parse", license: "MIT", last_updated: "2026-01-15", stars: 5200, has_tests: true, docs_quality: "good", windows_support: true, macos_support: true },
      { name: "sketchy-pdf", license: "unknown", last_updated: "2021-02-01", stars: 40, has_install_script: true, runs_shell: true, docs_quality: "poor" },
    ];
    const data = await api("/api/self/github/search", { method: "POST", body: { gap_id: state.gapId, candidates } }).then((r) => r.data);
    addTimeline("GitHub scout", `top=${data.top_recommendation || "—"} • manual_review=${data.manual_review_required}`);
    switchTab("selfupgrade");
    loadSelfUpgrade();
    toast(`Scored ${data.candidates.length} candidates`);
  },
  "self.sandbox.install": async () => {
    const sb = await api("/api/self/sandbox/create", { method: "POST", body: {} }).then((r) => r.data);
    const manifest = { name: "candidate-lib", version: "1.0.0", license: "MIT", scripts: { postinstall: "node build.js" }, dependencies: { left: "1.0.0" } };
    const data = await api("/api/self/sandbox/install", { method: "POST", body: { sandbox_id: sb.sandbox_id, manifest } }).then((r) => r.data);
    addTimeline("Sandbox install", `${data.install_result} • risk ${data.inspection.risk_level}`, "failed");
    if (data.requires_permission) { switchTab("permissions"); loadPermissions(); }
    toast(data.requires_permission ? "Install needs approval" : data.install_result);
  },
  "self.upgrade.delegate": async () => {
    if (!state.proposalId) await ensureProposal();
    const data = await api("/api/self/upgrade/delegate", { method: "POST", body: { proposal_id: state.proposalId, agent: "codex" } }).then((r) => r.data);
    if (data.requires_permission) { addTimeline("Delegate upgrade", "permission required", ""); switchTab("permissions"); loadPermissions(); }
    else addTimeline("Delegate upgrade", "prompt generated");
    toast(data.requires_permission ? "Delegation needs approval" : "Prompt generated");
  },
  "self.upgrade.apply": async () => {
    if (!state.proposalId) await ensureProposal();
    const data = await api("/api/self/upgrade/apply", { method: "POST", body: { proposal_id: state.proposalId } }).then((r) => r.data);
    addTimeline("Apply upgrade", data.requires_permission ? "permission required (critical)" : data.status, "");
    if (data.requires_permission) { switchTab("permissions"); loadPermissions(); }
    loadSelfUpgrade();
    toast(data.requires_permission ? "Apply needs approval" : data.status);
  },
  "self.upgrade.rollback": async () => {
    if (!state.proposalId) return toast("No proposal to roll back");
    const data = await api("/api/self/upgrade/rollback", { method: "POST", body: { proposal_id: state.proposalId } }).then((r) => r.data);
    addTimeline("Rollback", data.status, "passed");
    loadSelfUpgrade();
    toast(data.status);
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

async function loadMemory(q = "") {
  const data = await api(`/api/memory/search?q=${encodeURIComponent(q)}`).then((r) => r.data);
  const box = $("#memory_list");
  if (!data.results || !data.results.length) {
    box.innerHTML = `<p class="hint">No memory entries${q ? ` matching "${q}"` : ""}.</p>`;
    return;
  }
  box.innerHTML =
    `<p class="hint">${data.matched} of ${data.total} entries${q ? ` matching "${q}"` : ""}</p>` +
    data.results
      .map((e) => `<div class="perm" style="border-color:var(--border)"><b>${e.kind}</b> <span class="hint">${e.id}</span><div>${e.text}</div><div class="hint">tags: ${(e.tags || []).join(", ") || "—"}</div></div>`)
      .join("");
}

async function loadDevices() {
  const { data } = await api("/api/devices");
  $("#devices_self").innerHTML = `
    <div class="stat"><b>${data.self.platform}</b><span>${data.self.device_name}</span></div>
    <div class="stat"><b>${data.self.ip}:${data.self.port}</b><span>this node</span></div>
    <div class="stat"><b>${data.peers.length}</b><span>peers</span></div>`;
  const box = $("#devices_list");
  if (!data.peers.length) {
    box.innerHTML = `<p class="hint">No peers discovered yet. Run Discover Devices on each machine on the same Wi-Fi.</p>`;
    return;
  }
  box.innerHTML = data.peers
    .map((p) => `<div class="perm" style="border-color:var(--border)"><b>${p.device_name}</b> <span class="badge ${p.trusted ? "connected" : "permission_required"}">${p.trusted ? "trusted" : "untrusted"}</span><div class="hint">${p.platform} · ${p.ip}:${p.port} · ${p.node_id}</div><div class="hint">capabilities: ${(p.capabilities || []).join(", ")}</div></div>`)
    .join("");
}

async function loadGestures() {
  const { data } = await api("/api/gestures");
  const tbody = $("#gesture_table tbody");
  tbody.innerHTML = "";
  for (const m of data.mappings) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${m.gesture_name}</td><td>${m.action_id}</td>
      <td><span class="badge ${m.risk_level === "low" ? "connected" : m.risk_level === "medium" ? "backend_missing" : "fake_or_unmapped"}">${m.risk_level}</span></td>
      <td>${m.requires_confirmation ? "yes" : "no"}</td><td>${m.min_confidence}</td><td>${m.enabled ? "✓" : "✕"}</td>`;
    tbody.appendChild(tr);
  }
}

async function loadVision() {
  const { data } = await api("/api/vision/status");
  const s = data.status;
  $("#vision_state").textContent = s.active ? "running" : "idle";
  $("#vision_frames").textContent = s.frames_seen;
  $("#vision_latest").textContent = s.latest_gesture ? s.latest_gesture.gesture_id : "—";
  const ev = await api("/api/vision/events").then((r) => r.data.events || []);
  $("#gesture_timeline").textContent = ev
    .slice()
    .reverse()
    .map((e) => `${e.gesture_id} → ${e.action_id || "—"} | ${e.executed ? "executed" : "not-exec"} | ${e.verification_result}`)
    .join("\n") || "(no gesture decisions yet)";
}

async function loadScheduler() {
  const tasks = await api("/api/scheduler/tasks").then((r) => r.data.tasks || []);
  const tt = $("#sched_tasks_table tbody");
  tt.innerHTML = tasks
    .map((t) => `<tr><td>${t.name}</td><td>${t.task_type}</td><td>${t.schedule_type}${t.interval_seconds ? " " + t.interval_seconds + "s" : ""}${t.cron_expr ? " " + t.cron_expr : ""}</td><td>${t.next_run_at || "—"}</td><td>${t.last_run_at || "—"}</td><td>${t.enabled ? "✓" : "✕"}</td></tr>`)
    .join("") || `<tr><td colspan="6" class="hint">No scheduled tasks yet.</td></tr>`;
  const runs = await api("/api/scheduler/runs").then((r) => r.data.runs || []);
  const rt = $("#sched_runs_table tbody");
  rt.innerHTML = runs
    .map((r) => `<tr><td>${r.id}</td><td>${r.scheduled_task_id}</td><td><span class="badge ${r.status === "completed" ? "connected" : r.status === "pending_approval" ? "permission_required" : "fake_or_unmapped"}">${r.status}</span></td><td>${r.verification_result || "—"}</td><td>${r.finished_at ? r.finished_at.slice(11, 19) : "—"}</td></tr>`)
    .join("") || `<tr><td colspan="5" class="hint">No runs yet.</td></tr>`;
}

async function loadDelivery() {
  const list = await api("/api/deliveries").then((r) => r.data.deliveries || []);
  const box = $("#delivery_list");
  if (!list.length) {
    box.innerHTML = `<p class="hint">No deliveries yet. Intake a Codex/Claude delivery to begin verification.</p>`;
    return;
  }
  box.innerHTML = list
    .map((d) => {
      const v = d.verification;
      const checks = v ? v.checks.map((c) => `<div class="hint">${c.status === "passed" ? "✅" : c.status === "failed" ? "❌" : "⏳"} ${c.name}: ${c.status}</div>`).join("") : `<div class="hint">not verified yet</div>`;
      return `<div class="perm" style="border-color:var(--border)"><b>${d.delivery_id}</b> <span class="badge ${d.status.includes("accept") || d.status === "verified" ? "connected" : d.status === "rejected" ? "fake_or_unmapped" : "backend_missing"}">${d.status}</span>
        <div class="hint">source: ${d.source_agent} · ${d.source_type} · req: ${d.requirement_contract_id || "—"}</div>
        ${checks}
        ${v ? `<div class="hint">recommendation: <b>${v.recommendation}</b>${v.human_approval_required ? " · human approval required" : ""}</div>` : ""}</div>`;
    })
    .join("");
}

async function ensureProposal() {
  if (!state.gapId) await handlers["self.gaps.detect"]();
  const data = await api("/api/self/upgrade/proposal", { method: "POST", body: {
    gap_id: state.gapId,
    title: "Self-upgrade demo",
    user_goal: "Add the capability described by the selected gap",
    must_have: ["new action_id", "backend API", "tests", "real usage scenario"],
    risk_level: "high",
  } }).then((r) => r.data);
  state.proposalId = data.proposal.id;
  addTimeline("Upgrade proposal created", data.proposal.id);
}

async function loadSelfUpgrade() {
  const gaps = await api("/api/self/gaps").then((r) => r.data.gaps || []);
  $("#gaps_list").innerHTML = gaps.length
    ? gaps.map((g) => `<div class="perm" style="border-color:var(--border)"><b>${g.title}</b> <span class="badge ${g.priority === "high" ? "fake_or_unmapped" : "backend_missing"}">${g.priority}</span><div class="hint">source: ${g.source} · ${g.gap_id} · ${g.status}</div></div>`).join("")
    : `<p class="hint">No gaps yet. Click Detect Capability Gaps.</p>`;
  const cands = await api("/api/self/candidates").then((r) => r.data.candidates || []);
  $("#candidates_table tbody").innerHTML = cands.length
    ? cands.map((c) => `<tr><td>${c.name}</td><td>${c.license || "unknown"}</td><td>${c.score}</td><td><span class="badge ${c.risk_level === "low" ? "connected" : c.risk_level === "medium" ? "backend_missing" : "fake_or_unmapped"}">${c.risk_level}</span></td><td>${c.recommendation}</td></tr>`).join("")
    : `<tr><td colspan="5" class="hint">No candidates scored yet.</td></tr>`;
  const props = await api("/api/self/upgrade/proposals").then((r) => r.data.proposals || []);
  $("#proposals_list").innerHTML = props.length
    ? props.map((p) => `<div class="perm" style="border-color:var(--border)"><b>${p.title}</b> <span class="badge ${p.status.includes("verified") || p.status.includes("applied") ? "connected" : p.status.includes("rolled") ? "fake_or_unmapped" : "backend_missing"}">${p.status}</span><div class="hint">risk: ${p.risk_level} · ${p.id}</div><div class="hint">rollback: ${(p.rollback_plan || []).join("; ")}</div></div>`).join("")
    : `<p class="hint">No upgrade proposals yet.</p>`;
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
