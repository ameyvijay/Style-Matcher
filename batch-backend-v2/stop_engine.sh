#!/bin/bash
lsof -t -i :8000 | xargs kill -9 2>/dev/null || true
pkill -f "ngrok http 8000" || true
exit 0
