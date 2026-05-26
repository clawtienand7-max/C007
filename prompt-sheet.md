# Claude Prompt Sheet

A practical reference of high-signal prompts organized by use case. Copy, adapt, and reuse.

---

## Table of Contents

1. [Claude Code & Agentic](#claude-code--agentic)
2. [Software Engineering](#software-engineering)
3. [General Use & Productivity](#general-use--productivity)

---

## Claude Code & Agentic

### Codebase Orientation

```
Read the README and any CLAUDE.md files in this repo, then give me a 5-bullet
summary of: (1) what this project does, (2) how to run it, (3) how to run tests,
(4) the main entry points, (5) anything non-obvious I should know before changing code.
```

```
List every file that touches [feature/module name]. Show file path and a one-line
description of its role. Don't read the files yet—just map the surface area.
```

### Targeted Exploration

```
Find where [function/class/symbol] is defined. Then find all call sites.
Show file:line for each. Don't summarize—just list locations.
```

```
Search for all TODO, FIXME, HACK, and XXX comments in the codebase.
Group them by file. Flag any that look like they block shipping.
```

### Making a Focused Change

```
I want to [describe change]. Before touching anything:
1. List every file you'll need to edit.
2. Describe in one sentence per file what you'll change.
3. Flag any risk or side-effect.
Wait for my approval before making changes.
```

```
Make only the minimal change needed to fix [bug/requirement].
Don't refactor, rename, or clean up surrounding code.
Show me the diff before committing.
```

### Code Review & PR

```
Review the diff on this branch against main. Focus only on:
- Correctness bugs (logic errors, off-by-ones, null dereferences)
- Security issues (injection, exposed secrets, insecure defaults)
- Broken or missing tests for changed behavior
Skip style, formatting, and subjective opinions.
```

```
I'm about to merge PR #[number]. Walk me through the highest-risk lines
in the diff and explain what could go wrong at each one.
```

### Tests

```
Write tests for [function/module]. Cover:
1. The happy path
2. Edge cases: empty input, max input, zero, null/undefined
3. Error paths that should throw or return an error code
Use the existing test style in this repo. Don't add new test dependencies.
```

```
This test is flaky. Here is the failure output: [paste output].
Diagnose the root cause without running the test. Propose a fix.
```

### Debugging with Claude Code

```
This command fails: [paste command + output].
Do not guess. Read the relevant source file(s) first, then explain why it fails
and what the fix is. Show the exact lines to change.
```

```
Add temporary debug logging to trace the value of [variable] through
[function/flow]. Use the project's existing logger. Remove the logging
once we've confirmed the fix.
```

### Agentic / Multi-step Tasks

```
Complete this task end-to-end: [describe task].
After each major step, tell me what you did and what comes next.
Stop and ask if you're about to do something destructive or irreversible.
```

```
Audit this codebase for [concern: e.g. "N+1 queries", "missing auth checks",
"deprecated API calls"]. For each finding, report: file, line, severity (high/medium/low),
and a one-line fix. Stop after 10 findings.
```

### Git & Commits

```
Summarize all changes on this branch vs main in plain English.
Group by: new features, bug fixes, refactors, test changes, config changes.
```

```
Write a commit message for the staged changes. Follow [conventional commits /
the style in recent git log]. Keep the subject under 72 chars.
Explain the WHY in the body, not the what.
```

---

## Software Engineering

### Architecture & Design

```
I need to design [system/feature]. Here are the constraints: [list constraints].
Give me 2-3 design options. For each: name it, describe it in 3 sentences,
list the main trade-off. Don't recommend one yet—I'll ask after.
```

```
Review this architecture diagram / description: [paste].
What are the single points of failure? What breaks first under 10x load?
What would you change and why?
```

### Refactoring

```
Refactor [function/class] to be more readable. Rules:
- Don't change behavior
- Don't change the public interface
- Don't introduce new abstractions unless they reduce duplication by 3+ uses
- Keep the same language idioms as the surrounding code
```

```
This function is 200 lines. Break it into smaller pieces.
Each piece should do one thing and have a name that describes what it does.
Show me the plan before writing any code.
```

### Performance

```
Profile this code path mentally: [paste code].
Where are the likely hotspots? Rank them by impact.
Suggest one targeted optimization per hotspot. Don't change anything yet.
```

```
This query is slow: [paste SQL or ORM call].
Explain the execution plan in plain English.
Suggest the minimal index or query change to fix it.
```

### Security

```
Review this code for security issues: [paste code].
Focus on OWASP Top 10. For each finding: describe the vulnerability,
show the vulnerable line(s), and show a corrected version.
```

```
I'm storing [type of sensitive data]. What's the correct approach for:
encryption at rest, encryption in transit, access control, and audit logging?
Be specific to [language/stack].
```

### Documentation

```
Write a docstring for this function: [paste function].
Cover: what it does, each parameter (name, type, meaning), return value,
and any exceptions it can raise. Be concise—no filler sentences.
```

```
Write a README section explaining how to [set up / use / configure] [feature].
Audience: a developer who hasn't touched this codebase before.
Include: prerequisites, step-by-step instructions, and one worked example.
```

### Code Explanation

```
Explain this code to me as if I'm familiar with programming but not this codebase:
[paste code].
Walk through what it does line by line, then give me a 2-sentence TL;DR.
```

```
What does [library/function/pattern] actually do under the hood?
Skip the docs summary—I want to understand the mechanism.
```

---

## General Use & Productivity

### Summarization

```
Summarize this in [3 bullets / 1 paragraph / 200 words]: [paste content].
Preserve the key numbers, names, and decisions. Cut everything else.
```

```
I have 10 items to read. Triage them: for each, give a title, a one-sentence
summary, and a recommended action (read now / skim / skip).
[paste list]
```

### Analysis & Research

```
I need to understand [topic] well enough to make a decision about [decision].
Give me: the key concepts (5 max), the main options/approaches, and the
most common pitfall. Cite your uncertainty where relevant.
```

```
Compare [A] vs [B] for my use case: [describe use case].
Give me a table: criterion, A score (1-5), B score (1-5), notes.
Then give a one-sentence recommendation.
```

### Brainstorming

```
Give me 10 ideas for [goal/problem]. Be specific—no generic suggestions.
For each, give a name and one sentence on how it works.
Mark your top 3 with a star.
```

```
I'm stuck on [problem]. Constraints: [list constraints].
Generate 5 unconventional approaches. Prioritize novelty over safety.
```

### Writing & Editing

```
Rewrite this to be clearer and more concise. Keep my meaning intact.
Cut anything that doesn't add information: [paste text].
```

```
This draft is too [long / jargon-heavy / passive / vague]. Fix that specific issue
without rewriting everything: [paste text].
```

### Decision Making

```
I need to decide between [A] and [B].
Here's my context: [describe situation].
Play devil's advocate for both sides. Don't tell me what to do yet.
```

```
Help me pressure-test this decision: [describe decision].
What assumptions am I making? Which one, if wrong, would most change my choice?
```

### Asking Better Questions

```
I'm going to ask Claude to do [task]. Help me write a clearer, more effective
version of my prompt. Here's my rough draft: [paste prompt].
```

```
What information would you need from me to give a better answer to: [question]?
List the 3 most important missing details.
```

---

## Tips for Better Prompts

| Pattern | Example |
|---|---|
| **Scope the output** | "Give me 3 options, not a full implementation" |
| **Specify the audience** | "Explain as if to a senior engineer, not a beginner" |
| **Separate research from action** | "First list what you'd change, then wait for approval" |
| **Name the constraint** | "Don't add new dependencies", "Keep the public API unchanged" |
| **Ask for uncertainty** | "Flag anything you're not confident about" |
| **Limit list length** | "Top 5 only — no padding" |
| **Request plain language** | "Explain the mechanism, not the marketing" |
| **Set the format explicitly** | "Respond as a table: column A, column B, column C" |
