// Telemetry — real system metrics from Node built-ins, with HONEST unavailable
// states. No fabricated numbers: CPU/RAM come from `os`; GPU (nvidia-smi), disk
// (df) and network throughput are best-effort and report available:false when
// they can't be measured in this environment.

import os from "node:os";
import { execSync } from "node:child_process";
import { listPeers } from "./device.js";

let lastCpu = null; // { idle, total }

function cpuSample() {
  const cpus = os.cpus();
  let idle = 0;
  let total = 0;
  for (const c of cpus) {
    for (const t of Object.values(c.times)) total += t;
    idle += c.times.idle;
  }
  return { idle, total };
}

function cpuUsagePercent() {
  const cur = cpuSample();
  if (!lastCpu) {
    lastCpu = cur;
    // since-boot average as a first reading (real, not faked)
    return Math.round((1 - cur.idle / cur.total) * 100);
  }
  const idleD = cur.idle - lastCpu.idle;
  const totalD = cur.total - lastCpu.total;
  lastCpu = cur;
  if (totalD <= 0) return null;
  return Math.round((1 - idleD / totalD) * 100);
}

function gpuInfo() {
  try {
    const out = execSync("nvidia-smi --query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits", { stdio: ["ignore", "pipe", "ignore"], timeout: 2000 }).toString().trim();
    const [name, usage, temp, vu, vt] = out.split("\n")[0].split(",").map((s) => s.trim());
    return { name, usage: Number(usage), temperature: Number(temp), vramUsed: Number(vu) / 1024, vramTotal: Number(vt) / 1024, available: true };
  } catch {
    return { name: null, usage: null, temperature: null, vramUsed: null, vramTotal: null, available: false, reason: "nvidia-smi unavailable (no NVIDIA GPU or tool not present)" };
  }
}

function diskInfo() {
  try {
    if (process.platform === "win32") return { available: false, reason: "disk metrics not wired for Windows in this build" };
    const out = execSync("df -k -P /", { stdio: ["ignore", "pipe", "ignore"], timeout: 2000 }).toString().trim().split("\n")[1];
    const parts = out.split(/\s+/);
    const totalKb = Number(parts[1]);
    const availKb = Number(parts[3]);
    return { available: true, freeGB: Math.round((availKb / 1024 / 1024) * 10) / 10, totalGB: Math.round((totalKb / 1024 / 1024) * 10) / 10, readMBps: null, writeMBps: null, io_note: "throughput not sampled (read/write MBps unavailable)" };
  } catch {
    return { available: false, reason: "df unavailable" };
  }
}

export function getSystem() {
  const mem = { total: os.totalmem(), free: os.freemem() };
  const usedGB = (mem.total - mem.free) / 1e9;
  const totalGB = mem.total / 1e9;
  const ifaces = os.networkInterfaces();
  const ipv4 = [];
  for (const name of Object.keys(ifaces)) {
    for (const i of ifaces[name] || []) if (i.family === "IPv4" && !i.internal) ipv4.push({ iface: name, address: i.address });
  }
  return {
    cpu: { usage: cpuUsagePercent(), cores: os.cpus().length, model: os.cpus()[0]?.model || null, loadavg: os.loadavg().map((n) => Math.round(n * 100) / 100), temperature: null, temperature_note: "CPU temperature unavailable from Node built-ins" },
    memory: { used: Math.round(usedGB * 10) / 10, total: Math.round(totalGB * 10) / 10, percent: Math.round(((mem.total - mem.free) / mem.total) * 100) },
    gpu: gpuInfo(),
    network: { interfaces: ipv4, lanPeers: listPeers().filter((p) => p.status === "online").length, downloadMbps: null, uploadMbps: null, throughput_note: "live throughput not measured in this build" },
    disk: diskInfo(),
    host: { platform: process.platform, hostname: os.hostname(), uptime_s: Math.round(os.uptime()) },
    updatedAt: new Date().toISOString(),
  };
}

export function getGpu() {
  return gpuInfo();
}
export function getNetwork() {
  const s = getSystem();
  return s.network;
}
export function getDisk() {
  return diskInfo();
}
