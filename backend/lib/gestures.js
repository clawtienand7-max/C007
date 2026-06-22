// Gesture mappings registry + Gesture Action Mapper.
//
// The mapper is the safety gate between "the camera thinks it saw a gesture"
// and "TFNK actually does something". A gesture NEVER bypasses the Action
// Registry or the Permission Controller:
//   recognised -> confidence check -> cooldown -> action lookup -> risk
//   assessment -> permission gate -> (maybe) execute -> verify.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./store.js";
import { getAction } from "./registry.js";
import { createPermission } from "./store.js";

const SEED_FILE = join(ROOT, "data", "gesture_mappings.json");
const RUNTIME_FILE = join(ROOT, "data", "runtime", "gesture_mappings.json");

let _mappings = null;
const lastFired = new Map(); // gesture_id -> timestamp (cooldown tracking)

function load() {
  if (_mappings) return _mappings;
  const file = existsSync(RUNTIME_FILE) ? RUNTIME_FILE : SEED_FILE;
  _mappings = JSON.parse(readFileSync(file, "utf8")).mappings;
  return _mappings;
}

function persist() {
  try {
    mkdirSync(join(ROOT, "data", "runtime"), { recursive: true });
    writeFileSync(RUNTIME_FILE, JSON.stringify({ version: "0.4.0", mappings: _mappings }, null, 2));
  } catch {
    /* best-effort */
  }
}

export function listMappings() {
  return load().map((m) => ({ ...m }));
}
export function getMapping(gesture_id) {
  return load().find((m) => m.gesture_id === gesture_id) || null;
}

export function mapGesture({ gesture_id, action_id, min_confidence, cooldown_ms, risk_level, requires_confirmation }) {
  if (!gesture_id || !action_id) return { error: "gesture_id and action_id required" };
  if (!getAction(action_id)) return { error: `action_id "${action_id}" is not in the action registry` };
  load();
  let m = _mappings.find((x) => x.gesture_id === gesture_id);
  if (!m) {
    m = { gesture_id, gesture_name: gesture_id, enabled: true };
    _mappings.push(m);
  }
  Object.assign(m, {
    action_id,
    min_confidence: min_confidence ?? m.min_confidence ?? 0.9,
    cooldown_ms: cooldown_ms ?? m.cooldown_ms ?? 1500,
    risk_level: risk_level ?? m.risk_level ?? getAction(action_id).risk,
    requires_confirmation: requires_confirmation ?? m.requires_confirmation ?? false,
  });
  persist();
  return { mapping: { ...m } };
}

export function setEnabled(gesture_id, enabled) {
  const m = getMapping(gesture_id);
  if (!m) return { error: "gesture not found" };
  m.enabled = enabled;
  persist();
  return { mapping: { ...m } };
}

// The mapper. `now` is injectable for deterministic cooldown tests.
export function mapToAction({ gesture_id, confidence = 0, status = "recognized" } = {}, now = Date.now()) {
  const base = { gesture_id, action_id: null, allowed: false, risk_level: null, requires_confirmation: false, verification_method: "" };

  if (status !== "recognized") {
    return { ...base, reason: `gesture status is "${status}", not actionable` };
  }
  const m = getMapping(gesture_id);
  if (!m) return { ...base, reason: "gesture not mapped to any action" };
  if (!m.enabled) return { ...base, action_id: m.action_id, reason: "gesture mapping disabled" };
  if (confidence < m.min_confidence) {
    return { ...base, action_id: m.action_id, risk_level: m.risk_level, reason: `confidence ${confidence} < min ${m.min_confidence}` };
  }
  const last = lastFired.get(gesture_id) || 0;
  if (now - last < m.cooldown_ms) {
    return { ...base, action_id: m.action_id, risk_level: m.risk_level, reason: `cooldown active (${m.cooldown_ms}ms)` };
  }
  const action = getAction(m.action_id);
  if (!action) return { ...base, action_id: m.action_id, reason: "mapped action no longer in registry" };

  const risk = m.risk_level || action.risk;
  // Critical gestures: only emergency-stop-class actions may auto-fire.
  const isEmergency = m.action_id === "emergency.stop";
  let allowed = false;
  let requires_confirmation = false;
  let reason = "";

  if (risk === "low") {
    allowed = true;
    reason = "low risk — execute directly";
  } else if (risk === "medium") {
    allowed = true;
    reason = "medium risk — execute with UI feedback";
  } else if (risk === "critical" && isEmergency) {
    allowed = true;
    reason = "emergency stop — safety priority, executes immediately";
  } else {
    // high or non-emergency critical -> never auto-execute from a gesture.
    requires_confirmation = true;
    const perm = createPermission({
      action_id: m.action_id,
      risk,
      reason: `Gesture "${gesture_id}" requests high-risk action "${m.action_id}"`,
      source: "gesture",
    });
    reason = `high/critical risk — queued for confirmation (${perm.permission_id})`;
    lastFired.set(gesture_id, now);
    return { ...base, action_id: m.action_id, allowed: false, risk_level: risk, requires_confirmation: true, permission_id: perm.permission_id, reason, verification_method: "user confirmation then action verify" };
  }

  lastFired.set(gesture_id, now);
  return {
    gesture_id,
    action_id: m.action_id,
    allowed,
    risk_level: risk,
    requires_confirmation,
    reason,
    verification_method: isEmergency ? "loop status becomes stopped" : "action-specific verify",
  };
}

export function _resetGesturesForTests() {
  _mappings = null;
  lastFired.clear();
}
