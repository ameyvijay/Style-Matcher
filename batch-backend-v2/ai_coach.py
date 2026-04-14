"""
Antigravity Engine v2.0 — Module 6: AI Photography Coach
Genre-aware coaching with composition, camera technique, and creative style intelligence.

Key Design:
- Genre detection from EXIF (focal length, aperture, scene mode)
- Genre-aware scoring interpretation (landscape ≠ portrait ≠ street)
- Composition coaching: Rule of Thirds, Leading Lines, Golden Ratio, etc.
- Camera shot & angle suggestions based on focal length
- Creative style guidance: lighting, color theory, perspective
- Exposure triangle coaching: specific, actionable advice
- Batch-level pattern analysis

Usage:
    from ai_coach import assess_image, compile_batch_report, self_test
    assessment = assess_image(filename, format, quality, exif, enhanced_path)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from models import (
    QualityScore, Tier, ImageAssessment, CoachingAdvice,
    BatchResult, SelfTestResult, GENRE_PROFILES, detect_genre,
)


# ─── Shot Types ──────────────────────────────────────────────────────
# Inference based on focal length


def _get_shot_type(focal_mm: float) -> str:
    """Classify camera shot type from focal length."""
    if not focal_mm:
        return "unknown"
    if focal_mm <= 18:
        return "extreme_wide"       # Extreme Wide Shot — environment focus
    elif focal_mm <= 35:
        return "wide"               # Wide/Long Shot — full scene
    elif focal_mm <= 50:
        return "medium"             # Medium Shot — waist up, street
    elif focal_mm <= 85:
        return "medium_close"       # Medium Close — chest up, classic portrait
    elif focal_mm <= 135:
        return "close_up"           # Close-Up — face, emotion
    elif focal_mm <= 200:
        return "tight_close_up"     # Tight Close-Up — details
    else:
        return "extreme_close_up"   # Extreme Close-Up with reach


SHOT_TYPE_NAMES = {
    "extreme_wide": "Extreme Wide Shot (establishing/environment)",
    "wide": "Wide Shot (full scene/landscape)",
    "medium": "Medium Shot (waist-up/street)",
    "medium_close": "Medium Close-Up (portrait/upper body)",
    "close_up": "Close-Up (face/emotion)",
    "tight_close_up": "Tight Close-Up (details/compression)",
    "extreme_close_up": "Extreme Close-Up (details at distance)",
    "unknown": "Unknown",
}


# ─── Composition Techniques Knowledge Base ────────────────────────────

COMPOSITION_TECHNIQUES = {
    "landscape": [
        "Rule of Thirds: Place the horizon on the upper or lower third — never dead center.",
        "Leading Lines: Use roads, rivers, fences, or shorelines to draw the eye into the scene.",
        "Foreground Interest: Include rocks, flowers, or patterns in the foreground for depth and scale.",
        "Golden Ratio/Spiral: Guide the viewer's eye naturally through the scene using the Fibonacci spiral.",
        "Diagonal Lines: Use mountain ridges or riverbanks diagonally for dynamic energy.",
        "Negative Space: Let vast skies or calm water emphasize the grandeur of the landscape.",
        "Layering: Stack foreground, midground, and background elements for three-dimensional depth.",
    ],
    "portrait": [
        "Fill the Frame: Get close — the subject should dominate the image for maximum emotional impact.",
        "Rule of Thirds: Place the subject's eyes at an upper-third intersection point.",
        "Frame Within a Frame: Use doorways, windows, or foliage to naturally frame the subject.",
        "Negative Space: Use clean, uncluttered backgrounds to draw attention to the subject.",
        "Odd Numbers: Groups of 3 or 5 subjects create more natural, dynamic compositions than even numbers.",
        "Symmetry: Position the subject centrally for a powerful, confrontational portrait.",
        "Depth Separation: Use wide aperture (f/1.4–f/2.8) to isolate the subject with creamy bokeh.",
    ],
    "street": [
        "Juxtaposition: Place contrasting elements (old/young, rich/poor, stillness/motion) near each other.",
        "Layering: Capture multiple planes of action — a foreground subject, midground activity, background context.",
        "Leading Lines: Use urban lines (tracks, crosswalks, building edges) to guide the eye.",
        "Decisive Moment: Anticipate peak action — the moment feet leave the ground, hands gesture, expressions form.",
        "Shadow Play: Use harsh sunlight and deep shadows to create graphic, high-contrast compositions.",
        "Minimalism: Isolate a single subject against a clean wall or empty space for maximum impact.",
        "Dutch Angle: Tilt the camera slightly for a sense of unease or dynamic energy in chaotic scenes.",
    ],
    "architecture": [
        "Symmetry: Find and exploit perfect bilateral symmetry in facades, hallways, and reflections.",
        "Leading Lines: Converging lines of buildings create powerful vanishing-point compositions.",
        "Patterns and Repetition: Windows, columns, and tiles create mesmerizing rhythmic patterns.",
        "Low Angle: Shoot upward to emphasize height and power of structures.",
        "Frame Within a Frame: Use archways, tunnels, or colonnades to frame the subject building.",
        "Golden Triangle: Use diagonal grids for dynamic architectural compositions.",
        "Minimalism: Isolate geometric shapes from the building for abstract, fine-art results.",
    ],
    "wildlife": [
        "Eye Contact: The subject's eyes must be tack-sharp — this is the non-negotiable rule.",
        "Rule of Space: Leave space in front of the animal's direction of travel for a sense of motion.",
        "Fill the Frame: Get as close (or crop) as needed — habitat context vs. detailed species study.",
        "Rule of Thirds: Place the subject at an intersection, never dead center.",
        "Low Angle: Get to the animal's eye level for an intimate, eye-to-eye connection.",
        "Background Simplicity: Use telephoto compression and wide aperture to melt distracting backgrounds.",
        "Catchlight: Wait for a highlight in the animal's eye — it makes the portrait come alive.",
    ],
    "macro": [
        "Depth of Field Control: At macro distances, DOF is razor-thin. Focus stack for edge-to-edge sharpness.",
        "Diagonal Composition: Angle subjects diagonally across the frame for dynamic energy.",
        "Negative Space: Use blurred backgrounds to isolate tiny subjects against clean color.",
        "Patterns and Textures: Macro reveals patterns invisible to the naked eye — find them.",
        "Backlighting: Translucent subjects (leaves, insect wings) glow beautifully when backlit.",
        "Symmetry: Many natural subjects exhibit bilateral symmetry — center them for impact.",
    ],
    "general": [
        "Rule of Thirds: Divide the frame into a 3×3 grid and place key elements at intersection points.",
        "Leading Lines: Use natural or man-made lines to draw the viewer's eye toward the subject.",
        "Frame Within a Frame: Use doorways, branches, or other elements to enclose the subject.",
        "Symmetry: Create balance and visual harmony by centering symmetrical elements.",
        "Foreground Interest: Include elements in the foreground for depth and scale.",
        "Fill the Frame: Remove distractions by making the subject dominant in the composition.",
    ],
}


# ─── Creative Style Coaching ─────────────────────────────────────────

CREATIVE_COACHING = {
    "landscape": [
        "Golden Hour Magic: Shoot during the first and last hour of sunlight for warm, directional light.",
        "Blue Hour Drama: 20-40 minutes after sunset for deep blue tones and city/mountain contrast.",
        "Long Exposure: Use a tripod and ND filter to smooth water (2-30 seconds) or streak clouds.",
        "Panoramic Vision: Consider stitching multiple frames for ultra-wide landscape panoramas.",
        "Weather as Character: Fog, storms, and rain add mood that sunshine cannot replicate.",
    ],
    "portrait": [
        "Catchlights: Position relative to the light so a bright highlight appears in both eyes.",
        "Rim Light: Place a light behind the subject for a glowing outline that separates them from the background.",
        "Shallow DOF: Open to f/1.4–f/2.0 for dreamy, buttery bokeh that isolates the subject.",
        "Color Harmony: Use complementary colors (blue/orange, green/red) between subject and background.",
        "Emotion Over Perfection: A genuine smile or unguarded moment beats a technically perfect but lifeless pose.",
    ],
    "street": [
        "Shoot from the Hip: Pre-focus and shoot without raising the camera for unposed candid moments.",
        "Zone Focus: Set manual focus to a hyperfocal distance (2-3m) for instant capture without AF delay.",
        "Silhouettes: Expose for the bright background to turn subjects into powerful black shapes.",
        "Reflections: Use puddles, windows, and chrome surfaces for layered, dreamlike compositions.",
        "Patience: The best street shots come from finding a great background and waiting for the moment.",
    ],
    "architecture": [
        "Blue Hour: Buildings with interior lights glow against deep blue skies — the ideal contrast.",
        "Tilt-Shift: Keep verticals parallel by using lens corrections or a tilt-shift lens.",
        "Human Scale: Include a small human figure to communicate the enormous scale of architecture.",
        "Long Exposure: Blur foot traffic around a static building for a sense of time passing.",
        "Interior Light Painting: Combine ambient and manual flash for evenly lit interiors.",
    ],
    "wildlife": [
        "Patience is Everything: Wildlife photography is 95% waiting, 5% shooting. Be prepared.",
        "Burst Mode: Use high-speed continuous shooting for fast-moving subjects — pick the decisive moment later.",
        "Pre-Focus on the Perch: Find where the animal returns to and pre-focus on that exact spot.",
        "Back-Button AF: Decouple autofocus from the shutter button for precise focus control.",
        "Golden Light: Early morning and late afternoon light warms fur and feathers dramatically.",
    ],
    "general": [
        "Experiment with Perspective: Try shooting from dramatically high or low angles instead of eye level.",
        "Intentional Color Palette: Pre-visualize the colors in your frame to create cohesive images.",
        "Break the Rules: Once you know the rules (rule of thirds, etc.), deliberately break them for creative impact.",
        "Tell a Story: Every great photo answers 'what,' 'who,' and 'why' — even abstractly.",
    ],
}


# ─── Per-Image Assessment ────────────────────────────────────────────
def assess_image(
    filename: str,
    filepath: str,
    format_type: str,
    quality: QualityScore,
    exif: dict,
    enhanced_path: str = "",
    denoising_applied: bool = False,
    processing_time: float = 0.0,
) -> ImageAssessment:
    """
    Generate a complete assessment for a single image.
    Genre-aware with composition, creative style, and technical coaching.
    """
    # Detect genre from EXIF
    genre = detect_genre(exif)
    focal_mm = exif.get("FocalLengthMM", 0)
    shot_type = _get_shot_type(focal_mm)

    # Detect technical flaws
    flaws = _detect_flaws(quality, exif)

    # Generate genre-aware reasoning
    reasoning = _generate_reasoning(quality, exif, flaws, genre, shot_type)

    # Generate genre-aware coaching
    coaching = _generate_coaching(quality, exif, flaws, genre, shot_type)

    return ImageAssessment(
        filename=filename,
        filepath=filepath,
        format=format_type,
        tier=quality.tier.value,
        composite_score=quality.composite,
        sharpness_score=quality.sharpness,
        aesthetic_score=quality.aesthetic,
        exposure_score=quality.exposure,
        reasoning=reasoning,
        technical_flaws=flaws,
        coaching=coaching,
        denoising_applied=denoising_applied,
        enhanced_path=enhanced_path,
        exif=exif,
        processing_time=processing_time,
    )


# ─── Technical Flaw Detection ────────────────────────────────────────
def _detect_flaws(quality: QualityScore, exif: dict) -> list[str]:
    """
    Detect specific technical flaws from quality scores and EXIF data.
    Returns a list of flaw identifiers.
    """
    flaws = []
    iso = exif.get("ISO", 0)
    shutter = exif.get("ShutterSpeed", 0)
    focal_mm = exif.get("FocalLengthMM", 0)

    # Motion blur detection via reciprocal rule
    if quality.sharpness < 30:
        if shutter > 0 and focal_mm > 0 and shutter > (1.0 / focal_mm):
            flaws.append("motion_blur")
            flaws.append("camera_shake")
        else:
            flaws.append("soft_focus")

    elif quality.sharpness < 50:
        flaws.append("soft_focus")

    # Exposure issues
    if quality.exposure < 20:
        flaws.append("underexposed")
    elif quality.exposure < 35:
        flaws.append("slightly_underexposed")
    elif quality.exposure > 90:
        flaws.append("overexposed")
    elif quality.exposure > 80:
        flaws.append("blown_highlights")

    # High ISO noise
    if iso > 3200:
        flaws.append("high_iso_noise")
    elif iso > 1600:
        flaws.append("moderate_iso_noise")

    # Shutter speed too slow for focal length (reciprocal rule)
    if shutter > 0 and focal_mm > 0:
        min_safe_shutter = 1.0 / max(focal_mm, 50)
        if shutter > min_safe_shutter * 2:
            if "camera_shake" not in flaws:
                flaws.append("slow_shutter")

    return flaws


# ─── Reasoning Generation ────────────────────────────────────────────
def _generate_reasoning(
    quality: QualityScore, exif: dict, flaws: list, genre: str, shot_type: str,
) -> str:
    """Generate human-readable reasoning with genre context."""
    parts = []
    profile = GENRE_PROFILES.get(genre, GENRE_PROFILES["general"])
    focal_str = exif.get("FocalLength", "")

    # Genre + shot type context
    genre_name = profile["name"]
    shot_name = SHOT_TYPE_NAMES.get(shot_type, "")
    if focal_str:
        parts.append(f"[{genre_name} — {shot_name} at {focal_str}]")
    else:
        parts.append(f"[{genre_name}]")

    # Tier summary
    tier = quality.tier
    inferred_tier = Tier.from_score(quality.composite)
    sync_note = " (Synchronized with pair)" if tier.rank > inferred_tier.rank else ""

    if tier == Tier.PORTFOLIO:
        parts.append(f"Exceptional image quality{sync_note} (score: {quality.composite:.0f}/100).")
    elif tier == Tier.KEEPER:
        parts.append(f"Solid image with good potential{sync_note} (score: {quality.composite:.0f}/100).")
    elif tier == Tier.REVIEW:
        parts.append(f"Borderline quality — worth reviewing{sync_note} (score: {quality.composite:.0f}/100).")
    else:
        parts.append(f"Below quality threshold (score: {quality.composite:.0f}/100).")

    # Sharpness detail
    if quality.sharpness >= 70:
        parts.append(f"Sharp focus ({quality.sharpness:.0f}/100).")
    elif quality.sharpness >= 40:
        parts.append(f"Acceptable sharpness ({quality.sharpness:.0f}/100).")
    else:
        if genre == "landscape" and quality.sharpness >= 25:
            parts.append(f"Soft sharpness ({quality.sharpness:.0f}/100) — may be acceptable for distant landscape subjects.")
        else:
            parts.append(f"Poor sharpness ({quality.sharpness:.0f}/100) — likely motion blur or missed focus.")

    # Exposure detail — genre-aware
    if quality.exposure >= 60:
        parts.append(f"Well-exposed ({quality.exposure:.0f}/100).")
    elif quality.exposure >= 40:
        parts.append(f"Acceptable exposure ({quality.exposure:.0f}/100).")
    elif quality.exposure >= 25 and genre in ("landscape", "street", "architecture"):
        # Creative underexposure is common in these genres
        parts.append(f"Intentional low-key exposure possible ({quality.exposure:.0f}/100) — common in {genre_name.lower()} for mood.")
    else:
        if "underexposed" in flaws:
            parts.append(f"Severely underexposed ({quality.exposure:.0f}/100).")
        elif "overexposed" in flaws:
            parts.append(f"Overexposed with blown highlights ({quality.exposure:.0f}/100).")
        else:
            parts.append(f"Poor exposure ({quality.exposure:.0f}/100).")

    # Flaw summary
    if "high_iso_noise" in flaws:
        iso = exif.get("ISO", 0)
        parts.append(f"High ISO ({iso}) introduced visible noise.")
    if "camera_shake" in flaws:
        shutter_s = exif.get("Shutter", "")
        parts.append(f"Camera shake detected at {shutter_s} with {focal_str}.")

    return " ".join(parts)


# ─── Coaching Advice ──────────────────────────────────────────────────
def _generate_coaching(
    quality: QualityScore, exif: dict, flaws: list, genre: str, shot_type: str,
) -> CoachingAdvice:
    """Generate genre-aware, actionable photography coaching."""
    iso = exif.get("ISO", 0)
    shutter = exif.get("ShutterSpeed", 0)
    fnumber = exif.get("FNumber", 0)
    focal_mm = exif.get("FocalLengthMM", 0)
    shutter_str = exif.get("Shutter", "")
    aperture_str = exif.get("Aperture", "")
    focal_str = exif.get("FocalLength", "")

    profile = GENRE_PROFILES.get(genre, GENRE_PROFILES["general"])
    coaching = CoachingAdvice()

    # ── Exposure Triangle Coaching ──
    triangle_parts = []

    if "camera_shake" in flaws or "motion_blur" in flaws:
        if focal_mm > 0:
            min_shutter = f"1/{int(focal_mm)}"
            triangle_parts.append(
                f"At {focal_str}, your minimum handheld shutter speed is {min_shutter}s. "
                f"You shot at {shutter_str} which is too slow."
            )

        if fnumber > 0 and fnumber > 2.8:
            one_stop_wider = fnumber / 1.4
            triangle_parts.append(
                f"Open aperture from {aperture_str} to f/{one_stop_wider:.1f} "
                f"to double your shutter speed and eliminate the blur."
            )
        elif iso > 0 and iso < 3200:
            triangle_parts.append(
                f"Increase ISO from {iso} to {iso * 2} to double your "
                f"shutter speed while keeping aperture the same."
            )

    if "high_iso_noise" in flaws:
        if fnumber > 0 and fnumber > 2.8:
            triangle_parts.append(
                f"ISO {iso} introduced noise. At {aperture_str}, open wider to ~f/2.8 "
                f"to allow ISO {max(100, iso // 2)} with the same exposure."
            )
        elif shutter > 0 and focal_mm > 0:
            min_safe = 1.0 / max(focal_mm, 50)
            if shutter < min_safe * 0.5:
                slower_shutter = f"1/{int(1.0 / (min_safe * 1.5))}"
                triangle_parts.append(
                    f"Shutter ({shutter_str}) was faster than needed. "
                    f"Slow to {slower_shutter}s to drop ISO to {max(100, iso // 2)}."
                )

    if "underexposed" in flaws or "slightly_underexposed" in flaws:
        triangle_parts.append(
            f"Underexposed. Use +0.7 to +1.3 EV exposure compensation "
            f"in similar lighting conditions."
        )

    if "overexposed" in flaws or "blown_highlights" in flaws:
        triangle_parts.append(
            f"Highlights blown. Use -0.7 EV exposure compensation "
            f"or spot-meter on the brightest area."
        )

    coaching.exposure_triangle = " ".join(triangle_parts) if triangle_parts else ""

    # ── Genre-Aware Composition Coaching ──
    comp_techniques = COMPOSITION_TECHNIQUES.get(genre, COMPOSITION_TECHNIQUES["general"])
    comp_parts = []

    if quality.aesthetic < 40:
        # Low aesthetic — provide 2-3 specific techniques for this genre
        comp_parts.append(f"For {profile['name'].lower()} photography, focus on:")
        for tech in comp_techniques[:3]:
            comp_parts.append(f"  • {tech}")
    elif quality.aesthetic < 60:
        comp_parts.append(f"Good foundation for {profile['name'].lower()}. To elevate:")
        for tech in comp_techniques[2:5]:
            comp_parts.append(f"  • {tech}")
    elif quality.aesthetic >= 80:
        comp_parts.append(f"Strong composition for {profile['name'].lower()}.")
        # Suggest advanced technique
        if len(comp_techniques) > 4:
            comp_parts.append(f"  Advanced: {comp_techniques[-1]}")

    # Shot type awareness — prevent mismatched advice
    if genre == "landscape" and shot_type in ("wide", "extreme_wide"):
        comp_parts.append(
            "Wide-angle landscapes: Emphasize depth with foreground-midground-background layering. "
            "The wide lens excels at showing the grandeur of the scene."
        )
    elif genre == "portrait" and shot_type in ("close_up", "medium_close"):
        comp_parts.append(
            "Subject-centric: Focus on the eyes, expression, and body language. "
            "Use the background as a complementary element, not a distraction."
        )

    coaching.composition = "\n".join(comp_parts) if comp_parts else ""

    # ── Creative Style + Artistic Coaching ──
    artistic_parts = []
    creative_tips = CREATIVE_COACHING.get(genre, CREATIVE_COACHING["general"])

    # Camera angle suggestions
    if quality.composite >= 60:
        artistic_parts.append(
            "Technical quality is solid. Now experiment with creative angles:"
        )
        if genre == "portrait":
            artistic_parts.append("  • Try a low angle — shooting upward gives the subject power and authority.")
            artistic_parts.append("  • Try a high angle — shooting downward creates vulnerability and intimacy.")
        elif genre == "landscape":
            artistic_parts.append("  • Try a ground-level angle — shooting from ground height creates dramatic foreground.")
            artistic_parts.append("  • Try an elevated viewpoint — overhead or hillside for a bird's eye perspective.")
        elif genre == "street":
            artistic_parts.append("  • Try a Dutch angle (tilted camera) for dynamic tension in chaotic urban scenes.")
            artistic_parts.append("  • Try POV perspective — shoot from the subject's likely viewpoint.")
        elif genre == "architecture":
            artistic_parts.append("  • Try a low angle — shooting upward emphasizes height and power of structures.")
            artistic_parts.append("  • Find perfect bilateral symmetry for maximum visual impact.")

    # Genre-specific creative coaching
    if quality.sharpness >= 50 and quality.exposure >= 40:
        # Technically passable — focus on creative development
        artistic_parts.append(f"\n💡 Creative tips for {profile['name'].lower()}:")
        for tip in creative_tips[:2]:
            artistic_parts.append(f"  • {tip}")

    # Camera shot recommendations based on current focal length
    if focal_mm > 0:
        shot_advice = _get_shot_type_advice(genre, shot_type, focal_mm)
        if shot_advice:
            artistic_parts.append(f"\n📷 Shot type ({SHOT_TYPE_NAMES.get(shot_type, 'Unknown')}):")
            artistic_parts.append(f"  {shot_advice}")

    # Style development
    if quality.composite >= 70:
        artistic_parts.append(
            "\n🎨 Style Development: Consistent editing (tone, color palette, contrast) "
            "creates a recognizable personal style. Consider developing a signature look "
            "through consistent color grading and tonal choices."
        )

    coaching.artistic = "\n".join(artistic_parts) if artistic_parts else ""

    # ── Improvement Priority ──
    if flaws:
        primary_flaw = flaws[0]
        flaw_priority = {
            "motion_blur": "Shutter speed management — practice the reciprocal rule: minimum shutter = 1/focal_length.",
            "camera_shake": "Camera stability — faster shutter speed, image stabilization, or tripod.",
            "soft_focus": "Focus accuracy — switch to single-point AF and place it precisely on the subject's eye or key detail.",
            "underexposed": "Exposure management — learn histogram reading and use exposure compensation proactively.",
            "overexposed": "Highlight protection — expose for the highlights (ETTR) and recover shadows in post.",
            "high_iso_noise": "Noise management — 'minimum ISO' discipline: start at ISO 100, increase only when necessary.",
            "moderate_iso_noise": "Good ISO awareness — consider a faster lens (f/1.8 or f/1.4) for available-light shooting.",
            "blown_highlights": "Highlight awareness — use the camera's highlight clipping warning (zebras).",
            "slow_shutter": "Shutter speed discipline — match shutter to the reciprocal of your focal length.",
            "slightly_underexposed": "Fine-tune exposure — use +0.3 to +0.7 EV compensation for this lighting.",
        }
        coaching.improvement_priority = flaw_priority.get(
            primary_flaw,
            "Continue practicing and analyzing your results."
        )
    else:
        coaching.improvement_priority = (
            f"Technically excellent {profile['name'].lower()} work. "
            f"Focus on artistic vision, storytelling, and capturing emotion."
        )

    return coaching


def _get_shot_type_advice(genre: str, shot_type: str, focal_mm: float) -> str:
    """Genre-appropriate advice for the current camera shot type."""
    advice_map = {
        ("landscape", "extreme_wide"): (
            "Ultra-wide captures the full scene. Use strong foreground anchors "
            "(rocks, flowers, water) to avoid empty foreground syndrome."
        ),
        ("landscape", "wide"): (
            "Classic wide-angle landscape. Layer the scene: foreground interest, "
            "midground subject, background sky/mountains for maximum depth."
        ),
        ("landscape", "medium"): (
            "Normal focal length in landscape. This works for 'intimate landscapes' — "
            "isolating specific elements rather than capturing the whole scene."
        ),
        ("portrait", "medium_close"): (
            "Classic portrait focal length. The slight telephoto compression "
            "flatters facial features and creates natural background separation."
        ),
        ("portrait", "close_up"): (
            "Headshot territory. Focus on the eyes — they must be tack-sharp. "
            "Use wide aperture for creamy bokeh separation."
        ),
        ("portrait", "medium"): (
            "Environmental portrait range. Include enough background context "
            "to tell the subject's story while keeping them prominent."
        ),
        ("street", "medium"): (
            "The classic street photography focal length (35-50mm). "
            "You see roughly what the eye sees — honest, documentary framing."
        ),
        ("street", "wide"): (
            "Wide street photography. Get closer to your subject — "
            "the wide lens exaggerates the foreground for dramatic storytelling."
        ),
        ("wildlife", "extreme_close_up"): (
            "Long telephoto reach. Compressed perspective flattens the scene — "
            "use this to stack elements (subject + out-of-focus background shapes)."
        ),
        ("architecture", "extreme_wide"): (
            "Ultra-wide architecture. Watch for converging verticals — "
            "keep the camera level or correct in post for professional results."
        ),
    }

    key = (genre, shot_type)
    return advice_map.get(key, "")


# ─── Batch Report ─────────────────────────────────────────────────────
def compile_batch_report(
    assessments: list[ImageAssessment],
    processing_time: float,
) -> str:
    """
    Compile aggregate coaching summary for the entire batch.
    Returns a human-readable coaching report string.
    """
    total = len(assessments)
    if total == 0:
        return "No images processed."

    # Count tiers
    tiers = {"portfolio": 0, "keeper": 0, "review": 0, "cull": 0}
    for a in assessments:
        tiers[a.tier] = tiers.get(a.tier, 0) + 1

    keeper_rate = ((tiers["portfolio"] + tiers["keeper"]) / total) * 100

    # Count common flaws
    flaw_counts: dict[str, int] = {}
    for a in assessments:
        for flaw in a.technical_flaws:
            flaw_counts[flaw] = flaw_counts.get(flaw, 0) + 1

    # Detect dominant genre
    genre_counts: dict[str, int] = {}
    for a in assessments:
        genre = detect_genre(a.exif)
        genre_counts[genre] = genre_counts.get(genre, 0) + 1
    dominant_genre = max(genre_counts, key=genre_counts.get) if genre_counts else "general"
    genre_name = GENRE_PROFILES.get(dominant_genre, GENRE_PROFILES["general"])["name"]

    # Build report
    lines = []
    lines.append(f"📊 Batch Summary: {total} images processed in {processing_time:.1f}s")
    lines.append(f"   📸 Dominant Genre: {genre_name}")
    lines.append(f"   🏆 Portfolio: {tiers['portfolio']} | ✅ Keeper: {tiers['keeper']} | "
                 f"🔍 Review: {tiers['review']} | ❌ Cull: {tiers['cull']}")
    lines.append(f"   📈 Keeper rate: {keeper_rate:.0f}% (Pro target: 60-70%)")
    lines.append("")

    if flaw_counts:
        lines.append("🔧 Most Common Issues:")
        for flaw, count in sorted(flaw_counts.items(), key=lambda x: -x[1])[:5]:
            pct = (count / total) * 100
            flaw_friendly = flaw.replace("_", " ").title()
            lines.append(f"   • {flaw_friendly}: {count} shots ({pct:.0f}%)")

    lines.append("")

    # Genre-specific batch coaching
    lines.append(f"📐 Composition Tips for {genre_name}:")
    genre_comp = COMPOSITION_TECHNIQUES.get(dominant_genre, COMPOSITION_TECHNIQUES["general"])
    for tip in genre_comp[:3]:
        lines.append(f"   • {tip}")
    lines.append("")

    # Creative development
    lines.append(f"🎨 Creative Development for {genre_name}:")
    genre_creative = CREATIVE_COACHING.get(dominant_genre, CREATIVE_COACHING["general"])
    for tip in genre_creative[:2]:
        lines.append(f"   • {tip}")
    lines.append("")

    if keeper_rate >= 70:
        lines.append("💡 Excellent session! Your keeper rate is professional-level.")
    elif keeper_rate >= 50:
        lines.append("💡 Good session. Focus on reducing the most common flaw to push your keeper rate higher.")
    else:
        lines.append("💡 Tough session. Addressing the top recurring flaw will significantly improve results.")

    return "\n".join(lines)


def save_report_json(
    assessments: list[ImageAssessment],
    output_path: str,
    batch_coaching: str = "",
    processing_time: float = 0.0,
) -> bool:
    """Save the full batch report as a JSON file for LLM ingestion."""
    try:
        report = {
            "engine": "Antigravity v2.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "processing_time_seconds": processing_time,
            "batch_coaching": batch_coaching,
            "total_images": len(assessments),
            "assessments": [],
        }

        for a in assessments:
            genre = detect_genre(a.exif)
            focal_mm = a.exif.get("FocalLengthMM", 0)
            shot_type = _get_shot_type(focal_mm)

            report["assessments"].append({
                "filename": a.filename,
                "format": a.format,
                "tier": a.tier,
                "genre": genre,
                "shot_type": shot_type,
                "composite_score": a.composite_score,
                "scores": {
                    "sharpness": a.sharpness_score,
                    "aesthetic": a.aesthetic_score,
                    "exposure": a.exposure_score,
                },
                "reasoning": a.reasoning,
                "technical_flaws": a.technical_flaws,
                "recovery_potential": a.recovery_potential,
                "recovery_notes": a.recovery_notes,
                "coaching": {
                    "exposure_triangle": a.coaching.exposure_triangle,
                    "composition": a.coaching.composition,
                    "artistic": a.coaching.artistic,
                    "improvement_priority": a.coaching.improvement_priority,
                },
                "denoising_applied": a.denoising_applied,
                "enhanced_path": a.enhanced_path,
                "exif": a.exif,
                "processing_time": a.processing_time,
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return True

    except Exception as e:
        print(f"[ai_coach] JSON save error: {e}")
        return False


# ─── Self-Test ────────────────────────────────────────────────────────
def self_test() -> SelfTestResult:
    """Verify coaching logic produces valid output with genre detection."""
    result = SelfTestResult(module="ai_coach")

    try:
        # Test with a landscape-like EXIF (wide angle, stopped down)
        test_quality = QualityScore(
            sharpness=45.0,
            aesthetic=60.0,
            exposure=70.0,
            composite=58.0,
            tier=Tier.REVIEW,
        )
        test_exif = {
            "ISO": 200, "Shutter": "1/125", "ShutterSpeed": 1/125,
            "Aperture": "f/11", "FNumber": 11.0,
            "FocalLength": "24mm", "FocalLengthMM": 24,
        }

        assessment = assess_image(
            filename="test.jpg",
            filepath="/test/test.jpg",
            format_type="JPEG",
            quality=test_quality,
            exif=test_exif,
        )

        # Verify genre detection
        genre = detect_genre(test_exif)
        shot_type = _get_shot_type(24)

        # Verify the assessment is populated
        checks = []
        checks.append(f"Genre: {genre}")
        checks.append(f"Shot: {shot_type}")
        if assessment.reasoning:
            checks.append("Reasoning: OK")
        if assessment.coaching.composition:
            checks.append("Composition: OK")
        if assessment.coaching.improvement_priority:
            checks.append("Priority: OK")

        result.passed = bool(
            assessment.reasoning
            and assessment.coaching.improvement_priority
            and genre in GENRE_PROFILES
        )
        result.message = "AI Coach operational" if result.passed else "Coaching generation incomplete"
        result.details = " | ".join(checks)

    except Exception as e:
        result.message = f"Self-test error: {e}"

    return result


# ─── CLI Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Module 6: AI Coach — Self-Test")
    print("=" * 60)
    test = self_test()
    status = "✅ PASS" if test.passed else "❌ FAIL"
    print(f"{status} | {test.message}")
    if test.details:
        print(f"        | {test.details}")

    # Demo: test different genres
    print("\n--- Genre Detection Demo ---")
    test_cases = [
        {"FocalLengthMM": 16, "FNumber": 11.0, "expected": "landscape"},
        {"FocalLengthMM": 85, "FNumber": 1.8, "expected": "portrait"},
        {"FocalLengthMM": 35, "FNumber": 2.8, "expected": "street"},
        {"FocalLengthMM": 400, "FNumber": 5.6, "expected": "wildlife"},
        {"FocalLengthMM": 14, "FNumber": 11.0, "expected": "architecture"},
    ]
    for tc in test_cases:
        detected = detect_genre(tc)
        match = "✅" if detected == tc["expected"] else "❌"
        print(f"  {match} {tc['FocalLengthMM']}mm f/{tc['FNumber']} → {detected} (expected: {tc['expected']})")
