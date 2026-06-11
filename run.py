#!/usr/bin/env python3
"""Entry point for the unattended agent loop.

Usage:
    python run.py missions/example.md
    python run.py missions/example.md --run-id nightly --resume
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent.loop import run_mission


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an autonomous Claude agent loop.")
    parser.add_argument("mission", help="Path to a mission file (plain text / markdown).")
    parser.add_argument("--run-id", default="default", help="Name this run (used for checkpoints).")
    parser.add_argument("--resume", action="store_true", help="Resume from the saved checkpoint.")
    args = parser.parse_args()

    mission_path = Path(args.mission)
    if not mission_path.is_file():
        print(f"mission file not found: {mission_path}", file=sys.stderr)
        return 2

    mission = mission_path.read_text(encoding="utf-8").strip()
    outcome = run_mission(mission, run_id=args.run_id, resume=args.resume)

    # Exit codes let you chain this into cron / CI / shell scripts.
    return {"completed": 0, "blocked": 1, "max_iterations": 3}.get(outcome, 4)


if __name__ == "__main__":
    raise SystemExit(main())
