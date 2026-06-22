// Scheduler Service — one-time / interval / cron scheduled tasks with real run
// records, retries, missed-run recovery and run-now. Unattended high-risk tasks
// are never auto-executed; they park as pending_approval.
//
// Zero-dependency: a minimal cron evaluator (m h dom mon dow with *, */n, a-b,
// and comma lists) computes next_run_at. State persists to data/runtime.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { ROOT, addLog } from "./store.js";
import { audit } from "../agents/uiAudit.js";
import { loadActions } from "./registry.js";
import * as loopEngine from "../loop.js";

const FILE = join(ROOT, "data", "runtime", "scheduler.json");

const state = {
  tasks: new Map(), // id -> scheduled_task
  runs: [], // task_run records (newest last)
};

// --- cron-lite --------------------------------------------------------------
function parseField(field, min, max) {
  const out = new Set();
  for (const part of String(field).split(",")) {
    if (part === "*") {
      for (let i = min; i <= max; i++) out.add(i);
    } else if (part.startsWith("*/")) {
      const step = Number(part.slice(2));
      for (let i = min; i <= max; i += step) out.add(i);
    } else if (part.includes("-")) {
      const [a, b] = part.split("-").map(Number);
      for (let i = a; i <= b; i++) out.add(i);
    } else {
      out.add(Number(part));
    }
  }
  return out;
}

export function cronNext(expr, from = new Date()) {
  const [m, h, dom, mon, dow] = String(expr).trim().split(/\s+/);
  if ([m, h, dom, mon, dow].some((x) => x === undefined)) return null;
  const mins = parseField(m, 0, 59);
  const hours = parseField(h, 0, 23);
  const doms = parseField(dom, 1, 31);
  const mons = parseField(mon, 1, 12);
  const dows = parseField(dow, 0, 6);

  const d = new Date(from.getTime() + 60000 - (from.getTime() % 60000)); // next minute
  for (let i = 0; i < 366 * 24 * 60; i++) {
    if (
      mins.has(d.getMinutes()) &&
      hours.has(d.getHours()) &&
      mons.has(d.getMonth() + 1) &&
      doms.has(d.getDate()) &&
      dows.has(d.getDay())
    ) {
      return d.toISOString();
    }
    d.setMinutes(d.getMinutes() + 1);
  }
  return null;
}

function computeNextRun(task, from = new Date()) {
  if (task.schedule_type === "once") return task.run_at || null;
  if (task.schedule_type === "interval") return new Date(from.getTime() + (task.interval_seconds || 60) * 1000).toISOString();
  if (task.schedule_type === "cron") return cronNext(task.cron_expr, from);
  return null;
}

// --- CRUD -------------------------------------------------------------------
export function createTask(input) {
  if (!input || !input.name) return { error: "name is required" };
  const id = `sched_${randomUUID().slice(0, 8)}`;
  const now = new Date();
  let run_at = input.run_at || null;
  if (input.schedule_type === "once" && !run_at && input.run_at_offset_seconds) {
    run_at = new Date(now.getTime() + input.run_at_offset_seconds * 1000).toISOString();
  }
  const task = {
    id,
    name: input.name,
    task_type: input.task_type || "custom",
    prompt: input.prompt || "",
    schedule_type: input.schedule_type || "once",
    cron_expr: input.cron_expr || null,
    interval_seconds: input.interval_seconds || null,
    run_at,
    risk_level: input.risk_level || "low",
    enabled: input.enabled !== false,
    last_run_at: null,
    next_run_at: null,
    max_retries: input.max_retries ?? 2,
    real_usage_scenario: input.real_usage_scenario || null,
    created_at: now.toISOString(),
  };
  task.next_run_at = computeNextRun(task, now);
  state.tasks.set(id, task);
  persist();
  addLog({ agent: "SchedulerAgent", event: "task_created", detail: { id, name: task.name, next_run_at: task.next_run_at } });
  return task;
}

export function listTasks() {
  return [...state.tasks.values()];
}
export function getTask(id) {
  return state.tasks.get(id) || null;
}
export function setEnabled(id, enabled) {
  const t = state.tasks.get(id);
  if (!t) return { error: "task not found", _status: 404 };
  t.enabled = enabled;
  if (enabled) t.next_run_at = computeNextRun(t, new Date());
  persist();
  return t;
}
export function deleteTask(id) {
  const existed = state.tasks.delete(id);
  persist();
  return { deleted: existed };
}
export function listRuns({ task_id, limit = 50 } = {}) {
  let runs = state.runs;
  if (task_id) runs = runs.filter((r) => r.scheduled_task_id === task_id);
  return runs.slice(-limit).reverse();
}
export function getRun(id) {
  return state.runs.find((r) => r.id === id) || null;
}

// --- execution --------------------------------------------------------------
// Built-in executors. Each returns { output, verification, evidence }.
async function execute(task, ctx = {}) {
  switch (task.task_type) {
    case "health_check": {
      const a = audit();
      const actions = loadActions().actions.length;
      const loop = loopEngine.getStatus();
      const healthy = a.fake_or_incomplete === 0;
      return {
        output: { actions, audit: { connected: a.connected, problems: a.fake_or_incomplete }, loop: loop.status },
        verification: healthy ? "passed" : "failed",
        evidence: [`actions=${actions}`, `audit_problems=${a.fake_or_incomplete}`, `loop=${loop.status}`],
      };
    }
    case "ui_audit": {
      const a = audit();
      return {
        output: { total: a.total_elements, connected: a.connected, problems: a.fake_or_incomplete },
        verification: a.fake_or_incomplete === 0 ? "passed" : "failed",
        evidence: [`scanned ${a.total_elements} elements`, `${a.fake_or_incomplete} problems`],
      };
    }
    case "real_usage": {
      if (!task.real_usage_scenario || !ctx.runScenario) {
        return { output: { note: "no scenario or runner available" }, verification: "skipped", evidence: [] };
      }
      const r = await ctx.runScenario(task.real_usage_scenario);
      return { output: r, verification: r.status === "passed" ? "passed" : "failed", evidence: [`scenario ${r.status}`] };
    }
    default:
      return { output: { note: `no executor for task_type "${task.task_type}"` }, verification: "skipped", evidence: [] };
  }
}

export async function runTask(id, { manual = false, ctx = {} } = {}) {
  const task = state.tasks.get(id);
  if (!task) return { error: "task not found", _status: 404 };

  const run = {
    id: `run_${randomUUID().slice(0, 8)}`,
    scheduled_task_id: id,
    status: "running",
    started_at: new Date().toISOString(),
    finished_at: null,
    input_json: { task_type: task.task_type, prompt: task.prompt },
    output_json: null,
    verification_result: null,
    error: null,
    evidence_path: null,
  };

  // Unattended high-risk tasks must not run without a human.
  if (!manual && (task.risk_level === "high" || task.risk_level === "critical")) {
    run.status = "pending_approval";
    run.finished_at = new Date().toISOString();
    state.runs.push(run);
    persist();
    addLog({ agent: "SchedulerAgent", event: "pending_approval", detail: { task: id } });
    return { run, task };
  }

  state.runs.push(run);
  let attempt = 0;
  let result = null;
  while (attempt <= task.max_retries) {
    try {
      result = await execute(task, ctx);
      run.output_json = result.output;
      run.verification_result = result.verification;
      run.evidence = result.evidence;
      run.status = result.verification === "failed" ? "failed" : "completed";
      if (run.status !== "failed") break;
    } catch (err) {
      run.error = String(err && err.message);
      run.status = "failed";
    }
    attempt += 1;
  }
  run.finished_at = new Date().toISOString();
  run.attempts = attempt + (run.status === "completed" ? 0 : 0);

  // Advance schedule.
  task.last_run_at = run.finished_at;
  if (task.schedule_type === "once") {
    task.enabled = false;
    task.next_run_at = null;
  } else {
    task.next_run_at = computeNextRun(task, new Date());
  }
  persist();
  addLog({ agent: "SchedulerAgent", event: "run_finished", detail: { run_id: run.id, status: run.status } });
  return { run, task };
}

// Tick: run any enabled task whose next_run_at is due. Returns the runs fired.
export async function tick({ now = new Date(), ctx = {} } = {}) {
  const fired = [];
  for (const task of state.tasks.values()) {
    if (!task.enabled || !task.next_run_at) continue;
    if (new Date(task.next_run_at) <= now) {
      fired.push(await runTask(task.id, { manual: false, ctx }));
    }
  }
  return fired;
}

// --- persistence ------------------------------------------------------------
function persist() {
  try {
    mkdirSync(join(ROOT, "data", "runtime"), { recursive: true });
    writeFileSync(FILE, JSON.stringify({ tasks: listTasks(), runs: state.runs.slice(-500) }, null, 2));
  } catch {
    /* best-effort */
  }
}
export function loadPersistedScheduler() {
  try {
    if (existsSync(FILE)) {
      const data = JSON.parse(readFileSync(FILE, "utf8"));
      for (const t of data.tasks || []) state.tasks.set(t.id, t);
      state.runs = data.runs || [];
    }
  } catch {
    /* ignore */
  }
}

export function _resetSchedulerForTests() {
  state.tasks.clear();
  state.runs = [];
}
