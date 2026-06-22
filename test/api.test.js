import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import { createApp } from "../backend/server.js";

let server;
let base;

before(async () => {
  server = createApp();
  await new Promise((r) => server.listen(0, r));
  base = `http://localhost:${server.address().port}`;
});

after(() => server && server.close());

const get = (p) => fetch(base + p).then((r) => r.json());
const post = (p, body) =>
  fetch(base + p, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then((r) => r.json());

test("test_health: /api/health is live", async () => {
  const r = await get("/api/health");
  assert.equal(r.ok, true);
  assert.equal(r.version, "0.7.0");
});

test("/api/actions annotates each action with a live status", async () => {
  const r = await get("/api/actions");
  assert.ok(Array.isArray(r.actions));
  const start = r.actions.find((a) => a.id === "loop.start");
  assert.equal(start.status, "connected");
  const shot = r.actions.find((a) => a.id === "computer.screenshot");
  assert.equal(shot.status, "connected");
  const wf = r.actions.find((a) => a.id === "workflow.run");
  assert.equal(wf.status, "backend_missing");
});

test("/api/ui-control-map returns annotated screens", async () => {
  const r = await get("/api/ui-control-map");
  assert.ok(r.screens.length > 0);
  assert.ok(r.screens[0].elements[0].status);
});

test("test_agent_session: session creation classifies intent", async () => {
  const r = await post("/api/agent/session", { goal: "audit fake ui" });
  assert.ok(r.session.session_id);
  assert.equal(r.intent.task_type, "ui_audit");
});

test("test_agent_plan: plan generation returns verifiable steps", async () => {
  const r = await post("/api/agent/plan", { goal: "audit fake ui" });
  assert.ok(r.plan.steps.length > 0);
  assert.ok(r.plan.steps.every((s) => s.verification_method));
});

test("test_step_run: running an audit step does real work", async () => {
  const r = await post("/api/agent/step/run", {
    step: { name: "scan", tool: "file_scanner", verification_method: "count" },
  });
  assert.ok(r.step.output.total_elements >= 0);
  assert.ok(["passed", "failed"].includes(r.step.verification));
});

test("test_ui_audit: audit endpoint reports elements", async () => {
  const r = await post("/api/agent/audit", {});
  assert.ok(r.report.total_elements > 0);
});

test("test_verify: verify rejects claims without evidence", async () => {
  const r = await post("/api/agent/verify", { task_type: "unknown", claim: {} });
  assert.equal(r.verified, false);
});

test("test_loop_start / test_loop_status / test_loop_stop: loop lifecycle", async () => {
  const started = await post("/api/loop/run", { max_iterations: 10 });
  assert.equal(started.ok, true);
  assert.equal(started.status.status, "running");

  const status = await get("/api/loop/status");
  assert.ok(["running", "completed"].includes(status.status.status));

  const stopped = await post("/api/loop/stop", {});
  // may already be completed if fast; either way it is terminal
  assert.ok(["completed", "stopped"].includes((await get("/api/loop/status")).status.status));
  assert.ok(stopped.ok === true || stopped.error);
});

test("test_emergency_stop: emergency stop engages and blocks new runs", async () => {
  await post("/api/emergency-stop", {});
  const blocked = await post("/api/loop/run", {});
  assert.equal(blocked.ok, false);
  await post("/api/loop/clear-emergency", {});
  const ok = await post("/api/loop/run", { max_iterations: 2 });
  assert.equal(ok.ok, true);
  await post("/api/loop/stop", {});
});

test("test_repair: repair reports nothing to do on a clean foundation", async () => {
  const r = await post("/api/agent/repair", {});
  assert.equal(r.requires_permission, false);
  assert.equal(r.repair_result, "passed");
});

test("test_permission_decide: repair with injected problems creates an approvable permission", async () => {
  const report = { items: [{ ui_id: "btn_x", action_id: "x", file: "frontend/index.html", status: "missing_backend", required_fix: "add route" }] };
  const r = await post("/api/agent/repair", { report });
  assert.equal(r.requires_permission, true);
  const perms = await get("/api/permissions");
  assert.ok(perms.permissions.some((p) => p.permission_id === r.permission_id));
  const decided = await post("/api/permissions/decide", { permission_id: r.permission_id, decision: "deny" });
  assert.equal(decided.permission.status, "denied");
});

test("/api/logs returns a trace", async () => {
  const r = await get("/api/logs?limit=10");
  assert.ok(Array.isArray(r.logs));
});

test("test_tests_run: GET /api/tests reports coverage inventory", async () => {
  const r = await get("/api/tests");
  assert.ok(r.coverage.total > 0);
  assert.ok(Array.isArray(r.test_files));
});
