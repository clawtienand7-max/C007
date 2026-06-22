// Cross Device Agent — manages Windows/macOS collaboration on the same LAN.
// Picks the best node for a task, and delegates by calling the peer's REST API
// for real. Safety: only TRUSTED peers may receive delegated work, and
// high/critical-risk actions are never auto-delegated — they raise a permission
// request first.

import { deviceInfo, listPeers, getPeer, isTrusted } from "../lib/device.js";
import { getAction } from "../lib/registry.js";
import { createPermission, addLog, nextId } from "../lib/store.js";
import { emit } from "../lib/events.js";

const tasks = new Map(); // task_id -> task record

export function listTasks() {
  return [...tasks.values()];
}
export function getTask(id) {
  return tasks.get(id) || null;
}

// Capability hints: which roles a class of work prefers.
function preferredCapability(action_id) {
  if (/^(ui\.|computer\.|vision\.|camera\.|gesture\.)/.test(action_id)) return "ui_controller";
  if (/^(tests\.|agent\.repair|loop\.|agent\.run)/.test(action_id)) return "heavy_compute";
  return null;
}

export function selectNode(action_id) {
  const want = preferredCapability(action_id);
  const peers = listPeers().filter((p) => isTrusted(p.node_id) && p.status === "online");
  if (want) {
    const match = peers.find((p) => (p.capabilities || []).includes(want));
    if (match) return { selected_node: match.node_id, reason: `peer has capability "${want}"`, peer: match };
  }
  if (peers.length) return { selected_node: peers[0].node_id, reason: "first trusted online peer", peer: peers[0] };
  return { selected_node: deviceInfo().node_id, reason: "no trusted peer online — running locally", peer: null };
}

export async function delegate({ action_id, input = {}, to_node, fetchImpl = fetch } = {}) {
  const action = getAction(action_id);
  if (!action) return { error: `action "${action_id}" not in registry`, _status: 400 };

  // Choose the target.
  let target = to_node ? getPeer(to_node) : selectNode(action_id).peer;
  const task_id = nextId("run", "task");
  const from_node = deviceInfo().node_id;
  const risk = action.risk;

  // Safety gate: high/critical never auto-delegate.
  if (risk === "high" || risk === "critical") {
    const perm = createPermission({
      action_id,
      risk,
      reason: `Cross-device delegation of high-risk action "${action_id}" to ${to_node || (target && target.node_id) || "a peer"}`,
      source: "cross_device",
    });
    const record = { task_id, from_node, to_node: target ? target.node_id : null, action_id, input, status: "awaiting_permission", permission_id: perm.permission_id, output: null, verification_result: "pending" };
    tasks.set(task_id, record);
    return { ...record, requires_permission: true, fallback_plan: ["approve permission, then re-delegate"] };
  }

  // Must have a trusted, reachable peer to actually delegate.
  if (!target) {
    const record = { task_id, from_node, to_node: null, action_id, input, status: "blocked", output: null, verification_result: "no_peer", reason: "no target peer; pair a device first" };
    tasks.set(task_id, record);
    return { ...record, fallback_plan: ["run locally", "pair a device and retry"] };
  }
  if (!isTrusted(target.node_id)) {
    const record = { task_id, from_node, to_node: target.node_id, action_id, input, status: "blocked", output: null, verification_result: "untrusted", reason: "target peer is not paired/trusted" };
    tasks.set(task_id, record);
    return { ...record, fallback_plan: ["pair the device first"] };
  }

  // Delegate for real over the peer's REST API.
  const url = `http://${target.ip}:${target.port}${action.api}`;
  const record = { task_id, from_node, to_node: target.node_id, action_id, input, status: "running", output: null, verification_result: "pending" };
  tasks.set(task_id, record);
  emit({ event: "task.delegated", from: from_node, to: target.node_id, task_id, action_id });
  addLog({ agent: "CrossDeviceAgent", event: "delegate", detail: { task_id, to: target.node_id, action_id } });

  try {
    const resp = await fetchImpl(url, {
      method: action.method,
      headers: { "Content-Type": "application/json" },
      body: action.method === "POST" ? JSON.stringify(input) : undefined,
    });
    const output = await resp.json().catch(() => ({}));
    record.output = output;
    record.status = resp.ok ? "completed" : "failed";
    record.verification_result = resp.ok ? "peer_responded_ok" : `peer_status_${resp.status}`;
  } catch (err) {
    record.status = "failed";
    record.verification_result = "unreachable";
    record.error = String(err && err.message);
  }
  emit({ event: "task.result", task_id, status: record.status });
  return record;
}

export function _resetTasksForTests() {
  tasks.clear();
}
