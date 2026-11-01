#!/bin/bash
# One command (macOS / Linux): installs Python + Node packages, builds the React app, starts the server.
#   ./run-dev.sh        build once, serve everything from FastAPI on :8000
#   ./run-dev.sh hot    also start the Vite dev server on :5173 with instant hot reload
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python) || { echo "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
bash scripts/build-frontend.sh || exit 1
if [ "$1" = "hot" ]; then
  (cd frontend && npm run dev -- --host 127.0.0.1) &
  VITE_PID=$!
  trap 'kill $VITE_PID 2>/dev/null' EXIT
  echo "Hot-reload site (use this while editing):  http://localhost:5173"
fi
echo "Site served by FastAPI:                    http://localhost:8000   (Ctrl+C to stop)"
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000 --no-server-header
