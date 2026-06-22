// TFNK Agent OS — HTTP server. Zero external dependencies (Node built-in http).
// Wires the orchestration endpoints, the LOOP state machine, safety/permission
// controls, the Test Center and static frontend hosting.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

import { ROOT, createSession, getSession, listSessions, saveStep, nextId, addLog, getLogs, createPermission, decidePermission, listPermissions, loadPersisted } from "./lib/store.js";
import { loadActions, loadUiMap, getAction, actionStatus, routeExists } from "./lib/registry.js";
import { classify } from "./agents/intent.js";
import { plan as makePlan } from "./agents/planner.js";
import { audit } from "./agents/uiAudit.js";
import { verify } from "./agents/verifier.js";
import { repair } from "./agents/repair.js";
import { listTests, runTests } from "./agents/testCenter.js";
import * as loopEngine from "./loop.js";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

function json(res, status, body) {
  const payload = JSON.stringify(body, null, 2);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  });
  res.end(payload);
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => {
      if (!data) return resolve({});
      try {
        resolve(JSON.parse(data));
      } catch {
        resolve({ _parse_error: true, _raw: data });
      }
    });
  });
}

async function serveStatic(req, res, pathname) {
  let rel = pathname === "/" ? "/index.html" : pathname;
  const filePath = normalize(join(ROOT, "frontend", rel));
  if (!filePath.startsWith(join(ROOT, "frontend"))) {
    return json(res, 403, { error: "forbidden" });
  }
  try {
    const buf = await readFile(filePath);
    res.writeHead(200, { "Content-Type": MIME[extname(filePath)] || "application/octet-stream" });
    res.end(buf);
  } catch {
    json(res, 404, { error: "not found", path: pathname });
  }
}

const ROUTES = {};
function route(method, path, handler) {
  ROUTES[`${method} ${path}`] = handler;
}

// --- meta -------------------------------------------------------------------
route("GET", "/api/health", () => ({ ok: true, service: "tfnk-agent-os", version: "0.3.0", time: new Date().toISOString() }));

route("GET", "/api/actions", () => {
  const reg = loadActions();
  return {
    version: reg.version,
    actions: reg.actions.map((a) => ({ ...a, status: actionStatus(a) })),
  };
});

route("GET", "/api/ui-control-map", () => {
  const map = loadUiMap();
  // annotate each element with the live status of its action
  const screens = map.screens.map((s) => ({
    ...s,
    elements: s.elements.map((el) => ({ ...el, status: actionStatus(getAction(el.action_id)) })),
  }));
  return { version: map.version, screens };
});

// --- agent orchestration ----------------------------------------------------
route("POST", "/api/agent/session", (body) => {
  const session = createSession({ goal: body.goal, mode: body.mode });
  const intent = classify(body.goal || "");
  session.risk_level = intent.risk_level;
  session.intent = intent;
  session.status = "planned";
  addLog({ session_id: session.session_id, agent: "IntentClassifier", event: "classified", detail: intent });
  return { session, intent };
});

route("GET", "/api/agent/session", (_b, q) => {
  if (q.id) {
    const s = getSession(q.id);
    return s ? { session: s } : { error: "not found", _status: 404 };
  }
  return { sessions: listSessions() };
});

route("POST", "/api/agent/plan", (body) => {
  const intent = body.intent || classify(body.goal || "");
  const planned = makePlan(intent);
  if (body.session_id) {
    const s = getSession(body.session_id);
    if (s) {
      s.plan = planned;
      s.status = "ready";
    }
  }
  addLog({ session_id: body.session_id, agent: "Planner", event: "planned", detail: { steps: planned.steps.length } });
  return { plan: planned };
});

route("POST", "/api/agent/step/run", (body) => {
  const { session_id, step } = body;
  if (!step || !step.name) return { error: "step with a name is required", _status: 400 };
  const record = {
    step_id: step.step_id || nextId("step", "step"),
    session_id: session_id || null,
    name: step.name,
    tool: step.tool || "noop",
    input: step.input || {},
    output: { ok: true, note: "step executed by foundation execution engine" },
    verification: step.verification_method ? "pending" : "skipped",
    started_at: new Date().toISOString(),
    duration_ms: 0,
  };
  const t0 = Date.now();
  // Dispatch a few real tools so steps do genuine work.
  if (step.tool === "file_scanner" || step.tool === "registry_reader") {
    record.output = audit();
    record.verification = record.output.fake_or_incomplete === 0 ? "passed" : "failed";
  } else if (step.tool === "api_checker") {
    const exists = step.input && step.input.api ? routeExists(step.input.method || "GET", step.input.api) : null;
    record.output = { exists };
    record.verification = exists ? "passed" : "failed";
  } else if (step.tool === "loop_engine") {
    record.output = loopEngine.getStatus();
    record.verification = "passed";
  }
  record.duration_ms = Date.now() - t0;
  saveStep(record);
  addLog({ session_id, agent: "ExecutionEngine", event: "step_run", detail: { step_id: record.step_id, verification: record.verification } });
  return { step: record };
});

route("POST", "/api/agent/verify", (body) => verify(body));

route("POST", "/api/agent/repair", (body) => repair(body));

route("POST", "/api/agent/audit", () => ({ report: audit() }));

// --- loop -------------------------------------------------------------------
route("POST", "/api/loop/run", (body) => loopEngine.start(body));
route("GET", "/api/loop/status", () => ({ status: loopEngine.getStatus() }));
route("POST", "/api/loop/stop", () => loopEngine.stop());

// --- safety -----------------------------------------------------------------
route("POST", "/api/emergency-stop", () => loopEngine.emergencyStop());
route("POST", "/api/loop/clear-emergency", () => loopEngine.clearEmergency());

// --- permissions ------------------------------------------------------------
route("GET", "/api/permissions", () => ({ permissions: listPermissions() }));
route("POST", "/api/permissions/decide", (body) => {
  if (!body.permission_id || !body.decision) return { error: "permission_id and decision required", _status: 400 };
  const p = decidePermission(body.permission_id, body.decision);
  if (!p) return { error: "permission not found", _status: 404 };
  addLog({ agent: "PermissionController", event: "decided", detail: { permission_id: p.permission_id, status: p.status } });
  return { permission: p };
});

// --- logs / trace -----------------------------------------------------------
route("GET", "/api/logs", (_b, q) => ({ logs: getLogs({ limit: Number(q.limit) || 200, session_id: q.session_id }) }));

// --- test center ------------------------------------------------------------
route("GET", "/api/tests", () => listTests());
route("POST", "/api/tests/run", async () => {
  addLog({ agent: "QATestAgent", event: "tests_started", detail: {} });
  const result = await runTests();
  addLog({ agent: "QATestAgent", event: "tests_finished", detail: result.summary });
  return { result };
});

export function createApp() {
  return createServer(async (req, res) => {
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      });
      return res.end();
    }
    const url = new URL(req.url, "http://localhost");
    const pathname = url.pathname;

    if (!pathname.startsWith("/api/")) return serveStatic(req, res, pathname);

    const handler = ROUTES[`${req.method} ${pathname}`];
    if (!handler) return json(res, 404, { error: "unknown route", route: `${req.method} ${pathname}` });

    try {
      const body = req.method === "POST" ? await readBody(req) : {};
      const query = Object.fromEntries(url.searchParams.entries());
      const result = await handler(body, query);
      const status = result && result._status ? result._status : result && result.error ? 400 : 200;
      if (result && result._status) delete result._status;
      json(res, status, result);
    } catch (err) {
      addLog({ agent: "Server", event: "error", detail: { route: pathname, message: String(err && err.message) } });
      json(res, 500, { error: "internal error", message: String(err && err.message) });
    }
  });
}

// Start when run directly (not when imported by tests).
const isMain = process.argv[1] && process.argv[1].endsWith("server.js");
if (isMain) {
  loadPersisted();
  const port = Number(process.env.PORT) || 4007;
  createApp().listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`TFNK Agent OS v0.3 listening on http://localhost:${port}`);
  });
}
