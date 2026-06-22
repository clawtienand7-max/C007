# TFNK Agent OS — V0.8 (OM HUD Command Interface)

> A **verifiable, controllable, repairable** computer-agent foundation.
> Not a chatbot with decorative buttons. The iron rule of this codebase:
>
> **Every button → a registered action → a real API → a real test → a trace.**

This implements the *TFNK Agent vNext+* blueprint (Phases 1–3) plus the *V0.4
Cross-Device Vision*, *V0.5 Scheduled Delivery Verification* and *V0.7
Self-Extension* builds. It is fully runnable today with **zero external
dependencies** (Node ≥ 20 only — no `npm install` required) so it works in
restricted/offline environments.

---

## What's in this build

| Module | Status | Where |
| --- | --- | --- |
| **Action Registry** | ✅ | `data/action_registry.json` |
| **UI Control Map** | ✅ | `data/ui_control_map.json` |
| **UI Audit Agent** (finds fake UI) | ✅ | `backend/agents/uiAudit.js` |
| **Intent Classifier** | ✅ | `backend/agents/intent.js` |
| **Task Planner** (verify-per-step) | ✅ | `backend/agents/planner.js` |
| **Verification Agent** (evidence-gated) | ✅ | `backend/agents/verifier.js` |
| **Repair Agent** (permission-gated) | ✅ | `backend/agents/repair.js` |
| **LOOP state machine** (real idle→running→completed/stopped) | ✅ | `backend/loop.js` |
| **Safety / Emergency Stop** | ✅ | `backend/loop.js`, `/api/emergency-stop` |
| **Permission Controller** | ✅ | `backend/lib/store.js`, `/api/permissions/*` |
| **Test Center** (runs the real suite) | ✅ | `backend/agents/testCenter.js` |
| **Trace Viewer / Logs** | ✅ | `/api/logs`, right dock in UI |
| **Agent Command Center UI** | ✅ | `frontend/` |
| **Master Orchestrator** (autonomous run + Report Generator) | ✅ Phase 2 | `backend/agents/orchestrator.js` |
| **Memory Center** (project knowledge) | ✅ Phase 2 | `backend/lib/memory.js` |
| **Computer Use Agent** (in-app virtual screen) | ✅ Phase 3 | `backend/agents/computerUse.js` |
| **Device layer** (identity + capabilities + peer registry) | ✅ V0.4 | `backend/lib/device.js` |
| **LAN discovery** (UDP announce/listen) | ✅ V0.4 | `backend/lib/discovery.js` |
| **Pairing + trust tokens** (6-digit code) | ✅ V0.4 | `backend/lib/device.js` |
| **Cross Device Agent** (node select + real HTTP delegation) | ✅ V0.4 | `backend/agents/crossDevice.js` |
| **Event bus** (SSE + ring buffer) | ✅ V0.4 | `backend/lib/events.js` |
| **Camera Adapter Layer** (capability detection + replay) | ✅ V0.4 | `backend/agents/cameraAdapter.js` |
| **Gesture mappings + Action Mapper** (safety-gated) | ✅ V0.4 | `backend/lib/gestures.js` |
| **Vision Engine** (smoothing → cooldown → risk → permission → verify) | ✅ V0.4 | `backend/agents/vision.js` |
| **Vision Control Center + Devices UI** | ✅ V0.4 | `frontend/` |
| **Scheduler Service** (once / interval / cron + runs + retries) | ✅ V0.5 | `backend/lib/scheduler.js` |
| **Requirement Contracts** (acceptance standard) | ✅ V0.5 | `backend/lib/contracts.js` |
| **Delivery Verification** (Codex/Claude acceptance officer) | ✅ V0.5 | `backend/agents/delivery.js` |
| **Real Usage Runner** (proves a feature is usable) | ✅ V0.5 | `backend/agents/realUsage.js` |
| **Codex/Claude prompt + repair generators** | ✅ V0.5 | `backend/agents/promptGen.js` |
| **Scheduler + Delivery Acceptance UI** | ✅ V0.5 | `frontend/` |
| **Capability Gap Detector** (self-audit) | ✅ V0.7 | `backend/lib/selfExt.js` |
| **Candidate scoring rubric** (license/maintenance/security/…) | ✅ V0.7 | `backend/lib/selfExt.js` |
| **Research + GitHub Scout** (network-gated, honest) | ✅ V0.7 | `backend/agents/research.js` |
| **Sandbox Inspector** (static; gated install) | ✅ V0.7 | `backend/agents/sandbox.js` |
| **Self-Upgrade Orchestrator** (gated delegate/apply/rollback) | ✅ V0.7 | `backend/agents/selfUpgrade.js` |
| **Self-Upgrade Center UI** | ✅ V0.7 | `frontend/` |
| Live web/GitHub fetch + real package install | 🔌 gated/pluggable (network + approval required) | honest blocked status |
| **OM HUD interface** (`/hud`: rings, OM graph, telemetry, weather, chat) | ✅ V0.8 | `frontend/hud.*`, `backend/lib/{telemetry,omGraph,weather,chat,hud}.js` |
| GPU/disk/throughput telemetry · HK weather · chat AI reply | 🔌 honest unavailable / real-intent reply (no LLM) | metrics agent · network · LLM backend |
| Live USB/RTSP/RTMP/HDMI capture + MediaPipe model | 🔌 pluggable (external worker via `/api/vision/ingest`) | honest capability detection |
| Workflow Canvas | ⏳ Phase 4 (declared, disabled) | registry `implemented:false` |

Future-phase controls are **honestly disabled** in the UI (greyed out, labelled
`no backend`) instead of pretending to work.

### V0.4 honesty boundary (zero-dependency, headless)

This build has **no external dependencies**, so it cannot run MediaPipe or open a
real camera/RTSP stream here — and the project's iron rule forbids faking. So:

- **Gesture recognition runs in an external worker** (e.g. MediaPipe) that pushes
  per-frame results to `POST /api/vision/ingest`. TFNK owns the **safety
  pipeline** (temporal smoothing → confidence → cooldown → Action Registry →
  risk/permission gate → execute → verify), which is fully real and tested.
- **Live capture adapters** (USB/UVC, RTSP, RTMP, HDMI, phone relay) report
  `available:false` with a reason and a test returns `connected:false` — they
  never emit fake frames. The **`frames_jsonl` replay adapter is fully real** and
  drives the pipeline from a file (see `data/samples/gestures_demo.jsonl`).
- **Cross-device delegation is real** over HTTP between trusted peers (tested with
  two live loopback instances). UDP discovery is best-effort; its packet
  parse/register handlers are pure and tested.

---

## Quick start

```bash
npm start            # serve UI + API on http://localhost:4007
npm test             # run the real test suite (85 tests)
npm run smoke        # real-world end-to-end checks (48 checks, boots the app)
npm run audit        # run the UI Audit Agent from the CLI
```

See **[OM.md](OM.md)** — the Operations Manual / operating memory — for the full
consolidated record (every build, API, safety model, honesty boundaries, and the
latest dated verification snapshot).

Open <http://localhost:4007> for the Agent Command Center.

---

## The "no fake UI" guarantee, mechanically

1. Every interactive control in `frontend/index.html` carries `data-action="..."`.
2. On load, `frontend/app.js` fetches `/api/actions` and **disables any control**
   whose action is not `connected` (or `permission_required`). A button with no
   live backend literally cannot be clicked.
3. The **UI Audit Agent** (`/api/agent/audit`) scans the real HTML, reconciles
   each control against the registry, the control map, and the *live route table*
   (`backend/lib/registry.js → LIVE_ROUTES`), and classifies every element:
   `connected | missing_action_id | missing_backend | missing_test |
   fake_or_unmapped | broken | client_only`.
4. Client-only controls (tab switches, refresh) must declare `data-client="true"`
   — they're explicitly excluded, never silently ignored.

The audit distinguishes three honest non-problems from genuine fakes:
`connected`, `client_only` (declared with `data-client`), and `pending_phase`
(declared `implemented:false` future work). Only genuine fakes
(`missing_action_id / missing_backend / missing_test / fake_or_unmapped /
broken`) fail the audit and CI.

Run `npm run audit` to see the live report. Current build:
**37 connected, ~16 client-only, 1 declared-pending (Phase 4), 0 genuine problems.**

---

## Agent workflow

```
goal → /api/agent/session   (Intent Classifier attaches structured intent + risk)
     → /api/agent/plan       (Planner: every step has a verification_method)
     → /api/agent/step/run   (Execution Engine: tools do real work)
     → /api/agent/verify     (Verifier: NO evidence ⇒ verified:false)
     → /api/agent/repair      (Repair: source edits ⇒ permission request)
```

Hard rules baked into code:

- **Verifier** returns `verified:false` unless it has concrete evidence. Seeing
  the string "success" is not proof.
- **Repair Agent** never silently edits source. It emits a `permission` request
  (risk `high`/`critical`) that a human approves/denies in the Permission Queue.
- **LOOP** is a genuine state machine that iterates real audit work, converges or
  hits `max_iterations`, and respects **Emergency Stop**.

---

## API (P0)

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | liveness |
| GET | `/api/actions` | registry + computed status per action |
| GET | `/api/ui-control-map` | screens + element→action status |
| POST | `/api/agent/session` | create session, classify intent |
| GET | `/api/agent/session` | list / fetch session(s) |
| POST | `/api/agent/plan` | generate verifiable plan |
| POST | `/api/agent/step/run` | execute a step |
| POST | `/api/agent/verify` | evidence-gated verification |
| POST | `/api/agent/repair` | propose minimal safe fix (gated) |
| POST | `/api/agent/audit` | run UI Audit Agent |
| POST | `/api/agent/run` | **autonomous** understand→plan→execute→verify→report |
| POST | `/api/memory/write` | save a rule / fact / fix to project memory |
| GET | `/api/memory/search` | recall project memory |
| POST | `/api/computer/screenshot` | virtual screen snapshot of the registered surface |
| POST | `/api/computer/click` | click a real bound control (refuses disabled/gated) |
| POST | `/api/computer/type` | type into a virtual field (write-then-read verify) |
| POST | `/api/loop/run` | start LOOP |
| GET | `/api/loop/status` | LOOP state |
| POST | `/api/loop/stop` | stop LOOP |
| POST | `/api/emergency-stop` | engage emergency stop |
| GET | `/api/permissions` | list permission requests |
| POST | `/api/permissions/decide` | approve / deny |
| GET | `/api/logs` | trace |
| GET | `/api/tests` | test coverage inventory |
| POST | `/api/tests/run` | run the real test suite, return summary |

### V0.4 — cross-device + vision

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/device/info` · `/api/device/capabilities` | this node's identity / capabilities |
| GET | `/api/devices` | self + discovered peers |
| POST | `/api/devices/discover` · `/api/devices/announce` | broadcast / register a peer |
| POST | `/api/devices/pair` · `/api/devices/trust` | 6-digit pairing → trust token |
| POST | `/api/devices/delegate-task` | delegate an action to a trusted peer (HTTP) |
| GET | `/api/camera/sources` | adapter capabilities + sources |
| POST | `/api/camera/source/add` · `/source/test` · `/start` | manage + test a camera source |
| POST | `/api/vision/start` · `/stop` · `/ingest` · `/replay` | vision session + frame pipeline |
| GET | `/api/vision/status` · `/gestures/latest` · `/events` | vision state + decisions |
| GET | `/api/gestures` · POST `/api/gestures/map` `/test` `/enable` `/disable` | gesture→action mappings |
| GET | `/api/events` (SSE) · `/api/events/recent` | live event stream |

### V0.5 — scheduler + delivery acceptance

| Method | Route | Purpose |
| --- | --- | --- |
| POST/GET | `/api/scheduler/tasks` | create / list scheduled tasks |
| POST | `/api/scheduler/tasks/run-now` · `/enable` · `/disable` · `/delete` | manage a task |
| GET | `/api/scheduler/runs` · `/api/scheduler/run` | task run records |
| POST/GET | `/api/contracts` | create / list requirement contracts |
| POST | `/api/contracts/codex-prompt` · `/claude-prompt` | generate delegation prompts |
| POST | `/api/deliveries/intake` | receive a Codex/Claude/manual delivery |
| POST | `/api/deliveries/verify` | run the acceptance pipeline (real tests + usage) |
| POST | `/api/deliveries/accept` · `/reject` · `/request-repair` | acceptance decision |
| POST | `/api/real-usage/run` | execute a real-usage scenario |

### V0.7 — self-extension & self-upgrade

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/self/gaps/detect` · POST/GET `/api/self/gaps` | detect / create / list capability gaps |
| POST | `/api/self/research/run` | research a gap (honest about network limits) |
| POST | `/api/self/github/search` · `/evaluate-repo` | score candidate libraries (real rubric) |
| POST/GET | `/api/self/skills/create` · `/api/self/skills` | package + list skills |
| POST | `/api/self/sandbox/create` · `/inspect` · `/install` · `/audit` · `/destroy` | sandbox (gated install) |
| POST/GET | `/api/self/upgrade/proposal` · `/proposals` | upgrade proposals |
| POST | `/api/self/upgrade/delegate` · `/verify` · `/request-approval` · `/apply` · `/rollback` | gated upgrade lifecycle |

---

## Architecture

```
backend/
  server.js            HTTP server, route table, static hosting (zero deps)
  loop.js              LOOP state machine + emergency stop
  lib/
    store.js           in-memory state + best-effort JSON persistence
    registry.js        registry/control-map loaders + LIVE_ROUTES + status rules
    memory.js          Memory Center (project knowledge) [Phase 2]
  agents/
    intent.js          Intent Classifier
    planner.js         Task Planner
    executor.js        Execution Engine (shared step runner)
    orchestrator.js    Master Orchestrator + Report Generator [Phase 2]
    uiAudit.js         UI Audit Agent
    verifier.js        Verification Agent
    repair.js          Repair Agent (permission-gated)
    computerUse.js     Computer Use Agent (in-app virtual screen) [Phase 3]
    crossDevice.js     Cross Device Agent — node select + delegation [V0.4]
    cameraAdapter.js   Camera Adapter Layer (capability detection + replay) [V0.4]
    vision.js          Vision Engine — gesture safety pipeline [V0.4]
    realUsage.js       Real Usage Runner [V0.5]
    delivery.js        Delivery Verification (acceptance officer) [V0.5]
    promptGen.js       Codex/Claude prompt + repair generators [V0.5]
    research.js        Research Agent + GitHub Scout (gated) [V0.7]
    sandbox.js         Sandbox Inspector (gated install) [V0.7]
    selfUpgrade.js     Self-Upgrade Orchestrator (gated) [V0.7]
    testCenter.js      runs the real test suite as a child process
  lib/
    device.js          device identity + peers + pairing/trust [V0.4]
    discovery.js       UDP LAN discovery [V0.4]
    events.js          event bus (SSE + ring buffer) [V0.4]
    gestures.js        gesture mappings + Gesture Action Mapper [V0.4]
    scheduler.js       Scheduler Service (once/interval/cron) [V0.5]
    contracts.js       Requirement Contract store [V0.5]
    selfExt.js         gaps + candidate scoring + skills + proposals [V0.7]
  cli/audit.js         `npm run audit`
data/
  action_registry.json action source of truth
  ui_control_map.json  UI→action bindings
  gesture_mappings.json gesture→action bindings [V0.4]
  samples/             gestures_demo.jsonl replay fixture [V0.4]
frontend/              Command Center + Vision + Devices + Scheduler + Delivery + Self-Upgrade
test/                  api / agents / phase23 / v04 / v05 / v07 (.test.js) — 70 tests, all green
.github/workflows/     ci.yml — runs the suite + audit on Node 20 & 22
```

## Roadmap (from the blueprint)

- **Phase 1** — ✅ Foundation: registry, audit, planner, verifier, repair, LOOP, tests.
- **Phase 2** — ✅ Master Orchestrator (autonomous `agent.run` + Report Generator) and Memory Center.
- **Phase 3** — ✅ Computer Use layer (screenshot / click / type / observe / verify), in-app virtual screen.
- **V0.4** — ✅ Cross-device LAN collaboration (discovery / pairing / trust / delegation) + safe gesture control (camera adapters, gesture→action mapper, vision pipeline).
- **V0.5** — ✅ Scheduler (once/interval/cron) + Requirement Contracts + Delivery Verification (TFNK as acceptance officer for Codex/Claude) + Real Usage Runner.
- **V0.7** — ✅ Self-extension: capability-gap detection, candidate scoring, research/scout, sandbox inspection, and a permission-gated self-upgrade lifecycle.
- **V0.8** — ✅ OM HUD Command Interface at `/hud`: rotating concentric rings, OM relation graph, real telemetry, HK weather, chat dock + frameless transparent conversation table.
- **Phase 4** — ⏳ Workflow Canvas (trigger / agent / tool / approval / retry nodes).
- **Phase 5** — ⏳ Engineering agent (issue → branch → edit → test → PR → rollback).

### V0.7 self-upgrade honesty boundary

TFNK may propose its own upgrades but **never installs unknown code or rewrites
itself unattended**. In this zero-dep, network-restricted environment:
- **Research / GitHub fetch** is injectable; with no network it returns
  `honest_status: blocked` (reason `no_network`) and **fabricates nothing**.
  Candidate **scoring** is real and deterministic (stars are a minor signal;
  unknown license ⇒ `needs_manual_review`; shell/binary/secret/install-script ⇒ high risk).
- **Sandbox install** is statically inspected (dangerous lifecycle scripts /
  network calls / secret access detected) and **permission-gated**; it is not
  executed here — a manifest is written for an external networked runner.
- **`delegate` is high-risk and `apply`/`rollback` are critical** — all
  permission-gated. `apply` (even when approved) records the verified proposal +
  rollback plan as `applied_pending_merge`; it does **not** auto-modify TFNK's
  source. The real merge happens via PR/CI.

### V0.5 delivery-acceptance honesty boundary

TFNK is the **final acceptance officer**: a Codex/Claude delivery is a *candidate*
until it passes requirement-match → diff-safety → **real tests** → UI/API audit →
**real usage**. This build can't fetch a live PR here, so a delivery is described
to `/api/deliveries/intake` (changed files + diff + report); verification runs the
**real** test suite and a **real** usage scenario and records evidence. Forbidden
patterns (hardcode / fake success / skipped tests) in the diff force a `reject`;
nothing is accepted without passing evidence.

### Computer Use scope & honesty

Phase 3 Computer Use operates on TFNK's **own registered UI surface** (the action
registry + control map + live state), not an OS-level screen grab. A "click"
performs the **real** action bound to the element and is verified against real
state. It refuses to click disabled controls, and never auto-clicks
permission-gated (high-risk) controls — it reports `blocked` instead. OS-level
screen control would require native dependencies and is out of scope for this
zero-dependency foundation.
