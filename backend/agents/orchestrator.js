// Master Orchestrator — runs a goal end-to-end autonomously:
// understand -> plan -> execute every step -> verify -> report.
// Honours the safety contract: if any step needs permission, it stops before
// that step and reports rather than escalating on its own.

import { createSession, addLog } from "../lib/store.js";
import { classify } from "./intent.js";
import { plan as makePlan } from "./planner.js";
import { executeStep } from "./executor.js";
import { verify } from "./verifier.js";
import { searchMemory } from "../lib/memory.js";

export function runAutonomous({ goal } = {}) {
  const session = createSession({ goal, mode: "safe_autonomy" });
  const intent = classify(goal || "");
  session.intent = intent;
  session.risk_level = intent.risk_level;

  // Context retrieval from project memory (rules relevant to this task).
  const context = searchMemory({ q: intent.task_type, limit: 5 }).results.map((m) => m.text);

  const planned = makePlan(intent);
  session.plan = planned;

  const executed = [];
  let stoppedForPermission = null;
  for (const step of planned.steps) {
    if (step.requires_permission) {
      stoppedForPermission = step;
      addLog({ session_id: session.session_id, agent: "MasterOrchestrator", event: "halt_for_permission", detail: { step: step.name } });
      break;
    }
    executed.push(executeStep(step, session.session_id));
  }

  const verification = verify({ task_type: intent.task_type });
  session.status = stoppedForPermission ? "awaiting_permission" : verification.verified ? "completed" : "needs_attention";
  session.progress = Math.round((executed.length / planned.steps.length) * 100);

  const report = generateReport({ goal, intent, context, planned, executed, verification, stoppedForPermission });
  addLog({ session_id: session.session_id, agent: "ReportGenerator", event: "report", detail: { status: session.status } });

  return { session, intent, context, plan: planned, steps: executed, verification, report };
}

// Report Generator — produces an honest, non-exaggerated delivery report.
export function generateReport({ goal, intent, context, planned, executed, verification, stoppedForPermission }) {
  const done = executed.filter((s) => s.verification === "passed").map((s) => `- ${s.name} (${s.tool})`);
  const failed = executed.filter((s) => s.verification === "failed").map((s) => `- ${s.name} (${s.tool})`);
  const blocked = stoppedForPermission ? [`- ${stoppedForPermission.name} — requires permission`] : [];

  const lines = [];
  lines.push(`# 任務結果 / Task Result`);
  lines.push(`**Goal:** ${goal || "(none)"}  `);
  lines.push(`**Intent:** ${intent.task_type} · risk ${intent.risk_level}`);
  if (context.length) lines.push(`\n## 參考記憶 / Context\n${context.map((c) => `- ${c}`).join("\n")}`);
  lines.push(`\n## 已完成 / Completed`);
  lines.push(done.length ? done.join("\n") : "- (none)");
  lines.push(`\n## 測試證據 / Evidence`);
  lines.push(`- 驗證方式: ${verification.method}`);
  lines.push(`- 結果: ${verification.verified ? "verified ✓" : "尚未驗證 (not verified)"}`);
  if (verification.evidence.length) lines.push(verification.evidence.map((e) => `- ${e}`).join("\n"));
  lines.push(`\n## 未完成 / 被阻擋 (Blocked)`);
  lines.push([...failed, ...blocked].length ? [...failed, ...blocked].join("\n") : "- (none)");
  lines.push(`\n## 下一步建議 / Next steps`);
  lines.push(
    stoppedForPermission
      ? "- 批准 permission 以繼續被阻擋的步驟。"
      : verification.verified
        ? "- 任務通過驗證，可合併或進入下一階段。"
        : `- ${verification.next_required_fix}`,
  );

  return {
    markdown: lines.join("\n"),
    completed: done.length,
    failed: failed.length,
    blocked: blocked.length,
    verified: verification.verified,
  };
}
