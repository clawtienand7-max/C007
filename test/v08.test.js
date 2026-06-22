import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import { createApp } from "../backend/server.js";
import { getHongKongWeather } from "../backend/lib/weather.js";
import { _resetChatForTests } from "../backend/lib/chat.js";
import { _resetHudForTests } from "../backend/lib/hud.js";

let S, base;
before(async () => {
  _resetChatForTests();
  _resetHudForTests();
  S = createApp();
  await new Promise((r) => S.listen(0, r));
  base = `http://127.0.0.1:${S.address().port}`;
});
after(() => S && S.close());

const get = (p) => fetch(base + p).then((r) => r.json());
const post = (p, body) =>
  fetch(base + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then((r) => r.json());

test("test_hud_renders: /hud page is served", async () => {
  const html = await fetch(base + "/hud").then((r) => r.text());
  assert.match(html, /OM HUD/);
  assert.match(html, /hud\.js/);
});

test("test_telemetry_api_returns_schema: real CPU/RAM, structured shape", async () => {
  const r = await get("/api/telemetry/system");
  assert.ok(typeof r.cpu.usage === "number" || r.cpu.usage === null);
  assert.ok(r.memory.total > 0, "memory total should be real");
  assert.ok("available" in r.gpu, "gpu has availability flag");
  assert.ok(r.updatedAt);
});

test("test_gpu_unavailable_not_fake: gpu reports availability honestly", async () => {
  const r = await get("/api/telemetry/gpu");
  assert.ok("available" in r);
  if (!r.available) {
    assert.equal(r.temperature, null);
    assert.ok(r.reason, "must explain why unavailable");
  }
});

test("test_telemetry_refresh: refresh returns fresh timestamp", async () => {
  const a = await post("/api/telemetry/refresh", {});
  assert.ok(a.updatedAt);
  assert.ok(a.memory.total > 0);
});

test("test_om_graph_load: OM core node is at the centre of a real graph", async () => {
  const r = await get("/api/om/graph");
  assert.ok(r.nodes.find((n) => n.id === "om_core" && n.type === "core"));
  assert.ok(r.edges.length > 0);
  assert.ok(r.nodes.find((n) => n.id === "claude") && r.nodes.find((n) => n.id === "codex"));
});

test("test_hk_weather_refresh + test_weather_api_error_state: never fabricated", async () => {
  const r = await get("/api/weather/hong-kong");
  assert.ok("available" in r);
  // In a no-network env available=false with an error; if network exists it's true with data.
  if (!r.available) assert.ok(r.error, "must explain unavailability");
  else assert.ok("temperature_c" in r);
});

test("weather module is honest with no fetcher injected", async () => {
  const r = await getHongKongWeather({ fetchImpl: null });
  assert.equal(r.available, false);
  assert.ok(r.error);
});

test("test_chat_new: new chat session via real API", async () => {
  const r = await post("/api/chat/session/new", { agent: "tfnk" });
  assert.ok(r.session.session_id);
  const list = await get("/api/chat/sessions");
  assert.ok(list.sessions.some((s) => s.session_id === r.session.session_id));
});

test("test_chat_send / test_transparent_chat_send_message: real msg, no fabricated AI", async () => {
  const r = await post("/api/chat/message", { text: "audit the fake ui please" });
  assert.ok(r.session_id);
  assert.equal(r.user.role, "user");
  assert.equal(r.reply.role, "tfnk");
  assert.ok(r.reply.intent.task_type, "reply carries real intent classification");
  assert.match(r.reply.honest_note, /no connected LLM|no AI answer is fabricated/);
});

test("test_hud_toggle_animation: animation state really toggles", async () => {
  const before = (await get("/api/hud/state")).hud.animation;
  const after = (await post("/api/hud/animation/toggle", {})).animation;
  assert.notEqual(before, after);
});

test("test_hud_layout_save: layout persists", async () => {
  const r = await post("/api/hud/layout/save", { layout: { panes: 3 } });
  assert.equal(r.saved, true);
  const got = await get("/api/hud/layout");
  assert.deepEqual(got.layout, { panes: 3 });
});

test("test_action_registry_contains_hud_actions + connected", async () => {
  const r = await get("/api/actions");
  for (const id of ["hud.toggle_animation", "hud.telemetry.refresh", "om.graph.load", "weather.hk.refresh", "chat.new", "chat.message.send", "hud.layout.save"]) {
    const a = r.actions.find((x) => x.id === id);
    assert.ok(a, `missing action ${id}`);
    assert.equal(a.status, "connected", `${id} not connected`);
  }
});

test("test_reduced_motion_supported: HUD css honors prefers-reduced-motion", async () => {
  const css = await fetch(base + "/hud.css").then((r) => r.text());
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /no-anim/);
});

test("test_emergency_stop_still_available: emergency stop action present + connected", async () => {
  const r = await get("/api/actions");
  const es = r.actions.find((a) => a.id === "emergency.stop");
  assert.ok(es && es.status === "connected");
});

test("HUD page still passes the no-fake-UI audit (multi-file scan)", async () => {
  const r = await post("/api/agent/audit", {});
  assert.equal(r.report.fake_or_incomplete, 0, "HUD must introduce no fake UI");
});
