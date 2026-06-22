// Vision Engine — turns a stream of per-frame gesture observations into safe,
// verified TFNK actions. The actual hand-landmark/gesture recognition (e.g.
// MediaPipe) runs in an external worker and pushes frames to ingest(); this
// engine owns the SAFETY pipeline that the blueprint insists on:
//
//   frame -> temporal smoothing -> confidence -> cooldown (in mapper) ->
//   Action Registry lookup -> risk/permission gate -> execute -> verify.
//
// A single noisy frame can never fire an action: a gesture must be stable
// across SMOOTH_N consecutive frames before it is even handed to the mapper.

import { addLog } from "../lib/store.js";
import { mapToAction } from "../lib/gestures.js";
import { emit } from "../lib/events.js";
import { audit } from "./uiAudit.js";
import * as loopEngine from "../loop.js";
import { loadFrames } from "./cameraAdapter.js";

const SMOOTH_N = 3; // consecutive stable frames required (blueprint suggests 3-5)
const BASE_CONFIDENCE = 0.6; // below this a frame is ignored entirely as noise

const session = {
  active: false,
  source_id: null,
  mode: null, // "replay" | "ingest"
  frames_seen: 0,
  recent: [], // recent raw frames
  events: [], // vision_events (decisions)
  latest_gesture: null,
};

export function status() {
  return {
    active: session.active,
    source_id: session.source_id,
    mode: session.mode,
    frames_seen: session.frames_seen,
    latest_gesture: session.latest_gesture,
    recent_events: session.events.slice(-10),
  };
}

export function start({ source_id, mode = "ingest" } = {}) {
  session.active = true;
  session.source_id = source_id || null;
  session.mode = source_id ? "replay" : mode;
  session.frames_seen = 0;
  session.recent = [];
  addLog({ agent: "VisionEngine", event: "started", detail: { source_id, mode: session.mode } });
  emit({ event: "vision.started", source_id: source_id || null, mode: session.mode });
  return status();
}

export function stop() {
  session.active = false;
  addLog({ agent: "VisionEngine", event: "stopped", detail: {} });
  emit({ event: "vision.stopped" });
  return status();
}

// Stable gesture detection over the trailing window.
function stableGesture() {
  const window = session.recent.slice(-SMOOTH_N);
  if (window.length < SMOOTH_N) return null;
  const first = window[0].gesture_id;
  const allSame = window.every((f) => f.gesture_id === first && f.confidence >= BASE_CONFIDENCE);
  if (!allSame) return null;
  const avg = window.reduce((s, f) => s + f.confidence, 0) / window.length;
  return { gesture_id: first, confidence: Number(avg.toFixed(3)) };
}

// Safe in-app dispatch for gestures the engine is allowed to execute.
function dispatch(action_id) {
  switch (action_id) {
    case "emergency.stop":
      return { result: loopEngine.emergencyStop(), verified: loopEngine.getStatus().emergency_stopped };
    case "loop.stop":
      return { result: loopEngine.stop(), verified: ["stopped", "completed"].includes(loopEngine.getStatus().status) };
    case "loop.status":
      return { result: loopEngine.getStatus(), verified: true };
    case "ui.audit":
      return { result: { report: audit() }, verified: true };
    default:
      // allowed but no in-app side effect wired here; honestly report that.
      return { result: { note: `action "${action_id}" allowed; no in-app dispatch in vision engine` }, verified: null };
  }
}

// Ingest one frame. Frame: { gesture_id, confidence, handedness?, landmarks?,
// status? }. Returns the decision for this frame (or a "pending" marker).
export function ingest(frame = {}, now = Date.now()) {
  if (!session.active) return { ignored: true, reason: "vision session not active" };
  session.frames_seen += 1;
  const f = {
    gesture_id: frame.gesture_id || "unknown",
    confidence: Number(frame.confidence) || 0,
    status: frame.status || "recognized",
    at: new Date().toISOString(),
  };
  session.recent.push(f);
  if (session.recent.length > 50) session.recent.shift();
  session.latest_gesture = f;

  // Don't even consider unknown/ambiguous frames for action mapping.
  if (f.status !== "recognized" || f.gesture_id === "unknown") {
    return { stable: false, reason: "frame not a recognised gesture" };
  }

  const stable = stableGesture();
  if (!stable) return { stable: false, reason: `awaiting ${SMOOTH_N} stable frames` };

  const decision = mapToAction({ gesture_id: stable.gesture_id, confidence: stable.confidence, status: "recognized" }, now);

  let executed = false;
  let verification_result = "not_executed";
  if (decision.allowed) {
    const d = dispatch(decision.action_id);
    executed = true;
    verification_result = d.verified === true ? "passed" : d.verified === false ? "failed" : "no_verification";
  } else if (decision.requires_confirmation) {
    verification_result = "queued_for_permission";
  } else {
    verification_result = "blocked";
  }

  const event = {
    event_id: `vis_${session.events.length + 1}`,
    timestamp: new Date().toISOString(),
    source_id: session.source_id,
    gesture_id: stable.gesture_id,
    confidence: stable.confidence,
    action_id: decision.action_id,
    allowed: decision.allowed,
    executed,
    verification_result,
    reason: decision.reason,
    permission_id: decision.permission_id || null,
  };
  session.events.push(event);
  // Reset the smoothing window so the same hold doesn't re-fire every frame.
  session.recent = [];
  addLog({ agent: "GestureActionMapper", event: "gesture_decision", detail: { gesture: stable.gesture_id, action: decision.action_id, executed, verification_result } });
  emit({ event: "gesture.command.detected", gesture: stable.gesture_id, confidence: stable.confidence, mapped_action: decision.action_id, executed, verification_result });
  return { stable: true, decision, event };
}

// Replay a started frames_jsonl source through the full pipeline. Real frames
// from a file, real pipeline — used for development and tests.
export function replay(source_id, now = Date.now()) {
  start({ source_id });
  const frames = loadFrames(source_id);
  const results = [];
  let t = now;
  for (const fr of frames) {
    t += 40; // advance virtual clock ~25fps so cooldowns behave realistically
    results.push(ingest(fr, t));
  }
  return { frames: frames.length, events: session.events.slice(), results };
}

export function latestGestures() {
  return { latest: session.latest_gesture, events: session.events.slice(-20) };
}
export function events() {
  return { events: session.events.slice() };
}

export function _resetVisionForTests() {
  session.active = false;
  session.source_id = null;
  session.mode = null;
  session.frames_seen = 0;
  session.recent = [];
  session.events = [];
  session.latest_gesture = null;
}
