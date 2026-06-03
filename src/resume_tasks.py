"""
TFNK™ resume_tasks.py
─────────────────────
Invoked by the OS scheduler every ~4.5 hours.

Behaviour
- Load pending tasks from disk (logs/task_queue.json)
- Skip any task that requires human authorisation  -> logs/pending_auth.json
- Resume all remaining tasks
- Attempt a Tailscale push notification (non-fatal if unavailable)
- Write a summary to logs/resume_run.log

Run directly:   python -m tfnk.resume_tasks
Or via module:  python src/resume_tasks.py
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────────────────

# Support both  python -m tfnk.resume_tasks  and  python src/resume_tasks.py
_SELF    = Path(__file__).resolve()
_SRC     = _SELF.parent
_ROOT    = _SRC.parent if _SRC.name == "src" else _SRC

LOGS_DIR        = _ROOT / "logs"
TASK_QUEUE_FILE = LOGS_DIR / "task_queue.json"
PENDING_AUTH    = LOGS_DIR / "pending_auth.json"
RESUME_LOG      = LOGS_DIR / "resume_run.log"

# ─── Logging ─────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(RESUME_LOG, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tfnk.resume_tasks")

# ─── Task status constants ────────────────────────────────────────────────────

STATUS_PENDING   = "PENDING"
STATUS_PAUSED    = "PAUSED"
STATUS_RUNNING   = "RUNNING"
STATUS_DONE      = "DONE"
STATUS_AUTH_REQ  = "AUTH_REQUIRED"

RESUMABLE_STATUSES = {STATUS_PENDING, STATUS_PAUSED}

# ─── Task loading / saving ───────────────────────────────────────────────────

def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read %s: %s", path, exc)
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_task_queue() -> list[dict]:
    data = _load_json(TASK_QUEUE_FILE, [])
    if not isinstance(data, list):
        log.warning("task_queue.json has unexpected format — treating as empty.")
        return []
    return data


def save_task_queue(tasks: list[dict]) -> None:
    _save_json(TASK_QUEUE_FILE, tasks)


def append_pending_auth(task: dict) -> None:
    existing = _load_json(PENDING_AUTH, [])
    if not isinstance(existing, list):
        existing = []
    # Avoid duplicates by task id
    ids = {t.get("id") for t in existing if isinstance(t, dict)}
    if task.get("id") not in ids:
        existing.append(task)
        _save_json(PENDING_AUTH, existing)
        log.info("Task %s added to pending_auth.json", task.get("id", "?"))


# ─── Task execution ───────────────────────────────────────────────────────────

def resume_task(task: dict) -> bool:
    """
    Attempt to resume a single task.

    The actual work is delegated back to the running TFNK™ FastAPI server via
    a local HTTP call if it is available, or falls back to a direct Python call
    into the agent runtime.

    Returns True if the task was successfully dispatched.
    """
    task_id   = task.get("id", "<unknown>")
    task_type = task.get("type", "generic")
    log.info("Resuming task id=%s type=%s", task_id, task_type)

    # Strategy 1: REST call to the local server (preferred when Tauri app runs)
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({"task_id": task_id, "action": "resume"}).encode()
        req = urllib.request.Request(
            "http://localhost:8000/api/tasks/resume",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("ok"):
                log.info("Task %s resumed via REST API", task_id)
                task["status"] = STATUS_RUNNING
                task["resumed_at"] = _now_iso()
                return True
            log.warning("REST resume returned not-ok: %s", body)
    except Exception as exc:
        log.debug("REST resume failed (%s), falling back to direct call", exc)

    # Strategy 2: Direct import into agent_runtime (offline / standalone mode)
    try:
        sys.path.insert(0, str(_ROOT))
        from agent_runtime import resume_task as _rt_resume  # type: ignore
        result = _rt_resume(task)
        if result:
            log.info("Task %s resumed via agent_runtime", task_id)
            task["status"] = STATUS_RUNNING
            task["resumed_at"] = _now_iso()
            return True
        log.warning("agent_runtime.resume_task returned falsy for task %s", task_id)
    except ImportError:
        log.debug("agent_runtime not importable — no direct fallback available")
    except Exception as exc:
        log.error("Direct resume of task %s raised: %s", task_id, exc)

    return False


# ─── Tailscale push notification ─────────────────────────────────────────────

def _tailscale_push(message: str) -> bool:
    """
    Send a push notification via Tailscale's local notify daemon.
    Silently returns False if Tailscale is not available.
    """
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        status = json.loads(result.stdout)
        self_node = status.get("Self", {})
        hostname  = self_node.get("HostName", "tfnk-node")

        # Use tailscale builtins if available; otherwise skip silently
        notify_result = subprocess.run(
            ["tailscale", "push", "--message", message],
            capture_output=True, text=True, timeout=10,
        )
        if notify_result.returncode == 0:
            log.info("Tailscale push notification sent from %s", hostname)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    except Exception as exc:
        log.debug("Tailscale push failed: %s", exc)
    return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─── Main logic ──────────────────────────────────────────────────────────────

def run() -> None:
    start_ts = time.monotonic()
    log.info("=== TFNK™ resume_tasks started at %s ===", _now_iso())

    tasks = load_task_queue()
    log.info("Loaded %d task(s) from queue", len(tasks))

    auth_count    = 0
    resumed_count = 0
    failed_count  = 0
    skipped_count = 0

    for task in tasks:
        status = task.get("status", STATUS_PENDING)

        # Skip tasks that are already done or currently running
        if status not in RESUMABLE_STATUSES:
            log.debug("Skipping task %s with status=%s", task.get("id"), status)
            skipped_count += 1
            continue

        # Auth-required tasks go to pending_auth.json
        if task.get("requires_auth") or status == STATUS_AUTH_REQ:
            log.info("Task %s requires authorisation — deferring to pending_auth.json", task.get("id"))
            append_pending_auth(task)
            task["status"] = STATUS_AUTH_REQ
            auth_count += 1
            continue

        # Attempt resume
        ok = resume_task(task)
        if ok:
            resumed_count += 1
        else:
            failed_count += 1

    # Persist updated statuses back to queue
    save_task_queue(tasks)

    elapsed = time.monotonic() - start_ts
    summary = (
        f"Completed in {elapsed:.1f}s — "
        f"resumed={resumed_count} auth_deferred={auth_count} "
        f"failed={failed_count} skipped={skipped_count}"
    )
    log.info(summary)
    log.info("=== TFNK™ resume_tasks finished ===")

    # Push notification via Tailscale (non-fatal)
    if resumed_count > 0 or auth_count > 0:
        notif_msg = (
            f"TFNK Scheduler: resumed {resumed_count} task(s)"
            + (f", {auth_count} awaiting your approval" if auth_count else "")
        )
        if not _tailscale_push(notif_msg):
            log.debug("Tailscale not available — skipping push notification")


# ─── Entry points ─────────────────────────────────────────────────────────────

def main() -> int:
    try:
        run()
        return 0
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        return 0
    except Exception as exc:
        log.exception("Unhandled exception in resume_tasks: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
