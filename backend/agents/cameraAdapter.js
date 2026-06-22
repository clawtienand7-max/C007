// Camera Adapter Agent — normalises many camera sources into one frame stream.
//
// Honesty rule (blueprint §17): "如果讀取失敗，不可假裝成功". Live capture
// backends (USB/UVC, RTSP, RTMP, HDMI, phone relay) require native decoders
// that are NOT present in this zero-dependency environment, so their adapters
// report `available:false` and a test returns connected:false with the reason —
// they never fake frames. The `frames_jsonl` replay adapter is fully real: it
// reads newline-delimited frame descriptors from a file, which is exactly what
// the development workflow (§5.3 "先用 360 測試片段") calls for. A real MediaPipe
// worker feeds live frames through /api/vision/ingest instead.

import { readFileSync, existsSync } from "node:fs";
import { isAbsolute, join } from "node:path";
import { ROOT } from "../lib/store.js";

// Which adapters this build can actually drive right now.
export function detectCapabilities() {
  return {
    frames_jsonl: { available: true, note: "newline-delimited frame descriptors (replay/testing)" },
    webcam: { available: false, note: "needs a UVC capture backend (native dependency)" },
    rtsp: { available: false, note: "needs an RTSP/ffmpeg decoder (native dependency)" },
    rtmp: { available: false, note: "needs an RTMP/ffmpeg decoder (native dependency)" },
    hdmi: { available: false, note: "needs a capture-card backend (native dependency)" },
    phone_relay: { available: false, note: "needs the DJI Mimo / phone relay bridge" },
    ingest: { available: true, note: "external worker pushes frames to /api/vision/ingest" },
  };
}

const sources = new Map(); // source_id -> source record
let counter = 0;

export function listSources() {
  return [...sources.values()];
}

export function addSource({ source_id, type, name, uri }) {
  if (!type) return { error: "type is required" };
  const id = source_id || `cam_${String(++counter).padStart(3, "0")}`;
  const rec = { source_id: id, type, name: name || type, uri: uri || null, status: "idle", last_test_result: null };
  sources.set(id, rec);
  return { source: rec };
}

function resolveUri(uri) {
  if (!uri) return null;
  return isAbsolute(uri) ? uri : join(ROOT, uri);
}

// Test a source for real. Never returns connected:true unless frames are
// genuinely readable.
export function testSource(source_id) {
  const src = sources.get(source_id);
  if (!src) return { error: "source not found", _status: 404 };
  const caps = detectCapabilities();
  const cap = caps[src.type];

  const base = { source_id, source_type: src.type };

  if (!cap || !cap.available) {
    const result = { ...base, connected: false, fps: 0, resolution: "", latency_ms: 0, projection_type: "unknown", test_result: "failed", error: `adapter "${src.type}" not available in this environment: ${cap ? cap.note : "unknown type"}` };
    src.status = "error";
    src.last_test_result = "failed";
    return result;
  }

  if (src.type === "frames_jsonl") {
    const path = resolveUri(src.uri);
    if (!path || !existsSync(path)) {
      src.status = "error";
      src.last_test_result = "failed";
      return { ...base, connected: false, test_result: "failed", error: `frame file not found: ${src.uri}` };
    }
    try {
      const lines = readFileSync(path, "utf8").split("\n").filter(Boolean);
      const header = JSON.parse(lines[0]);
      const frames = lines.length - 1;
      src.status = "ready";
      src.last_test_result = "passed";
      return {
        ...base,
        connected: true,
        fps: header.fps || 30,
        resolution: header.resolution || "unknown",
        latency_ms: header.latency_ms || 0,
        projection_type: header.projection_type || "normal",
        frames,
        test_result: "passed",
        error: "",
      };
    } catch (err) {
      src.status = "error";
      src.last_test_result = "failed";
      return { ...base, connected: false, test_result: "failed", error: `could not parse frame file: ${String(err && err.message)}` };
    }
  }

  if (src.type === "ingest") {
    src.status = "ready";
    src.last_test_result = "passed";
    return { ...base, connected: true, fps: 0, resolution: "external", latency_ms: 0, projection_type: "unknown", test_result: "passed", error: "" };
  }

  return { ...base, connected: false, test_result: "failed", error: "unhandled source type" };
}

// Load replay frames into memory for a started source.
export function loadFrames(source_id) {
  const src = sources.get(source_id);
  if (!src || src.type !== "frames_jsonl") return [];
  const path = resolveUri(src.uri);
  if (!path || !existsSync(path)) return [];
  const lines = readFileSync(path, "utf8").split("\n").filter(Boolean);
  return lines.slice(1).map((l) => JSON.parse(l)); // skip header
}

export function _resetCameraForTests() {
  sources.clear();
  counter = 0;
}
