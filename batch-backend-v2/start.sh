#!/bin/bash
# Antigravity Engine v2.0 — Startup Script

set -e

PORT=8000
VENV_PATH="./.venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

# 1. Create/activate virtual environment
if [ ! -d "$VENV_PATH" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    echo "📥 Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source "$VENV_PATH/bin/activate"
fi

# 2. Check exiftool
if ! command -v exiftool &> /dev/null; then
    echo "⚠️  exiftool not found. Install with: brew install exiftool"
    echo "   The engine will work without it, but preview extraction will be limited."
fi

# 3. Show network info
MINI_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀 Antigravity Engine v2.0"
echo "  📡 http://$MINI_IP:$PORT"
echo "  📡 http://localhost:$PORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 4. Launch
uvicorn main:app --host 0.0.0.0 --port $PORT --reload
