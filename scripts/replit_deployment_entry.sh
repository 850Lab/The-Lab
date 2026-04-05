#!/bin/sh
# Replit Autoscale deployment entry.
#
# Many Repl templates lock .replit to "public port 80 → local 5000". We cannot rely on
# git-pushed .replit edits, so the *customer* app must bind to 5000 here.
#
# - FastAPI + web/dist (React) → 5000 (this is what the public URL hits).
# - Streamlit admin → 5001 (open from Replit Ports / preview).
set -e
streamlit_pid=""
cleanup() {
  if [ -n "$streamlit_pid" ]; then
    kill "$streamlit_pid" 2>/dev/null || true
    wait "$streamlit_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

streamlit run app.py \
  --server.port 5001 \
  --server.address 0.0.0.0 \
  --server.headless true &
streamlit_pid=$!

exec python -m uvicorn api.workflow_app:app --host 0.0.0.0 --port 5000
