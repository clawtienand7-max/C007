// Test Center — runs the real test suite as a child process and parses the
// TAP-ish summary from Node's built-in runner. This is what proves "每個 API
// 有 test / 每個 test 有 report": the button triggers actual test execution.

import { spawn } from "node:child_process";
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "../lib/store.js";
import { loadActions } from "../lib/registry.js";

// Static inventory: which registered actions claim a test, used by GET /api/tests.
export function listTests() {
  const actions = loadActions().actions;
  let files = [];
  try {
    files = readdirSync(join(ROOT, "test")).filter((f) => f.endsWith(".test.js"));
  } catch {
    files = [];
  }
  return {
    test_files: files,
    actions: actions.map((a) => ({
      action_id: a.id,
      test_id: a.test_id,
      has_test: Boolean(a.test_id),
      implemented: a.implemented,
    })),
    coverage: {
      total: actions.length,
      with_test: actions.filter((a) => a.test_id).length,
      implemented_without_test: actions.filter((a) => a.implemented && !a.test_id).length,
    },
  };
}

export function runTests({ timeoutMs = 60000 } = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, ["--test"], {
      cwd: ROOT,
      env: { ...process.env, TFNK_TEST_CHILD: "1" },
    });
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
    }, timeoutMs);

    child.stdout.on("data", (d) => (out += d.toString()));
    child.stderr.on("data", (d) => (err += d.toString()));
    child.on("close", (code) => {
      clearTimeout(timer);
      const summary = parseSummary(out);
      resolve({
        ran_at: new Date().toISOString(),
        exit_code: code,
        result: code === 0 ? "passed" : "failed",
        summary,
        stdout_tail: out.split("\n").slice(-40).join("\n"),
        stderr_tail: err.split("\n").slice(-20).join("\n"),
      });
    });
  });
}

function parseSummary(out) {
  const pick = (label) => {
    const m = new RegExp(`# ${label} (\\d+)`).exec(out);
    return m ? Number(m[1]) : null;
  };
  return {
    tests: pick("tests"),
    pass: pick("pass"),
    fail: pick("fail"),
    cancelled: pick("cancelled"),
    skipped: pick("skipped"),
  };
}
