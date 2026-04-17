# Style Matcher: Master Product Requirements Document (PRD)

## 1. Executive Summary
**Style Matcher** is a professional-grade, privacy-first image workbench designed for photographers and content creators. It provides a suite of tools for aesthetic transformation, high-precision background removal, and massive parallel batch processing—all anchored on a "Local First" philosophy that leverages modern AI (M4/Ollama) while providing a mobile-first RLHF feedback loop.

---

## 2. Product Vision
To bridge the gap between complex professional photo editors and simple AI filters by providing a tool that is:
- **Fast**: Leveraging local WASM and M4 hardware acceleration.
- **Intelligent**: Using Large Language Models (LLMs) and VLMs for aesthetic coaching, semantic analysis, and RLHF.
- **Adaptive**: Learning from user "swipes" to refine aesthetic preferences in real-time.
- **Non-Destructive**: Preserving original data via industry-standard metadata (XMP/EXIF) and macOS native tagging.
- **Private**: Minimizing cloud dependency by supporting local models (Ollama vision/gemma).

---

## 3. Product Architecture
- **Frontend**: Next.js 15+ (App Router) with a premium "Antigravity" glassmorphism design system.
- **Mobile Feedback**: Progressive Web App (PWA) allowing for offline-first, mobile culling.
- **Backend (Mac Mini)**: FastAPI (Python 3.12+) modular service-oriented architecture.
- **Sync Layer**: Hybrid Cloud Bridge (Firebase Firestore/Storage) facilitating the RLHF handshake between local processing and mobile UI.

---

## 4. Feature Set Breakdown

### 4.1. Universal Landing Dashboard
- **ToolCards**: Entry points for Style Matcher, Background Removal, AI Batch Studio, and RLHF Workspace.
- **Global Settings**: Centralized configuration for AI providers (Google Gemini or Local Ollama) and universal benchmark directory management.

### 4.2. RLHF Workspace (PWA)
A dedicated mobile-first interface for refining model intelligence through human feedback.
- **Swipe Interface**: Tinder-style "Accept/Reject" workflow for AI-culled photos.
- **Second Chance QA**: A "Review Bin" for accidentally rejected photos, ensuring no high-recall shots are lost.
- **Intelligence Dashboard**: Real-time monitoring of Model Performance (F1-Score, Precision, Recall) based on human vs. AI decisions.

### 4.3. Style Matcher (Aesthetic Transformation)
- **Mood Extraction**: Leverages Multimodal LLMs to analyze a "Benchmark Image" and extract specific aesthetic footprints.
- **Live Preview Canvas**: Real-time rendering of extracted filters onto a target image.
- **Manual Studio**: Granular sliders for fine-tuning AI-suggested grades.

### 4.4. AI Batch Studio (V2 Architecture)
The "Enterprise" arm of the application, optimized for non-destructive high-volume culling.
- **Parallel Analysis**: Massive multithreaded evaluation of target folders.
- **Objective Quality Assessment**:
    - **Laplacian Blur Scoring**: Mathematical focus check.
    - **Luminance Histograms**: Automated exposure validation.
    - **Semantic Analysis**: Ollama-powered scene understanding and captioning.
- **Non-Destructive Culling**:
    - **macOS Finder Color Tags**: Programmatic assignment of Green/Yellow/Red dots.
    - **XMP Sidecars**: Universal rating synchronization for Lightroom/Capture One.

---

## 5. Technical Specifications & Stack
- **Frontend**: React, Next.js, Framer Motion, Firebase Client SDK.
- **AI Libraries**: `@google/genai`, `Ollama` (Local VLM), `Zero-DCE`, `PyTorch`.
- **Computer Vision**: OpenCV, NumPy, `exifread`, `pyobjc` (CoreImage).
- **Database**: Local SQLite (RAG Store) + Firebase Firestore (Real-time Sync).
- **Communication**: FastAPI, Firebase Cloud Bridge.

---

## 6. Implementation Milestones (The "Evergreen" Log)
- **Milestone 1**: Monolithic Backend & Basic React Dashboard. (Completed)
- **Milestone 2**: Modular Backend Refactoring & CoreImage Integration. (Completed)
- **Milestone 3**: V2 Non-Destructive DAM Architecture & Metadata Tagging. (Completed)
- **Milestone 4**: RLHF Infrastructure & PWA Mobile Interface. (Completed)
- **Milestone 5**: Semantic Intelligence Stabilization & Adaptive Learning (RAG). (Current)

---

## 7. Security & Compliance
- **Local-First Processing**: Prioritize local execution for all pixel-altering tasks.
- **Authentication**: Google OAuth via Firebase for secure access to the RLHF loop.
- **Data Integrity**: Zero destructive operations on original masters.
- **Privacy**: Binary uploads restricted to temporary "For RLHF" folders with automated cleanup.
