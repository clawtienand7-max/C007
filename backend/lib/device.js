// Device layer — this node's identity + capabilities, the peer registry, and
// the pairing / trust-token security model for same-LAN collaboration.
//
// Security stance (blueprint §2.3): status/peer listing is open; delegating
// tasks requires a *trusted* peer; high-risk remote actions always require an
// explicit confirmation on top of trust.

import { hostname, platform as osPlatform, networkInterfaces } from "node:os";
import { randomBytes, randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./store.js";

const FILE = join(ROOT, "data", "runtime", "devices.json");

function lanIp() {
  const ifaces = networkInterfaces();
  for (const name of Object.keys(ifaces)) {
    for (const i of ifaces[name] || []) {
      if (i.family === "IPv4" && !i.internal) return i.address;
    }
  }
  return "127.0.0.1";
}

const PLATFORM = osPlatform() === "darwin" ? "macOS" : osPlatform() === "win32" ? "Windows" : "Linux";

// Capabilities are derived from the platform + what this build can actually do.
// macOS/laptop-ish defaults lean to UI/camera; otherwise lean to compute.
function deriveCapabilities() {
  const base = ["agent_planning", "file_access", "test_runner", "verification"];
  if (PLATFORM === "macOS") return [...base, "ui_controller", "camera_input", "gesture_recognition"];
  if (PLATFORM === "Windows") return [...base, "heavy_compute", "terminal", "gpu_worker"];
  return base;
}

const self = {
  node_id: `tfnk_${PLATFORM.toLowerCase()}_${randomUUID().slice(0, 8)}`,
  device_name: hostname(),
  platform: PLATFORM,
  ip: lanIp(),
  port: Number(process.env.PORT) || 4007,
  role: PLATFORM === "Windows" ? ["executor", "gpu_worker", "backend_host"] : ["ui_controller", "camera_input", "planner"],
  status: "online",
  capabilities: deriveCapabilities(),
  version: "0.4.0",
};

const state = {
  peers: new Map(), // node_id -> peer record
  pendingPairings: new Map(), // node_id -> { code, created_at }
  trustTokens: new Map(), // node_id -> token
};

export function deviceInfo() {
  return { ...self };
}
export function deviceCapabilities() {
  return { node_id: self.node_id, capabilities: self.capabilities, role: self.role, platform: self.platform };
}

// --- peer registry ----------------------------------------------------------
export function upsertPeer(peer) {
  if (!peer || !peer.node_id || peer.node_id === self.node_id) return null;
  const existing = state.peers.get(peer.node_id) || {};
  const record = {
    ...existing,
    ...peer,
    trusted: state.trustTokens.has(peer.node_id) || existing.trusted || false,
    last_seen: new Date().toISOString(),
    status: "online",
  };
  state.peers.set(peer.node_id, record);
  persist();
  return record;
}

export function listPeers() {
  return [...state.peers.values()];
}
export function getPeer(node_id) {
  return state.peers.get(node_id) || null;
}

// --- pairing + trust --------------------------------------------------------
// Step 1: the discovering node requests pairing; we mint a 6-digit code that
// the *other* device's user reads out / enters.
export function beginPairing(node_id) {
  if (!node_id) return { error: "node_id required" };
  const code = String(randomBytes(3).readUIntBE(0, 3) % 1000000).padStart(6, "0");
  state.pendingPairings.set(node_id, { code, created_at: Date.now() });
  return { node_id, pairing_code: code, expires_in_ms: 120000 };
}

// Step 2: confirm with the code -> mint a durable trust token.
export function confirmPairing(node_id, code) {
  const pending = state.pendingPairings.get(node_id);
  if (!pending) return { error: "no pending pairing for this node", trusted: false };
  if (Date.now() - pending.created_at > 120000) {
    state.pendingPairings.delete(node_id);
    return { error: "pairing code expired", trusted: false };
  }
  if (String(code) !== pending.code) return { error: "incorrect pairing code", trusted: false };
  const token = randomUUID();
  state.trustTokens.set(node_id, token);
  state.pendingPairings.delete(node_id);
  const peer = state.peers.get(node_id);
  if (peer) peer.trusted = true;
  persist();
  return { node_id, trusted: true, trust_token: token };
}

export function isTrusted(node_id) {
  return state.trustTokens.has(node_id);
}

// --- persistence ------------------------------------------------------------
function persist() {
  try {
    mkdirSync(join(ROOT, "data", "runtime"), { recursive: true });
    writeFileSync(
      FILE,
      JSON.stringify(
        { self, peers: listPeers(), trust: [...state.trustTokens.keys()] },
        null,
        2,
      ),
    );
  } catch {
    /* best-effort */
  }
}

export function _resetDevicesForTests() {
  state.peers.clear();
  state.pendingPairings.clear();
  state.trustTokens.clear();
}
