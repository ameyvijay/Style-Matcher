# Style Matcher: Master Product Requirements Document (PRD)

## 1. Executive Summary
**Style Matcher** is a professional-grade, privacy-first image workbench designed for photographers and content creators. It provides a suite of tools for aesthetic transformation, high-precision background removal, and massive parallel batch processing—all anchored on a "Local First" philosophy that leverages modern AI while respecting data sovereignty.

---

## 2. Product Vision
To bridge the gap between complex professional photo editors and simple AI filters by providing a tool that is:
- **Fast**: Leveraging local WASM and hardware acceleration.
- **Intelligent**: Using Large Language Models (LLMs) and Deep Learning for aesthetic coaching and enhancement.
- **Non-Destructive**: Preserving original data via industry-standard metadata (XMP/EXIF) and macOS native tagging.
- **Private**: Minimizing cloud dependency by supporting local models (Ollama).

---

## 3. Product Architecture
- **Frontend**: React / Next.js (App Router) with a premium "Antigravity" glassmorphism design system.
- **Backend**: FastAPI (Python) modular service-oriented architecture.
- **Communication**: Seamless REST API integration for deep image analysis and file system operations.

---

## 4. Feature Set Breakdown

### 4.1. Universal Landing Dashboard
- **ToolCards**: Categorized entry points for Style Matcher, Background Removal, and Batch Studio.
- **Global Settings**: Centralized configuration for AI providers (Google Gemini or Local Ollama) and universal benchmark directory management.

### 4.2. Style Matcher (Aesthetic Transformation)
- **Mood Extraction**: Leverages Multimodal LLMs to analyze a "Benchmark Image" and extract specific aesthetic footprints (brightness, contrast, saturation, hue).
- **Live Preview Canvas**: Real-time rendering of extracted filters onto a target image.
- **Manual Studio**: Granular sliders for the user to fine-tune the AI-suggested grade before export.

### 4.3. Background Removal (Object Isolation)
- **Local WASM Engine**: Uses `@imgly/background-removal` to isolate subjects completely on-device, ensuring no photos hit the cloud.
- **Manual Refinement Studio**: 
    - **Erase/Restore Brushes**: Precision tools to manually fix AI mask errors.
    - **Original Layer Overlay**: Faint background guide for accurate pixel restoration.
- **Multi-Resolution Export**: Capability to download isolated objects at 50%, 75%, or native resolution.

### 4.4. AI Batch Studio (V2 Architecture)
The "Enterprise" arm of the application, optimized for non-destructive high-volume culling.
- **Parallel Analysis**: Massive multithreaded evaluation of target folders.
- **Objective Quality Assessment**:
    - **Laplacian Blur Scoring**: Mathematical focus check.
    - **Luminance Histograms**: Automated exposure validation.
- **Non-Destructive Culling (The DAM Layer)**:
    - **macOS Finder Color Tags**: Programmatic assignment of Green (Accepted), Yellow (Amber), and Red (Rejected) dots natively in Finder.
    - **XMP Sidecars**: Universal 1, 3, or 5-star ratings for cross-platform compatibility (Lightroom/digiKam).
- **"Amber" Human-in-the-loop**: A specific "yellow zone" for subjective borderline cases.
- **Bypass Render Proxies**: Automatic generation of `_enhanced.jpg` files via native Mac CoreImage logic to provide instant visual feedback in Finder thumbnails.

---

## 5. Technical Specifications & Stack
- **AI Libraries**: `@google/genai` (Cloud), `Ollama` (Local), `Zero-DCE` (Enhancement).
- **Computer Vision**: OpenCV (`cv2`), `NumPy`, `exifread`.
- **Deduplication**: `imagededup` (pHash architecture).
- **OS Integration**: `xattr` (macOS Extended Attributes), `pyobjc` (CoreImage Frameworks).

---

## 6. Implementation Milestones (The "Evergreen" Log)
- **Milestone 1**: Monolithic Backend & Basic React Dashboard.
- **Milestone 2**: Modular Backend Refactoring (Extraction of Models/Utils/Processor).
- **Milestone 3**: Frontend UI Componentization (InputGroups/ToolCards/SettingsPanels).
- **Milestone 4 (Current)**: Transition to V2 Non-Destructive DAM Architecture & Metadata Tagging.

---

## 7. Security & Compliance
- **Local Processing**: Prioritize local execution for all pixel-altering tasks.
- **Data Integrity**: Zero destructive operations (Original photos are never overwritten or deleted by default).
- **Privacy**: Prompt users before any image binary is sent to cloud LLM providers.
