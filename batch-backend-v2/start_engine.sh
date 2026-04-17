#!/bin/bash
# Antigravity Engine MLOps Wrapper
# Executed silently by 'Start Engine.app'

cd /Users/shivamagent/Desktop/Style-Matcher/batch-backend-v2

# 1. Kill any zombie instances quietly
lsof -t -i :8000 | xargs kill -9 2>/dev/null || true
pkill -f "ngrok http 8000" || true

# 2. Boot the FastAPI Backend Engine
source .venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

# Wait 5 seconds for self-tests to pass
sleep 5

# 3. Boot the Ngrok tunnel
nohup ngrok http 8000 --domain=embroider-fragment-flight.ngrok-free.dev > ngrok.log 2>&1 &

# Exit cleanly
exit 0
