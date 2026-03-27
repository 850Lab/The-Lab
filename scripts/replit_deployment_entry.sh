#!/bin/sh
# Replit deployment: workflow API (8000) + Streamlit (5000). Trap stops uvicorn when Streamlit exits.
set -e
uvicorn_pid=""
cleanup() {
  if [ -n "$uvicorn_pid" ]; then
    kill "$uvicorn_pid" 2>/dev/null || true
    wait "$uvicorn_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

python -m uvicorn api.workflow_app:app --host 0.0.0.0 --port 8000 &
uvicorn_pid=$!

exec streamlit run app.py \
  --server.port 5000 \
  --server.address 0.0.0.0 \
  --server.headless true
