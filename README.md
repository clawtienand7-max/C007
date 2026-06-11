# Unattended Agent Loop

An external Python daemon that drives the Claude API in a bounded loop, feeding
each step's result into the next, until the goal is reached. This is the "motor
and treads" that lets the model run unattended instead of being hand-fed one
prompt at a time.

```
[mission goal]
      │
 ┌────────────── bounded loop (run.py → agent/loop.py) ───────────────┐
 │ 1. send running conversation to Claude (streamed)                  │
 │ 2. Claude calls tools → loop executes them → results fed back      │
 │ 3. Claude emits [MISSION_COMPLETED] → break; else continue        │
 │ 4. checkpoint conversation to state/ (resume-safe)                 │
 └───────────────────────────────────────────────────────────────────┘
      │
[final report + exit code]
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then put your key in .env
```

## Run

```bash
python run.py missions/example.md                       # fresh run
python run.py missions/example.md --run-id nightly      # named run
python run.py missions/example.md --run-id nightly --resume   # resume after a kill
```

Exit codes: `0` completed · `1` blocked · `3` hit iteration cap. That lets you
chain it into cron, CI, or a shell script.

## How a mission ends

The agent is instructed (in `agent/loop.py`'s system prompt) to print the exact
token `[MISSION_COMPLETED]` on its own line **only when the goal is done and
verified**. The loop watches for that token and stops. `[MISSION_BLOCKED]` ends
it early if the agent is genuinely stuck.

Write goals so "done" is checkable — see `missions/example.md`.

## Files

| Path | Role |
|---|---|
| `run.py` | CLI entry point |
| `agent/loop.py` | the driver loop + system prompt + sentinel handling |
| `agent/tools.py` | what the agent can DO: `run_bash`, `read_file`, `write_file` (sandboxed to `workspace/`) |
| `missions/` | mission/goal files |
| `state/` | per-run conversation checkpoints (gitignored) |
| `workspace/` | where the agent's file/command work happens (gitignored) |

## Design notes (and a few honest corrections to the original spec)

- **Model & reasoning.** Uses `claude-opus-4-8` with adaptive thinking and
  `effort=high`. Override via env (`AGENT_MODEL`, `AGENT_EFFORT`).
- **No bare `while True`.** The loop is capped at `AGENT_MAX_ITERATIONS`
  (default 50). An unbounded loop is the fast path to a surprise bill.
- **Long-reasoning timeouts.** Handled by **streaming** (`messages.stream` +
  `get_final_message`), which is the correct fix — not by cranking a global
  timeout. The SDK also auto-retries `429`/`5xx` with backoff.
- **"Memory continuity."** Real continuity comes from sending the full
  conversation each turn (the API is stateless) plus the on-disk checkpoint in
  `state/`, which makes `--resume` exact after a crash.
- **The "30-second heartbeat to stop the OS sleeping" is not needed.** That's
  advice for keeping a *laptop* awake; a server/cloud process doesn't sleep.
  The genuine safety mechanisms here are the iteration cap, the checkpoint, and
  SDK retries. If you do want a liveness signal, the per-iteration timestamped
  log already provides one.
- **The "+300% / 99% / 0%" figures** in the original write-up are slogans, not
  measurements — intentionally left out.

## Tools & safety

`run_bash` executes real shell commands, confined to `workspace/`. That's
powerful and unattended — run this where a mistake is cheap (a container,
throwaway VM, or scratch dir), and keep missions scoped. Add an approval gate in
`agent/tools.execute` if you need a human in the loop for destructive actions.
