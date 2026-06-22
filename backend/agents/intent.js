// Intent Classifier — turns a free-text goal into a structured task.
// Deterministic and rule-based so it runs with zero external dependencies.
// (When an LLM is wired in later, it can replace classify() while keeping the
// same output contract.)

const RULES = [
  { type: "ui_audit", kw: ["audit", "fake", "fake ui", "假", "按鈕", "button", "ui scan"] },
  { type: "backend_fix", kw: ["api", "route", "backend", "endpoint", "補"] },
  { type: "loop_run", kw: ["loop", "循環", "repeat", "iterate"] },
  { type: "app_build", kw: ["build app", "create app", "scaffold", "建立"] },
  { type: "research", kw: ["search", "research", "find out", "上網", "查"] },
  { type: "computer_use", kw: ["click", "screenshot", "type", "操作", "畫面"] },
  { type: "testing", kw: ["test", "tests", "qa", "測試", "verify all"] },
  { type: "settings", kw: ["setting", "config", "設定"] },
];

const DESTRUCTIVE = ["delete", "remove", "rm ", "drop", "overwrite", "刪除", "覆蓋", "deploy", "terminal"];

export function classify(input) {
  const text = String(input || "").toLowerCase();
  let task_type = "unknown";
  for (const rule of RULES) {
    if (rule.kw.some((k) => text.includes(k))) {
      task_type = rule.type;
      break;
    }
  }

  const destructive = DESTRUCTIVE.some((k) => text.includes(k));
  let risk_level = "low";
  if (task_type === "backend_fix" || task_type === "loop_run") risk_level = "medium";
  if (task_type === "computer_use") risk_level = "medium";
  if (destructive) risk_level = "high";

  let target = "unknown";
  if (text.includes("backend") || text.includes("api")) target = "backend";
  else if (text.includes("frontend") || text.includes("ui") || text.includes("button")) target = "frontend";
  else if (text.includes("loop")) target = "loop";
  else if (text.includes("setting") || text.includes("設定")) target = "settings";

  const required_tools = [];
  if (task_type === "ui_audit") required_tools.push("file_scanner", "registry_reader");
  if (task_type === "backend_fix") required_tools.push("api_checker", "test_runner");
  if (task_type === "loop_run") required_tools.push("loop_engine");
  if (task_type === "computer_use") required_tools.push("screenshot", "mouse_keyboard");
  if (task_type === "testing") required_tools.push("test_runner");

  return {
    goal: String(input || "").trim(),
    task_type,
    target,
    required_context: task_type === "ui_audit" ? ["action_registry", "ui_control_map"] : [],
    required_tools,
    risk_level,
    needs_permission: risk_level === "high" || risk_level === "critical",
    success_criteria:
      task_type === "ui_audit"
        ? ["every interactive element has an action_id", "no unmapped elements"]
        : task_type === "loop_run"
          ? ["loop reaches completed or stopped state"]
          : ["task verified with evidence"],
    possible_failure_points: destructive
      ? ["destructive operation requires approval"]
      : ["missing backend route", "failing test"],
  };
}
