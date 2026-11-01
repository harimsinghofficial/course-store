#!/bin/bash
# Builds the React app into frontend/dist when it is missing or older than the source. Needs Node 20+.
cd "$(dirname "$0")/../frontend" || exit 1
command -v node >/dev/null || { echo "Node.js 20+ is required: https://nodejs.org/"; exit 1; }
NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
[ "$NODE_MAJOR" -ge 20 ] || { echo "Node.js 20+ is required (you have $(node -v))."; exit 1; }
[ -d node_modules ] || npm ci --no-audit --no-fund || npm install --no-audit --no-fund || exit 1
if [ ! -f dist/index.html ] || [ -n "$(find src index.html package.json vite.config.js -newer dist/index.html -type f 2>/dev/null | head -1)" ]; then
  echo "Building the React frontend..."
  npm run build || exit 1
fi
