#!/bin/bash
# Antigravity Engine v3.0 — Hybrid-Cloud Unified Bootstrapper
# Optimized for Mac Mini M4 Studio Worker Node

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Load Control Plane Environment
if [ -f .env.local ]; then
    echo "🔑 Loading .env.local..."
    export $(grep -v '^#' .env.local | xargs)
else
    echo "⚠️  WARNING: .env.local not found. Using system defaults."
fi

# 2. Cleanup Zombie Processes
echo "🧹 Cleaning up existing Antigravity processes..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
pkill -f "sync_watchdog.py" || true

# 3. Environment Prep
source .venv/bin/activate
export PYTHONUNBUFFERED=1

# 4. Launch Backend API (Control Plane Bridge)
echo "🚀 Booting FastAPI Gateway (Stay Awake Enabled)..."
# -i prevents system idle sleep, -s prevents system sleep, -d prevents display sleep
nohup caffeinate -isd python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!

# 5. Launch Cloud Worker (GPS fulfilment)
echo "📡 Initializing Firestore Pull Listener..."
nohup caffeinate -is python3 sync_watchdog.py > sync_watchdog.out.log 2>&1 &
WORKER_PID=$!

# 6. Terminal Dashboard
clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀 ANTIGRAVITY HYBRID-CLOUD ENGINE v3.0"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ● Backend Gateway:  PID [$BACKEND_PID] - Port 8000"
echo "  ● Cloud Worker:     PID [$WORKER_PID]"
echo "  ● Source Root:      $SOURCE_ROOT"
echo "  ● Master Root:      $LOCAL_MASTER_ROOT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📡 Streaming Real-time Worker Logs:"
echo ""

# Tail the watchdog log to provide a live observation window
tail -f sync_watchdog.out.log
