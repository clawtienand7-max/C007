# TFNK Agent OS — V0.3 (Agent OS Foundation Build)

> A **verifiable, controllable, repairable** computer-agent foundation.
> Not a chatbot with decorative buttons. The iron rule of this codebase:
>
> **Every button → a registered action → a real API → a real test → a trace.**

This is the Phase 1 / V0.3 foundation from the *TFNK Agent vNext+* blueprint. It
is fully runnable today with **zero external dependencies** (Node ≥ 20 only — no
`npm install` required) so it works in restricted/offline environments.

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
| Workflow Canvas | ⏳ Phase 4 (declared, disabled) | registry `implemented:false` |

Future-phase controls are **honestly disabled** in the UI (greyed out, labelled
`no backend`) instead of pretending to work.

---

## Quick start

```bash
npm start            # serve UI + API on http://localhost:4007
npm test             # run the real test suite (32 tests)
npm run audit        # run the UI Audit Agent from the CLI
```

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

Run `npm run audit` to see the live report. Current foundation:
**17 connected, 9 client-only, 1 declared-pending (Phase 4), 0 genuine problems.**

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
    testCenter.js      runs the real test suite as a child process
  cli/audit.js         `npm run audit`
data/
  action_registry.json action source of truth
  ui_control_map.json  UI→action bindings
frontend/              Agent Command Center (index.html / app.js / styles.css)
test/                  api / agents / phase23 (.test.js) — 32 tests, all green
.github/workflows/     ci.yml — runs the suite + audit on Node 20 & 22
```

## Roadmap (from the blueprint)

- **Phase 1** — ✅ Foundation: registry, audit, planner, verifier, repair, LOOP, tests.
- **Phase 2** — ✅ Master Orchestrator (autonomous `agent.run` + Report Generator) and Memory Center.
- **Phase 3** — ✅ Computer Use layer (screenshot / click / type / observe / verify), in-app virtual screen.
- **Phase 4** — ⏳ Workflow Canvas (trigger / agent / tool / approval / retry nodes).
- **Phase 5** — ⏳ Engineering agent (issue → branch → edit → test → PR → rollback).

### Computer Use scope & honesty

Phase 3 Computer Use operates on TFNK's **own registered UI surface** (the action
registry + control map + live state), not an OS-level screen grab. A "click"
performs the **real** action bound to the element and is verified against real
state. It refuses to click disabled controls, and never auto-clicks
permission-gated (high-risk) controls — it reports `blocked` instead. OS-level
screen control would require native dependencies and is out of scope for this
zero-dependency foundation.
