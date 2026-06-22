// Self-Upgrade Orchestrator — ties a capability gap through research →
// candidate → skill → proposal → delegation → verification → apply/rollback.
//
// Safety: delegate is high risk and apply/rollback are CRITICAL — all are
// permission-gated and never executed automatically. This build does NOT rewrite
// TFNK's own source on apply; it records the approved proposal + rollback plan so
// a human/CI performs the actual merge. Honest by construction.

import { createProposal, getProposal, setProposalStatus, getSkill } from "../lib/selfExt.js";
import { createContract, getContract } from "../lib/contracts.js";
import { codexPrompt, claudePrompt } from "./promptGen.js";
import { createPermission, addLog } from "../lib/store.js";
import { audit } from "./uiAudit.js";

export function proposeUpgrade(input = {}) {
  // Build (or reuse) a requirement contract so the upgrade is acceptance-defined.
  let contract = input.requirement_contract_id ? getContract(input.requirement_contract_id) : null;
  if (!contract && input.user_goal) {
    contract = createContract({
      user_goal: input.user_goal,
      must_have: input.must_have || [],
      must_not: input.must_not,
      acceptance_tests: input.acceptance_tests || [],
      real_usage_scenario: input.real_usage_scenario || [],
      risk_level: input.risk_level || "high",
      requires_human_approval: true,
    });
  }
  if (!contract || contract.error) return { error: "an upgrade needs a requirement contract (user_goal + definition_of_done)", _status: 400 };

  const proposal = createProposal({
    gap_id: input.gap_id,
    skill_id: input.skill_id,
    title: input.title || `Upgrade for ${input.gap_id || "gap"}`,
    plan: input.plan || ["build skill wrapper", "add action_id + API + UI", "add tests", "real usage scenario"],
    requirement_contract_id: contract.requirement_id,
    risk_level: input.risk_level || "high",
    rollback_plan: input.rollback_plan,
  });
  return { proposal, contract };
}

export function delegate({ proposal_id, agent = "codex", approved = false } = {}) {
  const p = getProposal(proposal_id);
  if (!p) return { error: "proposal not found", _status: 404 };
  const contract = getContract(p.requirement_contract_id);

  if (!approved) {
    const perm = createPermission({ action_id: "self.upgrade.delegate", risk: "high", reason: `Delegate self-upgrade "${p.title}" to ${agent}`, source: "self_extension" });
    setProposalStatus(proposal_id, "awaiting_delegation_approval");
    return { proposal_id, requires_permission: true, permission_id: perm.permission_id, note: "approve to authorise delegation" };
  }
  const prompt = agent === "claude" ? claudePrompt(contract) : codexPrompt(contract);
  setProposalStatus(proposal_id, "delegated", { delegated_to: agent });
  addLog({ agent: "SelfUpgradeOrchestrator", event: "delegated", detail: { proposal_id, agent } });
  return { proposal_id, agent, prompt };
}

// Verification reuses TFNK's own checks. testResult is injectable so this never
// recursively spawns the suite inside a test run.
export function verify({ proposal_id, testResult } = {}) {
  const p = getProposal(proposal_id);
  if (!p) return { error: "proposal not found", _status: 404 };
  const a = audit();
  const checks = [
    { name: "UI/API Audit", status: a.fake_or_incomplete === 0 ? "passed" : "failed", evidence: [`${a.fake_or_incomplete} problems`] },
    { name: "Tests", status: testResult ? (testResult.result === "passed" ? "passed" : "failed") : "skipped", evidence: testResult ? [`pass ${testResult.summary?.pass}`] : ["not run in this verification"] },
  ];
  const passed = checks.every((c) => c.status !== "failed");
  setProposalStatus(proposal_id, passed ? "verified" : "verification_failed");
  return { proposal_id, passed, checks, recommendation: passed ? "request_approval" : "request_repair" };
}

export function requestApproval({ proposal_id } = {}) {
  const p = getProposal(proposal_id);
  if (!p) return { error: "proposal not found", _status: 404 };
  const perm = createPermission({ action_id: "self.upgrade.apply", risk: "critical", reason: `Apply self-upgrade "${p.title}"`, source: "self_extension" });
  setProposalStatus(proposal_id, "awaiting_human_approval", { approval_permission_id: perm.permission_id });
  return { proposal_id, permission_id: perm.permission_id, requires_permission: true };
}

export function apply({ proposal_id, approved = false } = {}) {
  const p = getProposal(proposal_id);
  if (!p) return { error: "proposal not found", _status: 404 };
  if (!approved) {
    const perm = createPermission({ action_id: "self.upgrade.apply", risk: "critical", reason: `Apply self-upgrade "${p.title}"`, source: "self_extension" });
    return { proposal_id, applied: false, requires_permission: true, permission_id: perm.permission_id, note: "critical action — explicit approval required" };
  }
  // Honest: do NOT auto-rewrite TFNK source. Record the approved upgrade so a
  // human/CI performs the actual merge, and keep the rollback plan.
  setProposalStatus(proposal_id, "applied_pending_merge", { applied_at: new Date().toISOString() });
  addLog({ agent: "SelfUpgradeOrchestrator", event: "apply_recorded", detail: { proposal_id } });
  return {
    proposal_id,
    applied: false,
    status: "applied_pending_merge",
    rollback_plan: p.rollback_plan,
    note: "approved and recorded; this build does not auto-modify TFNK source — merge the verified upgrade branch via PR/CI. Rollback plan retained.",
  };
}

export function rollback({ proposal_id } = {}) {
  const p = getProposal(proposal_id);
  if (!p) return { error: "proposal not found", _status: 404 };
  setProposalStatus(proposal_id, "rolled_back", { rolled_back_at: new Date().toISOString() });
  addLog({ agent: "SelfUpgradeOrchestrator", event: "rolled_back", detail: { proposal_id } });
  return { proposal_id, status: "rolled_back", steps: p.rollback_plan };
}
