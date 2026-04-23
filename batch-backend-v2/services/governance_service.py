import os
import hashlib
from sqlalchemy.orm import Session
from database import Media, Annotation, DatasetSnapshot
from typing import List, Optional

class GovernanceService:
    def __init__(self, db: Session):
        self.db = db

    def _calculate_hash(self, file_path: str) -> str:
        """Content-addressable hash (File Size + SHA-256 of first 1MB for speed)."""
        stats = os.stat(file_path)
        hasher = hashlib.sha256()
        hasher.update(str(stats.st_size).encode())
        with open(file_path, "rb") as f:
            hasher.update(f.read(1024 * 1024))
        return hasher.hexdigest()

    def register_media(self, file_path: str, source_node: str = "local_m4") -> Media:
        """Registers or updates media. Survives path changes via hash check."""
        file_hash = self._calculate_hash(file_path)
        
        media = self.db.query(Media).filter(Media.photo_hash == file_hash).first()
        if media:
            # Path moved logic: Update path, keep lineage
            if media.file_path != file_path:
                print(f"🔄 Media moved: {media.file_path} -> {file_path}")
                media.file_path = file_path
                media.source_node = source_node
            return media
        
        # New entry
        new_media = Media(
            photo_hash=file_hash,
            file_path=file_path,
            filename=os.path.basename(file_path),
            source_node=source_node,
            logical_role='rag'
        )
        self.db.add(new_media)
        self.db.commit()
        return new_media

    def promote_to_role(self, photo_hash: str, role: str, is_manual: bool = False):
        """Promotes media to Golden, Benchmark, etc."""
        media = self.db.query(Media).filter(Media.photo_hash == photo_hash).first()
        if not media:
            raise ValueError("Media not found")
        
        media.logical_role = role
        media.is_manual_entry = is_manual
        self.db.commit()
        return {"status": "success", "media_id": media.id, "new_role": role}

    def get_lineage(self, photo_hash: str):
        """Traces the entire history of a photo across models and snapshots."""
        media = self.db.query(Media).filter(Media.photo_hash == photo_hash).first()
        if not media:
            return None
        
        return {
            "media_id": media.id,
            "hash": media.photo_hash,
            "role": media.logical_role,
            "annotations": [
                {"action": a.action, "timestamp": a.timestamp} 
                for a in media.annotations
            ],
            "inferences": [
                {"model": i.model.name, "value": i.inference_value, "created_at": i.created_at}
                for i in media.inferences
            ]
        }
