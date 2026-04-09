# Unified Master Implementation Plan: Style Matcher V2 Architectures

This implementation plan consolidates all feature requests into a single, comprehensive architectural roadmap. It transitions the application from a destructive file mover into a professional, non-destructive Digital Asset Management (DAM) engine with advanced aesthetic grading capabilities, zero-reference fallback enhancement, and native OS previewing.

---

## Pillar 1: Non-Destructive Culling via Metadata Tagging

Instead of physically moving multi-megabyte `.ARW` or `.jpg` files across the disk (which risks I/O corruption and wastes space), the backend will evaluate the photos and tag them non-destructively in place.

1.  **Universal XMP Sidecars**: 
    The script will write a 1KB `filename.xmp` file natively using standard XML strings next to each evaluated photo. This embeds a universal Star Rating recognizable by Windows Explorer natively or free open-source DAMs like `digiKam`.
    *   `5 Stars`: Accepted
    *   `3 Stars`: Review Needed (Amber)
    *   `1 Star`: Rejected 
2.  **macOS Native Finder Tags**:
    The script will shell out to the macOS native `xattr` command to embed Apple's `_kMDItemUserTags` flag. 
    *   This instantly paints a `Green`, `Yellow`, or `Red` dot next to the file inside the Mac Finder window without any software dependencies.

## Pillar 2: The "Amber" Borderline Zone (Human Feedback Loop)

To prepare for future Reinforcement Learning from Human Feedback (RLHF), we will mathematically bound a "Gray Area" where an image is sent to the photographer for subjective review rather than being instantly rejected or accepted.

**Changes required in `utils.py` and `models.py`:**
*   Add `REVIEW_NEEDED` to `ProcessingStatus` Enum.
*   **Blur Thresholds**: 
    *   `> 100` = Accept (Green)
    *   `70 - 100` = Review Needed (Yellow)
    *   `< 70` = Reject (Red)
*   **Exposure Luminance Thresholds**:
    *   Between `30` and `230` = Accept (Perfect exposure)
    *   Borderline `15 - 30` or `230 - 245` = Review Needed (Recoverable)
    *   Below `15` or above `245` = Reject (Destroyed data)

## Pillar 3: Reference-Based Style Transfer (The "Visual RAG")

The original request highlighted using the `benchmark_folder` identically to a RAG fine-tuning set. 

Instead of just checking if a photo is blurry, we will introduce a new sequential step in `processor.py`. Once a photo clears the Acceptance pipeline (is marked Green/5-Stars), it will be routed to an Enhancement queue.

**Execution Logic:**
1.  **AI Styling Injection**: In `processor.py`, we will allocate a placeholder block integrating the Python pipeline for **FastPhotoStyle** (or LUT application). 
2.  **How it matches**: If standard enhancement is requested, the system will select an aesthetic reference from the `benchmark_folder` and apply its color grading matrices onto the target `Green` photo natively.

> [!NOTE]
> For this sprint, I will write the precise architectural hooks/functions for Pillar 3 within `processor.py`, executing the *routing* logic. The specific style transfer mapping will be orchestrated natively.

## Pillar 4: Zero-Reference Image Enhancement (Empty Benchmark)

If the `benchmark_folder` is totally empty, the script cannot execute "Visual RAG". It must fall back to an out-of-the-box industry-standard algorithm to ensure the photo is strictly improved.

**Execution Logic:**
1.  **Google-Backed architectures & Zero-DCE**: The backend will utilize algorithms conceptually identical to Google's HDR+ or specifically the open-source **Zero-DCE (implemented in TensorFlow/PyTorch)**. These algorithms correct light mathematically without reference data. 
2.  If this fails or deep learning packages are too heavy, it falls back to **OpenCV CLAHE (Contrast Limited Adaptive Histogram Equalization)** for strict, fast local thresholding.
3.  If evaluated as `ACCEPTED` (Green), the target image undergoes this autonomous pixel enhancement curve.

## Pillar 5: Bypassing Adobe (Native OS Preview Rendering)

**Important Technical Distinction:** macOS Finder and Windows Explorer do *not* apply XMP color-grading metadata to render thumbnails natively. If we just write an XMP file, the OS preview remains flat.

**The Solution:**
To see the beautifully enhanced photo natively in Finder *without* an Adobe subscription, the script must physically "develop" the photo.

*   **Mac Native CoreImage Rendering**: For the ultimate Mac-native approach, we can leverage Python's `pyobjc` library to inject the AI's enhancement thresholds *directly* into Apple's native CoreImage hardware engine (`CIFilter` / `CIExposureAdjust`). This is the exact same C++ rendering engine Apple Preview uses!
*   The script will natively save this beautifully rendered **`_enhanced.jpg`** proxy alongside the original `RAW` file.
*   **XMP Integration (The Safe Harbor)**: As requested, the script *will still* generate the `.xmp` file for the RAW photo. This ensures that if you ever do drag this folder into Lightroom or digiKam in the future, the exact slider configurations are perfectly preserved natively!
*   **Result**: When you open Mac Finder, the `_enhanced.jpg` shows the brilliant AI result instantly (Green Tagged), while your untouched RAW file sits safely next to it alongside an XMP sidecar.
