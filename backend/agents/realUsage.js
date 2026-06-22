// Real Usage Runner — proves a delivered feature is actually USABLE, not merely
// "tests pass". It executes a scenario of real steps and collects evidence.
//
// step.type:
//   "api"  -> performs a real HTTP call against the running server and checks
//             status_code / body_contains.
//   "wait" -> waits N seconds (capped so test/dev runs stay fast).
//   "ui"   -> in this headless build there is no browser, so UI steps are
//             reported "skipped" with an honest note (never faked as passed).

const MAX_WAIT_SECONDS = 3; // keep scenarios snappy in dev/CI

function parseAction(action) {
  const [method, path] = String(action).split(/\s+/);
  return { method: (method || "GET").toUpperCase(), path: path || action };
}

async function runApiStep(step, base_url, fetchImpl) {
  const { method, path } = parseAction(step.action);
  const url = base_url.replace(/\/$/, "") + path;
  let resp, body;
  try {
    resp = await fetchImpl(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: method === "POST" ? JSON.stringify(step.input || {}) : undefined,
    });
    body = await resp.text();
  } catch (err) {
    return { step: step.action, expected: JSON.stringify(step.expect || {}), actual: `request failed: ${String(err && err.message)}`, status: "failed", evidence: [] };
  }
  const exp = step.expect || {};
  const checks = [];
  if (exp.status_code !== undefined) checks.push(resp.status === exp.status_code);
  for (const needle of exp.body_contains || []) checks.push(body.includes(needle));
  const ok = checks.length === 0 ? resp.ok : checks.every(Boolean);
  return {
    step: step.action,
    expected: JSON.stringify(exp),
    actual: `status ${resp.status}`,
    status: ok ? "passed" : "failed",
    evidence: [`HTTP ${resp.status}`, body.slice(0, 200)],
  };
}

export async function runScenario(scenario, { base_url, fetchImpl = fetch } = {}) {
  // scenario may be a structured object {steps:[...]} or a bare array of steps.
  const steps = Array.isArray(scenario) ? scenario : scenario.steps || [];
  const results = [];
  let failed = false;

  for (const step of steps) {
    if (typeof step === "string") {
      // descriptive (string) scenario steps can't be executed automatically.
      results.push({ step, expected: "", actual: "descriptive step — needs structured api/ui step to auto-run", status: "skipped", evidence: [] });
      continue;
    }
    if (step.type === "wait") {
      const s = Math.min(step.seconds || 0, MAX_WAIT_SECONDS);
      await new Promise((r) => setTimeout(r, s * 1000));
      results.push({ step: `wait ${s}s`, expected: "", actual: "waited", status: "passed", evidence: [] });
    } else if (step.type === "api") {
      if (!base_url) {
        results.push({ step: step.action, expected: "", actual: "no base_url to run api step", status: "skipped", evidence: [] });
        continue;
      }
      const r = await runApiStep(step, base_url, fetchImpl);
      if (r.status === "failed") failed = true;
      results.push(r);
    } else if (step.type === "ui") {
      results.push({ step: step.action, expected: JSON.stringify(step.expect || {}), actual: "no headless browser in this build", status: "skipped", evidence: ["ui step requires a browser driver (out of scope for zero-dep build)"] });
    } else {
      results.push({ step: JSON.stringify(step), expected: "", actual: "unknown step type", status: "skipped", evidence: [] });
    }
  }

  const executed = results.filter((r) => r.status !== "skipped");
  const usable = executed.length > 0 && executed.every((r) => r.status === "passed");
  return {
    scenario_id: scenario.scenario_id || "scenario",
    status: failed ? "failed" : usable ? "passed" : "blocked",
    steps: results,
    usable_for_real_work: usable && !failed,
    issues: results.filter((r) => r.status === "failed").map((r) => r.step),
  };
}
