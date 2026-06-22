// Research Agent + GitHub Library Scout.
//
// Honesty: this build does not assume network access (the environment's network
// policy may block it). Query generation and candidate SCORING are real and
// deterministic; the actual web/GitHub fetch is injectable (fetchImpl). With no
// fetcher and no supplied candidates, the agent returns honest_status "blocked"
// with reason "no_network" — it never invents sources or repos.

import { saveCandidate } from "../lib/selfExt.js";
import { addLog } from "../lib/store.js";

export function generateQueries(gap) {
  const base = [];
  if (gap.title) base.push(gap.title.replace(/[^\p{L}\p{N} ]/gu, " ").trim());
  for (const q of gap.suggested_research_queries || []) base.push(q);
  // a couple of structured variants
  if (gap.title) {
    base.push(`open source library ${gap.title}`);
    base.push(`${gap.title} Node.js OR TypeScript`);
    base.push(`MCP server ${gap.title}`);
  }
  return [...new Set(base.filter(Boolean))].slice(0, 8);
}

export async function runResearch(gap, { fetchImpl } = {}) {
  const queries = generateQueries(gap);
  const report = {
    research_id: `research_${gap.gap_id}`,
    gap_id: gap.gap_id,
    queries,
    sources: [],
    recommended_direction: "",
    risks: [],
    unknowns: [],
    honest_status: "blocked",
  };
  if (!fetchImpl) {
    report.unknowns.push("no network fetcher available in this environment");
    report.risks.push("cannot validate external sources without network access");
    report.recommended_direction = "supply a fetcher or run in a networked environment to gather sources";
    addLog({ agent: "ResearchAgent", event: "research_blocked", detail: { gap_id: gap.gap_id, reason: "no_network" } });
    return report;
  }
  // Real path: caller injected a fetcher. We still don't fabricate — we record
  // exactly what came back.
  try {
    const results = await fetchImpl(queries);
    report.sources = Array.isArray(results) ? results : [];
    report.honest_status = "ready";
    report.recommended_direction = report.sources.length ? "shortlist top sources for candidate evaluation" : "no sources found";
  } catch (err) {
    report.honest_status = "failed";
    report.risks.push(`fetch failed: ${String(err && err.message)}`);
  }
  return report;
}

// GitHub Library Scout. `candidates` may be injected (manual paste or a real
// GitHub API result mapped to metadata); each is scored with the real rubric.
export async function githubSearch(gap, { fetchImpl, candidates } = {}) {
  const search_queries = generateQueries(gap).map((q) => `${q} in:name,description`);
  let metas = candidates;

  if (!metas) {
    if (fetchImpl) {
      try {
        metas = await fetchImpl(search_queries);
      } catch (err) {
        return { search_queries, candidates: [], top_recommendation: null, manual_review_required: true, unknowns: [`github fetch failed: ${String(err && err.message)}`], honest_status: "failed" };
      }
    } else {
      return { search_queries, candidates: [], top_recommendation: null, manual_review_required: true, unknowns: ["no network access — supply candidates or a fetcher"], honest_status: "blocked" };
    }
  }

  const scored = (metas || []).map((m) => saveCandidate(gap.gap_id, m));
  scored.sort((a, b) => b.score - a.score);
  const shortlisted = scored.filter((c) => c.recommendation === "shortlist");
  const top = shortlisted[0] || null;
  addLog({ agent: "GitHubScout", event: "scored_candidates", detail: { gap_id: gap.gap_id, n: scored.length } });

  return {
    search_queries,
    candidates: scored,
    top_recommendation: top ? top.name : null,
    manual_review_required: scored.some((c) => c.recommendation === "needs_manual_review"),
    unknowns: scored.filter((c) => c.recommendation === "needs_manual_review").map((c) => `${c.name}: ${c.reasons.join("; ")}`),
    honest_status: "ready",
  };
}
