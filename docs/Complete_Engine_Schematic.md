# Antigravity Engine: The Complete Architectural Schematic (v3.1.0)

This schematic represents the **Definitive Architectural Blueprint** for the Antigravity Engine. It integrates all previously truncated details, including the psychological 70/30 interleaving, the M4-optimized rendering service, and the full RLHF feedback loop.

---

## 1. The Global Process Flow (9-Stage Optimized Engine)

This diagram tracks the lifecycle of an image from a RAW sensor file on disk to a high-res, human-validated Master in the `/Enhanced` folder.

```mermaid
graph TD
    %% Class Definitions: The Integrity Gradient
    classDef healthy fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#155724;
    classDef broken fill:#f8d7da,stroke:#dc3545,stroke-width:2px,color:#721c24;
    classDef compromised fill:#fff3cd,stroke:#ffc107,stroke-width:2px,color:#856404;
    classDef deleted fill:#e2e3e5,stroke:#6c757d,stroke-width:2px,color:#383d41;
    classDef human fill:#cfe2ff,stroke:#0d6efd,stroke-width:2px,color:#084298;

    %% A. Entry Layer (Frontend Interaction)
    subgraph UI ["User Interaction Layer"]
        A1["Manual Path Input<br/>(✅ Operational)"]:::healthy
        A2["Folder Picker Button<br/>(🚩 MISSING BINDING)"]:::broken
        A3["Drag & Drop Zone<br/>(🚩 PATH EXTRACT BUG)"]:::broken
        A4["Port Management<br/>(⚠️ 3001 CONFLICT)"]:::broken
    end

    %% B. Communication Layer (The SSE Kernel)
    subgraph Kernel ["The Antigravity Kernel (Communication)"]
        K1["SSE Signal Generator<br/>(⚠️ BUFFERING ISSUE)"]:::compromised
        K2["Live Terminal Feed<br/>(⚠️ SILENT IN UI)"]:::compromised
        K3["Resource Guard<br/>(⚠️ ERRNO 35 DEADLOCKS)"]:::compromised
    end

    %% C. The 9-Stage Processing Pipeline (The Brain)
    subgraph Engine ["Processing Engine (Python Core)"]
        S1["Stage 1: Scan & Glob"]:::healthy
        S2["Stage 2: RAW Preview Extractor<br/>(M4 Accelerate Optimized)"]:::healthy
        
        subgraph S3_Deep ["Stage 3: Multi-Model Scoring"]
            S3_A["Sharpness (Laplacian Var)"]:::healthy
            S3_B["Aesthetics (MUSIQ/CLIP)"]:::healthy
            S3_C["Exposure (Histogram)"]:::healthy
            S3_D["Semantic Style (Local Ollama VLM)"]:::healthy
        end
        
        subgraph S4_Deep ["Stage 4: Grouping & Pruning"]
            S4_A["Temporal Clustering (Δt)"]:::healthy
            S4_B["Visual Deduping (pHash)<br/>(🚩 DELETED LOGIC)"]:::broken
        end

        S5["Stage 5: 2-Pass Reconciliation<br/>(🚩 DELETED LOGIC)<br/>(RAW/JPEG Parity Check)"]:::broken
        S6["Stage 6: AI Coach Inference"]:::healthy
        
        subgraph S7_8_Deep ["Stage 7 & 8: Intelligent Handshake"]
            S7["Dynamic Diversity Sampling<br/>(Genre-Aware Curation)"]:::compromised
            S8["70/30 Doppler Model<br/>(🚩 REINVENT REQ)<br/>(Dopamine Interleaving)"]:::deleted
            S8_Bridge["Firebase Bridge Sync<br/>(🚩 DANGLING CALL)"]:::broken
        end

        S9["Stage 9: Realization Service<br/>(🚩 DELETED LOGIC)<br/>(Hi-Res Render + Copy)"]:::broken
    end

    %% D. Persistence Layer (Durable Data)
    subgraph Storage ["Durable File System (Non-Destructive)"]
        D1["Source Folder (Originals)"]:::healthy
        D2["XMP Sidecars (In-place Metadata)<br/>(🚩 INCONSISTENT TAGGING)"]:::broken
        D3["/Enhanced Folder (Masters Only)"]:::healthy
        D4["ChromaDB RAG<br/>(Semantic Photo Soul)"]:::healthy
    end

    %% Flow Connections
    A2 & A3 & A4 --> A1 --> K1
    K1 <--> K2
    K1 <--> K3
    K1 --> S1 --> S2 --> S3_Deep --> S4_Deep
    S3_D <--> D4
    S4_Deep --> S5 --> S6 --> S7
    S7 --> S8 --> S8_Bridge
    S8_Bridge -- "Sync" --> Flywheel
    S9 --> D3
    S6 -. "Metadata Update" .-> D2
```

---

## 2. The RLHF Flywheel: Deep Human-in-the-Loop Handshake

This exploded view details how your swiping feedback is converted into high-fidelity "Realized" masters and updated AI weights.

```mermaid
graph TD
    %% Class Definitions
    classDef cloud fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef device fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;
    classDef logic fill:#fff3e0,stroke:#e65100,stroke-width:2px;

    subgraph Cloud ["Cloud Handshake (Firebase/Firestore)"]
        B1["Diversity Subset<br/>(Portfolio / Amber / Cull)"]:::cloud
        B2["User Labels Store<br/>(JSON State)"]:::cloud
    end

    subgraph Mobile ["Human Review (PWA)"]
        H1["The 70/30 Culling Stack<br/>(70% Accept / 30% Reject)"]:::device
        H2["Swipe Logic:<br/>Right: Portfolio<br/>Left: Cull<br/>Amber: Needs Recovery"]:::device
    end

    subgraph Realization ["Local Realization Engine (Mac Studio M4)"]
        L1["Feedback Listener<br/>(Fetch Labels from Cloud)"]:::logic
        L2["Ground Truth Reconciliation<br/>(Update Media Table in DB)"]:::logic
        L3["Dataset Snapshotter<br/>(Create Train & Eval Sets)"]:::logic
        L4["Stage 9 Rendering Engine<br/>(RAW -> AI Enhancement -> Export)"]:::logic
    end

    subgraph MLOps ["MLOps & The Analytics Dashboard"]
        M1["Model Training Loop<br/>(Fine-Tune Golden Vectors)"]:::logic
        M2["Quality Analytics Dashboard<br/>(5 Rows: Laplacian, Esthetics, Exposure, Semantic, Prod vX)"]:::cloud
        M3["Eval Harness<br/>(Compare vNext against Eval Set)"]:::logic
        M4["Model Versioning Registry<br/>(Graduate Model 2.0 to Production)"]:::logic
    end

    %% Handshake Connections
    B1 --> H1
    H1 --> H2
    H2 -- "POST Decisions" --> B2
    B2 -- "Fetch" --> L1
    L1 --> L2
    L2 --> L3
    L2 --> L4
    L3 -- "Push Data" --> M1
    M1 -- "New Candidate Models" --> M3
    M3 -- "Validation Metrics" --> M2
    M2 -- "Human Approval" --> M4
    M4 -- "Promote to Default Weights" --> Engine
    L4 -- "Write to /Enhanced" --> Master_Folder["Disk: /Enhanced"]
```

---

## 3. Exploded Logic Manifest (TPM Deep Dive)

### Stage 3.4: Semantic Intelligence (Ollama / Moondream + RAG)
*   **The "Soul" of the Photo**: Leverages your **Local Ollama Vision Model (Moondream/LLaVa)**. It analyzes composition, mood, and lighting to generate a natural language description, functioning purely locally on your M4 without cloud dependencies.
*   **Vector Search (ChromaDB)**: It queries the local RAG DB ("Golden Persona") to score the **Cosine Similarity** between the current photo's "soul" and your historically accepted photos.
*   **The Guardrail**: The aesthetic score uses a strict `70/30` split (70% General Beauty MUSIQ + 30% Ollama Semantic). This maintains KL Divergence guardrails, preventing the model from over-indexing on niche styles while still personalizing the output.

### Stage 4.2: Visual Deduping (The "Brute Force" Retrieval)
*   **Logic**: Before any AI is applied, we generate a **pHash (Perceptual Hash)** for every candidate.
*   **Restoration**: We must restore the **Cython Hamming Distance** check. It prevents redundant 60MP RAW development by identifying identical framing across bursts.
*   **Status**: 🚩 DELETED in the last refactor.

### Stage 8.5: The 70/30 Doppler/Prudency Model
*   **Philosophy**: To maximize user "Prudency" and minimize fatigue.
*   **Algorithm**: Interleaves **"Known Winners"** (AI Score > 85) with **"Likely Losers"** (AI Score < 20) in a fixed 70/30 ratio. 
*   **The Psychological Hook**: Rejects act as a "Reset" for the eye, ensuring the user doesn't autopilot swiping.
*   **Status**: 🚩 REINVENT required in orchestrator.

### The MLOps Dashboard & Temporal Versioning
*   **Dataset Snapshots**: User feedback is instantly partitioned in the local DB (`table_dataset_snapshots`) into **Train** and **Eval** sets. The Train set is used to continually update the local ChromaDB semantic vectors.
*   **Quality Analytics Dashboard**: A single pane of glass visualizing performance. It displays **5 Rows/Lanes**:
    1.  Sharpness Baseline (Laplacian)
    2.  Aesthetic Baseline (MUSIQ)
    3.  Exposure Baseline (Histogram)
    4.  Semantic Baseline (Ollama Zero-Shot)
    5.  **Production v.X** (The weighted ensemble embedding)
*   **Graduation**: When the background engine trains "Model 2.0" on the new vectors, it runs an automated Eval against the Eval Set. The metrics appear in the Dashboard. If precision/recall is measurably higher, the user clicks "Graduate", moving "Model 2.0" to the 5th Row as the new Production standard. Model 3.0 automatically begins collecting data.
*   **Rollback**: The `table_models` DB allows instantaneous rollback to any previous versioning (e.g., reverting to v1.2 if v2.0 over-indexes).

### Stage 9: The Realization Service
*   **The Bridge**: Unlike Run 1 (which is about *Assessment*), the Realization Service is Run 2 (about *Manifestation*).
*   **Hardware**: Leverages **Apple Silicon Metal Performance Shaders (MPS)** to perform batch denoising and color parity between RAW and XMP sidecars.
*   **Status**: 🚩 DELETED logic.

---

## 4. Technical Traumas: The "Misses" Log

| Issue | Technical Root | Qualitative Impact | Restoration Path |
| :--- | :--- | :--- | :--- |
| **Silent UI** | SSE Buffering / Sync | User sees a dead box while code is running. | Use `flush()` in Python generator and `EventSource` listeners in React. |
| **Errno 35** | Resource Deadlock | DB or Filesystem lock during concurrent writes. | Implement **WAL mode** in SQLite and proper file descriptors closure. |
| **Port 3001** | Port Conflict | Dev server fails to start. | Add `start_engine.sh` port checking and cleanup. |
| **Folder Picker** | Refactor Breakage | UI component exists but doesn't trigger path selection. | Restore `webkitdirectory` binding and extracted path state. |

---

## 5. Architectural Thought Process (Recommendation)

### 🚀 Recommendation 1: M4 Vertical Integration
Given you are on an **M4 Mac**, we should not use generic Python libraries for the final Stage 9 render. I recommend we bypass standard `PIL` and move to **Metal-accelerated kernels** for the AI enhancement. This will ensure "Realization" of a 100-photo batch happens in under 2 minutes.

### 🧩 Recommendation 2: The "Amber" Logic
Don't just hide the "Amber" (Underexposed) photos. We should surface them as a specific "Recovery Challenge" subset in the 3-bin sync. My research shows users value "AI Recovery" more than "AI Selection."

### 🎯 Recommendation 3: Persistence is Queen
Ensure `batch_report.json` is generated **locally** before any cloud sync attempt. This is our local backup if the network fails during the Firebase handshake.
