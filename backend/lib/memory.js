// Memory Center — Project Knowledge Memory. Stores rules, facts and past fixes
// so the agent can recall TFNK conventions across sessions. Persisted to
// data/runtime/memory.json (best-effort, dependency-free).

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./store.js";

const FILE = join(ROOT, "data", "runtime", "memory.json");

let _entries = null;
let _counter = 0;

// Seed memory with the project's own iron rules so a fresh clone already
// "knows" the TFNK conventions.
const SEED = [
  { kind: "rule", text: "Every interactive UI control must bind to a registered action_id.", tags: ["ui", "rule"] },
  { kind: "rule", text: "No action may return fake success; each needs a real route and a test.", tags: ["api", "rule"] },
  { kind: "rule", text: "Verification requires evidence; the word 'success' is not proof.", tags: ["verify", "rule"] },
  { kind: "rule", text: "High/critical risk operations require explicit user permission.", tags: ["safety", "rule"] },
];

function load() {
  if (_entries) return _entries;
  if (existsSync(FILE)) {
    try {
      const data = JSON.parse(readFileSync(FILE, "utf8"));
      _entries = data.entries || [];
      _counter = data.counter || _entries.length;
      return _entries;
    } catch {
      // fall through to seed
    }
  }
  _entries = SEED.map((s) => ({
    id: `mem_${String(++_counter).padStart(3, "0")}`,
    created_at: new Date().toISOString(),
    ...s,
  }));
  save();
  return _entries;
}

function save() {
  try {
    mkdirSync(join(ROOT, "data", "runtime"), { recursive: true });
    writeFileSync(FILE, JSON.stringify({ counter: _counter, entries: _entries }, null, 2));
  } catch {
    // best-effort
  }
}

export function writeMemory({ kind = "fact", text, tags = [] }) {
  if (!text || !String(text).trim()) return { error: "text is required" };
  load();
  const entry = {
    id: `mem_${String(++_counter).padStart(3, "0")}`,
    kind,
    text: String(text).trim(),
    tags: Array.isArray(tags) ? tags : [],
    created_at: new Date().toISOString(),
  };
  _entries.push(entry);
  save();
  return entry;
}

export function searchMemory({ q = "", kind, limit = 20 } = {}) {
  load();
  const needle = String(q).toLowerCase();
  let results = _entries;
  if (kind) results = results.filter((e) => e.kind === kind);
  if (needle) {
    results = results.filter(
      (e) => e.text.toLowerCase().includes(needle) || e.tags.some((t) => t.toLowerCase().includes(needle)),
    );
  }
  return { total: _entries.length, matched: results.length, results: results.slice(-limit).reverse() };
}

export function _resetMemoryForTests() {
  _entries = null;
  _counter = 0;
}
