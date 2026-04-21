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
        """
        import psutil
        import torch

        # Get average confidence for specific models
        models = self.db.query(ModelRegistry).all()
        model_health = {}
        
        for m in models:
            avg_conf = self.db.query(func.avg(Inference.confidence))\
                .filter(Inference.model_id == m.id).scalar() or 0.0
            
            # Simple health check: if avg confidence > 0.4, it's "Healthy"
            status = "Healthy" if avg_conf > 0.4 else "Degraded"
            if avg_conf == 0: status = "Unknown"
            
            model_health[m.name] = {
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
