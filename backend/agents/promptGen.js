// Prompt Generators — turn a Requirement Contract into ready-to-send task
// prompts for Codex or Claude Code, and into a repair request when a delivery
// fails acceptance. Pure functions: deterministic, no side effects.

function bullets(arr) {
  return (arr && arr.length ? arr : ["(none specified)"]).map((x) => `- ${x}`).join("\n");
}

export function codexPrompt(contract) {
  if (!contract) return { error: "contract required" };
  return [
    "# Task",
    "請完成以下 TFNK 工程任務：",
    "",
    "## User Goal",
    contract.user_goal,
    "",
    "## Requirements (必須做到)",
    bullets(contract.must_have),
    "",
    "## Forbidden (不可做)",
    bullets(contract.must_not),
    "",
    "## Expected Files / Areas",
    bullets(contract.affected_areas),
    "",
    "## Acceptance Tests (請新增或修復)",
    bullets(contract.acceptance_tests),
    "",
    "## Real Usage Scenario (交付後 TFNK 會這樣驗收)",
    bullets((contract.real_usage_scenario || []).map((s) => (typeof s === "string" ? s : s.action || JSON.stringify(s)))),
    "",
    "## Delivery Rules",
    "1. 不可只做假 UI。",
    "2. 每個 UI 控制必須接 Action Registry。",
    "3. 每個 action 必須有 backend API。",
    "4. 每個 API 必須有測試。",
    "5. 不可移除 Safety Center、Emergency Stop、LOOP state machine。",
    "6. 請保留清楚 commit / PR 說明。",
    "7. 若無法完成，請列出 blocker，不要假裝完成。",
    "",
    "## Output Expected",
    "- changed files",
    "- tests added",
    "- how to run tests",
    "- known limitations",
    "- verification evidence",
  ].join("\n");
}

export function claudePrompt(contract) {
  if (!contract) return { error: "contract required" };
  return [
    "請在目前 TFNK repo 中完成以下任務。",
    "",
    `目標：${contract.user_goal}`,
    "",
    "請先閱讀：",
    "- data/action_registry.json",
    "- data/ui_control_map.json",
    "- backend/server.js 與相關 routes",
    "- frontend screens",
    "- test files",
    "",
    "必須做到：",
    bullets(contract.must_have),
    "",
    "不可做：",
    bullets(contract.must_not),
    "",
    "請按以下流程工作：",
    "1. 探索相關檔案。",
    "2. 說明目前問題。",
    "3. 修改最小必要檔案。",
    "4. 新增或修復測試。",
    "5. 執行測試。",
    "6. 若測試失敗，修正後重跑。",
    "7. 交付前列出：changed files / tests run / evidence / remaining risks。",
    "",
    "重要規則：",
    "- 不可 hardcode success。",
    "- 不可只修改文字或樣式讓 UI 看似成功。",
    "- 不可跳過測試。",
    "- 不可破壞 Emergency Stop。",
    "- 不可標記完成，除非測試與真實使用場景都可通過。",
  ].join("\n");
}

export function repairPrompt({ contract, failed_checks = [], violations = [] }) {
  return [
    "# Repair Required",
    "你之前交付的任務沒有通過 TFNK 驗收。",
    "",
    "## Original Goal",
    contract ? contract.user_goal : "(no contract)",
    "",
    "## Failed Checks",
    bullets(failed_checks.map((c) => `${c.name}: ${c.status} — ${(c.evidence || []).join("; ")}`)),
    "",
    "## Violations",
    bullets(violations),
    "",
    "## Do Not",
    "- 不可 hardcode success。",
    "- 不可移除測試來讓結果通過。",
    "- 不可跳過 Real Usage Scenario。",
    "- 不可改動與任務無關的大量檔案。",
    "- 不可破壞 Safety Center / Emergency Stop / Action Registry。",
    "",
    "## Must Pass",
    bullets(contract ? contract.acceptance_tests : []),
    "",
    "## Final Delivery Must Include",
    "- changed files",
    "- tests run",
    "- test output",
    "- real usage evidence",
    "- remaining risks",
  ].join("\n");
}
