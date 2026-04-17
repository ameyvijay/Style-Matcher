#!/usr/bin/env python3
"""
Antigravity Engine - Sync Watchdog Daemon
Independent Spooler for TrueNAS Durable Storage

Execution: Run as a standalone daemon via launchd.
"""

import sys
import time
import subprocess
import asyncio
from datetime import datetime

from sqlalchemy.orm import Session
from database import SessionLocal, SyncQueue

# Configuration
NAS_TARGET = "admin@100.x.y.z:/mnt/pool/nas_dataset/"
MAX_RETRIES = 5
POLL_INTERVAL_SEC = 30

def check_tailscale_status() -> bool:
    """Pre-flight check: ensure the Tailscale tunnel is active."""
    try:
        # Note: adjust tailscale path if it's uniquely installed on the M4 Studio
        result = subprocess.run(
            ["/Applications/Tailscale.app/Contents/MacOS/Tailscale", "status", "--json"],
            capture_output=True, timeout=5
        )
        # Using a simple check here; if the binary runs and returns 0, tailscale daemon is up.
        # Ideally, we would parse JSON to look for the specific 100.x.y.z node, but this prevents
        # immediate crashes if the ISP drops the whole tunnel.
        return result.returncode == 0
    except Exception as e:
        # Simple fallback ping test
        try:
            ping_res = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "100.x.y.z"],
                capture_output=True, timeout=3
            )
            return ping_res.returncode == 0
        except Exception:
            return False


async def sync_directory(session: Session, queue_item: SyncQueue):
    """Executes the hardened rsync pass to TrueNAS."""
    queue_item.status = "SYNCING"
    queue_item.last_attempt_timestamp = datetime.utcnow()
    session.commit()

    print(f"[{datetime.now()}] 📡 Initiating TrueNAS Sync for {queue_item.enhanced_dir_path}")

    try:
        # Hardened Rsync command
        # --partial and --append-verify allow for robust recovery of massive 60MP files automatically.
        result = subprocess.run(
            [
                "rsync", "-av", "--partial", "--append-verify", "--timeout=60",
                f"{queue_item.enhanced_dir_path}/", NAS_TARGET
            ],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            queue_item.status = "COMPLETED"
            print(f"[{datetime.now()}] ✅ Successfully synced {queue_item.enhanced_dir_path}")
        else:
            # Typical error codes: 10 (Socket I/O), 12 (Stream Error), 23 (Partial Transfer), 30 (Timeout)
            print(f"[{datetime.now()}] ⚠️ Rsync Exit Code {result.returncode} for {queue_item.enhanced_dir_path}")
            queue_item.retry_count += 1
            if queue_item.retry_count >= MAX_RETRIES:
                queue_item.status = "FAILED"
                print(f"[{datetime.now()}] ❌ Sync FAILED (Max Retries Reached) for {queue_item.enhanced_dir_path}")
            else:
                queue_item.status = "PENDING"
                
    except Exception as e:
        print(f"[{datetime.now()}] 🚨 Fatal Sync Exception: {e}")
        queue_item.retry_count += 1
        queue_item.status = "FAILED" if queue_item.retry_count >= MAX_RETRIES else "PENDING"

    session.commit()


async def watchdog_loop():
    print("🐾 Antigravity Sync Watchdog Started. Monitoring db...")
    while True:
        session = SessionLocal()
        try:
            # Fetch directories pending sync
            pending_items = session.query(SyncQueue).filter(
                SyncQueue.status.in_(["PENDING"])
            ).order_by(SyncQueue.created_at.asc()).all()

            if pending_items:
                if not check_tailscale_status():
                    print(f"[{datetime.now()}] 🛑 Tailscale Tunnel Offline. Sleeping...")
                else:
                    for item in pending_items:
                        await sync_directory(session, item)
        except Exception as e:
            print(f"[{datetime.now()}] Database Query Error: {e}")
        finally:
            session.close()

        await asyncio.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        asyncio.run(watchdog_loop())
    except KeyboardInterrupt:
        print("Watchdog manually terminated.")
        sys.exit(0)
