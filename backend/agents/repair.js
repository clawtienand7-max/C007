// Repair Agent — proposes the smallest safe, rollback-able fix. High/critical
// risk fixes never auto-apply; they emit a permission request instead.

import { createPermission, addLog } from "../lib/store.js";
import { audit } from "./uiAudit.js";

// What the foundation is allowed to repair automatically vs. what must always
// be gated. Mirrors the blueprint's "可自動修 / 不應自動修" table.
const SAFE_ROOT_CAUSES = new Set([
  "missing_action_id",
  "missing_test",
  "missing_backend",
  "broken_ui_handler",
  "config_default",
]);

export function repair({ session_id, dry_run = true } = {}) {
  const report = audit();
  const broken = report.items.filter((i) => i.status !== "connected");

  if (broken.length === 0) {
    return {
      root_cause: "none",
      fix_plan: [],
      risk_level: "low",
      requires_permission: false,
      files_to_change: [],
      repair_result: "passed",
      test_result: "nothing to repair",
      notes: ["audit found no incomplete elements"],
    };
  }

  const fix_plan = broken.map((b) => ({
    ui_id: b.ui_id,
    root_cause: b.status,
    fix: b.required_fix,
    safe: SAFE_ROOT_CAUSES.has(b.status),
  }));

  const anyUnsafe = fix_plan.some((f) => !f.safe);
  const files_to_change = [...new Set(broken.map((b) => b.file))];
  // Repair that edits source files is treated as high risk in the foundation:
  // we surface the plan and require approval rather than silently writing code.
  const risk_level = anyUnsafe ? "critical" : "high";
  const requires_permission = true;

  const permission = createPermission({
    action_id: "agent.repair",
    risk: risk_level,
    reason: `Repair Agent wants to fix ${broken.length} incomplete UI element(s)`,
    files: files_to_change,
  });

  addLog({
    session_id,
    agent: "RepairAgent",
    event: "repair_proposed",
    detail: { broken: broken.length, permission_id: permission.permission_id },
  });

  return {
    root_cause: broken.map((b) => b.status).join(", "),
    fix_plan,
    risk_level,
    requires_permission,
    permission_id: permission.permission_id,
    files_to_change,
    repair_result: dry_run ? "blocked" : "blocked",
    test_result: "not run — awaiting permission",
    notes: [
      "Foundation policy: source edits require explicit approval.",
      `Approve permission ${permission.permission_id} to authorise the fix.`,
    ],
  };
}
