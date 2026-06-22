import { test } from "node:test";
import assert from "node:assert/strict";

import { classify } from "../backend/agents/intent.js";
import { plan } from "../backend/agents/planner.js";
import { audit } from "../backend/agents/uiAudit.js";
import { verify } from "../backend/agents/verifier.js";
import { repair } from "../backend/agents/repair.js";
import { runToCompletionSync, getStatus } from "../backend/loop.js";
import { _resetForTests } from "../backend/lib/store.js";

test("intent classifier detects ui_audit and risk", () => {
  const r = classify("Audit and repair fake UI in TFNK");
  assert.equal(r.task_type, "ui_audit");
  assert.ok(["low", "medium", "high"].includes(r.risk_level));
  assert.ok(r.success_criteria.length > 0);
});

test("intent classifier escalates destructive tasks to high risk", () => {
  const r = classify("delete the backend routes folder");
  assert.equal(r.risk_level, "high");
  assert.equal(r.needs_permission, true);
});

test("planner produces steps that all carry a verification_method", () => {
  const p = plan(classify("audit fake ui"));
  assert.ok(p.steps.length > 0);
  for (const s of p.steps) {
    assert.ok(s.verification_method && s.verification_method.length > 0, `step ${s.name} missing verification`);
  }
});

test("ui audit scans real frontend and classifies every element", () => {
  const r = audit();
  assert.ok(r.total_elements > 0, "should find interactive elements");
  assert.equal(r.connected + r.client_only + r.pending + r.fake_or_incomplete, r.total_elements);
  for (const item of r.items) {
    assert.ok(item.status, "each item has a status");
  }
});

test("ui audit reports zero genuine problems on a clean foundation", () => {
  const r = audit();
  assert.equal(r.fake_or_incomplete, 0, "no genuine fakes should remain");
});

test("ui audit marks declared future-phase buttons as pending_phase, not fake", () => {
  const r = audit();
  const wf = r.items.find((i) => i.action_id === "workflow.run");
  assert.ok(wf, "workflow button should be found");
  assert.equal(wf.status, "pending_phase");
});

test("repair gates source edits behind a permission when given problems", () => {
  const fakeReport = {
    items: [
      { ui_id: "btn_x", action_id: "x", file: "frontend/index.html", status: "missing_backend", required_fix: "add route" },
    ],
  };
  const r = repair({ report: fakeReport });
  assert.equal(r.requires_permission, true);
  assert.ok(r.permission_id);
});

test("repair reports nothing to do on a clean audit", () => {
  const r = repair({});
  assert.equal(r.requires_permission, false);
  assert.equal(r.repair_result, "passed");
});

test("verifier refuses to pass without evidence", () => {
  const r = verify({ task_type: "unknown", claim: {} });
  assert.equal(r.verified, false);
  assert.ok(r.failed_checks.length > 0);
});

test("loop state machine runs to a terminal state", () => {
  _resetForTests();
  const status = runToCompletionSync({ max_iterations: 3 });
  assert.ok(["completed", "stopped"].includes(status.status));
  assert.ok(status.iteration >= 1);
  assert.equal(getStatus().status, status.status);
});
