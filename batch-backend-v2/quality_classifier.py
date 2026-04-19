"""
Antigravity Engine v2.0 — Module 2: Quality Classifier
Multi-signal image quality scoring: sharpness, aesthetics, exposure.

Key Design:
- Sharpness: OpenCV Laplacian variance (industry standard, 15+ years proven)
- Aesthetics: pyiqa MUSIQ/CLIPIQA (ML-based, understands composition & beauty)
- Exposure: NumPy histogram analysis (fast, mathematically precise)
- All scores normalized to 0-100 and combined into a composite tier

Usage:
    from quality_classifier import classify, self_test
    score = classify("/path/to/image.jpg")  # or pass bytes
    print(f"Tier: {score.tier}, Score: {score.composite}")
"""
from __future__ import annotations

import io
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from models import QualityScore, Tier, SelfTestResult, GENRE_PROFILES, detect_genre
from vision_analyst import VisionAnalyst

# ─── ML Model (Lazy Initialize) ──────────────────────────────────────
_musiq_model = None
_clipiqa_model = None
_ml_available = False
_ml_init_attempted = False


def _init_ml_models():
    """Lazy-load pyiqa models on first use. Runs on MPS if available."""
    global _musiq_model, _clipiqa_model, _ml_available, _ml_init_attempted

    if _ml_init_attempted:
        return
    _ml_init_attempted = True

    try:
        import torch
        import pyiqa

        # Force CPU for ML scoring — MPS crashes on full-resolution images
        # due to memory pressure with MUSIQ's multi-scale architecture.
        # CPU is ~2-3s per image but 100% stable.
        device = torch.device('cpu')
        print("[quality_classifier] Using CPU (stable mode for full-res scoring)")

        # MUSIQ: handles native resolution, excellent quality assessment
        _musiq_model = pyiqa.create_metric('musiq', device=device)
        # CLIPIQA: semantic understanding of composition and beauty
        _clipiqa_model = pyiqa.create_metric('clipiqa', device=device)

        _ml_available = True
        print("[quality_classifier] ML models loaded successfully")

    except ImportError as e:
        print(f"[quality_classifier] pyiqa/torch not available: {e}")
        print("[quality_classifier] Falling back to OpenCV-only mode")
    except Exception as e:
        print(f"[quality_classifier] ML init error: {e}")
        print("[quality_classifier] Falling back to OpenCV-only mode")


# ─── Core Classification ─────────────────────────────────────────────
# Classification working resolution: 1600px max on longest side.
# RAW previews from exiftool are ~1620px. JPEGs must be normalized to
# the same resolution for fair, consistent scoring across formats.
_CLASSIFY_MAX_DIM = 1600
_vision_analyst = None

def _get_vision_analyst():
    global _vision_analyst
    if _vision_analyst is None:
        _vision_analyst = VisionAnalyst()
    return _vision_analyst


def classify(image_input: str | bytes, exif: dict = None) -> QualityScore:
    """
    Analyze an image and return a comprehensive quality score.
    Now genre-aware if EXIF is provided.
    
    Args:
        image_input: File path (str) or JPEG bytes
        exif: Optional EXIF dictionary for genre-aware scoring
    
    Returns:
        QualityScore with sharpness, aesthetic, exposure, composite, and tier
    """
    return classify_with_analyst(image_input, None, exif)

def classify_with_analyst(
    image_input: str | bytes,
    analyst: Optional[VisionAnalyst] = None,
    exif: dict = None,
    rag_similarity_score: Optional[float] = None,
) -> QualityScore:
    """
    Full classification loop including semantic analysis.

    Args:
        image_input:          File path (str) or JPEG bytes.
        analyst:              Optional VisionAnalyst for Ollama-based description
                              and text-similarity scoring.
        exif:                 Optional EXIF dict for genre-aware weighting.
        rag_similarity_score: Optional pre-computed similarity score (0-100)
                              from the SemanticRAG / ChromaDB retrieval step.
                              When supplied this replaces the default 50.0
                              neutral value for the 70/30 composite calculation,
                              allowing RLHF signals to actively influence scoring.
    """
    start = time.time()

    # Load image for OpenCV analysis
    if isinstance(image_input, bytes):
        nparr = np.frombuffer(image_input, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        img = cv2.imread(image_input, cv2.IMREAD_COLOR)

    if img is None:
        return QualityScore(tier=Tier.CULL, processing_time=time.time() - start)

    # Normalize to classification working resolution (1600px max).
    # RAW previews are already ~1620px from exiftool. Full-res JPEGs
    # (6000x4000) must be downsized to match for consistent scoring
    # and to prevent CPU-bound ML models from hanging (30-60s per image).
    h, w = img.shape[:2]
    if max(h, w) > _CLASSIFY_MAX_DIM:
        scale = _CLASSIFY_MAX_DIM / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # 1. Sharpness (OpenCV Laplacian Variance) — uses 1024px resize internally
    sharpness = _compute_sharpness(img)

    # 2. Aesthetic (pyiqa MUSIQ + CLIPIQA)
    aesthetic = _compute_aesthetic_from_img(img)

    # 3. Exposure (Histogram Analysis) — now with bimodal detection
    exposure = _compute_exposure(img)

    # 4. Semantic Intelligence (Ollama + RAG)
    # We use a temp file for vision analysis if input is bytes.
    # Priority: rag_similarity_score (ChromaDB) > analyst text similarity > neutral 50.0
    description = ""
    # Seed with the RAG score if available; analyst text-similarity can override below.
    similarity = rag_similarity_score if rag_similarity_score is not None else 50.0

    if analyst:
        tmp_path = None
        if isinstance(image_input, bytes):
            tmp_path = tempfile.mktemp(suffix=".jpg")
            cv2.imwrite(tmp_path, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            description = analyst.analyze_image(tmp_path)
            if tmp_path and os.path.exists(tmp_path): os.unlink(tmp_path)
        else:
            description = analyst.analyze_image(image_input)

        # Analyst text-similarity overwrites the RAG seed when a VisionAnalyst
        # is active — the text-based signal is considered more specific.
        similarity = analyst.get_similarity_score(description)

    # 4. Composite Score (Genre-Aware Weighted Average)
    genre = detect_genre(exif)
    profile = GENRE_PROFILES.get(genre, GENRE_PROFILES["general"])
    
    w_sharp = profile["sharpness_weight"]
    w_aesth = profile["aesthetic_weight"]
    w_expo = profile["exposure_weight"]
    
    # Semantic weight: Part of the aesthetic bucket
    # We use a 70/30 split between general aesthetic and personal preference
    # to maintain KL Divergence guardrails (Personalization < 30% total influence).
    final_aesthetic = (aesthetic * 0.7) + (similarity * 0.3)
    
    composite = (sharpness * w_sharp) + (final_aesthetic * w_aesth) + (exposure * w_expo)
    tier = Tier.from_score(composite)

    # Recovery potential: sharp but poorly exposed/composed photos
    # can often be rescued in post-processing (shadows, brightness, colors)
    recovery = ""
    if tier in (Tier.CULL, Tier.REVIEW):
        if sharpness >= 60:
            # Sharp photo dragged down by exposure/aesthetic — very recoverable
            recovery = "high"
        elif sharpness >= 40:
            # Moderately sharp — some recovery possible
            recovery = "medium"
        elif sharpness >= 25 and exposure >= 30:
            # Slightly soft but not hopeless, exposure workable
            recovery = "low"

    return QualityScore(
        sharpness=round(sharpness, 1),
        aesthetic=round(aesthetic, 1),
        exposure=round(exposure, 1),
        composite=round(composite, 1),
        tier=tier,
        recovery_potential=recovery,
        semantic_description=description,
        semantic_similarity=similarity,
        processing_time=round(time.time() - start, 3),
    )


# ─── Signal 1: Sharpness (Laplacian Variance) ────────────────────────
def _compute_sharpness(img: np.ndarray) -> float:
    """
    Compute sharpness using Laplacian variance.
    Returns normalized 0-100 score.
    
    Industry standard: higher variance = sharper image.
    Normalized to 1024px wide for consistent scoring across resolutions.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Resize to consistent width for comparable scores
    target_width = 1024
    h, w = gray.shape
    if w > target_width:
        scale = target_width / w
        gray = cv2.resize(gray, (target_width, int(h * scale)))

    # Light Gaussian pre-blur to suppress sensor noise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Laplacian variance (the core metric)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = laplacian.var()

    # Normalize to 0-100 scale
    # Empirical range: 0-500+ for very sharp images
    # Mapping: 0 → 0, 50 → ~30, 100 → ~55, 200 → ~75, 500+ → ~100
    normalized = min(100.0, (variance / 300.0) * 100.0)

    return max(0.0, normalized)


# ─── Signal 2: Aesthetic Score (ML) ───────────────────────────────────
def _compute_aesthetic_from_img(img: np.ndarray) -> float:
    """
    Compute aesthetic score using pyiqa MUSIQ + CLIPIQA ensemble.
    Accepts OpenCV BGR image, saves to temp file for pyiqa inference.
    Returns normalized 0-100 score.
    """
    _init_ml_models()

    if not _ml_available:
        return 50.0

    tmp_path = None
    try:
        import torch

        # Save full-res image to temp file (pyiqa requires file path)
        tmp_path = tempfile.mktemp(suffix=".jpg")
        cv2.imwrite(tmp_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])

        scores = []

        # MUSIQ score (typically 0-100 range)
        if _musiq_model is not None:
            try:
                with torch.no_grad():
                    musiq_score = _musiq_model(tmp_path).item()
                scores.append(min(100.0, max(0.0, musiq_score)))
            except Exception as e:
                print(f"[quality_classifier] MUSIQ error: {e}")

        # CLIPIQA score (typically 0-1 range)
        if _clipiqa_model is not None:
            try:
                with torch.no_grad():
                    clip_score = _clipiqa_model(tmp_path).item()
                scores.append(min(100.0, max(0.0, clip_score * 100.0)))
            except Exception as e:
                print(f"[quality_classifier] CLIPIQA error: {e}")

        if scores:
            return sum(scores) / len(scores)
        return 50.0

    except Exception as e:
        print(f"[quality_classifier] Aesthetic scoring error: {e}")
        return 50.0
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


# ─── Signal 3: Exposure Quality (Histogram) ──────────────────────────
def _compute_exposure(img: np.ndarray) -> float:
    """
    Compute exposure quality via histogram analysis.
    Returns 0-100 score. Higher is better.
    
    Design Philosophy:
    - 128 midtone is "ideal" but creative under/overexposure is valid
    - High-contrast scenes (dark indoor + bright outdoor) have bimodal
      histograms — these should NOT be penalized heavily
    - Moderate clipping (<15%) is common in contrasty scenes
    - Only extreme clipping (>25%) gets heavy penalties
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(gray))
    std_val = float(np.std(gray))
    total_pixels = gray.size

    # Calculate percentage of clipped pixels
    black_clip = float(np.sum(gray < 5)) / total_pixels * 100
    white_clip = float(np.sum(gray > 250)) / total_pixels * 100

    # Detect bimodal histogram (high-contrast scenes like indoor/outdoor)
    # High std deviation = wide tonal range = likely intentional contrast
    is_high_contrast = std_val > 70

    # Base score: distance from ideal midpoint (128)
    # Use a gentler curve — creative exposure is valid
    distance_from_ideal = abs(mean_val - 128) / 128.0
    # Quadratic falloff: more forgiving near midpoint, harsher at extremes
    base_score = (1.0 - distance_from_ideal ** 1.5) * 100.0

    # High-contrast bonus: bimodal histograms have wide std dev
    # These are often artistic (dark interior, bright exterior)
    if is_high_contrast:
        base_score = max(base_score, 55.0)  # Floor at 55 for high-contrast scenes

    # Penalties for clipping (gentler thresholds)
    clipping_penalty = 0.0
    if black_clip > 20:
        clipping_penalty += (black_clip - 20) * 1.5
    if white_clip > 20:
        clipping_penalty += (white_clip - 20) * 1.5

    score = max(0.0, min(100.0, base_score - clipping_penalty))

    # Extreme cases only
    if mean_val < 15:
        score = min(score, 15.0)  # Nearly black
    elif mean_val > 245:
        score = min(score, 15.0)  # Nearly white

    return score


# ─── Self-Test ────────────────────────────────────────────────────────
def self_test() -> SelfTestResult:
    """
    Verify OpenCV loads and Laplacian variance works correctly.
    Creates a sharp image and a blurred image, verifies sharp > blurred.
    """
    result = SelfTestResult(module="quality_classifier")

    try:
        # Create a sharp checkerboard pattern (high frequency content)
        sharp = np.zeros((200, 200), dtype=np.uint8)
        for i in range(0, 200, 20):
            for j in range(0, 200, 20):
                if (i // 20 + j // 20) % 2 == 0:
                    sharp[i:i+20, j:j+20] = 255
        sharp_bgr = cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)

        # Create a heavily blurred version
        blurred_bgr = cv2.GaussianBlur(sharp_bgr, (31, 31), 10)

        # Score both
        sharp_score = _compute_sharpness(sharp_bgr)
        blurred_score = _compute_sharpness(blurred_bgr)

        # Verify sharp image scores higher than blurred
        if sharp_score > blurred_score and sharp_score > 0:
            details = [f"Sharp={sharp_score:.1f}, Blurred={blurred_score:.1f}"]
            details.append(f"OpenCV {cv2.__version__}")

            # Check ML availability
            _init_ml_models()
            if _ml_available:
                details.append("ML models: loaded (MUSIQ + CLIPIQA)")
            else:
                details.append("ML models: unavailable (OpenCV-only mode)")

            result.passed = True
            result.message = "Quality classifier operational"
            result.details = " | ".join(details)
        else:
            result.message = f"Sharpness scoring inverted: sharp={sharp_score}, blurred={blurred_score}"

    except Exception as e:
        result.message = f"Self-test error: {e}"

    return result


# ─── CLI Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Module 2: Quality Classifier — Self-Test")
    print("=" * 60)
    test = self_test()
    status = "✅ PASS" if test.passed else "❌ FAIL"
    print(f"{status} | {test.message}")
    if test.details:
        print(f"        | {test.details}")
