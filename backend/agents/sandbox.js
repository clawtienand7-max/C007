// Sandbox Integration Agent — isolate, INSPECT, and (only with approval) try a
// candidate. This build performs real STATIC inspection of a package manifest
// and creates an isolated directory, but never executes install scripts or
// downloads packages on its own: actual install is permission-gated and, in
// this zero-dep/network-restricted environment, reported as blocked rather than
// faked. No secrets are read.

import { mkdirSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { ROOT, createPermission, addLog } from "../lib/store.js";

const SANDBOX_ROOT = join(ROOT, "data", "runtime", "sandbox");
const sandboxes = new Map();

export function createSandbox({ proposal_id, candidate } = {}) {
  const sandbox_id = `sbx_${randomUUID().slice(0, 8)}`;
  const dir = join(SANDBOX_ROOT, sandbox_id);
  try {
    mkdirSync(dir, { recursive: true });
  } catch {
    /* ignore */
  }
  const rec = { sandbox_id, proposal_id: proposal_id || null, candidate: candidate || null, dir, environment: { platform: process.platform, node: process.version, isolated: true, network: "restricted" }, created_at: new Date().toISOString(), status: "created" };
  sandboxes.set(sandbox_id, rec);
  addLog({ agent: "SandboxAgent", event: "created", detail: { sandbox_id } });
  return { sandbox_id, environment: rec.environment, dir: `data/runtime/sandbox/${sandbox_id}` };
}

// Static inspection of a package manifest (package.json-like object). Detects
// the behaviours the blueprint flags as high-risk.
export function inspectPackage(manifest = {}) {
  const scripts = manifest.scripts || {};
  const flags = [];
  const dangerousScripts = ["preinstall", "install", "postinstall", "prepare"].filter((s) => scripts[s]);
  if (dangerousScripts.length) flags.push(`lifecycle install scripts present: ${dangerousScripts.join(", ")}`);
  const scriptText = Object.values(scripts).join(" ; ").toLowerCase();
  if (/curl|wget|http:\/\/|https:\/\//.test(scriptText)) flags.push("scripts make network calls");
  if (/\b(sh|bash|node|python)\b/.test(scriptText) && dangerousScripts.length) flags.push("install scripts execute shell/interpreters");
  if (manifest.bin) flags.push("package ships executables (bin)");
  if (/process\.env|dotenv|secret|token/.test(scriptText)) flags.push("scripts may read environment/secrets");
  const depCount = Object.keys(manifest.dependencies || {}).length + Object.keys(manifest.optionalDependencies || {}).length;

  let risk = "low";
  if (dangerousScripts.length || manifest.bin) risk = "high";
  else if (depCount > 30) risk = "medium";

  return {
    name: manifest.name || "unknown",
    version: manifest.version || "unknown",
    license: manifest.license || "unknown",
    dependency_count: depCount,
    dangerous_scripts: dangerousScripts,
    flags,
    risk_level: risk,
    recommendation: risk === "high" ? "needs_manual_review" : risk === "medium" ? "review_dependencies" : "safe_to_trial",
  };
}

// Install is high risk: gated behind explicit approval, and not actually
// executed in this build.
export function install({ sandbox_id, manifest, approved = false } = {}) {
  const sb = sandboxes.get(sandbox_id);
  if (!sb) return { error: "sandbox not found", _status: 404 };
  const inspection = inspectPackage(manifest || {});

  if (!approved) {
    const perm = createPermission({
      action_id: "self.sandbox.install",
      risk: "high",
      reason: `Install "${inspection.name}" into sandbox ${sandbox_id}`,
      detail: inspection,
      source: "self_extension",
    });
    sb.status = "awaiting_approval";
    return { sandbox_id, install_result: "blocked", requires_permission: true, permission_id: perm.permission_id, inspection, note: "approve the permission to authorise a sandbox install" };
  }

  // Approved — but this build does not execute installs/network itself.
  sb.status = "inspected";
  // Persist the manifest into the sandbox dir for an external runner to use.
  try {
    if (existsSync(sb.dir)) writeFileSync(join(sb.dir, "package.json"), JSON.stringify(manifest, null, 2));
  } catch {
    /* ignore */
  }
  addLog({ agent: "SandboxAgent", event: "install_prepared", detail: { sandbox_id, risk: inspection.risk_level } });
  return {
    sandbox_id,
    install_result: "blocked",
    inspection,
    note: "approved, but automatic install execution is disabled in this environment; an external sandbox runner must perform the install. Manifest written for that runner.",
    next_step: "run npm/pip install in an isolated networked runner, then POST audit + demo evidence",
  };
}

export function audit({ sandbox_id } = {}) {
  const sb = sandboxes.get(sandbox_id);
  if (!sb) return { error: "sandbox not found", _status: 404 };
  // npm audit / pip-audit require network + installed deps; honestly blocked.
  return {
    sandbox_id,
    security_result: "blocked",
    note: "dependency audit (npm audit / pip-audit / dependency review) requires a networked sandbox; not run here",
    required: ["run dependency audit in the external sandbox", "fail on any high/critical vulnerability"],
  };
}

export function destroy({ sandbox_id } = {}) {
  const sb = sandboxes.get(sandbox_id);
  if (!sb) return { error: "sandbox not found", _status: 404 };
  try {
    rmSync(sb.dir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
  sandboxes.delete(sandbox_id);
  addLog({ agent: "SandboxAgent", event: "destroyed", detail: { sandbox_id } });
  return { sandbox_id, destroyed: true };
}

export function _resetSandboxForTests() {
  sandboxes.clear();
}
