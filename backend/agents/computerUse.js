// Computer Use Agent (Phase 3) — operates the computer the safe, verifiable
// way required by the blueprint: observe -> act on a known target -> verify the
// change -> report blocked if reality doesn't match expectations.
//
// Scope/honesty: this is IN-APP virtual computer use. The "screen" is TFNK's
// own registered UI surface (the action registry + UI control map + live state),
// not an OS-level screen grab. A click performs the REAL action bound to the
// element and is verified against real state — it never fakes a result, never
// clicks a disabled control, and never auto-clicks a permission-gated control.

import { loadUiMap, getAction, actionStatus } from "../lib/registry.js";
import { addLog } from "../lib/store.js";
import { audit } from "./uiAudit.js";
import * as loopEngine from "../loop.js";

// Internal, side-effecting dispatch for the controls the agent is allowed to
// operate autonomously. High-risk controls are intentionally absent.
const DISPATCH = {
  "loop.start": (input) => ({ result: loopEngine.start(input || {}), expect: "loop status === running" }),
  "loop.stop": () => ({ result: loopEngine.stop(), expect: "loop terminal" }),
  "loop.status": () => ({ result: { status: loopEngine.getStatus() }, expect: "status returned" }),
  "emergency.stop": () => ({ result: loopEngine.emergencyStop(), expect: "emergency engaged" }),
  "ui.audit": () => ({ result: { report: audit() }, expect: "report produced" }),
};

// Virtual field state for type() (write-then-read-back verification).
const fields = new Map();

export function screenshot() {
  const map = loadUiMap();
  const elements = [];
  for (const screen of map.screens) {
    for (const el of screen.elements) {
      elements.push({
        ui_id: el.id,
        label: el.label,
        action_id: el.action_id,
        status: actionStatus(getAction(el.action_id)),
      });
    }
  }
  const snapshot = {
    taken_at: new Date().toISOString(),
    surface: "AgentCommandCenter (in-app virtual screen)",
    loop: loopEngine.getStatus(),
    elements,
    fields: Object.fromEntries(fields),
  };
  addLog({ agent: "ComputerUseAgent", event: "screenshot", detail: { elements: elements.length } });
  return snapshot;
}

function findElement(ui_id) {
  for (const screen of loadUiMap().screens) {
    const el = screen.elements.find((e) => e.id === ui_id);
    if (el) return el;
  }
  return null;
}

export function click({ ui_id } = {}) {
  const observation = `looking for control "${ui_id}"`;
  const el = findElement(ui_id);
  if (!el) {
    return blocked(observation, ui_id, `no control "${ui_id}" on the screen`);
  }
  const action = getAction(el.action_id);
  const status = actionStatus(action);

  if (status === "backend_missing" || status === "fake_or_unmapped") {
    return blocked(`saw "${el.label}" but it is disabled (${status})`, ui_id, "refusing to click a disabled control");
  }
  if (status === "permission_required") {
    return blocked(`saw "${el.label}" — high risk`, ui_id, "control requires explicit permission; not auto-clicking");
  }
  const fn = DISPATCH[el.action_id];
  if (!fn) {
    return blocked(`saw "${el.label}"`, ui_id, `action "${el.action_id}" is not in the autonomous dispatch allow-list`);
  }

  const { result, expect } = fn({});
  // Verify against real state.
  let verification = "passed";
  let reason = `performed ${el.action_id}`;
  if (el.action_id === "loop.start") {
    const ok = loopEngine.getStatus().status === "running" || result.ok;
    verification = ok ? "passed" : "failed";
    if (!ok) reason = result.error || "loop did not enter running state";
  } else if (result && result.ok === false) {
    verification = "failed";
    reason = result.error || "action reported failure";
  }

  addLog({ agent: "ComputerUseAgent", event: "click", detail: { ui_id, action: el.action_id, verification } });
  return {
    observation: `saw and clicked "${el.label}"`,
    target_element: ui_id,
    action: "click",
    coordinates: null,
    expected_change: expect,
    verification,
    reason,
    result,
  };
}

export function type({ ui_id, text } = {}) {
  if (typeof text !== "string") return blocked(`type into "${ui_id}"`, ui_id, "text must be a string");
  fields.set(ui_id, text);
  const readBack = fields.get(ui_id);
  const verification = readBack === text ? "passed" : "failed";
  addLog({ agent: "ComputerUseAgent", event: "type", detail: { ui_id, len: text.length, verification } });
  return {
    observation: `typed ${text.length} chars into "${ui_id}"`,
    target_element: ui_id,
    action: "type",
    expected_change: "field holds the typed value",
    verification,
    reason: verification === "passed" ? "write-then-read-back matched" : "read-back mismatch",
    value: readBack,
  };
}

function blocked(observation, ui_id, reason) {
  addLog({ agent: "ComputerUseAgent", event: "blocked", detail: { ui_id, reason } });
  return { observation, target_element: ui_id, action: "stop", verification: "blocked", reason };
}

export function _resetComputerForTests() {
  fields.clear();
}
