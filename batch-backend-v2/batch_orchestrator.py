"""
Antigravity Engine v2.0 — Module 7: Batch Orchestrator
The pipeline controller that wires all modules together.

Key Design:
- Sequential processing (one file at a time — safe, predictable)
- Per-file timing and telemetry logged to terminal
- Creates /Enhanced/ and /Rejected/ subdirectories
- Manages temp workspace lifecycle
- Calls dedup after all files are scored
- Produces structured BatchResult for the API

Usage:
    from batch_orchestrator import run_batch, run_all_self_tests
    result = run_batch("/path/to/photos")
"""
from __future__ import annotations

import os
import shutil
import time
import tempfile
from pathlib import Path

from typing import Any
from models import (
    ImageAssessment, BatchResult,
    QualityScore, Tier, TIER_CONFIG,
    IMAGE_EXTENSIONS, NEEDS_CONVERSION, get_format_type,
    SelfTestResult, ENHANCEMENT_PROFILE_MASTER, ENHANCEMENT_PROFILE_RLHF
)

# Import all modules
import preview_extractor
import quality_classifier
import raw_developer
import image_enhancer
import file_tagger
import ai_coach
import hashlib
import json
from database import SessionLocal, Media, Inference, ModelRegistry
from firebase_bridge import FirebaseBridge
from diversity_sampler import DiversitySampler


# ─── Main Batch Processing ───────────────────────────────────────────
def run_batch(
    target_folder: str,
    benchmark_folder: str | None = None,
) -> BatchResult:
    """
    Process all images in a folder through the full pipeline.
    
    Flow per file:
    1. Check if already processed (XMP sidecar exists → skip)
    2. Extract preview (zero-lock via exiftool)
    3. Extract EXIF metadata
    4. Classify quality (Laplacian + MUSIQ + histogram)
    5. Route by tier:
       - Portfolio/Keeper → develop + enhance → /Enhanced/
       - Review (sharp ≥80) → develop + enhance → /Enhanced/ (for meaningful review)
       - Cull (high recovery) → tag as Recoverable, move to /Rejected/
       - Cull (low recovery) → move to /Rejected/
    6. Tag with Finder tags + comments + XMP sidecars
    7. Generate AI coaching assessment with recovery notes
    
    After all files:
    8. Compile batch report with coaching
    """
    batch_start = time.time()

    # Validate target
    if not os.path.isdir(target_folder):
        print(f"[orchestrator] Error: folder not found: {target_folder}")
        return BatchResult()

    # Create output directories
    enhanced_dir = os.path.join(target_folder, "Enhanced")
    rejected_dir = os.path.join(target_folder, "Rejected")
    rlhf_input_dir = os.path.join(target_folder, "For RLHF input")
    workspace_dir = os.path.join(target_folder, ".antigravity_workspace")
    
    for d in [enhanced_dir, rejected_dir, rlhf_input_dir, workspace_dir]:
        os.makedirs(d, exist_ok=True)

    # Scan for images and group by stem (basename)
    # RAW+JPEG pairs (e.g., DSC001.ARW and DSC001.JPG) share the same stem.
    groups: dict[str, list[str]] = {}
    skipped = 0
    
    # First pass: collect all valid image files
    all_raw_files = sorted(os.listdir(target_folder))
    for f in all_raw_files:
        fpath = os.path.join(target_folder, f)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
            
        # Re-run safety: skip groups that already have an XMP sidecar
        stem = Path(f).stem
        xmp_path = os.path.join(target_folder, f"{stem}.xmp")
        if os.path.exists(xmp_path):
            skipped += 1
            continue
            
        if stem not in groups:
            groups[stem] = []
        groups[stem].append(f)

    # Calculate total individual files for progress tracking
    total_files = sum(len(files) for files in groups.values())
    stems = sorted(groups.keys())
    
    print(f"\n{'='*60}")
    print(f"🚀 Antigravity Engine v2.1 — Processing {len(groups)} groups ({total_files} images)")
    if skipped > 0:
        print(f"⏭️  Skipped {skipped} already-processed files (XMP exists)")
    print(f"📁 Source: {target_folder}")
    print(f"📂 Enhanced: {enhanced_dir}")
    print(f"📂 Rejected: {rejected_dir}")
    print(f"{'='*60}\n")

    # Initialize Semantic Analyst
    analyst = quality_classifier._get_vision_analyst()
    
    # Initialize DB Session
    db = SessionLocal()
    
    # Ensure Laplacian model exists in registry
    model_name = "laplacian_v2" # Using default for now
    model_record = db.query(ModelRegistry).filter(ModelRegistry.name == model_name).first()
    if not model_record:
        model_record = ModelRegistry(name=model_name, model_type="heuristics", is_production=True)
        db.add(model_record)
        db.commit()

    # Process each group
    assessments: list[ImageAssessment] = []
    result = BatchResult(total_scanned=total_files)
    processed_count = 0

    for stem_idx, stem in enumerate(stems, 1):
        group_files = groups[stem]
        group_results = []
        
        # ── Group Stage 1: Assessment ──
        # Score all files in the group to find the best quality tier
        for filename in group_files:
            file_start = time.time()
            filepath = os.path.join(target_folder, filename)
            format_type = get_format_type(filepath)
            
            try:
                exif = preview_extractor.extract_metadata(filepath)
                preview_bytes = preview_extractor.extract_preview(filepath)
                if not preview_bytes:
                    continue
                
                quality = quality_classifier.classify(preview_bytes, exif=exif)
                group_results.append({
                    "filename": filename,
                    "filepath": filepath,
                    "format_type": format_type,
                    "exif": exif,
                    "quality": quality,
                    "preview_bytes": preview_bytes,
                    "file_start": file_start
                })
            except Exception as e:
                print(f"❌ Error assessing {filename}: {e}")

        if not group_results:
            continue

        # ── Group Stage 2: Reconciliation ──
        # Find the max tier achieved in the group
        max_tier = Tier.CULL
        for res in group_results:
            if res["quality"].tier.rank > max_tier.rank:
                max_tier = res["quality"].tier
        
        # Determine if we have a RAW file to use as the master for enhancement
        raw_master = next((res for res in group_results if res["format_type"] == "RAW"), None)
        # If the max tier is high enough, we'll enhance the best available source
        should_enhance = max_tier.rank >= Tier.KEEPER.rank or (max_tier == Tier.REVIEW and any(r["quality"].sharpness >= 80 for r in group_results))
        
        # ── Group Stage 3: Execution ──
        # Apply the reconciled tier to all files in the group
        for res in group_results:
            processed_count += 1
            filename = res["filename"]
            filepath = res["filepath"]
            format_type = res["format_type"]
            quality = res["quality"]
            exif = res["exif"]
            
            # Sync tier
            original_tier = quality.tier
            quality.tier = max_tier
            
            # Message for terminal
            elevation_msg = ""
            if original_tier != max_tier:
                elevation_msg = f" (↑ {max_tier.value})"
            
            print(f"[{processed_count}/{total_files}] {filename} ({format_type})", end=" → ", flush=True)

            try:
                recovery_notes = _build_recovery_notes(quality, exif)
                enhanced_path = ""
                tag_filepath = filepath
                
                # MLOps: Hash the file to track it immutably
                file_hash = hashlib.sha256(f"{filename}_{os.path.getsize(filepath)}".encode()).hexdigest()
                
                # Check absolute paths to insert/update Media record
                media_record = db.query(Media).filter(Media.photo_hash == file_hash).first()
                if not media_record:
                    media_record = Media(
                        photo_hash=file_hash,
                        file_path=filepath,
                        format=format_type,
                        file_size=os.path.getsize(filepath),
                        width=exif.get("ImageWidth"),
                        height=exif.get("ImageLength")
                    )
                    db.add(media_record)
                    db.commit() # Commit to get ID
                
                # Route based on reconciled tier (NO MOVING FILES)
                if max_tier == Tier.CULL:
                    result.culled += 1
                    if quality.recovery_potential in ("high", "medium"):
                        result.recoverable += 1
                else:                     
                    # Keeper / Portfolio / Enhanced Review
                    if max_tier == Tier.REVIEW:
                        result.review += 1
                    else:
                        if max_tier == Tier.PORTFOLIO: result.portfolio += 1
                        else: result.keepers += 1
                    
                    # RLHF Stream: Review / Keeper / Portfolio
                    # We always generate a 90% RLHF version for these tiers
                    is_best_source = (raw_master and res == raw_master) or (not raw_master)
                    if is_best_source:
                        # 1. RLHF Version (90% quality, capped size)
                        rlhf_name = f"{stem}_rlhf.jpg"
                        rlhf_path = os.path.join(rlhf_input_dir, rlhf_name)
                        _enhance_file(
                            filepath, filename, format_type, exif.get("ISO", 0),
                            rlhf_path, workspace_dir, result, ENHANCEMENT_PROFILE_RLHF
                        )
                        
                        # 2. Master Version (100% quality)
                        enhanced_name = f"{stem}_master.jpg"
                        enhanced_path = os.path.join(enhanced_dir, enhanced_name)
                        _enhance_file(
                            filepath, filename, format_type, exif.get("ISO", 0),
                            enhanced_path, workspace_dir, result, ENHANCEMENT_PROFILE_MASTER
                        )
                        
                        media_record.enhanced_path = enhanced_path
                        db.commit()
                        
                # Log Inference to Database
                inference = Inference(
                    media_id=media_record.id,
                    model_id=model_record.id,
                    inference_value=json.dumps({
                        "tier": max_tier.value,
                        "composite": quality.composite,
                        "sharpness": quality.sharpness,
                        "aesthetic": quality.aesthetic,
                        "exposure": quality.exposure,
                        "recovery_potential": quality.recovery_potential
                    }),
                    confidence=1.0,
                    processing_time_ms=quality.processing_time * 1000
                )
                db.add(inference)
                db.commit()

                # Tagging (using reconciled tier but individual scores)
                file_tagger.tag_photo(
                    tag_filepath, max_tier,
                    score=quality.composite,
                    sharpness=quality.sharpness,
                    aesthetic=quality.aesthetic,
                    exposure=quality.exposure,
                    reasoning=f"Group Reconciled: {max_tier.value}{elevation_msg}",
                    recovery_potential=quality.recovery_potential,
                    recovery_notes=recovery_notes,
                )

                # AI Coach Assessment
                file_time = time.time() - res["file_start"]
                denoising_applied = exif.get("ISO", 0) > 1600 and enhanced_path != ""
                if denoising_applied: result.denoised += 1

                assessment = ai_coach.assess_image(
                    filename=filename,
                    filepath=filepath,
                    format_type=format_type,
                    quality=quality,
                    exif=exif,
                    enhanced_path=enhanced_path,
                    denoising_applied=denoising_applied,
                    processing_time=file_time,
                )
                assessment.recovery_potential = quality.recovery_potential
                assessment.recovery_notes = recovery_notes
                assessments.append(assessment)

                # Terminal Telemetry
                tier_emoji = {"portfolio": "🏆", "keeper": "✅", "review": "🔍", "cull": "❌"}
                emoji = tier_emoji.get(max_tier.value, "?")
                recovery_tag = ""
                if quality.recovery_potential:
                    recovery_tag = f" 🔧{quality.recovery_potential.upper()}"
                
                print(f"{emoji} {max_tier.value.upper()}{elevation_msg} "
                      f"(Score: {quality.composite:.0f} | "
                      f"Sharp: {quality.sharpness:.0f} | "
                      f"Aesth: {quality.aesthetic:.0f} | "
                      f"Expo: {quality.exposure:.0f})"
                      f"{recovery_tag} "
                      f"[{file_time:.1f}s]")

            except Exception as e:
                print(f"❌ ERROR: {e}")
                import traceback
                traceback.print_exc()

    # ── Stage 7: Compile Reports ──
    batch_time = time.time() - batch_start
    result.processing_time = round(batch_time, 1)
    result.files = assessments

    batch_coaching = ai_coach.compile_batch_report(assessments, batch_time)
    result.batch_coaching = batch_coaching

    # Save JSON report
    report_path = os.path.join(target_folder, "batch_report.json")
    ai_coach.save_report_json(assessments, report_path, batch_coaching, batch_time)

    # ── Stage 8: RLHF Curation & Firebase Injection ──
    sampler = DiversitySampler(target_batch_size=50)
    rlhf_batch = sampler.curate_rlhf_batch(assessments)
    
    if rlhf_batch:
        # Note: service account path and bucket are hardcoded here for simplicity, 
        # but should ideally come from env/config.
        bridge = FirebaseBridge(
            "firebase-service-account.json", 
            "style-matcher-9480d.firebasestorage.app"
        )
        if bridge.initialize():
            # Update assessments with rlhf_url
            for a in rlhf_batch:
                rlhf_file_path = os.path.join(rlhf_input_dir, f"{Path(a.filename).stem}_rlhf.jpg")
                a.enhanced_path = rlhf_file_path # Temporary mapping for upload
            
            bridge.upload_rlhf_batch(f"batch_{int(time.time())}", rlhf_batch)

    # Clean up workspace
    try:
        shutil.rmtree(workspace_dir, ignore_errors=True)
    except:
        pass

    # Print summary
    print(f"\n{'='*60}")
    print(batch_coaching)
    print(f"{'='*60}")
    print(f"📄 Full report: {report_path}")
    print(f"📂 Enhanced files: {enhanced_dir}")
    if result.culled > 0:
        print(f"📂 Rejected files: {rejected_dir}")
    if result.recoverable > 0:
        print(f"🔧 Recoverable in /Rejected/: {result.recoverable} (sharp but under/overexposed)")

    return result


def _enhance_file(
    filepath: str, filename: str, format_type: str, iso: int,
    enhanced_path: str, workspace_dir: str, result: BatchResult,
    profile: Any = None
) -> str:
    """
    Develop + enhance a single file to a specific output path.
    """
    stem = os.path.splitext(filename)[0]
    
    if profile is None:
        from models import EnhancementProfile
        profile = EnhancementProfile()

    if format_type == "RAW":
        # RAW: develop first, then enhance
        developed_path = os.path.join(workspace_dir, f"{stem}_dev.jpg")
        dev_ok = raw_developer.develop(filepath, developed_path)
        if dev_ok:
            enh_ok = image_enhancer.enhance(developed_path, enhanced_path, iso=iso)
            if enh_ok:
                result.enhanced += 1
            else:
                shutil.copy2(developed_path, enhanced_path)
                result.enhanced += 1
            # Clean up intermediate
            if os.path.exists(developed_path):
                os.unlink(developed_path)
            return enhanced_path
    else:
        # JPEG/PNG/HEIC/TIFF: enhance directly
        enh_ok = image_enhancer.enhance(filepath, enhanced_path, iso=iso)
        if enh_ok:
            result.enhanced += 1
            return enhanced_path

    return ""


def _build_recovery_notes(quality: QualityScore, exif: dict) -> str:
    """
    Generate human-readable recovery notes for photos with recovery potential.
    Tells the photographer exactly what adjustments could rescue this shot.
    """
    if not quality.recovery_potential:
        return ""

    notes = []
    
    # Exposure recovery suggestions
    if quality.exposure < 40:
        if quality.exposure < 20:
            notes.append("Heavily underexposed — lift shadows +60, increase exposure +1.5 stops")
        else:
            notes.append("Underexposed — lift shadows +30, increase exposure +0.7 stops")
    elif quality.exposure > 85:
        notes.append("Overexposed — recover highlights, reduce exposure -0.5 stops")

    # Aesthetic improvement suggestions
    if quality.aesthetic < 40:
        notes.append("Boost contrast +15, apply split toning for mood")
    elif quality.aesthetic < 55:
        notes.append("Try creative color grading, slight contrast boost")

    # ISO/noise consideration
    iso = exif.get("ISO", 0)
    if iso and iso > 3200:
        notes.append(f"High ISO ({iso}) — apply luminance noise reduction")
    elif iso and iso > 1600:
        notes.append(f"Moderate ISO ({iso}) — light noise reduction recommended")

    # Sharpness note
    if quality.sharpness >= 60:
        notes.append(f"Good sharpness ({quality.sharpness:.0f}) — worth recovering")
    elif quality.sharpness >= 40:
        notes.append(f"Moderate sharpness ({quality.sharpness:.0f}) — sharpen in post")

    return "; ".join(notes) if notes else ""


# ─── Scan-Only Mode ──────────────────────────────────────────────────
def scan_only(target_folder: str) -> BatchResult:
    """
    Score all images WITHOUT modifying anything.
    No files moved, no XMPs created, no enhancements.
    Returns results with per-file tier assignments.
    
    Use this to preview what the engine would do, then cherry-pick
    files for a full enhancement run.
    """
    batch_start = time.time()

    if not os.path.isdir(target_folder):
        print(f"[orchestrator] Error: folder not found: {target_folder}")
        return BatchResult()

    # Scan for images and group by stem (basename)
    groups: dict[str, list[str]] = {}
    valid_files = sorted(os.listdir(target_folder))
    for f in valid_files:
        if os.path.isfile(os.path.join(target_folder, f)) and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
            stem = Path(f).stem
            if stem not in groups:
                groups[stem] = []
            groups[stem].append(f)

    total_files = sum(len(files) for files in groups.values())
    stems = sorted(groups.keys())

    print(f"\n{'='*60}")
    print(f"🔍 Antigravity Engine v2.1 — SCAN ONLY ({len(groups)} groups, {total_files} images)")
    print(f"📁 Source: {target_folder}")
    print(f"   ⚠️  Read-only mode: NO files moved, NO XMP, NO enhancement")
    print(f"{'='*60}\n")

    assessments: list[ImageAssessment] = []
    result = BatchResult(total_scanned=total_files)

    # Tier buckets for the summary
    portfolio_files = []
    keeper_files = []
    review_files = []
    cull_files = []
    recoverable_files = []

    processed_count = 0
    for stem_idx, stem in enumerate(stems, 1):
        group_files = groups[stem]
        group_results = []
        
        # ── Group Stage 1: Assessment ──
        for filename in group_files:
            file_start = time.time()
            filepath = os.path.join(target_folder, filename)
            format_type = get_format_type(filepath)
            
            try:
                exif = preview_extractor.extract_metadata(filepath)
                preview_bytes = preview_extractor.extract_preview(filepath)
                if not preview_bytes:
                    continue
                
                quality = quality_classifier.classify(preview_bytes, exif=exif)
                group_results.append({
                    "filename": filename,
                    "filepath": filepath,
                    "format_type": format_type,
                    "exif": exif,
                    "quality": quality,
                    "file_start": file_start
                })
            except Exception as e:
                print(f"❌ Error scanning {filename}: {e}")

        if not group_results:
            continue

        # ── Group Stage 2: Reconciliation ──
        max_tier = Tier.CULL
        for res in group_results:
            if res["quality"].tier.rank > max_tier.rank:
                max_tier = res["quality"].tier
        
        # ── Group Stage 3: Reporting ──
        for res in group_results:
            processed_count += 1
            filename = res["filename"]
            filepath = res["filepath"]
            format_type = res["format_type"]
            quality = res["quality"]
            exif = res["exif"]
            
            # Sync tier
            original_tier = quality.tier
            quality.tier = max_tier
            
            elevation_msg = ""
            if original_tier != max_tier:
                elevation_msg = f" (↑ {max_tier.value})"

            print(f"[{processed_count}/{total_files}] {filename} ({format_type})", end=" → ", flush=True)

            try:
                recovery_notes = _build_recovery_notes(quality, exif)
                file_time = time.time() - res["file_start"]

                # Track tier counts and buckets
                if max_tier == Tier.PORTFOLIO:
                    result.portfolio += 1
                    portfolio_files.append(filename)
                elif max_tier == Tier.KEEPER:
                    result.keepers += 1
                    keeper_files.append(filename)
                elif max_tier == Tier.REVIEW:
                    result.review += 1
                    review_files.append(filename)
                else:
                    result.culled += 1
                    cull_files.append(filename)
                
                if quality.recovery_potential in ("high", "medium"):
                    result.recoverable += 1
                    recoverable_files.append(filename)

                # Generate assessment
                assessment = ai_coach.assess_image(
                    filename=filename,
                    filepath=filepath,
                    format_type=format_type,
                    quality=quality,
                    exif=exif,
                    processing_time=file_time,
                )
                assessment.recovery_potential = quality.recovery_potential
                assessment.recovery_notes = recovery_notes
                assessments.append(assessment)

                # Terminal telemetry
                tier_emoji = {"portfolio": "🏆", "keeper": "✅", "review": "🔍", "cull": "❌"}
                emoji = tier_emoji.get(max_tier.value, "?")
                recovery_tag = ""
                if quality.recovery_potential:
                    recovery_tag = f" 🔧{quality.recovery_potential.upper()}"
                
                print(f"{emoji} {max_tier.value.upper()}{elevation_msg} "
                      f"(Score: {quality.composite:.0f} | "
                      f"Sharp: {quality.sharpness:.0f} | "
                      f"Aesth: {quality.aesthetic:.0f} | "
                      f"Expo: {quality.exposure:.0f})"
                      f"{recovery_tag} "
                      f"[{file_time:.1f}s]")

            except Exception as e:
                print(f"❌ ERROR: {e}")

    # Compile results
    batch_time = time.time() - batch_start
    result.processing_time = round(batch_time, 1)
    result.files = assessments
    result.batch_coaching = ai_coach.compile_batch_report(assessments, batch_time)

    # Print tidy file listing per tier
    print(f"\n{'='*60}")
    print(f"📋 SCAN RESULTS — File Summary")
    print(f"{'='*60}")
    print(result.batch_coaching)
    print(f"{'='*60}")

    if portfolio_files:
        print(f"\n🏆 PORTFOLIO ({len(portfolio_files)}) — Best shots, ready for enhancement:")
        for f in portfolio_files:
            print(f"   {f}")

    if keeper_files:
        print(f"\n✅ KEEPER ({len(keeper_files)}) — Solid shots, enhance these:")
        for f in keeper_files:
            print(f"   {f}")

    if recoverable_files:
        print(f"\n🔧 RECOVERABLE ({len(recoverable_files)}) — Salvageable shots (lift shadows/exposure):")
        for f in recoverable_files:
            print(f"   {f}")

    if review_files:
        print(f"\n🔍 REVIEW ({len(review_files)}) — Worth a second look:")
        for f in review_files:
            print(f"   {f}")

    if cull_files:
        non_recoverable = [f for f in cull_files if f not in recoverable_files]
        print(f"\n❌ CULL ({len(cull_files)}) — Below threshold:")
        for f in non_recoverable:
            print(f"   {f}")

    print(f"\n{'='*60}")
    print(result.batch_coaching)
    print(f"{'='*60}")
    print(f"\n⏱️  Scan completed in {batch_time:.1f}s")
    print(f"\n💡 To enhance: move the files you want into a folder and run the full batch on it.")

    return result


# ─── Self-Tests ──────────────────────────────────────────────────────
def run_all_self_tests() -> dict[str, SelfTestResult]:
    """Run self-tests for all modules. Returns dict of results."""
    modules = {
        "preview_extractor": preview_extractor.self_test,
        "quality_classifier": quality_classifier.self_test,
        "raw_developer": raw_developer.self_test,
        "image_enhancer": image_enhancer.self_test,
        "file_tagger": file_tagger.self_test,
        "ai_coach": ai_coach.self_test,
    }

    results = {}
    all_passed = True

    print(f"\n{'='*60}")
    print("🔍 Antigravity Engine v2.0 — Module Self-Tests")
    print(f"{'='*60}")

    for name, test_fn in modules.items():
        try:
            test_result = test_fn()
        except Exception as e:
            test_result = SelfTestResult(
                module=name, passed=False, message=f"Test crashed: {e}"
            )

        results[name] = test_result
        status = "✅ PASS" if test_result.passed else "❌ FAIL"
        print(f"  {status} | {name}: {test_result.message}")
        if test_result.details:
            print(f"         | {test_result.details}")

        if not test_result.passed:
            all_passed = False

    print(f"{'='*60}")
    if all_passed:
        print("✅ Engine v2.0 Ready — All 6 modules operational")
    else:
        failed = [n for n, r in results.items() if not r.passed]
        print(f"⚠️  Engine partially ready — {len(failed)} module(s) need attention: {', '.join(failed)}")
    print(f"{'='*60}\n")

    return results


# ─── CLI Test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Run batch on provided folder
        folder = sys.argv[1]
        print(f"Running batch on: {folder}")
        run_all_self_tests()
        result = run_batch(folder)
    else:
        # Just run self-tests
        run_all_self_tests()
