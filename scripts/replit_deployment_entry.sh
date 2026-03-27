#!/bin/sh
set -e

echo "=== 850 Lab Deployment ==="

echo "[1/2] Building React frontend..."
cd web
npm install --production=false 2>&1
npm run build 2>&1
cd ..
echo "[1/2] Frontend build complete."

echo "[2/2] Starting FastAPI (serves API + React frontend)..."
exec python -m uvicorn api.workflow_app:app --host 0.0.0.0 --port 5000
