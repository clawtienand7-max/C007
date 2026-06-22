// In-memory store with optional JSON persistence for sessions, steps,
// permissions, logs and the LOOP state machine. Kept dependency-free so the
// foundation runs anywhere Node >= 20 is present. State that must survive a
// restart (logs, sessions) is mirrored to data/runtime/*.json best-effort.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
export const ROOT = join(__dirname, "..", "..");
const RUNTIME_DIR = join(ROOT, "data", "runtime");

function ensureRuntimeDir() {
  if (!existsSync(RUNTIME_DIR)) mkdirSync(RUNTIME_DIR, { recursive: true });
}

const state = {
  sessions: new Map(), // session_id -> session
  steps: new Map(), // step_id -> step
  permissions: new Map(), // permission_id -> permission request
  logs: [], // trace entries (capped)
  loop: {
    status: "idle", // idle | running | completed | stopped | error
    run_id: null,
    iteration: 0,
    max_iterations: 0,
    started_at: null,
    finished_at: null,
    last_result: null,
    history: [],
    emergency_stopped: false,
  },
  counters: { session: 0, step: 0, permission: 0, run: 0 },
};

let _timer = null;

export function nextId(kind, prefix) {
  state.counters[kind] = (state.counters[kind] || 0) + 1;
  return `${prefix}_${String(state.counters[kind]).padStart(3, "0")}`;
}

// --- sessions ---------------------------------------------------------------
export function createSession({ goal, mode = "safe_autonomy" }) {
  const id = nextId("session", "agent_sess");
  const session = {
    session_id: id,
    goal: goal || "",
    status: "created",
    mode,
    current_step: null,
    progress: 0,
    risk_level: "low",
    steps: [],
    created_at: new Date().toISOString(),
  };
  state.sessions.set(id, session);
  persist("sessions");
  return session;
}

export function getSession(id) {
  return state.sessions.get(id) || null;
}

export function listSessions() {
  return [...state.sessions.values()];
}

export function saveStep(step) {
  state.steps.set(step.step_id, step);
  const session = state.sessions.get(step.session_id);
  if (session) {
    session.steps = session.steps.filter((s) => s.step_id !== step.step_id);
    session.steps.push(step);
    session.current_step = step.name;
    persist("sessions");
  }
  return step;
}

// --- permissions ------------------------------------------------------------
export function createPermission(req) {
  const id = nextId("permission", "perm");
  const permission = {
    permission_id: id,
    status: "pending",
    requires_user_approval: true,
    created_at: new Date().toISOString(),
    ...req,
  };
  state.permissions.set(id, permission);
  persist("permissions");
  return permission;
}

export function decidePermission(id, decision) {
  const p = state.permissions.get(id);
  if (!p) return null;
  p.status = decision === "approve" ? "approved" : "denied";
  p.decided_at = new Date().toISOString();
  persist("permissions");
  return p;
}

export function listPermissions() {
  return [...state.permissions.values()];
}

// --- logs / trace -----------------------------------------------------------
export function addLog(entry) {
  const record = { ts: new Date().toISOString(), ...entry };
  state.logs.push(record);
  if (state.logs.length > 2000) state.logs.splice(0, state.logs.length - 2000);
  persist("logs");
  return record;
}

export function getLogs({ limit = 200, session_id } = {}) {
  let logs = state.logs;
  if (session_id) logs = logs.filter((l) => l.session_id === session_id);
  return logs.slice(-limit);
}

// --- loop -------------------------------------------------------------------
export const loop = state.loop;

export function setLoopTimer(t) {
  _timer = t;
}
export function clearLoopTimer() {
  if (_timer) {
    clearTimeout(_timer);
    _timer = null;
  }
}

// --- persistence (best effort) ---------------------------------------------
function persist(kind) {
  try {
    ensureRuntimeDir();
    if (kind === "sessions") {
      writeFileSync(
        join(RUNTIME_DIR, "sessions.json"),
        JSON.stringify(listSessions(), null, 2),
      );
    } else if (kind === "permissions") {
      writeFileSync(
        join(RUNTIME_DIR, "permissions.json"),
        JSON.stringify(listPermissions(), null, 2),
      );
    } else if (kind === "logs") {
      writeFileSync(
        join(RUNTIME_DIR, "logs.json"),
        JSON.stringify(state.logs.slice(-2000), null, 2),
      );
    }
  } catch {
    // persistence is best-effort; never crash the agent over a disk hiccup
  }
}

export function loadPersisted() {
  try {
    const f = join(RUNTIME_DIR, "logs.json");
    if (existsSync(f)) {
      const arr = JSON.parse(readFileSync(f, "utf8"));
      if (Array.isArray(arr)) state.logs = arr;
    }
  } catch {
    // ignore
  }
}

// Test helper: wipe volatile state between test files.
export function _resetForTests() {
  state.sessions.clear();
  state.steps.clear();
  state.permissions.clear();
  state.logs = [];
  Object.assign(state.loop, {
    status: "idle",
    run_id: null,
    iteration: 0,
    max_iterations: 0,
    started_at: null,
    finished_at: null,
    last_result: null,
    history: [],
    emergency_stopped: false,
  });
  clearLoopTimer();
}
