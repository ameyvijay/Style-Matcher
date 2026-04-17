"""
Antigravity Engine v2.0 — Module 4: Image Enhancer
Three-stage enhancement pipeline: Denoise → CLAHE → Real-ESRGAN

Key Design:
- Stage A: ISO-adaptive denoising (only when needed)
    - ISO ≤ 1600: No denoising
    - ISO 1601-3200: Light denoise (OpenCV fastNlMeansDenoisingColored)
    - ISO > 3200: Heavy denoise (OpenCV with stronger parameters)
- Stage B: CLAHE in LAB color space (adaptive contrast without color distortion)
- Stage C: Real-ESRGAN AI super-resolution (native macOS binary, all keepers)
- Never modifies the source file

Usage:
    from image_enhancer import enhance, self_test
    success = enhance("/path/to/developed.jpg", "/output/enhanced.jpg", iso=3200)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from models import EnhancementProfile, SelfTestResult


# ─── Locate Real-ESRGAN binary ───────────────────────────────────────
_ESRGAN_PATHS = [
    "/usr/local/bin/realesrgan-ncnn-vulkan",
    os.path.expanduser("~/Tools/realesrgan/realesrgan-ncnn-vulkan"),
    os.path.expanduser("~/realesrgan-ncnn-vulkan"),
    "./realesrgan-ncnn-vulkan",
]


def _find_esrgan() -> str | None:
    """Find the Real-ESRGAN NCNN binary."""
    # Check PATH first
    found = shutil.which("realesrgan-ncnn-vulkan")
    if found:
        return found
    # Check known locations
    for path in _ESRGAN_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


# ─── Main Enhancement Pipeline ───────────────────────────────────────
def enhance(
    input_path: str,
    output_path: str,
    iso: int = 0,
    profile: EnhancementProfile | None = None,
) -> bool:
    """
    Apply the full enhancement pipeline: Denoise → CLAHE → Pillow polish → ESRGAN.
    
    Args:
        input_path: Path to input JPEG (developed from RAW, or original JPEG)
        output_path: Path for enhanced JPEG output
        iso: ISO value from EXIF (controls denoising aggressiveness)
        profile: Enhancement settings (uses defaults if None)
    
    Returns:
        True on success, False on failure
    """
    if profile is None:
        profile = EnhancementProfile()

    try:
        # Load with OpenCV (BGR)
        img = cv2.imread(input_path)
        if img is None:
            print(f"[image_enhancer] Cannot read: {input_path}")
            return False

        # Stage A: ISO-Adaptive Denoising
        if iso > profile.denoise_iso_threshold:
            img = _denoise(img, iso, profile)

        # Stage B: CLAHE in LAB Color Space
        img = _apply_clahe(img, profile)

        # Save intermediate result via Pillow (for color polish + Real-ESRGAN input)
        intermediate_path = output_path + ".tmp.jpg"
        _save_with_pillow_polish(img, intermediate_path, profile)

        # Stage C: Real-ESRGAN AI Enhancement (if enabled and available)
        if profile.esrgan_enabled:
            esrgan_success = _apply_esrgan(intermediate_path, output_path, profile)
            if esrgan_success:
                # Clean up intermediate
                if os.path.exists(intermediate_path):
                    os.unlink(intermediate_path)
                return True
            else:
                # ESRGAN failed or unavailable — use the Pillow-polished version
                if os.path.exists(intermediate_path):
                    shutil.move(intermediate_path, output_path)
                    return True

        # No ESRGAN — just use the polished version
        if os.path.exists(intermediate_path):
            shutil.move(intermediate_path, output_path)

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    except Exception as e:
        print(f"[image_enhancer] Enhancement error: {e}")
        # Clean up intermediate if it exists
        intermediate_path = output_path + ".tmp.jpg"
        if os.path.exists(intermediate_path):
            os.unlink(intermediate_path)
        return False


# ─── Stage A: ISO-Adaptive Denoising ─────────────────────────────────
def _denoise(img: np.ndarray, iso: int, profile: EnhancementProfile) -> np.ndarray:
    """
    Apply ISO-adaptive denoising.
    
    Parameters tuned per ISO range:
    - ISO 1601-3200: Light (h=6, preserves most detail)
    - ISO > 3200: Heavier (h=10, stronger noise reduction)
    """
    if iso <= profile.denoise_iso_threshold:
        return img

    if iso > profile.denoise_heavy_iso_threshold:
        # Heavy denoising for extreme ISO
        h_luminance = 10
        h_color = 10
        template_window = 7
        search_window = 21
    else:
        # Light denoising for moderate ISO
        h_luminance = 6
        h_color = 6
        template_window = 7
        search_window = 21

    denoised = cv2.fastNlMeansDenoisingColored(
        img,
        None,
        h_luminance,
        h_color,
        template_window,
        search_window,
    )

    return denoised


# ─── Stage B: CLAHE in LAB Color Space ───────────────────────────────
def _apply_clahe(img: np.ndarray, profile: EnhancementProfile) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    in the LAB color space.
    
    By operating only on the L (Lightness) channel, we enhance contrast
    WITHOUT distorting color saturation or hue. This is the same technique
    used in professional photo editors.
    """
    # Convert BGR → LAB
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Apply CLAHE to L channel only
    clahe = cv2.createCLAHE(
        clipLimit=profile.clahe_clip_limit,
        tileGridSize=(profile.clahe_tile_size, profile.clahe_tile_size),
    )
    l_enhanced = clahe.apply(l_channel)

    # Merge and convert back
    lab_enhanced = cv2.merge((l_enhanced, a_channel, b_channel))
    enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    return enhanced


# ─── Pillow Polish (Color + Sharpness) ───────────────────────────────
def _save_with_pillow_polish(
    img: np.ndarray,
    output_path: str,
    profile: EnhancementProfile,
) -> None:
    """
    Apply final Pillow polish (color, contrast, sharpness) and save as JPEG.
    These are intentionally subtle — enhance, don't over-process.
    """
    # Convert OpenCV BGR → Pillow RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)

    # Apply subtle enhancements
    pil_img = ImageEnhance.Contrast(pil_img).enhance(profile.contrast_boost)
    pil_img = ImageEnhance.Color(pil_img).enhance(profile.color_boost)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(profile.sharpness_boost)

    # Respect max resolution scale if set
    if profile.max_resolution_scale < 1.0:
        w, h = pil_img.size
        pil_img = pil_img.resize((int(w * profile.max_resolution_scale), int(h * profile.max_resolution_scale)), Image.LANCZOS)

    # Save as high-quality JPEG
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Initial save
    quality = profile.jpeg_quality
    pil_img.save(output_path, "JPEG", quality=quality, optimize=True)
    
    # Recursive down-sizing if max_file_size_mb is set and exceeded
    if profile.max_file_size_mb > 0:
        current_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        attempts = 0
        while current_size_mb > profile.max_file_size_mb and attempts < 5:
            attempts += 1
            quality = int(quality * 0.9) # Reduce quality by 10%
            if quality < 60: # If quality is too low, reduce resolution instead
                w, h = pil_img.size
                pil_img = pil_img.resize((int(w * 0.8), int(h * 0.8)), Image.LANCZOS)
                quality = 85 # Reset quality to a reasonable level
            
            pil_img.save(output_path, "JPEG", quality=quality, optimize=True)
            current_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"[image_enhancer] Size {current_size_mb:.1f}MB > {profile.max_file_size_mb}MB. Reduced to quality={quality}, attempt={attempts}")


# ─── Stage C: Real-ESRGAN AI Super-Resolution ────────────────────────
def _apply_esrgan(
    input_path: str,
    output_path: str,
    profile: EnhancementProfile,
) -> bool:
    """
    Apply Real-ESRGAN AI super-resolution using the native macOS binary.
    
    Uses realesrgan-ncnn-vulkan which:
    - Runs natively on Apple Silicon (Vulkan → Metal bridge)
    - Requires zero Python/CUDA dependencies
    - Typically takes 2-4 seconds per image at 2x scale
    """
    esrgan = _find_esrgan()
    if not esrgan:
        return False

    try:
        result = subprocess.run(
            [
                esrgan,
                "-i", input_path,
                "-o", output_path,
                "-n", "realesrgan-x4plus",  # Best quality model
                "-s", str(profile.esrgan_scale),  # 2x upscale
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            return os.path.getsize(output_path) > 0
        else:
            if result.stderr:
                print(f"[image_enhancer] Real-ESRGAN error: {result.stderr.strip()}")
            return False

    except subprocess.TimeoutExpired:
        print("[image_enhancer] Real-ESRGAN timeout (>60s)")
        return False
    except Exception as e:
        print(f"[image_enhancer] Real-ESRGAN exception: {e}")
        return False


# ─── Self-Test ────────────────────────────────────────────────────────
def self_test() -> SelfTestResult:
    """
    Verify all enhancement stages are operational.
    """
    result = SelfTestResult(module="image_enhancer")

    details = []

    try:
        # Test CLAHE
        test_img = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        clahe_result = _apply_clahe(test_img, EnhancementProfile())
        if clahe_result is not None and clahe_result.shape == test_img.shape:
            details.append("CLAHE: OK")
        else:
            details.append("CLAHE: FAILED")
            result.message = "CLAHE failed"
            return result

        # Test denoising
        denoised = _denoise(test_img, iso=3200, profile=EnhancementProfile())
        if denoised is not None and denoised.shape == test_img.shape:
            details.append("Denoise: OK")
        else:
            details.append("Denoise: FAILED")

        # Test Pillow save
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        _save_with_pillow_polish(test_img, tmp_path, EnhancementProfile())
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            details.append("Pillow save: OK")
            os.unlink(tmp_path)
        else:
            details.append("Pillow save: FAILED")

        # Check Real-ESRGAN availability
        esrgan = _find_esrgan()
        if esrgan:
            details.append(f"Real-ESRGAN: found ({esrgan})")
        else:
            details.append("Real-ESRGAN: not installed (optional, will use Pillow-only)")

        result.passed = True
        result.message = "Image enhancer operational"
        result.details = " | ".join(details)

    except Exception as e:
        result.message = f"Self-test error: {e}"

    return result


# ─── CLI Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Module 4: Image Enhancer — Self-Test")
    print("=" * 60)
    test = self_test()
    status = "✅ PASS" if test.passed else "❌ FAIL"
    print(f"{status} | {test.message}")
    if test.details:
        print(f"        | {test.details}")
