"""Tools the agent can call to actually do work.

Each tool is (1) a JSON schema the model sees and (2) a Python function the
loop executes. This is what turns the loop from a chatbot into something that
takes real actions. Everything is confined to WORKSPACE so a runaway agent
can't wander the whole filesystem.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# All file/command activity is sandboxed under here.
WORKSPACE = Path("workspace").resolve()


def _safe_path(relative: str) -> Path:
    """Resolve a path and refuse anything that escapes the workspace."""
    target = (WORKSPACE / relative).resolve()
    if WORKSPACE not in target.parents and target != WORKSPACE:
        raise ValueError(f"path {relative!r} escapes the workspace")
    return target


# --- tool implementations -------------------------------------------------


def run_bash(command: str, timeout: int = 120) -> str:
    """Run a shell command inside the workspace and return combined output."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[error] command timed out after {timeout}s"
    out = (proc.stdout or "") + (proc.stderr or "")
    return f"[exit {proc.returncode}]\n{out.strip() or '(no output)'}"


def read_file(path: str) -> str:
    target = _safe_path(path)
    if not target.is_file():
        return f"[error] no such file: {path}"
    return target.read_text(encoding="utf-8", errors="replace")


def write_file(path: str, content: str) -> str:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"[ok] wrote {len(content)} chars to {path}"


# --- dispatch + schemas the model sees ------------------------------------

DISPATCH = {
    "run_bash": lambda i: run_bash(i["command"], i.get("timeout", 120)),
    "read_file": lambda i: read_file(i["path"]),
    "write_file": lambda i: write_file(i["path"], i["content"]),
}

SCHEMAS = [
    {
        "name": "run_bash",
        "description": (
            "Run a shell command in the workspace directory. Use for inspecting "
            "files, running scripts, installing packages, git, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
                "timeout": {"type": "integer", "description": "Seconds before giving up (default 120)."},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file from the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path relative to the workspace."}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a text file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the workspace."},
                "content": {"type": "string", "description": "Full file contents."},
            },
            "required": ["path", "content"],
        },
    },
]


def execute(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run a tool by name. Returns (result_text, is_error)."""
    fn = DISPATCH.get(name)
    if fn is None:
        return f"[error] unknown tool: {name}", True
    try:
        return fn(tool_input), False
    except Exception as exc:  # surface the error to the model so it can adapt
        return f"[error] {type(exc).__name__}: {exc}", True
