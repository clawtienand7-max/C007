// HUD state — animation on/off, theme, telemetry refresh interval and saved
// layout. Persisted best-effort so the HUD remembers user preferences.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./store.js";

const FILE = join(ROOT, "data", "runtime", "hud.json");

const state = {
  animation: true,
  theme: "sci-fi-dark",
  telemetry_interval_ms: 3000,
  weather_source: "hong-kong",
  layout: null,
};

export function getState() {
  return { ...state };
}

export function toggleAnimation(on) {
  state.animation = typeof on === "boolean" ? on : !state.animation;
  persist();
  return { animation: state.animation };
}

export function updateTheme(patch = {}) {
  if (patch.theme) state.theme = patch.theme;
  if (typeof patch.telemetry_interval_ms === "number") state.telemetry_interval_ms = Math.max(500, patch.telemetry_interval_ms);
  if (patch.weather_source) state.weather_source = patch.weather_source;
  persist();
  return getState();
}

export function getLayout() {
  return { layout: state.layout };
}
export function saveLayout(layout) {
  state.layout = layout || null;
  persist();
  return { saved: true, layout: state.layout };
}

function persist() {
  try {
    mkdirSync(join(ROOT, "data", "runtime"), { recursive: true });
    writeFileSync(FILE, JSON.stringify(state, null, 2));
  } catch {
    /* best-effort */
  }
}
export function loadPersistedHud() {
  try {
    if (existsSync(FILE)) Object.assign(state, JSON.parse(readFileSync(FILE, "utf8")));
  } catch {
    /* ignore */
  }
}
export function _resetHudForTests() {
  Object.assign(state, { animation: true, theme: "sci-fi-dark", telemetry_interval_ms: 3000, weather_source: "hong-kong", layout: null });
}
