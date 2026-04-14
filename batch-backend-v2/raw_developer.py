"""
Antigravity Engine v2.0 — Module 3: RAW Developer
Converts RAW files to high-quality developed JPEGs.

Key Design:
- Primary: rawpy (LibRaw) — full control over WB, demosaic, exposure
- Fallback: macOS sips — zero-install, native M4, less control
- Never modifies the source RAW file
- Output goes to a separate /Enhanced/ directory

Usage:
    from raw_developer import develop, self_test
    success = develop("/path/to/image.ARW", "/output/image_developed.jpg")
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time

from models import SelfTestResult, NEEDS_CONVERSION

# Check rawpy availability
_HAS_RAWPY = False
try:
    import rawpy
    _HAS_RAWPY = True
except ImportError:
    pass


def develop(input_path: str, output_path: str) -> bool:
    """
    Develop a RAW file into a high-quality JPEG.
    
    Uses rawpy (LibRaw) as primary engine, falls back to macOS sips.
    The source file is NEVER modified.
    
    Args:
        input_path: Path to RAW file (.arw, .cr2, .nef, etc.)
        output_path: Path for output JPEG
    
    Returns:
        True on success, False on failure
    """
    ext = os.path.splitext(input_path)[1].lower()

    # For JPEG/PNG, just copy (no development needed)
    if ext not in NEEDS_CONVERSION:
        try:
            shutil.copy2(input_path, output_path)
            return True
        except Exception as e:
            print(f"[raw_developer] Copy error: {e}")
            return False

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Primary: rawpy (LibRaw)
    if _HAS_RAWPY:
        success = _develop_rawpy(input_path, output_path)
        if success:
            return True
        print(f"[raw_developer] rawpy failed, trying sips fallback...")

    # Fallback: macOS sips
    return _develop_sips(input_path, output_path)


def _develop_rawpy(input_path: str, output_path: str) -> bool:
    """
    Develop RAW using rawpy (LibRaw wrapper).
    
    Settings tuned for high-quality output:
    - Camera white balance (honors what the photographer set)
    - AHD demosaic algorithm (highest quality, handles fine detail)
    - sRGB output color space
    - Auto exposure scaling
    """
    try:
        from PIL import Image

        with rawpy.imread(input_path) as raw:
            # Develop the RAW with professional settings
            rgb = raw.postprocess(
                use_camera_wb=True,                    # Honor camera WB setting
                no_auto_bright=False,                  # Allow auto exposure scaling
                output_color=rawpy.ColorSpace.sRGB,    # Standard color space
                output_bps=8,                          # 8-bit output (for JPEG)
                demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,  # High quality
                four_color_rgb=False,                  # Standard 3-channel output
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Full,  # Built-in denoise
            )

        # Save as high-quality JPEG via Pillow (preserves color accuracy)
        img = Image.fromarray(rgb)
        img.save(output_path, "JPEG", quality=95, optimize=True)

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    except Exception as e:
        print(f"[raw_developer] rawpy error: {e}")
        return False


def _develop_sips(input_path: str, output_path: str) -> bool:
    """
    Develop RAW using macOS native sips CLI.
    
    sips uses Apple's ImageIO framework at the C level —
    same GPU acceleration as Core Image, but exposed through a stable CLI
    that works perfectly headless.
    """
    try:
        result = subprocess.run(
            [
                "sips",
                "-s", "format", "jpeg",
                "-s", "formatOptions", "95",
                "--matchTo", "/System/Library/ColorSync/Profiles/sRGB Profile.icc",
                input_path,
                "--out", output_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            return os.path.getsize(output_path) > 0
        else:
            if result.stderr:
                print(f"[raw_developer] sips error: {result.stderr.strip()}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[raw_developer] sips timeout on {input_path}")
        return False
    except FileNotFoundError:
        print("[raw_developer] sips not found (not macOS?)")
        return False
    except Exception as e:
        print(f"[raw_developer] sips exception: {e}")
        return False


def self_test() -> SelfTestResult:
    """
    Verify at least one RAW development method is available.
    Tests with a synthetic image (actual RAW testing requires a real file).
    """
    result = SelfTestResult(module="raw_developer")

    details = []

    # Check rawpy
    if _HAS_RAWPY:
        details.append(f"rawpy: available (v{rawpy.__version__})")
    else:
        details.append("rawpy: not installed (pip install rawpy)")

    # Check sips
    try:
        sips_result = subprocess.run(
            ["sips", "--help"],
            capture_output=True,
            timeout=5,
        )
        if sips_result.returncode == 0 or sips_result.returncode == 1:
            details.append("sips: available (macOS native)")
        else:
            details.append("sips: not available")
    except FileNotFoundError:
        details.append("sips: not found (not macOS)")
    except Exception:
        details.append("sips: check failed")

    # Test Pillow JPEG save (shared by both paths)
    try:
        from PIL import Image
        import numpy as np

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        img.save(tmp_path, "JPEG", quality=95)
        saved = os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0
        os.unlink(tmp_path)

        if saved:
            details.append("Pillow JPEG save: OK")
        else:
            details.append("Pillow JPEG save: FAILED")
    except Exception as e:
        details.append(f"Pillow: error ({e})")
        saved = False

    # Pass if at least one development method + Pillow works
    has_engine = _HAS_RAWPY or shutil.which("sips") is not None
    result.passed = has_engine and saved
    result.message = "RAW developer operational" if result.passed else "No RAW development engine available"
    result.details = " | ".join(details)

    return result


# ─── CLI Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Module 3: RAW Developer — Self-Test")
    print("=" * 60)
    test = self_test()
    status = "✅ PASS" if test.passed else "❌ FAIL"
    print(f"{status} | {test.message}")
    if test.details:
        print(f"        | {test.details}")
