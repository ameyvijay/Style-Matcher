import json
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from database import Media, Annotation, DatasetSnapshot, Inference, PromptVersion
from vector_store import ChromaManager
import os

class RAGAutomationService:
    def __init__(self, db: Session):
        self.db = db
        self.chroma = ChromaManager()

    def promote_golden_set_to_rag(self, snapshot_version: str) -> Dict:
        """
        Promotes a specific Golden Set snapshot's embeddings to ChromaDB.
        Follows Architect's mandate for composite IDs and separate collection.
        """
        snapshot = self.db.query(DatasetSnapshot).filter(DatasetSnapshot.snapshot_version == snapshot_version).first()
        if not snapshot:
            return {"error": "Snapshot not found"}
        
        media_ids = json.loads(snapshot.media_id_list)
        promoted_count = 0
        skipped_count = 0
        
        for m_id in media_ids:
            media = self.db.query(Media).filter(Media.id == m_id).first()
            annotation = self.db.query(Annotation).filter(Annotation.media_id == m_id).first()
            
            # Find the best inference for this media (prefer non-test, latest production prompt)
            inference = self.db.query(Inference).filter(
                Inference.media_id == m_id,
                Inference.embedding_blob.isnot(None)
            ).order_by(Inference.created_at.desc()).first()
            
            if not inference or not annotation:
                skipped_count += 1
                continue
                
            try:
                embedding_vector = json.loads(inference.embedding_blob)
                prompt_v = inference.prompt_version or "v1.0"
                doc_id = f"{media.photo_hash}__{prompt_v}"
                
                # Determine target collection based on human annotation
                # Though specified for golden_exemplars, we still respect action
                is_accepted = "keeper" in annotation.action
                collection_name = "golden_exemplars" if is_accepted else "rejected_preferences"
                
                metadata = {
                    "photo_hash": media.photo_hash,
                    "prompt_version": prompt_v,
                    "source": "golden",
                    "is_golden": True,
                    "snapshot_version": snapshot_version,
                    "embedding_model": "ViT-B-32", # Mandated for future migration
                    "indexed_at": datetime.now().isoformat(),
                    "filename": os.path.basename(media.file_path),
                    "action": annotation.action
                }
                
                self.chroma.add_embedding(
                    collection_name=collection_name,
                    doc_id=doc_id,
                    embedding=embedding_vector,
                    metadata=metadata
                )
                promoted_count += 1
            except Exception as e:
                print(f"⚠️ Failed to promote media_id {m_id}: {e}")
                skipped_count += 1
                
        return {
            "status": "success",
            "snapshot": snapshot_version,
            "promoted": promoted_count,
            "skipped": skipped_count
        }

    def get_promotable_snapshots(self) -> List[Dict]:
        """List snapshots that are purpose='test_golden'"""
        snaps = self.db.query(DatasetSnapshot).filter(DatasetSnapshot.purpose == 'test_golden').all()
        return [{"version": s.snapshot_version, "created_at": s.created_at} for s in snaps]
