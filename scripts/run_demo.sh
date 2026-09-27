#!/usr/bin/env bash
# Start the BRE dashboard in demo mode (simulated Bob) on http://127.0.0.1:8000
#   scripts/run_demo.sh            simulated Bob
#   scripts/run_demo.sh --live     real IBM Bob (needs Bob Shell on PATH and BOB_API_KEY set)
set -euo pipefail
cd "$(dirname "$0")/.."
export BRE_DEMO=1 BRE_DEMO_DIR="${TMPDIR:-/tmp}/bre-demo" BRE_OPERATOR_KEY=demo-operator-key \
       BRE_OPERATOR_NAME="Demo operator" BRE_DEMO_SHOW_KEY=1 BRE_TAU=0.30
if [[ "${1:-}" == "--live" ]]; then unset BRE_BOB_TRANSPORT; MODE=LIVE; else export BRE_BOB_TRANSPORT=replay; MODE=SIMULATED; fi
PY=venv/bin/python; [[ -x venv/Scripts/python.exe ]] && PY=venv/Scripts/python.exe; command -v "$PY" >/dev/null || PY=python3
echo "BRE dashboard: http://127.0.0.1:${PORT:-8000}   (Bob: $MODE)"
echo "Video walkthrough (script beside the real dashboard): http://127.0.0.1:${PORT:-8000}/walkthrough"
exec "$PY" -m uvicorn apps.api.main:app --host 127.0.0.1 --port "${PORT:-8000}"
