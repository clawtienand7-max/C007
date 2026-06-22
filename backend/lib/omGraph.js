// OM Relation Graph — the knowledge/relationship network at the HUD centre.
// Built from TFNK's REAL subsystems and live counts (not a static picture):
// node weights reflect actual action counts, memory entries, peers, etc.

import { loadActions } from "./registry.js";
import { searchMemory } from "./memory.js";
import { listPeers } from "./device.js";
import { getStatus as loopStatus } from "../loop.js";

export function buildGraph() {
  const actions = loadActions().actions.length;
  const memCount = searchMemory({ q: "", limit: 1000 }).total;
  const peers = listPeers().length;
  const loop = loopStatus().status;

  const nodes = [
    { id: "om_core", label: "OM", type: "core", weight: 100 },
    { id: "tfnk_loop", label: `LOOP (${loop})`, type: "system", weight: 80 },
    { id: "action_registry", label: "Action Registry", type: "safety", weight: 60 + actions },
    { id: "test_center", label: "Test Center", type: "verification", weight: 70 },
    { id: "memory", label: `Memory (${memCount})`, type: "memory", weight: 50 + memCount },
    { id: "scheduler", label: "Scheduler", type: "automation", weight: 55 },
    { id: "vision", label: "Vision/Gesture", type: "camera", weight: 50 },
    { id: "self_upgrade", label: "Self-Upgrade", type: "upgrade", weight: 55 },
    { id: "claude", label: "Claude", type: "agent", weight: 70 },
    { id: "codex", label: "Codex", type: "agent", weight: 70 },
    { id: "devices", label: `Devices (${peers})`, type: "device", weight: 45 + peers * 5 },
  ];

  const edges = [
    { source: "om_core", target: "tfnk_loop", type: "controls" },
    { source: "om_core", target: "action_registry", type: "governs" },
    { source: "om_core", target: "test_center", type: "verifies" },
    { source: "om_core", target: "memory", type: "remembers" },
    { source: "om_core", target: "scheduler", type: "schedules" },
    { source: "om_core", target: "vision", type: "perceives" },
    { source: "om_core", target: "self_upgrade", type: "evolves" },
    { source: "om_core", target: "claude", type: "delegates" },
    { source: "om_core", target: "codex", type: "delegates" },
    { source: "om_core", target: "devices", type: "collaborates" },
    { source: "self_upgrade", target: "test_center", type: "requires" },
    { source: "scheduler", target: "test_center", type: "runs" },
  ];

  return { nodes, edges, generated_at: new Date().toISOString(), memory_link_count: edges.length };
}

export function getNode(id) {
  return buildGraph().nodes.find((n) => n.id === id) || null;
}
