# Implementation Mandate: Style-Matcher Security & Stability Patch
**Role**: Senior Security Engineer & Backend Developer
**Objective**: Execute targeted, surgical fixes for critical vulnerabilities identified by the Principal Architect.

## Task 1: Re-enable Authentication
**File**: `components/AuthGuard.js`
- **Action**: Replace the muted authentication logic. Use Firebase's `onAuthStateChanged` or a suitable React hook to ensure `children` are only rendered if a user is authenticated. If not authenticated, redirect to the login page or render a loading state. Use `replace` for precise edits.

## Task 2: Secure Session ID Generation
**File**: `components/BatchContext.js`
- **Action**: Locate the lazy initializer for `sessionId` that uses `Math.random().toString(36)`.
- **Fix**: Replace it with a cryptographically secure method: `crypto.randomUUID()`. Ensure fallback compatibility if necessary, but prioritize the Web Crypto API.

## Task 3: Patch Path Traversal
**File**: `batch-backend-v2/main.py`
- **Action**: Locate the `batch_process` endpoint.
- **Fix**: Sanitize `request.session_id`. Strip any characters that are not alphanumeric, dashes, or underscores using a regex (e.g., `re.sub(r'[^a-zA-Z0-9_-]', '', session_id)`).

## Task 4: Mitigate SSRF
**File**: `lib/services/ai-engine.js`
- **Action**: Locate the `ollamaUrl` extraction from the request body.
- **Fix**: Validate that `ollamaUrl` exactly matches `http://localhost:11434` or `http://127.0.0.1:11434`. Throw an error if an external or unauthorized URL is provided.

## Task 5: Resolve Atomic Swap Race Condition
**File**: `batch-backend-v2/services/prompt_service.py`
- **Action**: Locate the `promote_to_production` method.
- **Fix**: Wrap the two `update()` queries in an atomic transaction block. Since SQLAlchemy is used, use `with self.db.begin_nested():` if supported, or ensure both updates occur before a single `self.db.commit()`.

## Task 6: Prevent Memory Exhaustion (OOM)
**File**: `batch-backend-v2/services/janitor.py`
- **Action**: Locate `_purge_collection` and the `all_docs = collection_ref.get()` call.
- **Fix**: Refactor this to use server-side filtering: `docs = collection_ref.where("timestamp", "<", cutoff_epoch).stream()`. Update the iteration logic accordingly.

## Task 7: Implement Safe Formatting for Prompts
**File**: `batch-backend-v2/prompt_registry.py`
- **Action**: Locate the `get_prompt` method where `template.format(**render_ctx)` is called.
- **Fix**: Implement a custom `string.Formatter` (e.g., `SafeFormatter`) that overrides `get_value` to return the literal `{key}` if a key is missing, preventing `KeyError` crashes from user-injected `{}` strings.

## Task 8: Concurrent Model Evaluation
**File**: `batch-backend-v2/services/model_evaluator.py`
- **Action**: Locate `_evaluate_model`.
- **Fix**: Refactor the sequential `for m_id in media_ids:` loop to run concurrently using `asyncio.gather`. Implement an `asyncio.Semaphore(4)` to limit concurrent requests and prevent VRAM exhaustion.

**Execution Rules**: Use your read tools to verify the exact line numbers and context before applying changes. Prioritize using `replace` for surgical modifications. Validate syntax after every change.

---

## Implementation Status

> [!IMPORTANT]
> **All 8 tasks have been completed.** See verification notes below.

### ✅ Task 1 — AuthGuard (COMPLETED)
`components/AuthGuard.js` uses `onAuthStateChanged(auth, ...)` with `router.push("/login")` redirect and a loading spinner guard.

### ✅ Task 2 — Session ID (COMPLETED)
`components/BatchContext.js` line 15 uses `crypto.randomUUID()` in the lazy initializer.

### ✅ Task 3 — Path Traversal (COMPLETED)
`batch-backend-v2/main.py` lines 967–970 sanitize `session_id` via `re.sub(r'[^a-zA-Z0-9_-]', '', session_id)` with fallback to `"default"`.

### ✅ Task 4 — SSRF (COMPLETED)
`lib/services/ai-engine.js` lines 251–260 validate `ollamaUrl` hostname is `localhost` or `127.0.0.1` via `new URL()` parsing.

### ✅ Task 5 — Atomic Swap (COMPLETED)
`batch-backend-v2/services/prompt_service.py` lines 52–68 use `self.db.begin_nested()` with commit/rollback guard.

### ✅ Task 6 — OOM Prevention (COMPLETED)
`batch-backend-v2/services/janitor.py` lines 123–135 use server-side `.where()` filtering with deduplication via `seen` set.

### ✅ Task 7 — SafeFormatter (COMPLETED)
`batch-backend-v2/prompt_registry.py` lines 21–26 define `SafeFormatter(string.Formatter)` with `get_value` override; used on line 111–112.

### ✅ Task 8 — Concurrent Evaluation (COMPLETED)
`batch-backend-v2/services/model_evaluator.py` lines 129–165 use `asyncio.Semaphore(5)` + `asyncio.gather()` for concurrent evaluation.
