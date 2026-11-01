@echo off
REM One-command local run (Windows): installs Python + Node packages, builds the React app, starts the server.
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv || python -m venv .venv)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if not exist .env copy .env.example .env >nul
where node >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & exit /b 1)
pushd frontend
if not exist node_modules call npm install --no-audit --no-fund
if not exist dist\index.html call npm run build
popd
echo Open http://localhost:8000  (Ctrl+C to stop)
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000 --no-server-header
