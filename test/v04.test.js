import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import { createApp } from "../backend/server.js";
import { _resetDevicesForTests } from "../backend/lib/device.js";
import { _resetEventsForTests } from "../backend/lib/events.js";
import { _resetCameraForTests } from "../backend/agents/cameraAdapter.js";
import { _resetVisionForTests } from "../backend/agents/vision.js";
import { _resetGesturesForTests, mapToAction } from "../backend/lib/gestures.js";

let A, B, baseA, baseB;

before(async () => {
  _resetDevicesForTests();
  _resetEventsForTests();
  _resetCameraForTests();
  _resetVisionForTests();
  _resetGesturesForTests();
  A = createApp();
  B = createApp();
  await new Promise((r) => A.listen(0, r));
  await new Promise((r) => B.listen(0, r));
  baseA = `http://127.0.0.1:${A.address().port}`;
  baseB = `http://127.0.0.1:${B.address().port}`;
});
after(() => {
  A && A.close();
  B && B.close();
});

const get = (base, p) => fetch(base + p).then((r) => r.json());
const post = (base, p, body) =>
  fetch(base + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then((r) => r.json());

test("device info reports identity + capabilities", async () => {
  const info = await get(baseA, "/api/device/info");
  assert.ok(info.node_id);
  assert.ok(["macOS", "Windows", "Linux"].includes(info.platform));
  assert.ok(Array.isArray(info.capabilities));
});

test("test_devices_discover: announce registers a foreign peer", async () => {
  const announce = { proto: "tfnk-discovery/1", node_id: "tfnk_peer_b", device_name: "Peer B", platform: "Windows", ip: "127.0.0.1", port: B.address().port, capabilities: ["heavy_compute", "test_runner"] };
  const r = await post(baseA, "/api/devices/announce", announce);
  assert.equal(r.peer.node_id, "tfnk_peer_b");
  const list = await get(baseA, "/api/devices");
  assert.ok(list.peers.some((p) => p.node_id === "tfnk_peer_b"));
});

test("test_devices_pair: pairing requires the correct 6-digit code", async () => {
  const begin = await post(baseA, "/api/devices/pair", { node_id: "tfnk_peer_b" });
  assert.match(begin.pairing_code, /^\d{6}$/);
  const wrong = await post(baseA, "/api/devices/trust", { node_id: "tfnk_peer_b", code: "000000" });
  // (1-in-a-million chance the random code is 000000; treat both as defined behaviour)
  if (begin.pairing_code !== "000000") assert.equal(wrong.trusted, false);
  const ok = await post(baseA, "/api/devices/trust", { node_id: "tfnk_peer_b", code: begin.pairing_code });
  assert.equal(ok.trusted, true);
  assert.ok(ok.trust_token);
});

test("cross-device delegation runs a low-risk action on the real peer over HTTP", async () => {
  // peer B is announced + trusted from the previous tests (shared module state)
  const r = await post(baseA, "/api/devices/delegate-task", { action_id: "ui.audit", to_node: "tfnk_peer_b" });
  assert.equal(r.to_node, "tfnk_peer_b");
  assert.equal(r.status, "completed");
  assert.ok(r.output.report, "peer should have returned a real audit report");
});

test("cross-device delegation refuses to auto-run a high-risk action", async () => {
  const r = await post(baseA, "/api/devices/delegate-task", { action_id: "agent.repair", to_node: "tfnk_peer_b" });
  assert.equal(r.requires_permission, true);
  assert.equal(r.status, "awaiting_permission");
});

test("camera adapter is honest: live backends report unavailable, never fake frames", async () => {
  const rtsp = await post(baseA, "/api/camera/source/add", { type: "rtsp", name: "fake cam", uri: "rtsp://1.2.3.4/live" });
  const test = await post(baseA, "/api/camera/source/test", { source_id: rtsp.source.source_id });
  assert.equal(test.connected, false);
  assert.equal(test.test_result, "failed");
  assert.match(test.error, /not available/i);
});

test("test_camera_start: frames_jsonl replay source is genuinely readable", async () => {
  const add = await post(baseA, "/api/camera/source/add", { type: "frames_jsonl", name: "demo", uri: "data/samples/gestures_demo.jsonl" });
  const started = await post(baseA, "/api/camera/start", { source_id: add.source.source_id });
  assert.equal(started.started, true);
  assert.equal(started.test.projection_type, "equirectangular");
  assert.ok(started.test.frames >= 1);
});

test("gesture mapper: low confidence is rejected", () => {
  const d = mapToAction({ gesture_id: "ok_confirm", confidence: 0.5, status: "recognized" });
  assert.equal(d.allowed, false);
  assert.match(d.reason, /confidence/);
});

test("gesture mapper: emergency stop is the only critical gesture allowed to auto-fire", () => {
  const d = mapToAction({ gesture_id: "two_hands_cross_emergency", confidence: 0.97, status: "recognized" });
  assert.equal(d.allowed, true);
  assert.equal(d.action_id, "emergency.stop");
});

test("test_gesture_mapping: high-risk gesture queues a permission instead of firing", () => {
  const d = mapToAction({ gesture_id: "wave_cancel", confidence: 0.96, status: "recognized" });
  assert.equal(d.allowed, false);
  assert.equal(d.requires_confirmation, true);
  assert.ok(d.permission_id);
});

test("test_vision_start: full pipeline replays real frames into safe, gated decisions", async () => {
  _resetVisionForTests();
  _resetGesturesForTests(); // clear cooldowns left by the mapper unit tests above
  const add = await post(baseA, "/api/camera/source/add", { type: "frames_jsonl", name: "demo2", uri: "data/samples/gestures_demo.jsonl" });
  const r = await post(baseA, "/api/vision/replay", { source_id: add.source.source_id });
  const byAction = Object.fromEntries(r.events.map((e) => [e.action_id, e]));
  // emergency stop must have executed and verified
  assert.ok(byAction["emergency.stop"]);
  assert.equal(byAction["emergency.stop"].executed, true);
  assert.equal(byAction["emergency.stop"].verification_result, "passed");
  // high-risk wave_cancel must be queued, not executed
  assert.ok(byAction["agent.repair"]);
  assert.equal(byAction["agent.repair"].executed, false);
});

test("test_vision_stop: a single noisy frame never fires an action (temporal smoothing)", async () => {
  _resetVisionForTests();
  await post(baseA, "/api/vision/start", {});
  const r = await post(baseA, "/api/vision/ingest", { gesture_id: "two_hands_cross_emergency", confidence: 0.99 });
  assert.equal(r.stable, false); // needs multiple stable frames
  await post(baseA, "/api/vision/stop", {});
});

test("vision ingest is ignored when no session is active", async () => {
  _resetVisionForTests();
  const r = await post(baseA, "/api/vision/ingest", { gesture_id: "open_palm_stop", confidence: 0.9 });
  assert.equal(r.ignored, true);
});

test("event ring buffer captures emitted events", async () => {
  const r = await get(baseA, "/api/events/recent?since=0&limit=200");
  assert.ok(Array.isArray(r.events));
});
