# TFNK Agent OS — Operations Manual (OM)

> **OM = the single durable record of what TFNK is, what it can do, and what is
> proven to work.** Updated as the system is built. Last updated: **2026-06-22**.

This document is the operating memory for TFNK Agent OS. It consolidates every
build (Phases 1–3, V0.4, V0.5, V0.7), the full API surface, the safety model,
the honesty boundaries, and the latest real-world verification results.

---

## 0. The iron rule (never broken)

**Every button → a registered action → a real API → a real test → a trace.**

Nothing is decorative. Nothing fakes success. A capability TFNK cannot perform
in this environment is **honestly reported as blocked / pending / unavailable**,
never pretended. Risky actions are **permission-gated**, not auto-executed.

- ❌ a button with no live backend → automatically **disabled** in the UI
- ❌ "completed" with no evidence → the Verifier returns `verified:false`
- ❌ hardcode / fake success in a delivery → **rejected**
- ❌ install unknown code / rewrite TFNK unattended → **blocked, needs approval**

---

## 1. Status snapshot (2026-06-22)

| Metric | Value |
| --- | --- |
| Version | **0.7.0** |
| Unit tests (`npm test`) | **70 / 70 passing** |
| Real-world smoke (`npm run smoke`) | **42 / 42 checks passed** |
| UI audit (`npm run audit`) | **0 genuine problems** (37 connected, ~16 client-only, 1 declared-pending) |
| Registered actions | 39 |
| Dependencies | **0** (Node ≥ 20 built-ins only) |
| CI | GitHub Actions runs suite + audit on Node 20 & 22 |

Run `npm run smoke` to regenerate the live checklist; `npm test` for units;
`npm run audit` for the no-fake-UI report.

---

## 2. Build history & capabilities

### Phase 1 — Foundation
Action Registry · UI Control Map · UI Audit Agent (no-fake-UI) · Intent
Classifier · Task Planner (verify-per-step) · Execution Engine · Verifier
(evidence-gated) · Repair Agent (permission-gated) · real LOOP state machine ·
Emergency Stop · Permission Controller · Test Center · Trace/Logs.

### Phase 2 — Autonomy & Memory
Master Orchestrator (`/api/agent/run`: understand→plan→execute→verify→report) ·
Report Generator · Memory Center (project knowledge).

### Phase 3 — Computer Use (in-app virtual screen)
`screenshot / click / type` over TFNK's own registered surface; clicks perform
the **real** bound action and verify; refuses disabled / permission-gated controls.

### V0.4 — Cross-Device + Vision
Device identity + capabilities · LAN discovery (UDP) · pairing (6-digit) + trust
tokens · Cross Device Agent (capability-based selection + **real HTTP delegation
between trusted peers**; high-risk gated) · event bus (SSE) · Camera Adapter
Layer (honest capability detection; `frames_jsonl` replay real) · Gesture Action
Mapper + Vision Engine safety pipeline (smoothing → confidence → cooldown → risk
→ permission → execute → verify; emergency-stop is the only critical gesture
allowed to auto-fire).

### V0.5 — Scheduled Delivery Verification
Scheduler (once / interval / cron-lite; run records; retries; run-now;
unattended high-risk → `pending_approval`) · Requirement Contracts (no
definition_of_done ⇒ rejected) · **Delivery Verification** — TFNK is the final
acceptance officer for Codex/Claude (requirement match → diff safety → real
tests → UI/API audit → real usage; hardcode/fake ⇒ reject) · Real Usage Runner ·
Codex/Claude prompt + repair generators.

### V0.7 — Self-Extension & Self-Upgrade
Capability Gap Detector (self-audit) · candidate scoring rubric
(license/maintenance/security/tests/docs/cross-platform; stars minor; unknown
license ⇒ manual review; shell/binary/secret/install-script ⇒ high risk) ·
Research + GitHub Scout (network-gated, honest) · Sandbox Inspector (static;
install permission-gated, not executed here) · Self-Upgrade Orchestrator
(delegate=high, apply/rollback=critical; all gated; `apply` records
`applied_pending_merge` and **never auto-rewrites TFNK source**).

### Declared-pending (honestly disabled)
- **Phase 4** — Workflow Canvas (`workflow.run`, `implemented:false`)
- **Phase 5** — Engineering agent (issue→branch→edit→test→PR→rollback)

---

## 3. Honesty boundaries (zero-dep, headless, network-restricted)

These are deliberate, documented limits — TFNK owns the real, tested logic and
**delegates the hardware/network/self-modify edges to an external worker or a
human**, never faking them:

| Capability | In this build | Real path |
| --- | --- | --- |
| MediaPipe / live camera (USB/RTSP/RTMP/HDMI) | adapters report `available:false`; gesture **pipeline** is real and tested | external worker pushes frames to `POST /api/vision/ingest` |
| Delivery from a live Codex/Claude PR | delivery is *described* to intake; verification runs **real** tests + usage | wire to GitHub PR fetch in a networked env |
| Web / GitHub research fetch | `honest_status: blocked` (no_network); **scoring is real** | inject a fetcher / run with network |
| Sandbox install of a package | statically inspected + permission-gated; **not executed** | external networked sandbox runner |
| `self.upgrade.apply` | records `applied_pending_merge` + rollback plan | merge the verified branch via PR/CI |

---

## 4. API surface (P0 + V0.4/V0.5/V0.7)

**Meta:** `GET /api/health` · `/api/actions` · `/api/ui-control-map`
**Agent:** `POST /api/agent/session|plan|step/run|verify|repair|audit|run` · `GET /api/agent/session`
**Memory:** `POST /api/memory/write` · `GET /api/memory/search`
**Computer Use:** `POST /api/computer/screenshot|click|type`
**LOOP/Safety:** `POST /api/loop/run|stop` · `GET /api/loop/status` · `POST /api/emergency-stop` · `/api/loop/clear-emergency`
**Permissions/Logs/Tests:** `GET /api/permissions|logs|tests` · `POST /api/permissions/decide` · `POST /api/tests/run`
**Cross-device:** `GET /api/device/info|capabilities` · `GET /api/devices` · `POST /api/devices/discover|announce|pair|trust|delegate-task` · `GET /api/devices/status|tasks`
**Camera/Vision:** `GET /api/camera/sources|status` · `POST /api/camera/source/add|test` · `/api/camera/start|stop` · `POST /api/vision/start|stop|ingest|replay|calibrate` · `GET /api/vision/status|gestures/latest|events`
**Gestures/Events:** `GET /api/gestures` · `POST /api/gestures/map|test|enable|disable` · `GET /api/events` (SSE) · `/api/events/recent`
**Scheduler:** `POST/GET /api/scheduler/tasks` · `POST /api/scheduler/tasks/run-now|enable|disable|delete` · `GET /api/scheduler/runs|run`
**Contracts/Delivery:** `POST/GET /api/contracts` · `POST /api/contracts/codex-prompt|claude-prompt` · `POST /api/deliveries/intake|verify|accept|reject|request-repair` · `GET /api/deliveries` · `POST /api/real-usage/run`
**Self-extension:** `POST /api/self/gaps/detect` · `POST/GET /api/self/gaps` · `POST /api/self/research/run` · `/api/self/github/search|evaluate-repo` · `POST/GET /api/self/skills*` · `POST /api/self/sandbox/create|inspect|install|audit|destroy` · `POST/GET /api/self/upgrade/proposal|proposals` · `POST /api/self/upgrade/delegate|verify|request-approval|apply|rollback`

---

## 5. Safety / risk model

| Risk | Behaviour |
| --- | --- |
| low | execute directly |
| medium | execute with UI feedback / logging |
| high | **permission request** before acting (e.g. repair, sandbox install, delegate) |
| critical | **explicit approval**; emergency-stop is the only critical that auto-fires for safety (`apply`/`rollback` are gated) |

Gestures, cross-device delegation, and self-upgrade all resolve through the
**same** Action Registry + Permission Controller — no path bypasses risk gating.

---

## 6. How to run & verify

```bash
npm start        # http://localhost:4007 — full UI (all centers/tabs)
npm test         # 70 unit tests
npm run smoke    # 42 real-world end-to-end checks (boots the app)
npm run audit    # no-fake-UI report (exits non-zero on genuine problems)
```

---

## 7. Latest real-world smoke result (2026-06-22) — 42/42 PASS

Foundation: health · actions · ui-control-map · audit(0 problems) · session ·
plan · step-run · verify(rejects no-evidence) · repair · autonomous-run ·
memory · computer screenshot/click/(refuses gated) · loop run/stop ·
emergency-stop+clear · permissions · logs · tests-inventory.
Cross-device: device-info · announce+pair+trust · **real HTTP delegation** ·
high-risk gated.
Vision: rtsp honestly unavailable · replay readable · **gesture pipeline
(emergency executed, high-risk queued)** · mappings.
V0.5: scheduler create+run-now · contract · delivery intake/verify+accept ·
hardcode-diff rejected · real-usage runner.
V0.7: gap detect · research honest-blocked · scout scoring · sandbox gated ·
proposal+gated-delegate · **apply never auto-rewrites source** ·
Test Center → **pass 70/70**.

---

## 8. Open items / roadmap

- Phase 4 — Workflow Canvas (trigger/agent/tool/approval/retry/schedule nodes).
- Phase 5 — Engineering agent (issue → branch → edit → test → PR → rollback).
- Networked deployments: wire live camera/MediaPipe worker, GitHub PR fetch for
  delivery, real sandbox runner, and PR/CI-based self-upgrade merge.
