// Task Planner — turns a classified intent into an executable plan where every
// step carries a verification_method (the blueprint forbids analysis-only steps).

import { nextId } from "../lib/store.js";

function step(name, agent, tool, input, expected, verify, risk = "low", perm = false) {
  return {
    step_id: nextId("step", "step"),
    name,
    agent,
    tool,
    input,
    expected_output: expected,
    verification_method: verify,
    risk_level: risk,
    requires_permission: perm,
  };
}

export function plan(intent) {
  const steps = [];
  const goal = intent.goal || "";

  switch (intent.task_type) {
    case "ui_audit":
      steps.push(
        step("Scan frontend for interactive elements", "UIAuditAgent", "file_scanner", { dir: "frontend" }, { elements: ">=0" }, "count elements found"),
        step("Reconcile against action registry", "UIAuditAgent", "registry_reader", { registry: "action_registry.json" }, { unmapped: 0 }, "classify each element"),
        step("Check backend routes are live", "BackendAgent", "api_checker", { routes: "LIVE_ROUTES" }, { missing: 0 }, "compare against live routes"),
        step("Produce audit report", "UIAuditAgent", "report", {}, { report: "object" }, "report has items array"),
      );
      break;
    case "loop_run":
      steps.push(
        step("Start loop state machine", "ExecutionEngine", "loop_engine", { goal }, { status: "running" }, "status === running", "medium"),
        step("Run iterations with verify", "VerificationEngine", "loop_engine", {}, { iterations: ">0" }, "each iteration verified"),
        step("Reach terminal state", "ExecutionEngine", "loop_engine", {}, { status: "completed|stopped" }, "status in {completed,stopped}", "medium"),
      );
      break;
    case "backend_fix":
      steps.push(
        step("Locate missing route", "BackendAgent", "api_checker", {}, { route: "string" }, "route identified"),
        step("Implement minimal route", "BackendAgent", "code_edit", {}, { implemented: true }, "route returns 2xx", "high", true),
        step("Add test and run", "QATestAgent", "test_runner", {}, { test_result: "passed" }, "test passes"),
      );
      break;
    case "testing":
      steps.push(
        step("Run test suite", "QATestAgent", "test_runner", {}, { passed: true }, "exit code 0"),
        step("Collect report", "QATestAgent", "report", {}, { report: "object" }, "report has results"),
      );
      break;
    default:
      steps.push(
        step("Clarify and analyse goal", "MasterOrchestrator", "intent", { goal }, { understood: true }, "intent.task_type !== unknown"),
        step("Verify outcome", "VerificationEngine", "verifier", {}, { verified: true }, "evidence present"),
      );
  }

  return {
    plan_id: nextId("run", "plan"),
    goal,
    task_type: intent.task_type,
    steps,
    rollback_plan: ["restore previous file versions from git", "stop loop", "deny pending permissions"],
    final_success_criteria: intent.success_criteria,
  };
}
