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
All batch processing logic is encapsulated in `pipeline/`. The engine uses a **Modular Pipeline Pattern** with isolated states (Discovery, Assessment, Enhancement, Embedding, Coaching, CloudSync).
1. Create a new class in `pipeline/stages/` inheriting from `ProcessingStage`.
2. Implement `execute(ctx: PipelineContext)`.
3. The `PipelineRunner` manages the execution flow, abort signals, and atomic rollbacks.

### Telemetry & Logging
- **SSE to Polling Migration**: The engine uses a **Durable File-Based Polling** pattern. 
- Logs are dual-written to `logs/{session_id}.jsonl` and the stream generator.
- The frontend `BatchStudio` polls `GET /api/logs/{session_id}` for real-time updates.
- `batch_status` (running, completed, failed) is tracked in the `SESSION_REGISTRY`.

### M4-Native Optimizations
- **MPS (Metal Performance Shaders)**: Always use `torch.device("mps")` for GPU acceleration on Mac.
- **Memory Guard**: The `ensure_memory_headroom` utility is called as a "pre-flight" check before the discovery stage begins.

### Cloud Synchronization
- Use `firebase_bridge.py` for all Firestore/Storage interactions.
- Added **Decision Listener**: Processes both `ADDED` and `MODIFIED` events to handle decisions made while the engine was offline.
- **Janitor Service**: Automatically purges Firestore documents > 10 days old on boot (Free Tier Guard).
- **Decision Reversal**: Atomic reversal of swipe decisions via `POST /api/decision/reverse`.

### Deduplication & MLOps
- **Media Hashing**: Files are deduped in `EnhancementStage` using a SHA-256 hash of `filename + filesize`. Existing records in the `Media` table are reused.
- **Inference History**: Rerunning the engine on the same folder appends new `Inference` records. The Intelligence Dashboard uses the **latest** inference/annotation pair for its calculations.

---

## 📁 Directory Structure
- `/app`: Next.js App Router pages (Dashboard, Cull, Style Match).
- `/batch-backend-v2`: FastAPI source code.
- `/batch-backend-v2/pipeline`: Refactored processing stages (Discovery, Assessment, Enhancement, Embedding, Coaching, CloudSync).
- `/components`: Shared React components (SwipeCard, Navigation).
- `/lib/services`: Frontend logic (AI Engine with Circuit Breaker).
- `/.legacy`: Deprecated files and logs with 0 impact on current code.

---

## ⚠️ Known Constraints
- **Gemini Model**: Use `gemini-1.5-flash` (do not use v2.5 placeholder).
- **SQLite Concurrency**: Engine must use `check_same_thread=False` and `PRAGMA journal_mode=WAL` due to background Firestore threads.
- **Nomenclature**: UI uses `accepted/rejected`, Backend maps to `swipe_right_keeper/swipe_left_cull`.

---

## 🛡️ Antigravity Persistent Safety Protocol

1. **Strict Authentication**: No frontend route or component under `app/` (except `/login` or `/landing`) may bypass Firebase Authentication. `AuthGuard` must remain active in all environments, including local development, unless explicitly overridden via a secure, short-lived environment variable.
2. **Input Sanitization (Zero Trust)**: All inputs used to construct file paths, database queries, or external requests MUST be sanitized. `session_id` must always be strictly validated against an alphanumeric regex.
3. **Local API Enforcement**: Any internal service communicating with local AI models (e.g., Ollama) must enforce a hardcoded allowlist of acceptable localhost URIs. Client-provided URLs for internal services are strictly forbidden.
4. **Database Atomicity**: Any operation modifying the state of "Production" or active flags across multiple rows MUST be wrapped in a transaction.
5. **Memory Limits**: Never fetch unbounded collections from Firestore into memory using `.get()`. Always use `.where()` constraints and `.stream()` for cursor-based pagination.

## 🔍 Code Review Protocol

When performing a code review, always follow the safety protocol above.
**Action Plan Prompt**:
"Role: QA Engineer. Analyze these code changes. Did the recent security patches (AuthGuard, SSRF, Path Traversal, Race Conditions) introduce any regressions? Provide a strict PASS/FAIL summary and a detailed action plan for any remediation required."
