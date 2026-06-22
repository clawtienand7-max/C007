// LAN discovery — lightweight mDNS-style presence over UDP broadcast.
// A node periodically broadcasts an "announce" packet; listeners add the sender
// to the peer registry. The network socket is best-effort (sandboxes may block
// UDP), but the packet build/parse handlers are pure and fully testable.

import dgram from "node:dgram";
import { deviceInfo, upsertPeer } from "./device.js";
import { addLog } from "./store.js";
import { emit } from "./events.js";

const DISCOVERY_PORT = Number(process.env.TFNK_DISCOVERY_PORT) || 47778;
const BROADCAST_ADDR = "255.255.255.255";

let socket = null;
let timer = null;

export function buildAnnounce() {
  const me = deviceInfo();
  return JSON.stringify({
    proto: "tfnk-discovery/1",
    node_id: me.node_id,
    device_name: me.device_name,
    platform: me.platform,
    ip: me.ip,
    port: me.port,
    role: me.role,
    capabilities: me.capabilities,
  });
}

// Pure handler: parse an announce packet and register the peer. Returns the
// peer record, or null if it isn't a valid foreign announce.
export function handleAnnounce(raw) {
  let msg;
  try {
    msg = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch {
    return null;
  }
  if (!msg || msg.proto !== "tfnk-discovery/1" || !msg.node_id) return null;
  const peer = upsertPeer({
    node_id: msg.node_id,
    device_name: msg.device_name,
    platform: msg.platform,
    ip: msg.ip,
    port: msg.port,
    role: msg.role,
    capabilities: msg.capabilities,
  });
  if (peer) emit({ event: "peer.online", node_id: peer.node_id, capabilities: peer.capabilities });
  return peer;
}

export function start() {
  if (socket) return { ok: true, already: true };
  try {
    socket = dgram.createSocket({ type: "udp4", reuseAddr: true });
    socket.on("message", (buf) => handleAnnounce(buf.toString()));
    socket.on("error", () => stop());
    socket.bind(DISCOVERY_PORT, () => {
      try {
        socket.setBroadcast(true);
      } catch {
        /* ignore */
      }
    });
    timer = setInterval(broadcast, 5000);
    addLog({ agent: "DiscoveryAgent", event: "started", detail: { port: DISCOVERY_PORT } });
    return { ok: true };
  } catch (err) {
    socket = null;
    return { ok: false, error: String(err && err.message) };
  }
}

export function broadcast() {
  if (!socket) return { ok: false, error: "discovery not running" };
  try {
    const packet = Buffer.from(buildAnnounce());
    socket.send(packet, 0, packet.length, DISCOVERY_PORT, BROADCAST_ADDR);
    return { ok: true };
  } catch (err) {
    return { ok: false, error: String(err && err.message) };
  }
}

export function stop() {
  if (timer) clearInterval(timer);
  timer = null;
  if (socket) {
    try {
      socket.close();
    } catch {
      /* ignore */
    }
  }
  socket = null;
  return { ok: true };
}
