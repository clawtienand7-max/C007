// Loads and queries the Action Registry and UI Control Map. This is the
// source of truth the whole "no fake UI" guarantee rests on.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./store.js";

let _actions = null;
let _uiMap = null;

export function loadActions() {
  if (!_actions) {
    const raw = readFileSync(join(ROOT, "data", "action_registry.json"), "utf8");
    _actions = JSON.parse(raw);
  }
  return _actions;
}

export function loadUiMap() {
  if (!_uiMap) {
    const raw = readFileSync(join(ROOT, "data", "ui_control_map.json"), "utf8");
    _uiMap = JSON.parse(raw);
  }
  return _uiMap;
}

export function getAction(actionId) {
  return loadActions().actions.find((a) => a.id === actionId) || null;
}

// The set of API routes the server actually serves. Kept here so the UI Audit
// Agent can confirm a registered action points at a route that truly exists,
// rather than trusting the registry's own `implemented` flag.
export const LIVE_ROUTES = new Set([
  "GET /api/health",
  "GET /api/actions",
  "GET /api/ui-control-map",
  "POST /api/agent/session",
  "GET /api/agent/session",
  "POST /api/agent/plan",
  "POST /api/agent/step/run",
  "POST /api/agent/verify",
  "POST /api/agent/repair",
  "POST /api/agent/audit",
  "POST /api/agent/run",
  "POST /api/memory/write",
  "GET /api/memory/search",
  "POST /api/computer/screenshot",
  "POST /api/computer/click",
  "POST /api/computer/type",
  "POST /api/loop/run",
  "GET /api/loop/status",
  "POST /api/loop/stop",
  "POST /api/emergency-stop",
  "GET /api/logs",
  "GET /api/tests",
  "POST /api/tests/run",
  "GET /api/permissions",
  "POST /api/permissions/decide",
  // V0.4 — cross-device + vision
  "GET /api/device/info",
  "GET /api/device/capabilities",
  "GET /api/devices",
  "POST /api/devices/discover",
  "POST /api/devices/announce",
  "POST /api/devices/pair",
  "POST /api/devices/trust",
  "POST /api/devices/delegate-task",
  "GET /api/devices/tasks",
  "GET /api/camera/sources",
  "POST /api/camera/source/add",
  "POST /api/camera/source/test",
  "POST /api/camera/start",
  "POST /api/camera/stop",
  "GET /api/camera/status",
  "POST /api/vision/start",
  "POST /api/vision/stop",
  "GET /api/vision/status",
  "POST /api/vision/ingest",
  "POST /api/vision/replay",
  "GET /api/vision/gestures/latest",
  "GET /api/vision/events",
  "GET /api/gestures",
  "POST /api/gestures/map",
  "POST /api/gestures/test",
  "POST /api/gestures/enable",
  "POST /api/gestures/disable",
  "GET /api/events/recent",
  // V0.5 — scheduler + delivery verification + real usage
  "POST /api/scheduler/tasks",
  "GET /api/scheduler/tasks",
  "POST /api/scheduler/tasks/run-now",
  "POST /api/scheduler/tasks/enable",
  "POST /api/scheduler/tasks/disable",
  "POST /api/scheduler/tasks/delete",
  "GET /api/scheduler/runs",
  "GET /api/scheduler/run",
  "POST /api/contracts",
  "GET /api/contracts",
  "POST /api/contracts/codex-prompt",
  "POST /api/contracts/claude-prompt",
  "POST /api/deliveries/intake",
  "GET /api/deliveries",
  "POST /api/deliveries/verify",
  "POST /api/deliveries/accept",
  "POST /api/deliveries/reject",
  "POST /api/deliveries/request-repair",
  "POST /api/real-usage/run",
]);

export function routeExists(method, api) {
  return LIVE_ROUTES.has(`${method.toUpperCase()} ${api}`);
}

// Compute display status for an action per the blueprint's UI display rules.
export function actionStatus(action) {
  if (!action) return "fake_or_unmapped";
  if (!action.implemented) return "backend_missing";
  if (!routeExists(action.method, action.api)) return "backend_missing";
  if (action.risk === "high" || action.risk === "critical") {
    return action.fallback === "request_permission"
      ? "permission_required"
      : "connected";
  }
  return "connected";
}
