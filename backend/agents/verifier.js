// Verification Agent — proves a task actually succeeded with evidence.
// Rule: no evidence => verified=false. Seeing the word "success" is not proof.

import { loop } from "../lib/store.js";
import { audit } from "./uiAudit.js";

export function verify({ task_type, target, claim } = {}) {
  const evidence = [];
  const failed_checks = [];
  let verified = false;
  let method = "";

  switch (task_type) {
    case "ui_audit": {
      method = "re-run UI audit and check for unmapped elements";
      const report = audit();
      evidence.push(`scanned ${report.total_elements} elements`);
      evidence.push(`${report.connected} connected, ${report.fake_or_incomplete} incomplete`);
      const unmapped = (report.by_status.fake_or_unmapped || 0) + (report.by_status.missing_action_id || 0);
      if (unmapped === 0) verified = true;
      else failed_checks.push(`${unmapped} unmapped/unbound elements remain`);
      break;
    }
    case "loop_run": {
      method = "inspect loop state machine transitions";
      evidence.push(`loop status=${loop.status}`, `iterations=${loop.iteration}`);
      if (["completed", "stopped"].includes(loop.status)) verified = true;
      else failed_checks.push(`loop status is "${loop.status}", expected completed/stopped`);
      break;
    }
    case "settings": {
      method = "write-then-read-back consistency check";
      if (claim && claim.written === claim.readBack) {
        verified = true;
        evidence.push(`value persisted: ${JSON.stringify(claim.written)}`);
      } else {
        failed_checks.push("written value does not match read-back value");
      }
      break;
    }
    default: {
      method = "evidence presence check";
      if (claim && Array.isArray(claim.evidence) && claim.evidence.length > 0) {
        verified = true;
        evidence.push(...claim.evidence);
      } else {
        failed_checks.push("no evidence supplied for the claim");
      }
    }
  }

  return {
    verified,
    method,
    evidence,
    failed_checks,
    next_required_fix: verified ? "" : failed_checks[0] || "investigate failure",
  };
}
