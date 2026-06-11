"""The driver loop — the "motor" that keeps Claude moving toward a goal.

It is a bounded agentic loop:

    [load mission + any saved state]
            |
       repeat (up to MAX_ITERATIONS):
          1. send the running conversation to the model (streamed)
          2. if the model called tools -> execute them, feed results back
          3. else inspect the text:
                - contains COMPLETION_SENTINEL  -> done, break
                - otherwise nudge it to continue
          4. checkpoint the conversation to disk (resume-safe)
            |
    [final report]

There is no `while True`. The iteration cap and on-disk checkpoint are the
real "defensive mechanisms" — they stop runaway spend and let a killed
process pick up exactly where it left off.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from . import tools

load_dotenv()

MODEL = os.environ.get("AGENT_MODEL", "claude-opus-4-8")
EFFORT = os.environ.get("AGENT_EFFORT", "high")
MAX_ITERATIONS = int(os.environ.get("AGENT_MAX_ITERATIONS", "50"))
MAX_TOKENS = 16000

COMPLETION_SENTINEL = "[MISSION_COMPLETED]"
STATE_DIR = Path("state")

SYSTEM_PROMPT = f"""\
You are an autonomous agent working toward a goal with no human watching in \
real time. You drive yourself one step at a time using the tools available to \
you.

How to operate:
- Each turn, take the next concrete step toward the goal. When you have enough \
information to act, act — don't re-derive what's already established or narrate \
options you won't pursue.
- Use tools to inspect and change the workspace. Report progress against actual \
tool results, not assumptions.
- When (and only when) the goal is fully achieved and verified, end your final \
message with the exact token {COMPLETION_SENTINEL} on its own line. Do not write \
that token until the work is genuinely done and checked — it stops the loop.
- If you become permanently blocked and cannot make progress, explain why and \
end your message with the token [MISSION_BLOCKED] on its own line.
"""


def _log(msg: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def _text_of(content_blocks) -> str:
    return "\n".join(b.text for b in content_blocks if b.type == "text")


def _checkpoint(run_id: str, messages: list, iteration: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"iteration": iteration, "messages": messages}
    (STATE_DIR / f"{run_id}.json").write_text(json.dumps(payload, indent=2, default=str))


def _load_checkpoint(run_id: str) -> tuple[list, int]:
    path = STATE_DIR / f"{run_id}.json"
    if path.is_file():
        data = json.loads(path.read_text())
        return data["messages"], data["iteration"]
    return [], 0


def run_mission(mission: str, run_id: str = "default", resume: bool = False) -> str:
    """Drive the agent until the goal is reached, blocked, or the cap is hit.

    Returns one of: "completed", "blocked", "max_iterations".
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    messages, start_iter = ([], 0)
    if resume:
        messages, start_iter = _load_checkpoint(run_id)
        if messages:
            _log(f"resuming '{run_id}' from iteration {start_iter}")

    if not messages:
        messages = [{"role": "user", "content": f"GOAL:\n{mission}"}]

    for iteration in range(start_iter, MAX_ITERATIONS):
        _log(f"--- iteration {iteration + 1}/{MAX_ITERATIONS} ---")

        # Streaming avoids HTTP timeouts on long reasoning; get_final_message
        # reassembles the full response for us. The SDK retries 429/5xx itself.
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            tools=tools.SCHEMAS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                _log(f"tool: {block.name} {json.dumps(block.input)[:120]}")
                result_text, is_error = tools.execute(block.name, block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                    "is_error": is_error,
                })
            messages.append({"role": "user", "content": results})
            _checkpoint(run_id, messages, iteration + 1)
            continue

        # No tool call -> the model produced a text turn. Inspect it.
        text = _text_of(response.content)
        if text.strip():
            _log(f"model: {text.strip()[:200]}")

        if COMPLETION_SENTINEL in text:
            _log("mission complete.")
            _checkpoint(run_id, messages, iteration + 1)
            return "completed"
        if "[MISSION_BLOCKED]" in text:
            _log("mission blocked by the agent.")
            _checkpoint(run_id, messages, iteration + 1)
            return "blocked"

        # Stopped without finishing — feed its own output back as the next step.
        messages.append({
            "role": "user",
            "content": "Continue toward the goal. Output the completion token only when truly done.",
        })
        _checkpoint(run_id, messages, iteration + 1)
        time.sleep(0.5)  # gentle pacing between turns

    _log(f"hit iteration cap ({MAX_ITERATIONS}) without completing.")
    return "max_iterations"
