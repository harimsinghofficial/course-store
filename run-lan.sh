#!/bin/bash
# Like run-dev.sh, but reachable from phones/laptops on the same Wi-Fi. For local testing only.
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python) || { echo "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
bash scripts/build-frontend.sh || exit 1
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
[ -n "$IP" ] || { echo "Could not find your Wi-Fi IP. Connect to Wi-Fi and try again."; exit 1; }
export ALLOWED_HOSTS="*"          # accept any Host header (dev only; never use in production)
export BASE_URL="http://$IP:8000"
echo ""
echo "On this computer:      http://localhost:8000"
echo "On other devices:      http://$IP:8000   (same Wi-Fi)"
echo "Ctrl+C to stop."
echo ""
exec python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 --no-server-header
