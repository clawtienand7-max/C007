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
import { executeStep } from "./agents/executor.js";
import { runAutonomous } from "./agents/orchestrator.js";
import { listTests, runTests } from "./agents/testCenter.js";
import { writeMemory, searchMemory } from "./lib/memory.js";
import * as computerUse from "./agents/computerUse.js";
import * as loopEngine from "./loop.js";
import { deviceInfo, deviceCapabilities, listPeers, getPeer, beginPairing, confirmPairing } from "./lib/device.js";
import * as discovery from "./lib/discovery.js";
import * as crossDevice from "./agents/crossDevice.js";
import * as camera from "./agents/cameraAdapter.js";
import * as vision from "./agents/vision.js";
import { listMappings, mapGesture, mapToAction, setEnabled } from "./lib/gestures.js";
import { subscribe, recent as recentEvents } from "./lib/events.js";
import * as scheduler from "./lib/scheduler.js";
import { loadPersistedScheduler } from "./lib/scheduler.js";
import { createContract, getContract, listContracts, loadPersistedContracts } from "./lib/contracts.js";
import { codexPrompt, claudePrompt } from "./agents/promptGen.js";
import * as delivery from "./agents/delivery.js";
import { runScenario } from "./agents/realUsage.js";
import * as selfExt from "./lib/selfExt.js";
import { loadPersistedSelfExt } from "./lib/selfExt.js";
import * as research from "./agents/research.js";
import * as sandbox from "./agents/sandbox.js";
import * as selfUpgrade from "./agents/selfUpgrade.js";
import * as telemetry from "./lib/telemetry.js";
import { buildGraph, getNode } from "./lib/omGraph.js";
import * as weather from "./lib/weather.js";
import * as chat from "./lib/chat.js";
import * as hud from "./lib/hud.js";
import { loadPersistedHud } from "./lib/hud.js";

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
  let rel = pathname === "/" ? "/index.html" : pathname === "/hud" ? "/hud.html" : pathname;
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
route("GET", "/api/health", () => ({ ok: true, service: "tfnk-agent-os", version: "0.8.0", time: new Date().toISOString() }));

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
  return { step: executeStep(step, session_id) };
});

route("POST", "/api/agent/verify", (body) => verify(body));

route("POST", "/api/agent/repair", (body) => repair(body));

route("POST", "/api/agent/audit", () => ({ report: audit() }));

// Master Orchestrator — autonomous understand→plan→execute→verify→report.
route("POST", "/api/agent/run", (body) => runAutonomous(body));

// --- memory -----------------------------------------------------------------
route("POST", "/api/memory/write", (body) => {
  const entry = writeMemory(body);
  if (entry.error) return { ...entry, _status: 400 };
  addLog({ agent: "MemoryAgent", event: "memory_write", detail: { id: entry.id, kind: entry.kind } });
  return { entry };
});
route("GET", "/api/memory/search", (_b, q) => searchMemory({ q: q.q, kind: q.kind, limit: Number(q.limit) || 20 }));

// --- computer use (Phase 3, in-app virtual screen) --------------------------
route("POST", "/api/computer/screenshot", () => ({ snapshot: computerUse.screenshot() }));
route("POST", "/api/computer/click", (body) => computerUse.click(body));
route("POST", "/api/computer/type", (body) => computerUse.type(body));

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

// --- device / LAN (V0.4) ----------------------------------------------------
route("GET", "/api/device/info", () => deviceInfo());
route("GET", "/api/device/capabilities", () => deviceCapabilities());
route("GET", "/api/devices", () => ({ self: deviceInfo(), peers: listPeers() }));
route("POST", "/api/devices/discover", () => {
  discovery.start();
  const b = discovery.broadcast();
  return { broadcast: b, peers: listPeers() };
});
// Peers (and tests) register presence by posting their announce packet.
route("POST", "/api/devices/announce", (body) => {
  const peer = discovery.handleAnnounce(body);
  return peer ? { peer } : { error: "invalid announce", _status: 400 };
});
route("POST", "/api/devices/pair", (body) => {
  const r = beginPairing(body.node_id);
  return r.error ? { ...r, _status: 400 } : r;
});
route("POST", "/api/devices/trust", (body) => {
  const r = confirmPairing(body.node_id, body.code);
  return r.error ? { ...r, _status: 400 } : r;
});
route("GET", "/api/devices/status", (_b, q) => {
  const p = getPeer(q.id);
  return p ? { peer: p } : { error: "peer not found", _status: 404 };
});
route("POST", "/api/devices/delegate-task", (body) => crossDevice.delegate(body));
route("GET", "/api/devices/tasks", () => ({ tasks: crossDevice.listTasks() }));

// --- camera adapter (V0.4) --------------------------------------------------
route("GET", "/api/camera/sources", () => ({ capabilities: camera.detectCapabilities(), sources: camera.listSources() }));
route("POST", "/api/camera/source/add", (body) => {
  const r = camera.addSource(body);
  return r.error ? { ...r, _status: 400 } : r;
});
route("POST", "/api/camera/source/test", (body) => camera.testSource(body.source_id));
route("POST", "/api/camera/start", (body) => {
  const r = camera.testSource(body.source_id);
  addLog({ agent: "CameraAdapter", event: "camera_start", detail: { source_id: body.source_id, connected: r.connected } });
  return { started: r.connected === true, test: r };
});
route("POST", "/api/camera/stop", (body) => ({ stopped: true, source_id: body.source_id || null }));
route("GET", "/api/camera/status", () => ({ capabilities: camera.detectCapabilities(), sources: camera.listSources() }));

// --- vision / gestures (V0.4) -----------------------------------------------
route("POST", "/api/vision/start", (body) => ({ status: vision.start(body) }));
route("POST", "/api/vision/stop", () => ({ status: vision.stop() }));
route("GET", "/api/vision/status", () => ({ status: vision.status() }));
route("POST", "/api/vision/ingest", (body) => vision.ingest(body));
route("POST", "/api/vision/replay", (body) => {
  if (!body.source_id) return { error: "source_id required", _status: 400 };
  return vision.replay(body.source_id);
});
route("GET", "/api/vision/gestures/latest", () => vision.latestGestures());
route("GET", "/api/vision/events", () => vision.events());
route("POST", "/api/vision/calibrate", (body) => ({ ok: true, primary_user: body.primary_user || "user_1", note: "calibration recorded; only the primary user is tracked" }));

route("GET", "/api/gestures", () => ({ mappings: listMappings() }));
route("POST", "/api/gestures/map", (body) => {
  const r = mapGesture(body);
  return r.error ? { ...r, _status: 400 } : r;
});
route("POST", "/api/gestures/test", (body) => mapToAction(body));
route("POST", "/api/gestures/enable", (body) => setEnabled(body.gesture_id, true));
route("POST", "/api/gestures/disable", (body) => setEnabled(body.gesture_id, false));

// --- events -----------------------------------------------------------------
route("GET", "/api/events/recent", (_b, q) => ({ events: recentEvents({ since: Number(q.since) || 0, limit: Number(q.limit) || 100 }) }));

// --- scheduler (V0.5) -------------------------------------------------------
route("POST", "/api/scheduler/tasks", (body) => {
  const t = scheduler.createTask(body);
  return t.error ? { ...t, _status: 400 } : { task: t };
});
route("GET", "/api/scheduler/tasks", (_b, q) => (q.id ? { task: scheduler.getTask(q.id) } : { tasks: scheduler.listTasks() }));
route("POST", "/api/scheduler/tasks/run-now", async (body, _q, ctx) => {
  const runScenarioBound = (scenario) => runScenario(scenario, { base_url: ctx && ctx.base_url });
  const r = await scheduler.runTask(body.id, { manual: true, ctx: { runScenario: runScenarioBound } });
  return r.error ? { ...r, _status: r._status || 400 } : r;
});
route("POST", "/api/scheduler/tasks/enable", (body) => {
  const r = scheduler.setEnabled(body.id, true);
  return r.error ? r : { task: r };
});
route("POST", "/api/scheduler/tasks/disable", (body) => {
  const r = scheduler.setEnabled(body.id, false);
  return r.error ? r : { task: r };
});
route("POST", "/api/scheduler/tasks/delete", (body) => scheduler.deleteTask(body.id));
route("GET", "/api/scheduler/runs", (_b, q) => ({ runs: scheduler.listRuns({ task_id: q.task_id, limit: Number(q.limit) || 50 }) }));
route("GET", "/api/scheduler/run", (_b, q) => ({ run: scheduler.getRun(q.id) }));

// --- requirement contracts (V0.5) -------------------------------------------
route("POST", "/api/contracts", (body) => {
  const c = createContract(body);
  return c.error ? { ...c, _status: 400 } : { contract: c };
});
route("GET", "/api/contracts", (_b, q) => (q.id ? { contract: getContract(q.id) } : { contracts: listContracts() }));
route("POST", "/api/contracts/codex-prompt", (body) => ({ prompt: codexPrompt(getContract(body.requirement_id)) }));
route("POST", "/api/contracts/claude-prompt", (body) => ({ prompt: claudePrompt(getContract(body.requirement_id)) }));

// --- delivery verification (V0.5) -------------------------------------------
route("POST", "/api/deliveries/intake", (body) => delivery.intake(body));
route("GET", "/api/deliveries", (_b, q) => (q.id ? { delivery: delivery.getDelivery(q.id) } : { deliveries: delivery.listDeliveries() }));
route("POST", "/api/deliveries/verify", async (body, _q, ctx) => {
  const r = await delivery.verify(body.id, {
    skipTests: body.skip_tests === true,
    testResult: body.test_result,
    base_url: ctx && ctx.base_url,
  });
  return r.error ? { ...r, _status: r._status || 400 } : r;
});
route("POST", "/api/deliveries/accept", (body) => {
  const r = delivery.accept(body.id, { force: body.force === true });
  return r.error ? { ...r, _status: r._status || 400 } : { delivery: r };
});
route("POST", "/api/deliveries/reject", (body) => ({ delivery: delivery.reject(body.id, { reason: body.reason }) }));
route("POST", "/api/deliveries/request-repair", (body) => delivery.requestRepair(body.id));

// --- real usage runner (V0.5) -----------------------------------------------
route("POST", "/api/real-usage/run", async (body, _q, ctx) => {
  const r = await runScenario(body.scenario || body, { base_url: (body && body.base_url) || (ctx && ctx.base_url) });
  return { result: r };
});

// --- self-extension & self-upgrade (V0.7) -----------------------------------
route("POST", "/api/self/gaps/detect", () => ({ gaps: selfExt.detectGaps() }));
route("POST", "/api/self/gaps", (body) => {
  const g = selfExt.createGap(body);
  return g.error ? { ...g, _status: 400 } : { gap: g };
});
route("GET", "/api/self/gaps", (_b, q) => (q.id ? { gap: selfExt.getGap(q.id) } : { gaps: selfExt.listGaps() }));

route("POST", "/api/self/research/run", async (body) => {
  const gap = selfExt.getGap(body.gap_id);
  if (!gap) return { error: "gap not found", _status: 404 };
  return { report: await research.runResearch(gap, {}) };
});
route("POST", "/api/self/github/search", async (body) => {
  const gap = selfExt.getGap(body.gap_id);
  if (!gap) return { error: "gap not found", _status: 404 };
  return await research.githubSearch(gap, { candidates: body.candidates });
});
route("POST", "/api/self/github/evaluate-repo", (body) => {
  if (!body.gap_id || !body.meta) return { error: "gap_id and meta required", _status: 400 };
  return { candidate: selfExt.saveCandidate(body.gap_id, body.meta) };
});
route("GET", "/api/self/candidates", (_b, q) => ({ candidates: selfExt.listCandidates(q.gap_id) }));

route("POST", "/api/self/skills/create", (body) => {
  const s = selfExt.createSkill(body);
  return s.error ? { ...s, _status: 400 } : { skill: s };
});
route("GET", "/api/self/skills", (_b, q) => (q.id ? { skill: selfExt.getSkill(q.id) } : { skills: selfExt.listSkills() }));

route("POST", "/api/self/sandbox/create", (body) => sandbox.createSandbox(body));
route("POST", "/api/self/sandbox/inspect", (body) => ({ inspection: sandbox.inspectPackage(body.manifest || {}) }));
route("POST", "/api/self/sandbox/install", (body) => sandbox.install(body));
route("POST", "/api/self/sandbox/audit", (body) => sandbox.audit(body));
route("POST", "/api/self/sandbox/destroy", (body) => sandbox.destroy(body));

route("POST", "/api/self/upgrade/proposal", (body) => {
  const r = selfUpgrade.proposeUpgrade(body);
  return r.error ? { ...r, _status: r._status || 400 } : r;
});
route("GET", "/api/self/upgrade/proposals", () => ({ proposals: selfExt.listProposals() }));
route("POST", "/api/self/upgrade/delegate", (body) => selfUpgrade.delegate(body));
route("POST", "/api/self/upgrade/verify", (body) => selfUpgrade.verify(body));
route("POST", "/api/self/upgrade/request-approval", (body) => selfUpgrade.requestApproval(body));
route("POST", "/api/self/upgrade/apply", (body) => selfUpgrade.apply(body));
route("POST", "/api/self/upgrade/rollback", (body) => selfUpgrade.rollback(body));

// --- HUD interface (V0.8) ---------------------------------------------------
route("GET", "/api/hud/state", () => ({ hud: hud.getState() }));
route("POST", "/api/hud/animation/toggle", (body) => hud.toggleAnimation(body.on));
route("POST", "/api/hud/theme/update", (body) => hud.updateTheme(body));
route("GET", "/api/hud/layout", () => hud.getLayout());
route("POST", "/api/hud/layout/save", (body) => hud.saveLayout(body.layout));

// --- telemetry (V0.8) -------------------------------------------------------
route("GET", "/api/telemetry/system", () => telemetry.getSystem());
route("POST", "/api/telemetry/refresh", () => telemetry.getSystem());
route("GET", "/api/telemetry/gpu", () => telemetry.getGpu());
route("GET", "/api/telemetry/network", () => telemetry.getNetwork());
route("GET", "/api/telemetry/disk", () => telemetry.getDisk());

// --- OM relation graph (V0.8) -----------------------------------------------
route("GET", "/api/om/graph", () => buildGraph());
route("GET", "/api/om/graph/node", (_b, q) => {
  const n = getNode(q.id);
  return n ? { node: n } : { error: "node not found", _status: 404 };
});
route("GET", "/api/om/memory/recent", () => searchMemory({ q: "", limit: 10 }));

// --- weather (V0.8) ---------------------------------------------------------
route("GET", "/api/weather/hong-kong", () => weather.getHongKongWeather());
route("GET", "/api/weather/hong-kong/rainfall", () => weather.getRainfall());
route("GET", "/api/weather/hong-kong/alerts", () => weather.getAlerts());

// --- chat dock (V0.8) -------------------------------------------------------
route("GET", "/api/chat/sessions", () => ({ sessions: chat.listSessions() }));
route("POST", "/api/chat/session/new", (body) => ({ session: chat.newSession(body) }));
route("GET", "/api/chat/session", (_b, q) => {
  const s = chat.getSession(q.id);
  return s ? { session: s } : { error: "session not found", _status: 404 };
});
route("POST", "/api/chat/message", (body) => {
  const r = chat.postMessage(body);
  return r.error ? { ...r, _status: 400 } : r;
});
route("POST", "/api/chat/session/pin-to-hud", (body) => chat.pinToHud(body.id, body.pinned !== false));

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

    // Server-Sent Events stream (the cross-device / vision event channel).
    if (req.method === "GET" && pathname === "/api/events") {
      const detach = subscribe(res);
      req.on("close", detach);
      return;
    }

    const handler = ROUTES[`${req.method} ${pathname}`];
    if (!handler) return json(res, 404, { error: "unknown route", route: `${req.method} ${pathname}` });

    try {
      const body = req.method === "POST" ? await readBody(req) : {};
      const query = Object.fromEntries(url.searchParams.entries());
      const ctx = { base_url: `http://${req.headers.host || "127.0.0.1"}` };
      const result = await handler(body, query, ctx);
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
  loadPersistedScheduler();
  loadPersistedContracts();
  loadPersistedSelfExt();
  loadPersistedHud();
  // Scheduler tick loop — fires due tasks unattended (high-risk tasks park as
  // pending_approval inside runTask).
  setInterval(() => {
    scheduler.tick({ ctx: { runScenario: (s) => runScenario(s, { base_url: `http://127.0.0.1:${process.env.PORT || 4007}` }) } }).catch(() => {});
  }, 30000);
  const port = Number(process.env.PORT) || 4007;
  createApp().listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`TFNK Agent OS v0.8 listening on http://localhost:${port} — HUD at /hud`);
  });
}
