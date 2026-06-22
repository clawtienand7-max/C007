// Delivery Verification System — TFNK is the final acceptance officer for work
// delivered by Codex / Claude / humans. A delivery is a *candidate*, never an
// accomplishment, until it passes: requirement match -> diff safety -> tests ->
// UI/API audit -> real usage. No evidence => not passed. Fake/hardcode => reject.

import { randomUUID } from "node:crypto";
import { addLog } from "../lib/store.js";
import { getContract } from "../lib/contracts.js";
import { audit } from "./uiAudit.js";
import { runTests as defaultRunTests } from "./testCenter.js";
import { runScenario } from "./realUsage.js";
import { repairPrompt } from "./promptGen.js";

const deliveries = new Map();

const FORBIDDEN = [/hardcode/i, /fake\s*success/i, /return\s+true;?\s*\/\/\s*todo/i, /skip.*test/i];

export function intake(input = {}) {
  const id = `delivery_${randomUUID().slice(0, 8)}`;
  const delivery = {
    delivery_id: id,
    source_agent: input.source_agent || "manual",
    source_type: input.source_type || "text",
    task_id: input.task_id || null,
    requirement_contract_id: input.requirement_id || input.requirement_contract_id || null,
    branch: input.branch || null,
    files_changed: input.changed_files || input.files_changed || [],
    diff: input.diff || "",
    report: input.report || "",
    status: "received",
    verification: null,
    received_at: new Date().toISOString(),
  };
  deliveries.set(id, delivery);
  addLog({ agent: "DeliveryIntakeAgent", event: "received", detail: { id, source: delivery.source_agent } });
  return { ...publicView(delivery), next_step: "verify_delivery" };
}

export function listDeliveries() {
  return [...deliveries.values()].map(publicView);
}
export function getDelivery(id) {
  const d = deliveries.get(id);
  return d ? publicView(d) : null;
}
function publicView(d) {
  const { diff, ...rest } = d;
  return { ...rest, diff_present: Boolean(diff) };
}

export async function verify(id, opts = {}) {
  const d = deliveries.get(id);
  if (!d) return { error: "delivery not found", _status: 404 };
  const contract = d.requirement_contract_id ? getContract(d.requirement_contract_id) : null;
  const checks = [];
  const violations = [];

  // 1. Requirement match.
  if (contract) {
    const haystack = `${d.files_changed.join(" ")} ${d.report} ${d.diff}`.toLowerCase();
    const matched = contract.must_have.filter((m) =>
      m.toLowerCase().split(/\s+/).some((w) => w.length > 3 && haystack.includes(w)),
    );
    const status = d.diff || d.report || d.files_changed.length ? (matched.length === contract.must_have.length ? "passed" : "blocked") : "blocked";
    checks.push({ name: "Requirement Match", status, evidence: [`matched ${matched.length}/${contract.must_have.length} must_have items`] });
  } else {
    checks.push({ name: "Requirement Match", status: "blocked", evidence: ["no requirement contract linked"] });
  }

  // 2. Diff safety.
  const hits = FORBIDDEN.filter((re) => re.test(d.diff)).map((re) => re.source);
  if (hits.length) violations.push(...hits.map((h) => `forbidden pattern in diff: ${h}`));
  checks.push({ name: "Diff Safety", status: hits.length ? "failed" : "passed", evidence: hits.length ? hits : ["no forbidden patterns detected"] });

  // 3. Tests (real). Injectable so unit tests don't recursively spawn the suite.
  const testResult = opts.testResult || (opts.skipTests ? null : await (opts.runTestsImpl || defaultRunTests)());
  if (testResult) {
    checks.push({ name: "Tests", status: testResult.result === "passed" ? "passed" : "failed", evidence: [`exit ${testResult.exit_code}`, `pass ${testResult.summary?.pass}/${testResult.summary?.tests}`] });
  } else {
    checks.push({ name: "Tests", status: "skipped", evidence: ["test run skipped for this verification"] });
  }

  // 4. UI/API audit (no fake UI introduced).
  const a = audit();
  checks.push({ name: "UI/API Audit", status: a.fake_or_incomplete === 0 ? "passed" : "failed", evidence: [`${a.connected} connected`, `${a.fake_or_incomplete} problems`] });

  // 5. Real usage.
  let real_usage_result = "skipped";
  if (contract && contract.real_usage_scenario && contract.real_usage_scenario.length) {
    const r = await runScenario(contract.real_usage_scenario, { base_url: opts.base_url, fetchImpl: opts.fetchImpl });
    real_usage_result = r.status;
    checks.push({ name: "Real Usage", status: r.status === "passed" ? "passed" : r.status === "blocked" ? "blocked" : "failed", evidence: r.steps.map((s) => `${s.step}: ${s.status}`) });
  } else {
    checks.push({ name: "Real Usage", status: "blocked", evidence: ["no structured real_usage_scenario to execute"] });
  }

  const hardFail = checks.some((c) => c.status === "failed");
  const passed = !hardFail && violations.length === 0;
  let recommendation = "accept";
  if (violations.length) recommendation = "reject";
  else if (hardFail) recommendation = "request_repair";

  const human_approval_required = Boolean(contract && contract.requires_human_approval) || (contract && contract.risk_level === "high");

  const verification = {
    delivery_id: id,
    requirement_id: d.requirement_contract_id,
    passed,
    checks,
    violations,
    tests_run: testResult ? [testResult.result] : [],
    real_usage_result,
    recommendation,
    human_approval_required,
    summary: passed
      ? `Delivery passed ${checks.filter((c) => c.status === "passed").length}/${checks.length} checks${human_approval_required ? " — awaiting human approval" : ""}`
      : `Delivery not accepted: ${violations.length ? "policy violations" : "failed checks"}`,
    verified_at: new Date().toISOString(),
  };
  d.verification = verification;
  d.status = passed ? (human_approval_required ? "verified_pending_human" : "verified") : recommendation === "reject" ? "rejected" : "needs_repair";
  addLog({ agent: "DeliveryVerificationAgent", event: "verified", detail: { id, passed, recommendation } });
  return verification;
}

export function accept(id, { force = false } = {}) {
  const d = deliveries.get(id);
  if (!d) return { error: "delivery not found", _status: 404 };
  if (!d.verification) return { error: "verify the delivery before accepting", _status: 400 };
  if (!d.verification.passed && !force) return { error: "cannot accept: verification did not pass", recommendation: d.verification.recommendation, _status: 400 };
  d.status = "accepted";
  d.accepted_at = new Date().toISOString();
  addLog({ agent: "AcceptanceAgent", event: "accepted", detail: { id } });
  return { ...publicView(d) };
}

export function reject(id, { reason } = {}) {
  const d = deliveries.get(id);
  if (!d) return { error: "delivery not found", _status: 404 };
  d.status = "rejected";
  d.reject_reason = reason || "rejected by user";
  addLog({ agent: "AcceptanceAgent", event: "rejected", detail: { id } });
  return { ...publicView(d) };
}

export function requestRepair(id) {
  const d = deliveries.get(id);
  if (!d) return { error: "delivery not found", _status: 404 };
  const contract = d.requirement_contract_id ? getContract(d.requirement_contract_id) : null;
  const failed = (d.verification?.checks || []).filter((c) => c.status === "failed");
  const prompt = repairPrompt({ contract, failed_checks: failed, violations: d.verification?.violations || [] });
  d.status = "repair_requested";
  addLog({ agent: "RepairRequestAgent", event: "repair_requested", detail: { id } });
  return { delivery_id: id, status: d.status, repair_prompt: prompt };
}

export function _resetDeliveriesForTests() {
  deliveries.clear();
}
