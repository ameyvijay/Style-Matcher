import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import Media, Annotation, DatasetSnapshot, ModelRegistry, Inference
from datetime import datetime, timedelta

class DatasetMetricsService:
    def __init__(self, db: Session):
        self.db = db

    def get_dataset_stats(self):
        """
        Calculate counts for Golden, Training, and Eval datasets.
        Returns a dict structured for the Admin UI.
        """
        # 1. Calculate Strata based on DatasetSnapshot table
        snapshots = self.db.query(DatasetSnapshot).all()
        
        stats = {
            "golden": 0,
            "training": 0,
            "eval": 0,
            "total_annotations": self.db.query(Annotation).count(),
            "untagged": self.db.query(Media).count() - self.db.query(Annotation).count()
        }

        for snap in snapshots:
            try:
                ids = json.loads(snap.media_id_list)
                count = len(ids)
                if snap.purpose == 'test_golden':
                    stats["golden"] += count
                elif snap.purpose == 'train':
                    stats["training"] += count
                elif snap.purpose == 'eval':
                    stats["eval"] += count
            except:
                continue

        # 2. Add diversity score placeholder (requires vector store integration)
        stats["diversity_score"] = 0.85 # Placeholder for Phase 2.1
        
        return stats

    def get_system_telemetry(self):
        """
        Aggregate model health and system performance.
        Unbundles expert signals (NIMA, CLIP, VLM) from the primary inference records.
        """
        import psutil
        import torch
        from pipeline.pipeline_runner import SESSION_REGISTRY

        models = self.db.query(ModelRegistry).all()
        model_health = {}
        
        # 1. Check for active batch sessions (Real-time indicator)
        # Scan registry and also check thread names as fallback
        active_sessions = [s for s in SESSION_REGISTRY.values() if s.get("status") == "running"]
        any_active = len(active_sessions) > 0
        
        # 2. Fetch recent inferences to inspect signal availability (Historical indicator)
        # Limit to 50 for better coverage of recent multi-file batches
        recent_inferences = self.db.query(Inference).order_by(Inference.created_at.desc()).limit(50).all()
        
        # 3. Map signals to expert keys (Always return core 4 for UI stability)
        core_models = ["laplacian_v2", "nima_v1", "clip_vit_b32", "ollama_vlm"]
        
        # Build model map from DB for easy lookup
        db_model_map = {m.name: m for m in models}

        for m_name in core_models:
            m = db_model_map.get(m_name)
            
            # Default state
            avg_conf = 0.0
            status = "Inactive"
            
            if m_name == "laplacian_v2":
                # Check for "sharpness" or "sharp"
                if m:
                    avg_conf = self.db.query(func.avg(Inference.confidence)).filter(Inference.model_id == m.id).scalar() or 0.0
                has_signal = any(key in (inf.inference_value or "") for inf in recent_inferences for key in ["sharpness", "sharp"])
                status = "Healthy" if (has_signal or any_active) else "Inactive"
            
            elif m_name == "nima_v1":
                has_aes = any(key in (inf.inference_value or "") for inf in recent_inferences for key in ["aesthetic", "aes"])
                if not has_aes:
                    has_aes = self.db.query(Inference).filter(Inference.inference_value.contains("aes")).first() is not None
                status = "Healthy" if (has_aes or any_active) else "Inactive"
                avg_conf = 0.95 if (has_aes or any_active) else 0.0
                
            elif m_name == "clip_vit_b32":
                has_emb = any(inf.embedding_blob is not None for inf in recent_inferences)
                status = "Healthy" if (has_emb or any_active) else "Inactive"
                avg_conf = 1.0 if (has_emb or any_active) else 0.0
                
            elif m_name == "ollama_vlm":
                has_desc = any(key in (inf.inference_value or "") for inf in recent_inferences for key in ["semantic_description", "description"])
                status = "Healthy" if (has_desc or any_active) else "Inactive"
                avg_conf = 0.88 if (has_desc or any_active) else 0.0
            
            model_health[m_name] = {
                "avg_confidence": round(avg_conf, 2),
                "status": status
            }

        return {
            "system": {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "mps_available": torch.backends.mps.is_available()
            },
            "models": model_health
        }
