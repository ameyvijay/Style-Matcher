#!/bin/bash
# Antigravity Engine MLOps Wrapper v2.1
# Executed by 'Start Engine.app'

echo "🚀 Booting Antigravity Kernel..."
cd /Users/shivamagent/Desktop/Style-Matcher/batch-backend-v2

# 1. Kill any zombie instances quietly
lsof -t -i :8000 | xargs kill -9 2>/dev/null || true
pkill -f "ngrok http 8000" || true

# 2. Boot the FastAPI Backend Engine
source .venv/bin/activate
export ENGINE_STATUS="online"
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

# 3. Boot the Ngrok tunnel
echo "🌐 Opening Global Tunnel..."
nohup ngrok http 8000 --domain=embroider-fragment-flight.ngrok-free.dev > ngrok.log 2>&1 &

# 4. Wait for stability & notify
sleep 3
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Engine is ONLINE"
    osascript -e 'display notification "Kernel is active and reachable via Ngrok." with title "🚀 Antigravity Engine" subtitle "System Online"'
else
    echo "❌ Engine FAILED to start. Check backend.log"
    osascript -e 'display notification "Kernel failed to boot. Check logs." with title "⚠️ Engine Error"'
fi

exit 0
