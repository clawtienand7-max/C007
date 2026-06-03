#!/usr/bin/env python3
"""
TFNK™ Scheduler Setup
Configures an OS-level recurring task that runs every 4.5 hours to resume
pending / paused agent tasks without requiring an active session.

Windows  -> Task Scheduler (schtasks)
Linux    -> cron  (user crontab)
macOS    -> launchd plist  (~/.local/share/launchd/com.tfnk.resume.plist)
"""

import os
import sys
import platform
import subprocess
import textwrap
from pathlib import Path

# ─── Project layout ───────────────────────────────────────────────────────────

ROOT       = Path(__file__).resolve().parent.parent
RESUME_CMD = f'"{sys.executable}" -m tfnk.resume_tasks'
LOCK_FILE  = ROOT / "logs" / "tfnk_scheduler.lock"

# 4.5 hours = 270 minutes
INTERVAL_MINUTES = 270

# ─── Colour helpers ───────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
WHITE  = "\033[97m"

def ok(m):   print(f"  {GREEN}[OK]{RESET}  {m}")
def warn(m): print(f"  {YELLOW}[WARN]{RESET} {m}")
def info(m): print(f"  {CYAN}[--]{RESET}  {m}")
def hdr(m):  print(f"\n{BOLD}{WHITE}{m}{RESET}")
def err(m):  print(f"  {RED}[ERR]{RESET} {m}")

# ─── Windows Task Scheduler ───────────────────────────────────────────────────

TASK_NAME = "TFNK_ResumeTask"

WINDOWS_WRAPPER = ROOT / "scripts" / "_run_resume.bat"

def _write_windows_wrapper() -> None:
    """Create a .bat that checks for a running lock before invoking Python."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    WINDOWS_WRAPPER.write_text(
        f"@echo off\n"
        f'IF EXIST "{LOCK_FILE}" (\n'
        f'    echo TFNK scheduler: session already running, skipping.\n'
        f'    EXIT /B 0\n'
        f')\n'
        f'echo %DATE% %TIME% > "{LOCK_FILE}"\n'
        f'cd /D "{ROOT}"\n'
        f'{RESUME_CMD}\n'
        f'DEL /Q "{LOCK_FILE}"\n',
        encoding="utf-8",
    )
    ok(f"Wrapper script: {WINDOWS_WRAPPER}")


def setup_windows() -> bool:
    hdr("Windows Task Scheduler")
    _write_windows_wrapper()

    # Trigger: every 270 minutes, starting at midnight
    trigger_duration = f"PT{INTERVAL_MINUTES}M"

    # Build schtasks command
    # /RI = repeat interval in minutes, /DU = duration (indefinite = 9999 days)
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/TR", str(WINDOWS_WRAPPER),
        "/SC", "MINUTE",
        "/MO", str(INTERVAL_MINUTES),
        "/RI", str(INTERVAL_MINUTES),
        "/DU", "9999:00",
        "/IT",  # only when user is logged in (interactive)
    ]

    info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            ok(f"Task '{TASK_NAME}' created successfully.")
            ok(f"Runs every {INTERVAL_MINUTES} minutes ({INTERVAL_MINUTES/60:.1f} h).")
            return True
        else:
            err(f"schtasks failed: {result.stderr.strip()}")
            warn("Try running this script as Administrator.")
            _print_windows_instructions()
            return False
    except FileNotFoundError:
        err("schtasks.exe not found — are you on Windows?")
        return False


def _print_windows_instructions() -> None:
    print(f"""
  {CYAN}Manual setup instructions (Windows):{RESET}
  1. Open Task Scheduler (taskschd.msc)
  2. Create Basic Task
     Name        : {TASK_NAME}
     Trigger     : Daily, repeat every {INTERVAL_MINUTES} min for 9999 days
     Action      : Start a program
     Program     : {WINDOWS_WRAPPER}
  3. In Conditions, uncheck "Start only on AC power" for laptops.
""")


# ─── Linux / macOS cron ───────────────────────────────────────────────────────

def setup_cron() -> bool:
    hdr("cron (Linux / macOS)")

    # Read existing crontab
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        err("crontab command not found.")
        return False

    marker   = "# TFNK_ResumeTask"
    cron_cmd = (
        f'[ -f "{LOCK_FILE}" ] && exit 0; '
        f'touch "{LOCK_FILE}"; '
        f'cd "{ROOT}" && {RESUME_CMD}; '
        f'rm -f "{LOCK_FILE}"'
    )
    # Every 270 minutes: cron doesn't support arbitrary intervals natively.
    # Use */270 with an hourly workaround via a time check, or simplify to
    # "every 4 hours" which is closest standard cron expression.
    # We add a python-level interval check inside resume_tasks.py.
    cron_line = f"0 */4 * * * {cron_cmd} {marker}"

    if marker in existing:
        info("Cron entry already exists — updating.")
        new_crontab = "\n".join(
            line for line in existing.splitlines() if marker not in line
        )
        new_crontab = new_crontab.rstrip("\n") + "\n" + cron_line + "\n"
    else:
        new_crontab = existing.rstrip("\n") + "\n" + cron_line + "\n"

    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    if proc.returncode == 0:
        ok("Cron entry installed (every 4 h, closest standard interval to 4.5 h).")
        ok(f"Command: {cron_cmd[:80]}...")
        return True
    else:
        err("Failed to install cron entry.")
        _print_cron_instructions(cron_line)
        return False


def _print_cron_instructions(cron_line: str) -> None:
    print(f"""
  {CYAN}Manual setup instructions (Linux / macOS):{RESET}
  Run:  crontab -e
  Add the following line:

  {YELLOW}{cron_line}{RESET}
""")


# ─── macOS launchd (alternative) ─────────────────────────────────────────────

def setup_launchd() -> bool:
    hdr("launchd (macOS alternative)")
    label   = "com.tfnk.resume"
    plist_dir  = Path.home() / "Library" / "LaunchAgents"
    plist_path = plist_dir / f"{label}.plist"
    plist_dir.mkdir(parents=True, exist_ok=True)

    interval_secs = INTERVAL_MINUTES * 60
    plist_content = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
            "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{label}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{sys.executable}</string>
                <string>-m</string>
                <string>tfnk.resume_tasks</string>
            </array>
            <key>WorkingDirectory</key>
            <string>{ROOT}</string>
            <key>StartInterval</key>
            <integer>{interval_secs}</integer>
            <key>RunAtLoad</key>
            <false/>
            <key>StandardOutPath</key>
            <string>{ROOT}/logs/launchd_resume.log</string>
            <key>StandardErrorPath</key>
            <string>{ROOT}/logs/launchd_resume_err.log</string>
        </dict>
        </plist>
    """)
    plist_path.write_text(plist_content, encoding="utf-8")
    ok(f"Plist written: {plist_path}")

    load_result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, text=True,
    )
    if load_result.returncode == 0:
        ok(f"launchd agent loaded: {label}")
        ok(f"Runs every {interval_secs} seconds ({INTERVAL_MINUTES / 60:.1f} h).")
        return True
    else:
        warn(f"launchctl load returned: {load_result.stderr.strip()}")
        info(f"Manual load:  launchctl load {plist_path}")
        return True  # plist written, user can load manually


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"""
{BOLD}{CYAN}  TFNK™ Scheduler Setup{RESET}
  Configures a recurring task every {INTERVAL_MINUTES} min ({INTERVAL_MINUTES/60:.1f} h)
  to resume pending/paused agent tasks automatically.
""")

    system = platform.system()
    success = False

    if system == "Windows":
        success = setup_windows()
    elif system == "Darwin":
        # Prefer launchd on macOS for better integration
        success = setup_launchd()
        if not success:
            info("Falling back to cron...")
            success = setup_cron()
    else:
        success = setup_cron()

    print()
    if success:
        print(f"{BOLD}{GREEN}Scheduler configured successfully.{RESET}")
        print(f"\n  The scheduler will run  {CYAN}python -m tfnk.resume_tasks{RESET}")
        print(f"  every {INTERVAL_MINUTES} minutes and will:")
        print(f"    - Skip if a session is already running (lock file check)")
        print(f"    - Resume PENDING / PAUSED tasks that don't need authorisation")
        print(f"    - Route auth-required tasks to  {CYAN}logs/pending_auth.json{RESET}")
        print(f"    - Send a Tailscale push notification when available")
    else:
        print(f"{BOLD}{YELLOW}Scheduler setup encountered issues — see above for details.{RESET}")

    print()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
