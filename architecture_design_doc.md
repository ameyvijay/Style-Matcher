# Technical Design Document: Antigravity Engine (v2.2.0)

## 1. System Architecture Overview
The Antigravity Engine is a **Native macOS Orchestration Layer** optimized for **Apple Silicon (M4)**. It bridges a React/Next.js frontend with local Python processing services and a mobile-first PWA feedback loop.

### Hybrid Orchestration
- **Local Node.js/FastAPI**: Handles massive parallel processing, RAW handling, and local VLM analysis.
- **Cloud Bridge (Firebase)**: Provides a synchronization layer for mobile RLHF without exposing the local file system.
- **PWA Frontend**: Mobile-optimized interface for "human-in-the-loop" decision making.

---

## 2. Hybrid Cloud Bridge (The "Firestore" Layer)
To enable mobile interaction without complex port forwarding or VPNs, the engine uses a specialized Firebase synchronization strategy.

### RLHF Handshake Workflow
1. **Curate**: Backend processes a batch and selects 20 photos for RLHF based on **Diversity Sampling**.
2. **Upload**: Photos are converted to lightweight JPEGs and uploaded to `Firebase Storage`.
3. **Sync**: A `batch_report` document is created in `Firestore` containing image URLs, AI scores, and prediction metadata.
4. **feedback**: User swipes on mobile; Firestore listener updates the document status to `accepted` or `rejected`.
5. **Realize**: Local `firebase_bridge.py` detects the update, pulls the final decisions, and executes final "Master" folder creation on the Mac Mini.

---

## 3. Semantic Intelligence & RLHF logic
The engine evolved from raw mathematical quality checks to semantic aesthetic understanding.

### VLM Integration (Ollama)
- **Model**: `llava` or `moondream` hosted locally.
- **Role**: Provides natural language scene captions (e.g., "Silhouette at sunset with high dynamic range") used to populate the local **RAG / Vector Store**.

### Adaptive Quality Classifier
- **Logic**: Combines Laplacian Blur scores with Semantic Similarity.
- **RLHF Adaptation**: User swipes are converted into "Preference Vectors."
- **KL Divergence Guardrails**: To prevent the model from over-fitting to a single style (e.g., only accepting sunset photos), a divergence penalty is applied if the current batch diversity deviates significantly from the global preference store history.

---

## 4. Intelligence Analytics (The "F1" Layer)
In photo culling, Precision (not keeping bad photos) and Recall (not missing good photos) are both critical.

### Metrics Monitoring
- **F1 Score**: Calculated as `2 * (Precision * Recall) / (Precision + Recall)`.
- **Precision**: How many of the AI-selected photos were swiped "Right" by the user.
- **Recall**: How many photos in the "Rejected" bin were rescued by the user via the **Second Chance QA Bin**.

---

## 5. PWA & Mobile UX Specifications
The frontend is designed for a native "App Store" feel.

### Tech Stack
- **Framework**: Next.js 15+ + `next-pwa`.
- **Animations**: `framer-motion` for zero-latency card dragging.
- **Auth**: Google OAuth via Firebase Client SDK.

### UI Features
- **Glassmorphism**: Backdrop blurs and translucent borders consistent with macOS design.
- **Swipe Gestures**: High-fidelity drag physics with visual feedback (Green/Red overlays).
- **Service Workers**: Caches high-resolution thumbnails for offline swiping.

---

## 6. Security & Privacy
- **Encrypted Handshakes**: All Firestore communication is restricted via Security Rules linked to the user's UID.
- **Temporary Storage**: RLHF photos in the cloud are treated as temporary "Handshake Proxies" and can be cleared after the local realization phase is complete.
