// UI Audit Agent — the heart of the "no fake UI" guarantee.
// Scans the real frontend source for interactive elements, then reconciles
// each one against the action registry, the UI control map and the live API
// routes. Produces a structured report classifying every element.

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "../lib/store.js";
import { loadActions, loadUiMap, routeExists } from "../lib/registry.js";

// Extract interactive elements from an HTML source string. We look for any
// element carrying a `data-action` attribute plus the element's id and label.
function scanHtml(html, file) {
  const elements = [];
  // Match opening tags for interactive controls.
  const tagRe = /<(button|input|select|a|div|span)\b([^>]*)>/gi;
  const lines = html.split("\n");
  let m;
  while ((m = tagRe.exec(html)) !== null) {
    const attrs = m[2];
    const idMatch = /\bid\s*=\s*"([^"]+)"/.exec(attrs);
    const actionMatch = /\bdata-action\s*=\s*"([^"]+)"/.exec(attrs);
    const labelMatch = /\bdata-label\s*=\s*"([^"]+)"/.exec(attrs);
    const clientMatch = /\bdata-client\s*=\s*"true"/.test(attrs);
    // Only consider controls that look interactive: a button/input/select, or
    // anything explicitly tagged with data-action.
    const tag = m[1].toLowerCase();
    const interactive = ["button", "input", "select"].includes(tag) || actionMatch;
    if (!interactive) continue;
    const upto = html.slice(0, m.index);
    const line = upto.split("\n").length;
    elements.push({
      ui_id: idMatch ? idMatch[1] : null,
      type: tag,
      label: labelMatch ? labelMatch[1] : idMatch ? idMatch[1] : tag,
      action_id: actionMatch ? actionMatch[1] : null,
      client_only: clientMatch,
      file,
      line,
    });
  }
  return elements;
}

export function audit() {
  const reg = loadActions();
  const uiMap = loadUiMap();
  const actionById = new Map(reg.actions.map((a) => [a.id, a]));
  const mapByElement = new Map();
  for (const screen of uiMap.screens) {
    for (const el of screen.elements) mapByElement.set(el.id, el);
  }

  // Scan every HTML file under frontend/ so multi-page UIs (e.g. the HUD) are
  // held to the same no-fake-UI standard.
  let htmlFiles = [];
  try {
    htmlFiles = readdirSync(join(ROOT, "frontend")).filter((f) => f.endsWith(".html"));
  } catch {
    htmlFiles = [];
  }
  const found = [];
  for (const f of htmlFiles) {
    try {
      found.push(...scanHtml(readFileSync(join(ROOT, "frontend", f), "utf8"), `frontend/${f}`));
    } catch {
      /* skip unreadable file */
    }
  }

  const items = [];
  for (const el of found) {
    let status = "connected";
    let reason = "";
    let required_fix = "";

    if (el.client_only) {
      status = "client_only";
      reason = "client-only control declared with data-client (no backend by design)";
    } else if (!el.ui_id) {
      status = "broken";
      reason = "element has no unique id";
      required_fix = "add a unique id attribute";
    } else if (!el.action_id) {
      status = "missing_action_id";
      reason = "element is not bound to any action_id";
      required_fix = "add data-action pointing at a registry action, or mark it non-interactive";
    } else {
      const action = actionById.get(el.action_id);
      const mapped = mapByElement.get(el.ui_id);
      if (!action) {
        status = "fake_or_unmapped";
        reason = `action_id "${el.action_id}" is not in action_registry.json`;
        required_fix = "register the action or remove the control";
      } else if (!mapped) {
        status = "fake_or_unmapped";
        reason = `element "${el.ui_id}" is missing from ui_control_map.json`;
        required_fix = "add the element to the UI control map";
      } else if (!action.implemented) {
        // Declared future-phase work (implemented:false in the registry). This
        // is NOT a fake — it is an honest "not yet". CI tolerates these; the UI
        // shows them disabled.
        status = "pending_phase";
        reason = `action "${action.id}" is declared but not yet implemented (future phase)`;
        required_fix = `implement ${action.method} ${action.api} and flip implemented=true when the phase lands`;
      } else if (!routeExists(action.method, action.api)) {
        // implemented:true but no live route => a genuine bug CI must catch.
        status = "missing_backend";
        reason = `route ${action.method} ${action.api} is not live on the server`;
        required_fix = `add route ${action.method} ${action.api}`;
      } else if (!action.test_id) {
        status = "missing_test";
        reason = `action "${action.id}" has no test_id`;
        required_fix = "add a test and set test_id";
      } else {
        status = "connected";
        reason = "bound to registered, implemented, routed and tested action";
      }
    }

    items.push({
      ui_id: el.ui_id,
      label: el.label,
      file: el.file,
      line: el.line,
      action_id: el.action_id,
      status,
      reason,
      required_fix,
    });
  }

  const connected = items.filter((i) => i.status === "connected").length;
  const client_only = items.filter((i) => i.status === "client_only").length;
  const pending = items.filter((i) => i.status === "pending_phase").length;
  // "Incomplete" = a genuine problem: a control that claims to be a real,
  // shipped feature but isn't fully wired. Client-only and declared-pending
  // controls are honest and excluded. Only this count fails the audit / CI.
  const fake_or_incomplete = items.length - connected - client_only - pending;

  return {
    generated_at: new Date().toISOString(),
    total_elements: items.length,
    connected,
    client_only,
    pending,
    fake_or_incomplete,
    by_status: items.reduce((acc, i) => {
      acc[i.status] = (acc[i.status] || 0) + 1;
      return acc;
    }, {}),
    items,
  };
}
