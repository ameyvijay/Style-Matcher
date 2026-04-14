# Technical Design Document: Antigravity Engine (v2.1.0)

## 1. System Architecture Overview

The Antigravity Engine operates as a **Native macOS Orchestration Layer**, bridging the React-based frontend with local Python processing services. Specifically optimized for **Apple Silicon (M4/M4 Pro)**, the architecture bypasses containerization (Docker) to directly leverage hardware acceleration for image processing.

### Native Orchestration
- **Frontend:** `Next.js 15+` running as a native Node.js process. It handles user state, global configurations, and the AI Batch Studio dashboard.
- **Backend:** `Python 3.12+ (FastAPI)` running natively on the host machine. It executes high-performance image analysis and metadata operations using macOS Core Image and Accelerate frameworks.
- **Inter-process Communication:** Managed via local HTTP REST requests (`localhost:8000`), allowing the frontend to trigger massive parallel batch operations without UI blocking.

---

## 2. RAW+JPEG Synchronization (The "Pairing" Layer)

Professional photography workflows often result in "pairs" (e.g., `DSC_001.ARW` and `DSC_001.JPG`). Version 2.1.0 introduces intelligent grouping logic to handle these consistently.

### Basename Grouping Logic
On directory ingestion, the engine executes a pre-scan to identify and group files by their base name. 
1. **Normalization**: `DSC_001.ARW` and `DSC_001.JPG` are mapped to the identity `DSC_001`.
2. **Metadata Merging**: Technical EXIF data from the RAW master is combined with the aesthetic rendering of the JPEG for a more complete AI context.

### Tier Reconciliation (Elevation)
To prevent accidental culling of high-utility files:
- **Rule**: If a JPEG is classified as a **Keeper**, its RAW counterpart is automatically elevated to **Keeper** status, regardless of its individual AI aesthetic score.
- **Rationale**: RAW files often appear "flat" or "lifeless" to standard AI vision models, but contain the most data for post-processing. Elevation ensures the photographer keeps the data they need for the shots they like.

---

## 3. Computer Vision & AI Quality Assessment (NR-IQA)

The engine offloads visual diagnostics to a dual-layer No-Reference Image Quality Assessment (NR-IQA) pipeline.

### Technical Assessment
- **Mechanism**: Laplacian Variance (Blur Detection) + Luminance Histogram (Exposure Check).
- **Tooling**: OpenCV (`cv2`) and NumPy.

### Aesthetic Assessment
- **Mechanism**: **NIMA (Neural Image Assessment)** and **BRISQUE**.
- **Model**: Custom-trained CNNs analyze color harmony, composition, and framing to assign an "Aesthetic Score" out of 10.

---

## 4. Metadata Mapping & Non-Destructive DAM

### XMP Sidecar Strategy
The engine utilizes industry-standard **XMP Sidecar files** for all culling decisions.
- **Format**: Tiny XML files (e.g., `DSC_001.xmp`) sitting next to the original files.
- **Compatibility**: Automatically recognized by Adobe Lightroom, Capture One, and Darktable.
- **Safety**: Zero risk of corrupting the original master RAW files.

### macOS Finder Integration (The "Tagging" Layer)
For instant visual culling directly in Finder, the engine writes **macOS Extended Attributes (`xattr`)** to assign color tags:
- **Green**: Highly Recommended (Keeper)
- **Yellow**: Borderline (Review)
- **Red/No Tag**: Rejected

---

## 5. Security & Privacy

### Model Context Protocol (MCP)
The engine integrates with the Antigravity session via MCP, allowing for secure tool execution on local files while preserving user-defined privacy boundaries.

### Local LLM Tunneling (Ollama)
For 100% offline analysis, the system targets the local Ollama daemon (`localhost:11434`) to generate the **AI Coach** coaching reports, ensuring that no image binary ever hits an external cloud provider unless explicitly enabled (e.g., Google Gemini).
