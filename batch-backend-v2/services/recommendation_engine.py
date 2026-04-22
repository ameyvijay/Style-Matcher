from sqlalchemy.orm import Session
from sqlalchemy import func
from database import Annotation, DatasetSnapshot, PromptVersion, Inference, ModelRegistry
import json

class RecommendationEngine:
    def __init__(self, db: Session):
        self.db = db

    def get_recommendations(self):
        recs = []
        
        # 1. RAG Rebuild Check
        # If new annotations since last snapshot > 10% of golden set, or > 50 new
        total_annotations = self.db.query(Annotation).count()
        last_golden = self.db.query(DatasetSnapshot).filter(DatasetSnapshot.purpose == 'test_golden').order_by(DatasetSnapshot.created_at.desc()).first()
        
        golden_count = 0
        if last_golden:
            golden_count = len(json.loads(last_golden.media_id_list))
            
        new_potential = total_annotations - golden_count
        if new_potential > 50:
            recs.append({
                "id": "rag_rebuild",
                "type": "OPTIMIZATION",
                "priority": "MEDIUM",
                "title": "RAG Index Rebuild Advised",
                "body": f"You have {new_potential} new human annotations not yet in your Golden Set. Rebuilding the RAG index will improve VLM context and retrieval accuracy.",
                "action": "Rebuild Index"
            })

        # 2. LoRA Fine-tune Check
        # If total annotations > 500 and no LoRA active, or 200 new since last LoRA
        total_training = self.db.query(Annotation).filter(Annotation.action != 'skipped').count()
        if total_training > 200:
            recs.append({
                "id": "lora_tune",
                "type": "TRAINING",
                "priority": "HIGH",
                "title": "Model Fine-tune Ready",
                "body": f"Your training dataset has reached {total_training} samples. Triggering a LoRA fine-tune could significantly improve the engine's alignment with your editing style.",
                "action": "Start LoRA"
            })

        # 3. Prompt Performance Check
        active_prompt = self.db.query(PromptVersion).filter(PromptVersion.is_production == True).first()
        if active_prompt and active_prompt.golden_success_rate:
            if active_prompt.golden_success_rate < 0.85:
                recs.append({
                    "id": "prompt_opt",
                    "type": "PROMPT",
                    "priority": "HIGH",
                    "title": "Prompt Optimization Required",
                    "body": f"Current production prompt ({active_prompt.version}) is performing at {round(active_prompt.golden_success_rate*100, 1)}% accuracy. We recommend testing a new candidate in the Prompt Playground.",
                    "action": "Go to Playground"
                })

        # 4. Data Diversity Check (Simulated)
        if total_annotations < 100:
            recs.append({
                "id": "more_data",
                "type": "COLLECTION",
                "priority": "LOW",
                "title": "Data Collection Phase",
                "body": "Your dataset is still small. Continue using the HiTL Swiper to build a more robust 'Golden Set' for better AI recommendations.",
                "action": "Open Swiper"
            })

        return recs
