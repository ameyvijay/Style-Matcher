#!/bin/bash
# Antigravity Engine Shutdown Utility v2.1
# Executed by 'Stop Engine.app'

echo "🛑 Shutting down Antigravity Kernel..."
lsof -t -i :8000 | xargs kill -9 2>/dev/null || true
pkill -f "ngrok http 8000" || true

echo "✅ Engine Offline."
osascript -e 'display notification "Kernel and Tunnel have been terminated." with title "🛑 Antigravity Engine" subtitle "System Offline"'

exit 0
