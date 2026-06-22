import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import { createApp } from "../backend/server.js";
import { _resetMemoryForTests } from "../backend/lib/memory.js";
import { _resetComputerForTests } from "../backend/agents/computerUse.js";

let server;
let base;

before(async () => {
  _resetMemoryForTests();
  _resetComputerForTests();
  server = createApp();
  await new Promise((r) => server.listen(0, r));
  base = `http://localhost:${server.address().port}`;
});
after(() => server && server.close());

const get = (p) => fetch(base + p).then((r) => r.json());
const post = (p, body) =>
  fetch(base + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then((r) => r.json());

test("test_agent_run: autonomous orchestrator runs end-to-end and returns a report", async () => {
  const r = await post("/api/agent/run", { goal: "audit fake ui in tfnk" });
  assert.ok(r.session.session_id);
  assert.ok(r.plan.steps.length > 0);
  assert.ok(r.steps.length > 0, "should execute steps");
  assert.ok(r.report.markdown.includes("任務結果"));
  assert.ok(["completed", "needs_attention", "awaiting_permission"].includes(r.session.status));
});

test("test_memory_write / test_memory_search: memory persists and is searchable", async () => {
  const w = await post("/api/memory/write", { kind: "rule", text: "Always verify with evidence", tags: ["verify"] });
  assert.ok(w.entry.id);
  const s = await get("/api/memory/search?q=evidence");
  assert.ok(s.matched >= 1);
  assert.ok(s.results.some((e) => e.text.includes("evidence")));
});

test("memory seeds the project's iron rules", async () => {
  const s = await get("/api/memory/search?kind=rule");
  assert.ok(s.matched >= 4, "seed rules should be present");
});

test("test_computer_screenshot: virtual screenshot lists the registered surface", async () => {
  const r = await post("/api/computer/screenshot", {});
  assert.ok(r.snapshot.elements.length > 0);
  assert.ok(r.snapshot.surface.includes("virtual"));
});

test("test_computer_click: clicking a connected control performs the real action and verifies", async () => {
  const r = await post("/api/computer/click", { ui_id: "btn_loop_status" });
  assert.equal(r.verification, "passed");
});

test("computer click refuses to click a disabled (future-phase) control", async () => {
  const r = await post("/api/computer/click", { ui_id: "btn_run_workflow" });
  assert.equal(r.verification, "blocked");
});

test("computer click refuses to auto-click a permission-gated control", async () => {
  const r = await post("/api/computer/click", { ui_id: "btn_auto_repair" });
  assert.equal(r.verification, "blocked");
  assert.match(r.reason, /permission/i);
});

test("test_computer_type: write-then-read-back verification", async () => {
  const r = await post("/api/computer/type", { ui_id: "goal_input", text: "hello tfnk" });
  assert.equal(r.verification, "passed");
  assert.equal(r.value, "hello tfnk");
});
