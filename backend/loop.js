// LOOP — a real state machine (idle -> running -> completed | stopped | error).
// Each iteration runs a genuine unit of work (a UI audit pass), records a
// verified result, and either continues, converges, or halts. This is the
// "真 LOOP" required by the blueprint: not a single fire-and-forget call.

import { loop, setLoopTimer, clearLoopTimer, addLog, nextId } from "./lib/store.js";
import { audit } from "./agents/uiAudit.js";

const ITERATION_DELAY_MS = 150; // keep snappy for tests/dev

export function getStatus() {
  return {
    status: loop.status,
    run_id: loop.run_id,
    iteration: loop.iteration,
    max_iterations: loop.max_iterations,
    started_at: loop.started_at,
    finished_at: loop.finished_at,
    last_result: loop.last_result,
    emergency_stopped: loop.emergency_stopped,
    history: loop.history.slice(-20),
  };
}

function runIteration() {
  if (loop.status !== "running") return;
  loop.iteration += 1;

  // Real work: audit the UI and measure convergence (incomplete elements).
  const report = audit();
  const result = {
    iteration: loop.iteration,
    incomplete: report.fake_or_incomplete,
    connected: report.connected,
    verified: report.fake_or_incomplete === 0,
    at: new Date().toISOString(),
  };
  loop.last_result = result;
  loop.history.push(result);
  addLog({ agent: "LoopEngine", event: "iteration", detail: result });

  // Termination conditions: converged, or hit max iterations.
  if (result.incomplete === 0) {
    finish("completed");
    return;
  }
  if (loop.iteration >= loop.max_iterations) {
    finish("completed");
    return;
  }
  setLoopTimer(setTimeout(runIteration, ITERATION_DELAY_MS));
}

function finish(status) {
  loop.status = status;
  loop.finished_at = new Date().toISOString();
  clearLoopTimer();
  addLog({ agent: "LoopEngine", event: "finished", detail: { status, iterations: loop.iteration } });
}

export function start({ max_iterations = 5, goal = "" } = {}) {
  if (loop.emergency_stopped) {
    return { ok: false, error: "emergency stop is engaged; clear it before starting", status: getStatus() };
  }
  if (loop.status === "running") {
    return { ok: false, error: "loop already running", status: getStatus() };
  }
  loop.status = "running";
  loop.run_id = nextId("run", "loop_run");
  loop.iteration = 0;
  loop.max_iterations = Math.max(1, Math.min(50, Number(max_iterations) || 5));
  loop.started_at = new Date().toISOString();
  loop.finished_at = null;
  loop.last_result = null;
  loop.history = [];
  addLog({ agent: "LoopEngine", event: "started", detail: { run_id: loop.run_id, goal, max_iterations: loop.max_iterations } });
  setLoopTimer(setTimeout(runIteration, ITERATION_DELAY_MS));
  return { ok: true, status: getStatus() };
}

export function stop() {
  if (loop.status !== "running") {
    return { ok: false, error: `cannot stop: loop is "${loop.status}"`, status: getStatus() };
  }
  finish("stopped");
  return { ok: true, status: getStatus() };
}

export function emergencyStop() {
  loop.emergency_stopped = true;
  if (loop.status === "running") finish("stopped");
  addLog({ agent: "SafetyAgent", event: "emergency_stop", detail: {} });
  return { ok: true, status: getStatus() };
}

export function clearEmergency() {
  loop.emergency_stopped = false;
  if (loop.status === "stopped" || loop.status === "error") loop.status = "idle";
  return { ok: true, status: getStatus() };
}

// Synchronous variant used by tests so they don't depend on timers.
export function runToCompletionSync({ max_iterations = 5 } = {}) {
  start({ max_iterations });
  clearLoopTimer();
  while (loop.status === "running") {
    loop.iteration += 1;
    const report = audit();
    const result = {
      iteration: loop.iteration,
      incomplete: report.fake_or_incomplete,
      connected: report.connected,
      verified: report.fake_or_incomplete === 0,
      at: new Date().toISOString(),
    };
    loop.last_result = result;
    loop.history.push(result);
    if (result.incomplete === 0 || loop.iteration >= loop.max_iterations) finish("completed");
  }
  return getStatus();
}
