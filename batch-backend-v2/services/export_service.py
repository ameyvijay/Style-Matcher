import json
import os
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from database import Media, Annotation, Inference

class DatasetExportService:
    def __init__(self, db: Session):
        self.db = db
        self.export_dir = "exports"
        if not os.path.exists(self.export_dir):
            os.makedirs(self.export_dir)

    def export_curated_dataset(self) -> Dict:
        """
        Aggregates Human Truth + AI Context into a machine-readable dataset.
        Format: JSONL (one image per line)
        """
        # Fetch all images that have a human annotation
        annotations = self.db.query(Annotation).all()
        
        filename = f"antigravity_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        filepath = os.path.join(self.export_dir, filename)
        
        records_exported = 0
        
        with open(filepath, 'w') as f:
            for ann in annotations:
                media = self.db.query(Media).filter(Media.id == ann.media_id).first()
                if not media: continue
                
                # Find latest VLM inference for description
                inference = self.db.query(Inference).filter(
                    Inference.media_id == media.id,
                    Inference.model_id.in_(
                        self.db.query(Inference.model_id).filter(Inference.inference_value.contains("description"))
                    )
                ).order_by(Inference.created_at.desc()).first()
                
                vlm_desc = ""
                if inference:
                    try:
                        data = json.loads(inference.inference_value)
                        vlm_desc = data.get("description", "")
                    except: pass

                record = {
                    "photo_hash": media.photo_hash,
                    "file_path": media.file_path,
                    "user_action": ann.action,
                    "user_tags": ann.custom_tags,
                    "vlm_description": vlm_desc,
                    "timestamp": ann.timestamp.isoformat() if ann.timestamp else None,
                    "metadata": {
                        "width": media.width,
                        "height": media.height,
                        "format": media.format
                    }
                }
                f.write(json.dumps(record) + "\n")
                records_exported += 1
                
        return {
            "status": "success",
            "records": records_exported,
            "file": filepath,
            "timestamp": datetime.now().isoformat()
        }
