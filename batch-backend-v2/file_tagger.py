"""
Antigravity Engine v2.0 — Module 5: File Tagger
macOS Finder tags via PyObjC NSURL + Adobe-compatible XMP sidecar generation.

Key Design:
- Finder tags use NSURL.setResourceValue_ (proven working from v1)
- XMP sidecars are standard Adobe XML (Lightroom/Capture One compatible)
- Gracefully degrades on non-macOS (skips Finder tags, still writes XMP)
- Never modifies the source image file

Usage:
    from file_tagger import tag_photo, set_finder_tag, write_xmp_sidecar, self_test
    tag_photo("/path/to/image.ARW", tier=Tier.PORTFOLIO, score=87.3, reasoning="Sharp, well-exposed")
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from models import Tier, TIER_CONFIG, SelfTestResult


# ─── macOS Finder Tag Support ────────────────────────────────────────
_HAS_PYOBJC = False
try:
    if sys.platform == "darwin":
        from Foundation import NSURL
        from AppKit import NSURLTagNamesKey
        _HAS_PYOBJC = True
except ImportError:
    pass

import subprocess


def set_finder_tag(filepath: str, tag_name: str) -> bool:
    """
    Apply a macOS Finder tag to a file.
    Uses native NSURL API — proven working, no shell commands.
    Returns True on success, False on failure or non-macOS.
    """
    if not _HAS_PYOBJC:
        return False

    try:
        url = NSURL.fileURLWithPath_(filepath)
        success, error = url.setResourceValue_forKey_error_(
            [tag_name], NSURLTagNamesKey, None
        )
        if success:
            return True
        else:
            print(f"[file_tagger] Tag failed for {os.path.basename(filepath)}: {error}")
            return False
    except Exception as e:
        print(f"[file_tagger] Tag exception: {e}")
        return False


def read_finder_tags(filepath: str) -> list:
    """Read Finder tags from a file. For testing/verification."""
    if not _HAS_PYOBJC:
        return []
    try:
        url = NSURL.fileURLWithPath_(filepath)
        success, tags, error = url.getResourceValue_forKey_error_(
            None, NSURLTagNamesKey, None
        )
        if success and tags:
            return list(tags)
        return []
    except Exception:
        return []


def set_finder_comment(filepath: str, comment: str) -> bool:
    """
    Set the Finder comment (visible in Get Info and Finder columns).
    Uses osascript to set the comment via Finder AppleScript.
    This makes score breakdowns visible when browsing in Finder.
    """
    try:
        escaped = comment.replace('"', '\\"').replace("'", "'\\''")
        script = f'''tell application "Finder"
            set theFile to POSIX file "{filepath}" as alias
            set comment of theFile to "{escaped}"
        end tell'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def write_xmp_sidecar(
    filepath: str,
    rating: int,
    label: str = "",
    score: float = 0.0,
    sharpness: float = 0.0,
    aesthetic: float = 0.0,
    exposure: float = 0.0,
    reasoning: str = "",
    technical_flaws: list = None,
    recovery_potential: str = "",
    recovery_notes: str = "",
) -> bool:
    """
    Write an Adobe-compatible XMP sidecar file next to the source image.
    
    Compatible with Adobe Lightroom, Capture One, darktable, and any XMP-aware viewer.
    Creates {filename}.xmp in the same directory as the source file.
    """
    try:
        base, _ = os.path.splitext(filepath)
        xmp_path = base + ".xmp"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        flaws_str = ", ".join(technical_flaws) if technical_flaws else ""

        xmp_content = f'''<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:antigravity="http://antigravity.ai/ns/1.0/"
    xmp:Rating="{rating}"
    xmp:Label="{label}"
    xmp:ModifyDate="{now}"
    antigravity:CompositeScore="{score:.1f}"
    antigravity:Sharpness="{sharpness:.1f}"
    antigravity:Aesthetic="{aesthetic:.1f}"
    antigravity:Exposure="{exposure:.1f}"
    antigravity:RecoveryPotential="{recovery_potential}"
    antigravity:RecoveryNotes="{_xml_escape(recovery_notes)}"
    antigravity:Reasoning="{_xml_escape(reasoning)}"
    antigravity:TechnicalFlaws="{_xml_escape(flaws_str)}"
    antigravity:EngineVersion="2.0.0">
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(xmp_content)

        return True

    except Exception as e:
        print(f"[file_tagger] XMP write error: {e}")
        return False


def _xml_escape(text: str) -> str:
    """Escape special characters for XML attributes."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def tag_photo(
    filepath: str,
    tier: Tier,
    score: float = 0.0,
    sharpness: float = 0.0,
    aesthetic: float = 0.0,
    exposure: float = 0.0,
    reasoning: str = "",
    technical_flaws: list = None,
    recovery_potential: str = "",
    recovery_notes: str = "",
) -> bool:
    """
    Apply Finder tag, Finder comment (with score breakdown), and XMP sidecar.
    This is the main entry point for other modules.
    """
    config = TIER_CONFIG[tier]

    # 1. Finder tag (macOS only, non-fatal if it fails)
    tag_name = config["tag"]
    if recovery_potential == "high" and tier == Tier.CULL:
        tag_name = "Recoverable"  # Special tag for moment-saver shots
    set_finder_tag(filepath, tag_name)

    # 2. Finder comment — visible in Finder's Comments column
    comment_parts = [f"{config['tag']} | Score:{score:.0f}"]
    comment_parts.append(f"Sharp:{sharpness:.0f} Aesth:{aesthetic:.0f} Expo:{exposure:.0f}")
    if recovery_potential:
        comment_parts.append(f"Recovery:{recovery_potential.upper()}")
    if recovery_notes:
        comment_parts.append(recovery_notes)
    comment = " | ".join(comment_parts)
    set_finder_comment(filepath, comment)

    # 3. XMP sidecar (works everywhere)
    xmp_ok = write_xmp_sidecar(
        filepath,
        rating=config["rating"],
        label=config["label"],
        score=score,
        sharpness=sharpness,
        aesthetic=aesthetic,
        exposure=exposure,
        reasoning=reasoning,
        technical_flaws=technical_flaws or [],
        recovery_potential=recovery_potential,
        recovery_notes=recovery_notes,
    )

    return xmp_ok


def self_test() -> SelfTestResult:
    """
    Verify Finder tagging and XMP sidecar generation.
    """
    result = SelfTestResult(module="file_tagger")

    try:
        # Create a temp file for testing
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test")
            tmp_path = tmp.name

        # Test XMP sidecar generation
        xmp_ok = write_xmp_sidecar(
            tmp_path, rating=5, label="Test",
            score=85.0, reasoning="Self-test verification"
        )
        xmp_path = os.path.splitext(tmp_path)[0] + ".xmp"
        xmp_exists = os.path.exists(xmp_path)

        # Test Finder tagging
        tag_ok = False
        tag_verified = False
        if _HAS_PYOBJC:
            tag_ok = set_finder_tag(tmp_path, "SelfTest")
            if tag_ok:
                tags = read_finder_tags(tmp_path)
                tag_verified = "SelfTest" in tags

        # Clean up
        os.unlink(tmp_path)
        if xmp_exists:
            os.unlink(xmp_path)

        # Report results
        details = []
        if xmp_ok and xmp_exists:
            details.append("XMP sidecar: OK")
        else:
            details.append("XMP sidecar: FAILED")

        if _HAS_PYOBJC:
            if tag_verified:
                details.append("Finder tags: OK (read-back verified)")
            elif tag_ok:
                details.append("Finder tags: Set but read-back failed")
            else:
                details.append("Finder tags: FAILED")
        else:
            details.append("Finder tags: Skipped (not macOS or PyObjC missing)")

        result.passed = xmp_ok and xmp_exists
        result.message = "File tagger operational" if result.passed else "XMP generation failed"
        result.details = " | ".join(details)

    except Exception as e:
        result.message = f"Self-test error: {e}"

    return result


# ─── CLI Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Module 5: File Tagger — Self-Test")
    print("=" * 60)
    test = self_test()
    status = "✅ PASS" if test.passed else "❌ FAIL"
    print(f"{status} | {test.message}")
    if test.details:
        print(f"        | {test.details}")
