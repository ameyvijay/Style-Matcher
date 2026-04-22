import os

# ─── System RAM Configuration ────────────────────────────────────────
# Default to 24 GB for the M4 Mac Mini base model.
SYSTEM_TOTAL_RAM_GB = int(os.getenv("ANTIGRAVITY_RAM_GB", "24"))

# macOS + Python + Frozen ML models (MUSIQ, CLIPIQA, CLIP)
# These are non-evictable residents during a batch run.
SYSTEM_OVERHEAD_GB = 8.2

# Buffer for OS page cache and I/O operations to prevent swap death.
HEADROOM_GB = 4.0

# Derived Thresholds
VLM_BUDGET_GB = SYSTEM_TOTAL_RAM_GB - SYSTEM_OVERHEAD_GB
SAFE_VLM_MAX_GB = VLM_BUDGET_GB - HEADROOM_GB

# Pre-flight Memory Gate (Percentage)
# On a 24GB system, 45% is ~10.8GB used. 
# This leaves ~2.6GB of "leak" tolerance above system overhead.
MEMORY_GATE_THRESHOLD_PCT = 45.0 if SYSTEM_TOTAL_RAM_GB <= 24 else 55.0

print(f"🖥️ [Config] System RAM: {SYSTEM_TOTAL_RAM_GB}GB | VLM Budget: {VLM_BUDGET_GB}GB | Safe Max: {SAFE_VLM_MAX_GB}GB")
