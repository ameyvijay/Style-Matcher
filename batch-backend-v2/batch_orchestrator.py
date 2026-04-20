"""
Antigravity Engine v2.1 — Module 7: Batch Orchestrator
The pipeline controller that wires all modules together with real-time streaming.

Key Design:
- 8-Stage Sequential Pipeline (RAW development, AI scoring, Tier reconciliation)
- Real-time SSE Streaming (Generator yields JSON events)
- Atomic Rollback Protocol (Session-based file/DB cleanup)
- Diversity Sampling & Firebase Integration
"""
from __future__ import annotations

import os
import shutil
import time
import json
import hashlib
import random
from pathlib import Path
from typing import Any, Generator, Set

# Import models & constants
from models import (
    ImageAssessment, BatchResult,
    QualityScore, Tier, TIER_CONFIG,
    IMAGE_EXTENSIONS, get_format_type,
    SelfTestResult, ENHANCEMENT_PROFILE_MASTER, ENHANCEMENT_PROFILE_RLHF
)

# Import engine modules
import preview_extractor
import quality_classifier
import raw_developer
import image_enhancer
import file_tagger
import ai_coach
from database import SessionLocal, Media, Inference, ModelRegistry
from firebase_bridge import FirebaseBridge
from diversity_sampler import DiversitySampler
from clip_embedder import ClipEmbedder
from vector_store import ChromaManager
from preference_engine import SemanticRAG
from prompt_registry import PromptRegistry, build_prompt_context, LATEST_VERSION

# ─── Global State ──────────────────────────────────────────────────
# Thread-safe registry for active sessions that should be aborted
ABORT_REGISTRY: Set[str] = set()

def _yield_log(message: str, type: str = "sys", data: Any = None) -> str:
    """Helper to format SSE log events."""
    return json.dumps({
        "timestamp": time.time(),
        "type": type,
        "message": message,
        "data": data
    }) + "\n"

# ─── Main Batch Processing (Streaming Generator) ───────────────────
def stream_batch(
    target_folder: str,
    benchmark_folder: str | None = None,
    session_id: str = "default"
) -> Generator[str, None, None]:
    """
    Executes the full 8-stage pipeline and yields real-time progress events.
    Supports atomic rollback if aborted via ABORT_REGISTRY.
    """
    yield _yield_log(f"Initializing Antigravity Kernel (Session: {session_id})", "sys")
    print(f"\n🚀 Antigravity Engine v2.1 — Kernel Active (Session: {session_id})")

    batch_start = time.time()
    session_files: list[str] = []      # Track created files for rollback
    session_db_ids: list[int] = []     # Track Media IDs for rollback
    inference_db_ids: list[int] = []   # Track Inference IDs for rollback
    
    try:
        db = SessionLocal()
        # --- Stage 0: Initialization ---
        
        if not os.path.isdir(target_folder):
            print(f"❌ Error: folder not found: {target_folder}")
            yield _yield_log(f"Error: folder not found: {target_folder}", "error")
            return

        # Create output directories
        enhanced_dir = os.path.join(target_folder, "Enhanced")
        rejected_dir = os.path.join(target_folder, "Rejected")
        rlhf_input_dir = os.path.join(target_folder, "For RLHF input")
        workspace_dir = os.path.join(target_folder, ".antigravity_workspace")
        
        for d in [workspace_dir]:
            os.makedirs(d, exist_ok=True)

        # Scan for images
        yield _yield_log("Scanning filesystem for RAW/JPEG groups...", "sys")
        groups: dict[str, list[str]] = {}
        all_files = sorted(os.listdir(target_folder))
        for f in all_files:
            fpath = os.path.join(target_folder, f)
            if os.path.isfile(fpath) and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                stem = Path(f).stem
                if stem not in groups: groups[stem] = []
                groups[stem].append(f)

        total_files = sum(len(files) for files in groups.values())
        stems = sorted(groups.keys())
        processed_count = 0
        
        print(f"📁 Source: {target_folder}")
        print(f"🔍 Found {len(stems)} groups ({total_files} files) to process.")
        yield _yield_log(f"Found {len(stems)} groups ({total_files} files) to process.", "sys")

        # Prep Model Registry
        model_record = db.query(ModelRegistry).filter(ModelRegistry.name == "laplacian_v2").first()
        if not model_record:
            model_record = ModelRegistry(name="laplacian_v2", model_type="heuristics", is_production=True)
            db.add(model_record)
            db.commit()

        print("="*60)

        # ── Phase C/E: Lazy-init CLIP Embedder, Vector Store & RAG ──
        clip_embedder: ClipEmbedder | None = None
        chroma_mgr: ChromaManager | None = None
        semantic_rag: SemanticRAG | None = None

        assessments: list[ImageAssessment] = []
        result = BatchResult(total_scanned=total_files)

        # Buckets for summary
        tier_buckets = {"portfolio": 0, "keeper": 0, "review": 0, "culled": 0, "recoverable": 0}

        # --- Main Pipeline Loop ---
        for stem_idx, stem in enumerate(stems, 1):
            # 🛑 Check for Abort Request
            if session_id in ABORT_REGISTRY:
                yield _yield_log("🚨 ABORT SIGNAL RECEIVED. Initiating Atomic Rollback...", "warn")
                break

            group_files = groups[stem]
            group_results = []
            
            # --- Stage 1 & 2: Assessment & Reconciliation ---
            for filename in group_files:
                filepath = os.path.join(target_folder, filename)
                try:
                    exif = preview_extractor.extract_metadata(filepath)
                    preview_bytes = preview_extractor.extract_preview(filepath)
                    if not preview_bytes: continue

                    # ── Phase E: Pre-classification RAG embedding ──────────
                    # Generate the CLIP embedding before calling the classifier
                    # so the SemanticRAG score can inform the 70/30 composite.
                    rag_similarity: float | None = None
                    pre_embedding: list[float] | None = None
                    try:
                        if clip_embedder is None:
                            clip_embedder = ClipEmbedder()
                            chroma_mgr = ChromaManager()
                            semantic_rag = SemanticRAG(chroma_mgr)
                        # Embed from bytes written to a temp file
                        import tempfile as _tf
                        _tmp = _tf.mktemp(suffix=".jpg")
                        try:
                            with open(_tmp, "wb") as _fh:
                                _fh.write(preview_bytes)
                            pre_embedding = clip_embedder.generate_embedding(_tmp)
                        finally:
                            if os.path.exists(_tmp):
                                os.unlink(_tmp)
                        rag_ctx = semantic_rag.get_few_shot_context(pre_embedding)
                        rag_similarity = rag_ctx["similarity_score"]
                    except Exception as _rag_err:
                        yield _yield_log(
                            f"⚠️ RAG pre-embedding skipped for {filename}: {_rag_err}",
                            "warn",
                        )

                    # Pass RAG score into classifier so it drives the 70/30 composite
                    quality = quality_classifier.classify_with_analyst(
                        preview_bytes,
                        analyst=None,
                        exif=exif,
                        rag_similarity_score=rag_similarity,
                    )
                    group_results.append({
                        "filename": filename, "filepath": filepath,
                        "exif": exif, "quality": quality, "start": time.time(),
                        "format_type": get_format_type(filepath),
                        "pre_embedding": pre_embedding,   # Reused in Phase C block below
                        "rag_context": rag_ctx if rag_similarity is not None else None,  # Phase F: full RAG context
                    })
                except Exception as e:
                    yield _yield_log(f"❌ Error assessing {filename}: {str(e)}", "error")

            if not group_results: continue

            # Reconciliation: ensure group shares the same tier
            max_tier = Tier.CULL
            for res in group_results:
                if res["quality"].tier.rank > max_tier.rank:
                    max_tier = res["quality"].tier
            
            raw_master = next((res for res in group_results if res["format_type"] == "RAW"), None)

            # --- Stage 3-6: Execution (Enhancement & Tagging) ---
            for res in group_results:
                processed_count += 1
                filename, filepath = res["filename"], res["filepath"]
                quality, exif = res["quality"], res["exif"]
                quality.tier = max_tier
                
                yield _yield_log(f"Processing image {processed_count}/{total_files}: {filename}", "progress", {
                    "tier": max_tier.value,
                    "sharpness": round(quality.sharpness, 1),
                    "aesthetic": round(quality.aesthetic, 1)
                })
                print(f"[{processed_count}/{total_files}] {filename} ({res['format_type']}) → {max_tier.value.upper()} ", end="", flush=True)

                try:
                    # MLOps: Hash & DB
                    file_hash = hashlib.sha256(f"{filename}_{os.path.getsize(filepath)}".encode()).hexdigest()
                    media = db.query(Media).filter(Media.photo_hash == file_hash).first()
                    if not media:
                        media = Media(photo_hash=file_hash, file_path=filepath, format=res["format_type"])
                        db.add(media)
                        db.commit()
                    session_db_ids.append(media.id)

                    # Tier Routing
                    enhanced_path = ""
                    rlhf_path = ""
                    recovery_notes = _build_recovery_notes(quality, exif)
                    
                    if max_tier == Tier.CULL:
                        result.culled += 1
                        tier_buckets["culled"] += 1
                        if quality.recovery_potential in ("high", "medium"):
                            result.recoverable += 1
                            tier_buckets["recoverable"] += 1
                        
                        # Even for Culls, we need a proxy for the 'Second Chance' bin
                        rlhf_path = os.path.join(rlhf_input_dir, f"{stem}_rlhf.jpg")
                        _enhance_file(filepath, filename, res["format_type"], exif.get("ISO", 0), rlhf_path, workspace_dir, result, ENHANCEMENT_PROFILE_RLHF)
                        session_files.append(rlhf_path)
                    else:
                        if max_tier == Tier.REVIEW:
                            result.review += 1
                            tier_buckets["review"] += 1
                        else:
                            if max_tier == Tier.PORTFOLIO:
                                result.portfolio += 1
                                tier_buckets["portfolio"] += 1
                            else:
                                result.keepers += 1
                                tier_buckets["keeper"] += 1
                        
                        # 1. RLHF Proxy (Global for all cloud-bound photos)
                        rlhf_path = os.path.join(rlhf_input_dir, f"{stem}_rlhf.jpg")
                        _enhance_file(filepath, filename, res["format_type"], exif.get("ISO", 0), rlhf_path, workspace_dir, result, ENHANCEMENT_PROFILE_RLHF)
                        session_files.append(rlhf_path)

                        # 2. Master & High-Res Enhancement
                        is_master = (raw_master and res == raw_master) or (not raw_master)
                        if is_master:
                            enhanced_path = os.path.join(enhanced_dir, f"{stem}_master.jpg")
                            _enhance_file(filepath, filename, res["format_type"], exif.get("ISO", 0), enhanced_path, workspace_dir, result, ENHANCEMENT_PROFILE_MASTER)
                            session_files.append(enhanced_path)
                            media.enhanced_path = enhanced_path
                            db.commit()

                    # ── Phase C: CLIP Embedding Persistence ───────────
                    # Re-use the pre_embedding generated in the RAG step above
                    # (already computed from the preview bytes).  If for any
                    # reason it is missing, fall back to the RLHF proxy path.
                    embedding_json = None
                    try:
                        if clip_embedder is None:
                            clip_embedder = ClipEmbedder()
                            chroma_mgr = ChromaManager()
                            semantic_rag = SemanticRAG(chroma_mgr)
                        embedding_vec = res.get("pre_embedding")
                        if embedding_vec is None:
                            embed_source = rlhf_path if rlhf_path and os.path.isfile(rlhf_path) else filepath
                            embedding_vec = clip_embedder.generate_embedding(embed_source)
                        embedding_json = json.dumps(embedding_vec)
                    except Exception as emb_err:
                        yield _yield_log(f"⚠️ CLIP embedding skipped for {filename}: {emb_err}", "warn")

                    # ── Phase F: Prompt Context & Traceability ─────────
                    # Build prompt context from RAG payload BEFORE the DB
                    # write so _prompt_version and _semantic_desc are
                    # available for the Inference record.
                    _rag_ctx = res.get("rag_context")
                    _prompt_version = LATEST_VERSION
                    _semantic_desc = ""
                    try:
                        from models import detect_genre as _dg
                        _genre = _dg(exif)
                        _p_ctx = build_prompt_context(_rag_ctx, genre=_genre)
                        _prompt_version = LATEST_VERSION
                        if _rag_ctx and _rag_ctx.get("exemplars"):
                            _semantic_desc = (
                                f"RAG-enriched assessment (v{_prompt_version}): "
                                f"similarity={_rag_ctx.get('similarity_score', 0):.1f}, "
                                f"exemplars={len(_rag_ctx['exemplars'])}"
                            )
                    except Exception as _pf_err:
                        yield _yield_log(
                            f"⚠️ Prompt context build skipped for {filename}: {_pf_err}",
                            "warn",
                        )

                    # Enrich the QualityScore with prompt metadata
                    quality.semantic_description = _semantic_desc or quality.semantic_description

                    # Database Inference — Phase F: include prompt_version + semantic_description
                    inf = Inference(
                        media_id=media.id, model_id=model_record.id,
                        inference_value=json.dumps({
                            "tier": max_tier.value,
                            "sharp": quality.sharpness,
                            "aes": quality.aesthetic,
                            "prompt_version": _prompt_version,
                            "semantic_description": _semantic_desc,
                        }),
                        embedding_blob=embedding_json,
                        confidence=1.0, processing_time_ms=(time.time()-res["start"])*1000
                    )
                    db.add(inf)
                    db.commit()
                    inference_db_ids.append(inf.id)

                    # External Metadata (XMP)
                    xmp_path = os.path.join(target_folder, f"{stem}.xmp")
                    file_tagger.tag_photo(filepath, max_tier, score=quality.composite, sharpness=quality.sharpness, aesthetic=quality.aesthetic, exposure=quality.exposure, reasoning=f"SSE Session: {session_id}", recovery_potential=quality.recovery_potential, recovery_notes=recovery_notes)
                    session_files.append(xmp_path)

                    # AI Coach — Phase F: pass full rag_context for prompt-versioned assessment
                    denoise = exif.get("ISO", 0) > 1600 and rlhf_path != ""
                    if denoise: result.denoised += 1

                    assessment = ai_coach.assess_image(
                        filename, filepath, res["format_type"], quality, exif,
                        enhanced_path, rlhf_path, denoise, (time.time()-res["start"]),
                    )
                    assessment.recovery_potential = quality.recovery_potential
                    assessment.recovery_notes = recovery_notes
                    assessment.prompt_version = _prompt_version  # Phase F traceability
                    assessments.append(assessment)
                    print(f"[{quality.composite:.0f}%] ✅")

                except Exception as e:
                    print(f"❌ ERROR: {e}")
                    yield _yield_log(f"⚠️ Internal error processing {filename}: {str(e)}", "error")


        # --- Stage 7: Compilation & Completion ---
        if session_id in ABORT_REGISTRY:
            # 🧨 ROLLBACK SEQUENCE
            yield _yield_log("Rolling back partial files...", "revert")
            for f in session_files:
                if os.path.exists(f): os.unlink(f)
                yield _yield_log(f"Deleted: {os.path.basename(f)}", "revert")
            
            yield _yield_log("Pruring pending database records...", "revert")
            db.query(Inference).filter(Inference.id.in_(inference_db_ids)).delete(synchronize_session=False)
            db.query(Media).filter(Media.id.in_(session_db_ids), Media.enhanced_path == None).delete(synchronize_session=False)
            db.commit()
            
            yield _yield_log("Rollback Complete. Session Terminated Safely.", "warn")
            ABORT_REGISTRY.remove(session_id)
        else:
            # NORMAL COMPLETION
            batch_time = time.time() - batch_start
            result.processing_time = round(batch_time, 1)
            result.files = assessments
            
            yield _yield_log("Compiling AI Coaching Batch Report...", "sys")
            coaching = ai_coach.compile_batch_report(assessments, batch_time)
            result.batch_coaching = coaching
            
            # Mandate 4: Doppler Manifest Generation
            yield _yield_log("Generating fatigue-optimized Doppler manifest...", "sys")
            
            # Use ImageAssessment objects for the manifest to preserve metadata (scores, tiers)
            portfolio = [a for a in assessments if a.tier == Tier.PORTFOLIO.value]
            amber = [a for a in assessments if a.tier in [Tier.KEEPER.value, Tier.REVIEW.value]]
            cull = [a for a in assessments if a.tier == Tier.CULL.value]
            
            manifest_dir = os.path.dirname(__file__)
            manifest_path, manifest_data = generate_doppler_manifest(portfolio, amber, cull, manifest_dir)
            yield _yield_log(f"Local Doppler manifest live at /api/batch-queue", "sys")

            # ─── Cloud Plane Handshake (GA Hybrid-Cloud) ──────────────────
            yield _yield_log("⚓ Initiating Cloud Plane Handshake...", "sys")
            
            # Use absolute path to resolve service account correctly regardless of CWD
            service_account = "/Users/shivamagent/Desktop/Style-Matcher/batch-backend-v2/firebase-service-account.json"
            bridge = FirebaseBridge(service_account, "style-matcher-9480d.firebasestorage.app")
            
            if bridge.initialize():
                batch_id = f"batch_{session_id}_{int(time.time())}"
                
                # Convert ImageAssessment objects back to dicts for JSON/Firestore compatibility
                manifest_photos = []
                for p in manifest_data["photos"]:
                    # Serialize CoachingAdvice dataclass → plain dict for Firestore
                    coaching_dict = {}
                    if hasattr(p, "coaching") and p.coaching:
                        coaching_obj = p.coaching
                        coaching_dict = {
                            "exposure_triangle": getattr(coaching_obj, "exposure_triangle", ""),
                            "composition": getattr(coaching_obj, "composition", ""),
                            "artistic": getattr(coaching_obj, "artistic", ""),
                            "improvement_priority": getattr(coaching_obj, "improvement_priority", ""),
                        }
                    manifest_photos.append({
                        # ── Identity ───────────────────────────────────────────
                        "filename": p.filename,
                        "filepath": p.filepath,
                        "enhanced_path": p.enhanced_path,
                        "rlhf_path": p.rlhf_path,
                        # ── AI Scores (all 4 needed by SwipeCard quality bars) ──
                        "composite_score": p.composite_score,
                        "sharpness_score": p.sharpness_score,
                        "aesthetic_score": p.aesthetic_score,
                        "exposure_score": p.exposure_score,
                        # ── Classification ─────────────────────────────────────
                        "tier": p.tier,
                        "genre": getattr(p, "genre", "general") or "general",
                        # ── AI Coach ───────────────────────────────────────────
                        "reasoning": getattr(p, "reasoning", ""),
                        "coaching": coaching_dict,
                        "prompt_version": getattr(p, "prompt_version", "v1.0") or "v1.0",
                        # ── EXIF (needed by bento grid + extended rows) ─────────
                        "exif": p.exif if isinstance(p.exif, dict) else {},
                    })
                
                yield _yield_log(f"Syncing {len(manifest_photos)} photos to cloud plane...", "sys")
                if bridge.push_doppler_manifest(batch_id, manifest_photos):
                    yield _yield_log(f"✅ Cloud Manifest Sync Complete. Batch ID: {batch_id}", "sys")
                else:
                    yield _yield_log("⚠️ Cloud Sync Failed. UI may remain blind.", "error")
            else:
                yield _yield_log(f"⚠️ Firebase Bridge failed (Creds check: {service_account})", "error")

            yield _yield_log(f"Batch Complete. ({len(assessments)} photos assessed)", "done", {
                "portfolio": result.portfolio, "keepers": result.keepers, "review": result.review,
                "culled": result.culled, "recoverable": result.recoverable, "processing_time": result.processing_time
            })

    except Exception as e:
        yield _yield_log(f"CRITICAL KERNEL ERROR: {str(e)}", "error")
    finally:
        db.close()
        shutil.rmtree(os.path.join(target_folder, ".antigravity_workspace"), ignore_errors=True)

# ─── Helper Functions (Restored) ───────────────────────────────────

def generate_doppler_manifest(portfolio_list: list, amber_list: list, cull_list: list, output_dir: str) -> tuple[str, dict]:
    """
    Mandate 4: Psychological Load Balancer (The 70/30 Dopamine Loop)
    Interleaves known winners (Portfolio) with likely losers (Amber/Cull) 
    in a strict 70/30 (7 accepts to 3 rejects) ratio, with stochastic jitter to avoid UI fatigue.
    """
    accepts = list(portfolio_list)
    rejects = list(amber_list) + list(cull_list)
    
    # Pre-shuffle to avoid clustering identical consecutive traits
    random.shuffle(accepts)
    random.shuffle(rejects)
    
    interleaved_queue = []
    
    while accepts or rejects:
        chunk_accepts = min(len(accepts), 7)
        chunk_rejects = min(len(rejects), 3)
        
        chunk = []
        for _ in range(chunk_accepts):
            chunk.append(accepts.pop(0))
        for _ in range(chunk_rejects):
            chunk.append(rejects.pop(0))
            
        # Jitter: Stochastic shuffle within the 10-item micro-batch
        random.shuffle(chunk)
        interleaved_queue.extend(chunk)
        
    # Edge Case: Fallback if mathematical parity is broken
    if accepts:
        print(f"⚠️ Doppler Warning: 70/30 ratio broken. Appended {len(accepts)} remaining accepts.")
        interleaved_queue.extend(accepts)
    if rejects:
        print(f"⚠️ Doppler Warning: 70/30 ratio broken. Appended {len(rejects)} remaining rejects.")
        interleaved_queue.extend(rejects)
        
    manifest_path = os.path.join(output_dir, "batch_queue.json")
    temp_path = f"{manifest_path}.tmp"
    
    manifest_data = {
        "generated_at": time.time(),
        "total_items": len(interleaved_queue),
        "photos": interleaved_queue # Each item is photo.filepath or ImageAssessment
    }
    
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        os.replace(temp_path, manifest_path)
    except Exception as e:
        print(f"❌ Failed to atomically write Doppler manifest: {e}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
            
    return manifest_path, manifest_data

def _enhance_file(filepath, filename, format_type, iso, enhanced_path, workspace_dir, result, profile) -> str:
    stem = os.path.splitext(filename)[0]
    if format_type == "RAW":
        developed_path = os.path.join(workspace_dir, f"{stem}_dev.jpg")
        if raw_developer.develop(filepath, developed_path):
            if image_enhancer.enhance(developed_path, enhanced_path, iso=iso):
                result.enhanced += 1
            else:
                shutil.copy2(developed_path, enhanced_path)
                result.enhanced += 1
            if os.path.exists(developed_path): os.unlink(developed_path)
            return enhanced_path
    else:
        if image_enhancer.enhance(filepath, enhanced_path, iso=iso):
            result.enhanced += 1
            return enhanced_path
    return ""

def _build_recovery_notes(quality, exif) -> str:
    if not quality.recovery_potential: return ""
    notes = []
    if quality.exposure < 40: notes.append("Underexposed — lift shadows +30, exposure +0.7")
    elif quality.exposure > 85: notes.append("Overexposed — recover highlights")
    iso = exif.get("ISO", 0)
    if iso and iso > 3200: notes.append(f"High ISO ({iso}) — noise reduction required")
    return "; ".join(notes)

def scan_only(target_folder: str) -> BatchResult:
    """Read-only scan (Fully restored from original 731-line logic)."""
    batch_start = time.time()
    if not os.path.isdir(target_folder): return BatchResult()

    groups: dict[str, list[str]] = {}
    valid_files = sorted(os.listdir(target_folder))
    for f in valid_files:
        if os.path.isfile(os.path.join(target_folder, f)) and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
            stem = Path(f).stem
            if stem not in groups: groups[stem] = []
            groups[stem].append(f)

    total_files = sum(len(files) for files in groups.values())
    stems = sorted(groups.keys())
    assessments: list[ImageAssessment] = []
    result = BatchResult(total_scanned=total_files)

    processed_count = 0
    for stem in stems:
        group_files = groups[stem]
        group_results = []
        for filename in group_files:
            filepath = os.path.join(target_folder, filename)
            try:
                exif = preview_extractor.extract_metadata(filepath)
                preview_bytes = preview_extractor.extract_preview(filepath)
                if not preview_bytes: continue
                quality = quality_classifier.classify(preview_bytes, exif=exif)
                group_results.append({"filename": filename, "filepath": filepath, "exif": exif, "quality": quality, "start": time.time()})
            except: continue

        if not group_results: continue
        max_tier = Tier.CULL
        for res in group_results:
            if res["quality"].tier.rank > max_tier.rank: max_tier = res["quality"].tier
        
        for res in group_results:
            processed_count += 1
            filename, quality, exif = res["filename"], res["quality"], res["exif"]
            quality.tier = max_tier
            
            if max_tier == Tier.PORTFOLIO: result.portfolio += 1
            elif max_tier == Tier.KEEPER: result.keepers += 1
            elif max_tier == Tier.REVIEW: result.review += 1
            else: result.culled += 1
            
            if quality.recovery_potential in ("high", "medium"): result.recoverable += 1

            assessment = ai_coach.assess_image(filename, res["filepath"], res.get("rlhf_path", ""), get_format_type(res["filepath"]), quality, exif, "", False, (time.time()-res["start"]))
            assessment.recovery_potential = quality.recovery_potential
            assessment.recovery_notes = _build_recovery_notes(quality, exif)
            assessments.append(assessment)

    batch_time = time.time() - batch_start
    result.processing_time = round(batch_time, 1)
    result.files = assessments
    result.batch_coaching = ai_coach.compile_batch_report(assessments, batch_time)
    return result

def run_all_self_tests() -> dict[str, SelfTestResult]:
    """Full 6-module diagnostic suite (Restored)."""
    modules = {"preview_extractor": preview_extractor.self_test, "quality_classifier": quality_classifier.self_test, "raw_developer": raw_developer.self_test, "image_enhancer": image_enhancer.self_test, "file_tagger": file_tagger.self_test, "ai_coach": ai_coach.self_test}
    results = {}
    for name, test_fn in modules.items():
        try: results[name] = test_fn()
        except Exception as e: results[name] = SelfTestResult(module=name, passed=False, message=str(e))
    return results
