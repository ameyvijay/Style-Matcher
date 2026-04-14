"""
Antigravity Engine v2.0 — Module 1: Preview Extractor
Zero-lock preview extraction and EXIF metadata via exiftool.

Key Design:
- Uses exiftool subprocess with stdout streaming (never locks source files)
- Extracts embedded JPEG preview from RAW files (no full decode needed)
- Returns binary bytes (no temp files on disk)
- Non-blocking: other processes can access the file simultaneously

Usage:
    from preview_extractor import extract_preview, extract_metadata, self_test
    preview_bytes = extract_preview("/path/to/image.ARW")
    metadata = extract_metadata("/path/to/image.ARW")
"""
from __future__ import annotations

import json
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

from models import SelfTestResult, NEEDS_CONVERSION, JPEG_EXTENSIONS


def _find_exiftool() -> str | None:
    """Locate the exiftool binary."""
    return shutil.which("exiftool")


def extract_preview(source_path: str) -> bytes | None:
    """
    Extract the embedded JPEG preview from a RAW/HEIC file.
    
    Returns binary JPEG bytes via stdout — the source file is NEVER locked.
    For JPEG/PNG files, reads the file directly (already viewable).
    Returns None on failure.
    """
    if not os.path.isfile(source_path):
        return None

    ext = os.path.splitext(source_path)[1].lower()

    # For JPEG/PNG, just read the file bytes directly
    if ext in JPEG_EXTENSIONS or ext == '.png':
        try:
            with open(source_path, 'rb') as f:
                return f.read()
        except Exception:
            return None

    # For RAW/HEIC/TIFF, extract the embedded preview via exiftool
    exiftool = _find_exiftool()
    if not exiftool:
        return None

    try:
        # Try PreviewImage first (most common in Sony ARW)
        result = subprocess.run(
            [exiftool, "-b", "-PreviewImage", source_path],
            capture_output=True,
            timeout=15
        )
        if result.returncode == 0 and result.stdout and len(result.stdout) > 100:
            return result.stdout

        # Fallback: try JpgFromRaw (some cameras embed full-size JPEG)
        result = subprocess.run(
            [exiftool, "-b", "-JpgFromRaw", source_path],
            capture_output=True,
            timeout=15
        )
        if result.returncode == 0 and result.stdout and len(result.stdout) > 100:
            return result.stdout

        # Fallback: try ThumbnailImage (smallest, always available)
        result = subprocess.run(
            [exiftool, "-b", "-ThumbnailImage", source_path],
            capture_output=True,
            timeout=15
        )
        if result.returncode == 0 and result.stdout and len(result.stdout) > 100:
            return result.stdout

        return None

    except subprocess.TimeoutExpired:
        print(f"[preview_extractor] Timeout extracting preview: {source_path}")
        return None
    except Exception as e:
        print(f"[preview_extractor] Error: {e}")
        return None


def extract_metadata(source_path: str) -> dict:
    """
    Extract full EXIF metadata as a Python dict.
    
    Uses exiftool -json for comprehensive, non-locking extraction.
    Returns empty dict on failure.
    """
    if not os.path.isfile(source_path):
        return {}

    exiftool = _find_exiftool()
    if not exiftool:
        return {}

    try:
        result = subprocess.run(
            [exiftool, "-json", "-n", source_path],  # -n: numeric values (no string formatting)
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            if isinstance(data, list) and len(data) > 0:
                raw = data[0]
                # Normalize to a clean, useful subset
                return _normalize_exif(raw)
        return {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"[preview_extractor] Metadata error: {e}")
        return {}
    except Exception as e:
        print(f"[preview_extractor] Unexpected error: {e}")
        return {}


def _normalize_exif(raw: dict) -> dict:
    """Extract the most useful EXIF fields into a clean dict."""
    def _safe_get(keys: list, default="Unknown"):
        for k in keys:
            if k in raw and raw[k] is not None:
                return raw[k]
        return default

    iso = _safe_get(["ISO", "ISOSpeedRatings"], 0)
    if isinstance(iso, list):
        iso = iso[0] if iso else 0

    shutter = _safe_get(["ExposureTime", "ShutterSpeedValue"], 0)
    if isinstance(shutter, (int, float)) and shutter > 0 and shutter < 1:
        shutter_str = f"1/{int(1/shutter)}"
    elif isinstance(shutter, (int, float)):
        shutter_str = f"{shutter}s"
    else:
        shutter_str = str(shutter)

    aperture = _safe_get(["FNumber", "ApertureValue"], 0)
    aperture_str = f"f/{aperture}" if isinstance(aperture, (int, float)) and aperture > 0 else str(aperture)

    focal = _safe_get(["FocalLength", "FocalLengthIn35mmFormat"], 0)
    focal_str = f"{focal}mm" if isinstance(focal, (int, float)) and focal > 0 else str(focal)

    return {
        "Make": _safe_get(["Make"]),
        "Model": _safe_get(["Model"]),
        "ISO": int(iso) if isinstance(iso, (int, float)) else 0,
        "Shutter": shutter_str,
        "ShutterSpeed": float(shutter) if isinstance(shutter, (int, float)) else 0,
        "Aperture": aperture_str,
        "FNumber": float(aperture) if isinstance(aperture, (int, float)) else 0,
        "FocalLength": focal_str,
        "FocalLengthMM": float(focal) if isinstance(focal, (int, float)) else 0,
        "DateTime": _safe_get(["DateTimeOriginal", "CreateDate", "ModifyDate"]),
        "WhiteBalance": _safe_get(["WhiteBalance"], "Auto"),
        "MeteringMode": _safe_get(["MeteringMode"], "Unknown"),
        "ExposureCompensation": _safe_get(["ExposureCompensation"], 0),
        "LensModel": _safe_get(["LensModel", "LensID", "Lens"], "Unknown"),
        "ImageWidth": _safe_get(["ImageWidth", "ExifImageWidth"], 0),
        "ImageHeight": _safe_get(["ImageHeight", "ExifImageHeight"], 0),
    }


def self_test() -> SelfTestResult:
    """
    Verify exiftool is installed and can extract data.
    """
    result = SelfTestResult(module="preview_extractor")

    # Check exiftool is available
    exiftool = _find_exiftool()
    if not exiftool:
        result.message = "exiftool not found. Install with: brew install exiftool"
        return result

    # Check version
    try:
        ver = subprocess.run(
            [exiftool, "-ver"],
            capture_output=True, text=True, timeout=5
        )
        if ver.returncode != 0:
            result.message = f"exiftool returned error code {ver.returncode}"
            return result

        version = ver.stdout.strip()

        # Test: Create a minimal JPEG, extract metadata
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
            # Write a minimal valid JPEG (2x2 white pixels)
            from PIL import Image
            img = Image.new("RGB", (2, 2), (255, 255, 255))
            img.save(tmp_path, "JPEG")

        metadata = extract_metadata(tmp_path)
        os.unlink(tmp_path)

        if metadata:
            result.passed = True
            result.message = f"exiftool v{version} operational"
            result.details = f"Path: {exiftool}"
        else:
            result.message = f"exiftool v{version} found but metadata extraction failed"

    except Exception as e:
        result.message = f"Self-test error: {e}"

    return result


# ─── CLI Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Module 1: Preview Extractor — Self-Test")
    print("=" * 60)
    test = self_test()
    status = "✅ PASS" if test.passed else "❌ FAIL"
    print(f"{status} | {test.message}")
    if test.details:
        print(f"        | {test.details}")
