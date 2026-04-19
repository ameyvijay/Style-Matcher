#!/bin/bash
LOG_FILE="/Users/shivamagent/Desktop/Style-Matcher/batch-backend-v2/sync_watchdog.out.log"
KILLSWITCH="/Users/shivamagent/Desktop/Style-Matcher/batch-backend-v2/chaos_killswitch.json"

echo "Auto-Severance daemon started. Monitoring $LOG_FILE"
tail -f "$LOG_FILE" | while read -r line; do
  echo "$line"
  # Target string from previous log: "📡 Syncing <N> assets to TrueNAS SCALE..."
  if echo "$line" | grep -q "Syncing .* to TrueNAS SCALE..."; then
    echo "=============================================="
    echo "🚨 TARGET SIGNAL DETECTED 🚨"
    echo "Triggering Killswitch..."
    touch "$KILLSWITCH"
    echo "Chaos killswitch engaged at $(date)"
    echo "=============================================="
    # exit the while loop
    break
  fi
done
echo "Auto-Severance daemon exiting."
