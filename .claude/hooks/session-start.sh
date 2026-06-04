#!/bin/bash
# SessionStart hook for C007 (TFNK Neural Agent Desktop App).
# Installs project dependencies so tests/linters work in Claude Code on the web.
# Forward-compatible: no-ops cleanly until a manifest exists.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}"

# Node / Electron app
if [ -f package.json ]; then
  echo "[session-start] package.json found -> installing npm dependencies"
  npm install
fi

# Python (pip / requirements)
if [ -f requirements.txt ]; then
  echo "[session-start] requirements.txt found -> pip install"
  pip install -r requirements.txt
fi

# Python (pyproject / Poetry-style)
if [ -f pyproject.toml ] && [ ! -f requirements.txt ]; then
  echo "[session-start] pyproject.toml found -> pip install ."
  pip install -e . || pip install .
fi

if [ ! -f package.json ] && [ ! -f requirements.txt ] && [ ! -f pyproject.toml ]; then
  echo "[session-start] No dependency manifest yet — nothing to install. Hook is ready for when you add one."
fi
