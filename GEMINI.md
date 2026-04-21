# Antigravity Engine (v2.1.0) — Technical Context

## Project Overview
Antigravity Engine is a high-performance, privacy-first AI image workbench optimized for **Apple Silicon (M4)**. It provides professional photographers with autonomous culling, RAW+JPEG synchronization, and non-destructive metadata management.

### Architecture
The project follows a **Hybrid-Cloud Architecture**:
- **Backend (Python/FastAPI)**: A heavy-compute worker node running natively on macOS. It uses a **Stage-Based Pipeline Pattern** for image processing.
- **Frontend (Next.js/React)**: A modern, glassmorphic PWA that communicates with the backend via REST and a resilient polling mechanism.
- **Cloud Plane (Firebase)**: Synchronizes user "swipe" decisions between the PWA and the local engine in real-time.
- **Data Persistence**: Local SQLite (WAL-mode) for MLOps tracking, ChromaDB for vector embeddings, and Firestore for cloud sync.

---

## 🛠 Building and Running

### Prerequisites
- **macOS 14+** (Sonoma) on Apple Silicon.
- **Python 3.12+** and **Node.js 18+**.
- **Ollama** (running locally for VLM features).

### Backend Setup
```bash
cd batch-backend-v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Start the engine
bash start_engine.sh
```

### Frontend Setup
```bash
npm install
npm run dev
```

### Key Commands
- **Run Tests**: `.venv/bin/pytest tests/`
- **Linting**: `npm run lint`
- **Verify Parity**: `.venv/bin/python tests/test_pipeline_parity.py`

---

## 📐 Development Conventions

### Pipeline Pattern (Backend)
All batch processing logic is encapsulated in `pipeline/stages/`. When adding new image processing steps:
1. Create a new class inheriting from `ProcessingStage`.
2. Implement `execute(ctx: PipelineContext)`.
3. Register the stage in `batch_orchestrator.py`.

### Telemetry & Logging
- **SSE is deprecated.** The system uses **Durable File-Based Logging**.
- Logs are written to `logs/{session_id}.jsonl` by `PipelineRunner._emit()`.
- Frontend polls `GET /api/logs/{session_id}` for real-time terminal updates.

### M4-Native Optimizations
- **MPS (Metal Performance Shaders)**: Always use `torch.device("mps")` for GPU acceleration on Mac.
- **Memory Guard**: The `ensure_memory_headroom` utility monitors RAM usage and unloads Ollama models if usage exceeds 80%.

### Cloud Synchronization
- Use `firebase_bridge.py` for all Firestore/Storage interactions.
- The listener processes both `ADDED` and `MODIFIED` events to ensure offline-first reliability.
- **Janitor Service**: Automatically purges Firestore documents > 10 days old on boot to stay within free-tier limits.

---

### Checkpoints
- **2026-04-21**: Persistent Stack Orchestration (PM2) and Admin Console UI Refactor complete. 
    - `ecosystem.config.js` implemented.
    - `/health` endpoint added to `main.py`.
    - `app/landing/page.js` refactored to Tabbed Admin Console.
    - `components/SwipeCard.js` updated with Skip-gesture stubs.
    - **Current Status**: All services online, stable, and GitHub synced.

---

## 📁 Directory Structure
- `/app`: Next.js App Router pages (Dashboard, Cull, Style Match).
- `/batch-backend-v2`: FastAPI source code.
- `/batch-backend-v2/pipeline`: Refactored processing stages.
- `/components`: Shared React components (SwipeCard, Navigation).
- `/lib/services`: Frontend logic (AI Engine with Circuit Breaker).
- `/.legacy`: Deprecated files and logs with 0 impact on current code.

---

## ⚠️ Known Constraints
- **Gemini Model**: Use `gemini-1.5-flash` (do not use v2.5 placeholder).
- **SQLite Concurrency**: Engine must use `check_same_thread=False` and `PRAGMA journal_mode=WAL` due to background Firestore threads.
- **Nomenclature**: UI uses `accepted/rejected`, Backend maps to `swipe_right_keeper/swipe_left_cull`.
