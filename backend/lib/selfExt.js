// Self-Extension Factory — stores + core logic for TFNK noticing its own gaps,
// scoring candidate libraries, packaging skills and drafting upgrade proposals.
//
// Safety: nothing here installs, downloads, or modifies TFNK. It produces
// records and decisions. Risky actions live behind permission gates in the
// sandbox / self-upgrade agents.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { ROOT, getLogs } from "./store.js";
import { loadActions } from "./registry.js";
import { audit } from "../agents/uiAudit.js";
import { listTests } from "../agents/testCenter.js";

const DIR = join(ROOT, "data", "runtime");
const FILE = join(DIR, "self_ext.json");

const store = {
  gaps: new Map(),
  candidates: new Map(),
  skills: new Map(),
  proposals: new Map(),
};

const id = (p) => `${p}_${randomUUID().slice(0, 8)}`;

// --- capability gaps --------------------------------------------------------
export function createGap(input = {}) {
  if (!input.title) return { error: "title is required" };
  const gap = {
    gap_id: input.gap_id || id("gap"),
    title: input.title,
    source: input.source || "user_request",
    impact: input.impact || "",
    affected_modules: input.affected_modules || [],
    priority: input.priority || "medium",
    suggested_research_queries: input.suggested_research_queries || [],
    status: "open",
    created_at: new Date().toISOString(),
  };
  store.gaps.set(gap.gap_id, gap);
  persist();
  return gap;
}

export function listGaps() {
  return [...store.gaps.values()];
}
export function getGap(gid) {
  return store.gaps.get(gid) || null;
}
export function setGapStatus(gid, status) {
  const g = store.gaps.get(gid);
  if (!g) return null;
  g.status = status;
  persist();
  return g;
}

// Detect gaps from TFNK's own state: audit problems, declared-but-unimplemented
// actions, actions implemented without tests, and recent errors in the trace.
export function detectGaps() {
  const found = [];
  const a = audit();
  if (a.fake_or_incomplete > 0) {
    found.push(createGap({
      title: `UI has ${a.fake_or_incomplete} control(s) without a real backend`,
      source: "self_audit",
      impact: "some UI controls would not perform real work",
      affected_modules: ["ui", "backend"],
      priority: "high",
      suggested_research_queries: ["how to wire UI control to backend action"],
    }));
  }
  for (const act of loadActions().actions) {
    if (!act.implemented) {
      found.push(createGap({
        title: `Action "${act.id}" is declared but not implemented`,
        source: "self_audit",
        impact: `feature "${act.label}" is not yet usable`,
        affected_modules: ["backend", "tools"],
        priority: "medium",
        suggested_research_queries: [`implement ${act.label}`],
      }));
    }
  }
  const cov = listTests().coverage;
  if (cov.implemented_without_test > 0) {
    found.push(createGap({
      title: `${cov.implemented_without_test} implemented action(s) lack a test`,
      source: "test_failure",
      impact: "implemented features are not covered by tests",
      affected_modules: ["test_center"],
      priority: "medium",
    }));
  }
  const errors = getLogs({ limit: 200 }).filter((l) => l.event === "error");
  if (errors.length) {
    found.push(createGap({
      title: `${errors.length} recent error(s) in the trace`,
      source: "failed_task",
      impact: "recent operations failed",
      affected_modules: ["backend"],
      priority: "high",
    }));
  }
  return found;
}

// --- candidate library scoring (the real rubric) ----------------------------
const PERMISSIVE = ["mit", "apache-2.0", "apache", "bsd", "bsd-3-clause", "bsd-2-clause", "isc", "mpl-2.0"];

// Score a candidate from its metadata. Deterministic, no network. Stars are a
// minor signal only — never the deciding factor.
export function scoreCandidate(meta = {}) {
  const reasons = [];
  let score = 50;
  let risk = "low";
  let recommendation = "shortlist";

  // License
  const lic = String(meta.license || "").toLowerCase();
  if (!meta.license || lic === "unknown" || lic === "") {
    recommendation = "needs_manual_review";
    score -= 15;
    reasons.push("unknown license — manual review required");
  } else if (PERMISSIVE.includes(lic)) {
    score += 15;
    reasons.push(`permissive license (${meta.license})`);
  } else if (lic.includes("gpl")) {
    score -= 10;
    risk = bump(risk, "medium");
    reasons.push(`copyleft license (${meta.license}) — integration caution`);
  }

  // Maintenance
  if (meta.last_updated) {
    const months = (Date.now() - new Date(meta.last_updated).getTime()) / (1000 * 60 * 60 * 24 * 30);
    if (months <= 12) {
      score += 12;
      reasons.push("actively maintained (<12mo)");
    } else if (months > 24) {
      score -= 15;
      risk = bump(risk, "medium");
      reasons.push("appears abandoned (>24mo)");
    }
  } else {
    reasons.push("maintenance status unknown");
  }

  // Security
  if (meta.security_alerts && meta.security_alerts > 0) {
    score -= 25;
    risk = bump(risk, "high");
    reasons.push(`${meta.security_alerts} known security alert(s)`);
  }
  // Dangerous behaviours
  if (meta.runs_shell || meta.downloads_binary || meta.reads_secrets || meta.has_install_script) {
    risk = bump(risk, "high");
    score -= 15;
    reasons.push("performs high-risk behaviour (shell/binary/secrets/install-script)");
  }

  // Quality signals
  if (meta.has_tests) {
    score += 8;
    reasons.push("has tests");
  } else {
    score -= 8;
    reasons.push("no tests — not production-ready as-is");
  }
  if (meta.docs_quality === "good") score += 6;
  else if (meta.docs_quality === "poor") {
    score -= 6;
    reasons.push("poor docs");
  }

  // Cross-platform
  if (meta.windows_support === false || meta.macos_support === false) {
    score -= 10;
    reasons.push("not cross-platform (Windows/macOS)");
  }

  // Stars: tiny nudge only.
  if (meta.stars) score += Math.min(5, Math.log10(meta.stars + 1));

  score = Math.max(0, Math.min(100, Math.round(score)));

  if (risk === "high") recommendation = recommendation === "needs_manual_review" ? "needs_manual_review" : "reject";
  else if (recommendation !== "needs_manual_review") recommendation = score >= 60 ? "shortlist" : "reject";

  return { score, risk_level: risk, recommendation, reasons };
}

function bump(cur, level) {
  const order = ["low", "medium", "high", "critical"];
  return order[Math.max(order.indexOf(cur), order.indexOf(level))];
}

export function saveCandidate(gap_id, meta) {
  const scored = scoreCandidate(meta);
  const rec = { id: id("cand"), gap_id, ...meta, ...scored, evaluated_at: new Date().toISOString() };
  store.candidates.set(rec.id, rec);
  persist();
  return rec;
}
export function listCandidates(gap_id) {
  const all = [...store.candidates.values()];
  return gap_id ? all.filter((c) => c.gap_id === gap_id) : all;
}

// --- skills -----------------------------------------------------------------
export function createSkill(input = {}) {
  if (!input.name) return { error: "name is required" };
  const skill = {
    skill_id: input.skill_id || id("skill"),
    name: input.name,
    purpose: input.purpose || "",
    source: input.source || {},
    tools: input.tools || [],
    actions: input.actions || [],
    permissions: input.permissions || [],
    tests: input.tests || [],
    real_usage_scenarios: input.real_usage_scenarios || [],
    rollback_plan: input.rollback_plan || [],
    status: "draft",
    created_at: new Date().toISOString(),
  };
  store.skills.set(skill.skill_id, skill);
  persist();
  return skill;
}
export function listSkills() {
  return [...store.skills.values()];
}
export function getSkill(sid) {
  return store.skills.get(sid) || null;
}

// --- upgrade proposals ------------------------------------------------------
export function createProposal(input = {}) {
  const proposal = {
    id: input.id || id("upg"),
    gap_id: input.gap_id || null,
    skill_id: input.skill_id || null,
    title: input.title || "Self-upgrade proposal",
    plan: input.plan || [],
    requirement_contract_id: input.requirement_contract_id || null,
    risk_level: input.risk_level || "high",
    status: "draft",
    rollback_plan: input.rollback_plan || ["git revert the upgrade branch", "restore previous skill registry"],
    created_at: new Date().toISOString(),
  };
  store.proposals.set(proposal.id, proposal);
  persist();
  return proposal;
}
export function listProposals() {
  return [...store.proposals.values()];
}
export function getProposal(pid) {
  return store.proposals.get(pid) || null;
}
export function setProposalStatus(pid, status, extra = {}) {
  const p = store.proposals.get(pid);
  if (!p) return null;
  p.status = status;
  Object.assign(p, extra);
  persist();
  return p;
}

// --- persistence ------------------------------------------------------------
function persist() {
  try {
    mkdirSync(DIR, { recursive: true });
    writeFileSync(
      FILE,
      JSON.stringify({ gaps: listGaps(), candidates: listCandidates(), skills: listSkills(), proposals: listProposals() }, null, 2),
    );
  } catch {
    /* best-effort */
  }
}
export function loadPersistedSelfExt() {
  try {
    if (!existsSync(FILE)) return;
    const d = JSON.parse(readFileSync(FILE, "utf8"));
    for (const g of d.gaps || []) store.gaps.set(g.gap_id, g);
    for (const c of d.candidates || []) store.candidates.set(c.id, c);
    for (const s of d.skills || []) store.skills.set(s.skill_id, s);
    for (const p of d.proposals || []) store.proposals.set(p.id, p);
  } catch {
    /* ignore */
  }
}
export function _resetSelfExtForTests() {
  store.gaps.clear();
  store.candidates.clear();
  store.skills.clear();
  store.proposals.clear();
}
