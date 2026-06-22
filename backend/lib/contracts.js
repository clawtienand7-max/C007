// Requirement Contract store — the engineering acceptance standard TFNK writes
// BEFORE asking Codex/Claude (or itself) to do a task. A contract with no
// definition_of_done is rejected: you may not delegate work you can't accept.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { ROOT } from "./store.js";

const FILE = join(ROOT, "data", "runtime", "contracts.json");
const contracts = new Map();

export function createContract(input = {}) {
  if (!input.user_goal) return { error: "user_goal is required" };
  const must_have = input.must_have || [];
  const dod = input.definition_of_done || must_have;
  if (!dod.length) return { error: "definition_of_done (or must_have) is required — cannot accept what isn't defined" };

  const id = input.requirement_id || `req_${randomUUID().slice(0, 8)}`;
  const contract = {
    requirement_id: id,
    user_goal: input.user_goal,
    must_have,
    must_not: input.must_not || ["不可 hardcode success", "不可只回傳 fake success", "不可移除 Emergency Stop / Safety Center", "不可破壞 Action Registry"],
    acceptance_tests: input.acceptance_tests || [],
    real_usage_scenario: input.real_usage_scenario || [],
    affected_areas: input.affected_areas || [],
    risk_level: input.risk_level || "medium",
    requires_human_approval: input.requires_human_approval ?? (input.risk_level === "high" || input.risk_level === "critical"),
    definition_of_done: dod,
    source_agent: input.source_agent || "manual",
    created_at: new Date().toISOString(),
  };
  contracts.set(id, contract);
  persist();
  return contract;
}

export function getContract(id) {
  return contracts.get(id) || null;
}
export function listContracts() {
  return [...contracts.values()];
}

function persist() {
  try {
    mkdirSync(join(ROOT, "data", "runtime"), { recursive: true });
    writeFileSync(FILE, JSON.stringify(listContracts(), null, 2));
  } catch {
    /* best-effort */
  }
}
export function loadPersistedContracts() {
  try {
    if (existsSync(FILE)) for (const c of JSON.parse(readFileSync(FILE, "utf8"))) contracts.set(c.requirement_id, c);
  } catch {
    /* ignore */
  }
}
export function _resetContractsForTests() {
  contracts.clear();
}
