#!/bin/bash
# Production start-up (Linux/macOS). Every value comes from config.json; secrets come from .env.
cd "$(dirname "$0")" || exit 1
# Build the React app on the server if it is not built yet (or build in CI and copy frontend/dist).
[ -f frontend/dist/index.html ] || bash scripts/build-frontend.sh || exit 1
HOST=$(python3    -c "import json; print(json.load(open('config.json'))['server']['host'])")
PORT=$(python3    -c "import json; print(json.load(open('config.json'))['server']['port'])")
WORKERS=$(python3 -c "import json; print(json.load(open('config.json'))['server']['workers'])")
TIMEOUT=$(python3 -c "import json; print(json.load(open('config.json'))['server']['timeout'])")
FWD=$(python3     -c "import json; print(json.load(open('config.json'))['server']['forwarded_allow_ips'])")

export APP_ENV="${APP_ENV:-production}"
exec gunicorn main:app \
  --bind           "$HOST:$PORT" \
  --workers        "$WORKERS" \
  --worker-class   uvicorn.workers.UvicornWorker \
  --timeout        "$TIMEOUT" \
  --keep-alive     5 \
  --forwarded-allow-ips "$FWD" \
  --access-logfile - \
  --error-logfile  -
