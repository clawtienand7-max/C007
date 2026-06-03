#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  TFNK™ Neural Agent Desktop — Linux / macOS startup script
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ─── ASCII banner ─────────────────────────────────────────────────────────────
cat <<'EOF'

  ████████╗███████╗███╗   ██╗██╗  ██╗
  ╚══██╔══╝██╔════╝████╗  ██║██║ ██╔╝
     ██║   █████╗  ██╔██╗ ██║█████╔╝
     ██║   ██╔══╝  ██║╚██╗██║██╔═██╗
     ██║   ██║     ██║ ╚████║██║  ██╗
     ╚═╝   ╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═╝

  TFNK™ 神經代理桌面  —  自主 AI 代理工作站
  ─────────────────────────────────────────
EOF

echo ""
echo "  Project root : ${PROJECT_ROOT}"

# ─── Activate virtual environment if present ──────────────────────────────────
VENV_DIRS=("${PROJECT_ROOT}/venv" "${PROJECT_ROOT}/.venv")
for venv in "${VENV_DIRS[@]}"; do
    if [ -f "${venv}/bin/activate" ]; then
        echo "  Activating   : ${venv}"
        # shellcheck disable=SC1091
        source "${venv}/bin/activate"
        break
    fi
done

# ─── Change to project root ───────────────────────────────────────────────────
cd "${PROJECT_ROOT}"

# ─── Load .env if present ─────────────────────────────────────────────────────
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source ".env"
    set +a
fi

TFNK_HOST="${TFNK_HOST:-0.0.0.0}"
TFNK_PORT="${TFNK_PORT:-8000}"
TFNK_LOG_LEVEL="${TFNK_LOG_LEVEL:-info}"

echo "  Server       : http://${TFNK_HOST}:${TFNK_PORT}"
echo "  Log level    : ${TFNK_LOG_LEVEL}"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# ─── Launch FastAPI ───────────────────────────────────────────────────────────
exec uvicorn webui.server:app \
    --host "${TFNK_HOST}" \
    --port "${TFNK_PORT}" \
    --log-level "${TFNK_LOG_LEVEL}"
