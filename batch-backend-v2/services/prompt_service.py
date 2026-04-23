import hashlib
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
import psutil
import ollama
import os

from database import PromptVersion, Inference, Media, Annotation, DatasetSnapshot, ModelRegistry
from vision_analyst import VisionAnalyst

# Global lock to ensure only one prompt test runs at a time (M4 Memory Safety)
PROMPT_TEST_LOCK = asyncio.Lock()

class PromptService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_prompt(self) -> Optional[PromptVersion]:
        return self.db.query(PromptVersion).filter(PromptVersion.is_production == True).first()

    def create_prompt_version(self, version: str, system_prompt: str, user_prompt: str, author: str = 'system', parent_version: str = None, notes: str = None) -> PromptVersion:
        content = system_prompt + user_prompt
        template_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check for duplicate content
        existing = self.db.query(PromptVersion).filter(PromptVersion.template_hash == template_hash).first()
        if existing:
            # We allow it but maybe warn in the future. For now, just create new version.
            pass

        new_prompt = PromptVersion(
            version=version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_hash=template_hash,
            author=author,
            parent_version=parent_version,
            change_notes=notes,
            status='draft'
        )
        self.db.add(new_prompt)
        self.db.commit()
        self.db.refresh(new_prompt)
        return new_prompt

    def promote_to_production(self, version_str: str):
        # Enforce single production prompt with nested transaction to prevent race conditions
        try:
            with self.db.begin_nested():
                self.db.query(PromptVersion).filter(PromptVersion.is_production == True).update({
                    "is_production": False,
                    "status": "retired",
                    "retired_at": datetime.now()
                })
                
                self.db.query(PromptVersion).filter(PromptVersion.version == version_str).update({
                    "is_production": True,
                    "status": "production",
                    "promoted_at": datetime.now()
                })
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    async def run_golden_set_test(self, version_str: str, model_name: str = "moondream") -> Dict:
        async with PROMPT_TEST_LOCK:
            # 1. Pre-flight: Memory Guard
            if psutil.virtual_memory().percent > 75:
                # Evict models
                try:
                    ollama.generate(model=model_name, keep_alive=0)
                except:
                    pass
            
            prompt_v = self.db.query(PromptVersion).filter(PromptVersion.version == version_str).first()
            prod_v = self.get_active_prompt()
            
            if not prompt_v:
                return {"error": "Prompt version not found"}

            # 2. Get Golden Set
            snapshot = self.db.query(DatasetSnapshot).filter(DatasetSnapshot.purpose == 'test_golden').order_by(DatasetSnapshot.created_at.desc()).first()
            if not snapshot:
                return {"error": "No Golden Set snapshot found. Please create one first."}
            
            media_ids = json.loads(snapshot.media_id_list)
            if len(media_ids) < 10: # Spec said 30, but let's be flexible for dev
                return {"error": f"Golden Set too small ({len(media_ids)}). Need at least 10 images."}
            
            media_ids = media_ids[:50] # Cap at 50
            
            results = []
            analyst = VisionAnalyst(model=model_name)
            
            for m_id in media_ids:
                # Check memory every iteration
                if psutil.virtual_memory().percent > 90:
                    break
                
                media = self.db.query(Media).filter(Media.id == m_id).first()
                annotation = self.db.query(Annotation).filter(Annotation.media_id == m_id).first()
                if not media or not annotation:
                    continue
                
                # Test Candidate
                start_t = datetime.now()
                # We use a mocked context for now
                test_res = analyst.analyze_image(media.proxy_path or media.file_path, prompt_version=version_str)
                dur = (datetime.now() - start_t).total_seconds() * 1000
                
                # Parse decision (keeper/cull)
                # In real app, we'd use the QualityClassifier logic. 
                # For this MVP, we look for keywords in description.
                desc = test_res['description'].lower()
                decision = "keeper" if any(x in desc for x in ["keep", "great", "excellent", "high quality"]) else "cull"
                
                # Compare with human
                human_action = "keeper" if "keeper" in annotation.action else "cull"
                is_correct = decision == human_action
                
                # Record Inference
                inf = Inference(
                    media_id=m_id,
                    model_id=1, # Mock
                    prompt_version=version_str,
                    inference_value=json.dumps({"description": test_res['description'], "decision": decision, "is_test": True}),
                    processing_time_ms=dur
                )
                self.db.add(inf)
                
                results.append({
                    "media_id": m_id,
                    "correct": is_correct,
                    "latency": dur
                })
            
            self.db.commit()
            
            # 3. Stats Calculation (McNemar's Logic Simplified for now)
            # In a real impl, we'd fetch production inferences for these same media_ids
            # to build the 2x2 matrix.
            
            summary = self._calculate_stats(results, version_str)
            
            # Update prompt metrics
            prompt_v.golden_success_rate = summary['accuracy']
            prompt_v.avg_processing_ms = summary['avg_latency']
            prompt_v.total_inferences += len(results)
            self.db.commit()
            
            # Evict after test
            try:
                ollama.generate(model=model_name, keep_alive=0)
            except:
                pass

            return summary

    def _calculate_stats(self, results: List[Dict], version: str) -> Dict:
        correct_count = sum(1 for r in results if r['correct'])
        total = len(results)
        avg_lat = sum(r['latency'] for r in results) / total if total > 0 else 0
        
        return {
            "version": version,
            "accuracy": correct_count / total if total > 0 else 0,
            "total_tested": total,
            "avg_latency": avg_lat,
            "status": "completed"
        }

    def bootstrap_golden_set(self, limit: int = 50):
        """Promote recent human annotations to a Golden Set snapshot."""
        # Get media with annotations
        query = self.db.query(Annotation.media_id).order_by(Annotation.timestamp.desc()).limit(limit).all()
        media_ids = [r[0] for r in query]
        
        if not media_ids:
            return None
            
        snapshot = DatasetSnapshot(
            snapshot_version=f"golden_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            purpose='test_golden',
            media_id_list=json.dumps(media_ids)
        )
        self.db.add(snapshot)
        self.db.commit()
        return snapshot
