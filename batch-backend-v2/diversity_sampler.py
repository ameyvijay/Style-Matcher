import random
from typing import List, Dict, Any
from models import ImageAssessment, Tier

class DiversitySampler:
    """
    Antigravity Engine v2.1 — Module 10: Diversity Sampler
    Curates the RLHF batch to ensure a balance between:
    1. Exploitation (Showing what the user likes)
    2. Exploration (Showing technical masters and counterfactuals)
    
    Prevents model drift and ensures high recall (AUC-PR).
    """

    def __init__(self, target_batch_size: int = 50):
        self.target_batch_size = target_batch_size

    def curate_rlhf_batch(
        self, 
        assessments: List[ImageAssessment], 
        user_preference_store: Any = None
    ) -> List[ImageAssessment]:
        """
        Selectors the best subset of images for user review.
        
        Strategy:
        - 70% "High Potential": Top semantic + aesthetic scores.
        - 20% "Technical Masters": Top sharpness + exposure scores.
        - 10% "Edge Cases/Counterfactuals": Random samples from the 'Review' tier 
          to calibrate the model boundaries.
        """
        if not assessments:
            return []

        # Filter out absolute noise (very low technical scores)
        valid_candidates = [
            a for a in assessments 
            if a.sharpness_score > 20 and a.exposure_score > 20
        ]
        
        if len(valid_candidates) <= self.target_batch_size:
            return valid_candidates

        # 1. Sort by segments
        # High Potential (using semantic similarity if available)
        high_potential = sorted(
            valid_candidates, 
            key=lambda x: (x.semantic_similarity * 0.6 + x.aesthetic_score * 0.4), 
            reverse=True
        )
        
        # Technical Masters
        tech_masters = sorted(
            valid_candidates, 
            key=lambda x: (x.sharpness_score * 0.7 + x.exposure_score * 0.3), 
            reverse=True
        )
        
        # Edge Cases (Review tier)
        edge_cases = [a for a in valid_candidates if a.tier == Tier.REVIEW.value]
        if not edge_cases:
            edge_cases = valid_candidates # Fallback if no review tier

        # 2. Select quotas
        n_hp = int(self.target_batch_size * 0.7)
        n_tm = int(self.target_batch_size * 0.2)
        n_ec = self.target_batch_size - n_hp - n_tm

        selected_ids = set()
        final_batch = []

        def add_unique(items, quota):
            count = 0
            for item in items:
                if item.filename not in selected_ids:
                    final_batch.append(item)
                    selected_ids.add(item.filename)
                    count += 1
                    if count >= quota:
                        break

        # Add segments
        add_unique(high_potential, n_hp)
        add_unique(tech_masters, n_tm)
        
        # Add random edge cases
        random.shuffle(edge_cases)
        add_unique(edge_cases, n_ec)

        # Final safety check: if we somehow missed the quota, fill with remaining tech masters
        if len(final_batch) < min(self.target_batch_size, len(valid_candidates)):
            remaining = [a for a in tech_masters if a.filename not in selected_ids]
            add_unique(remaining, self.target_batch_size - len(final_batch))

        print(f"[diversity_sampler] Curated {len(final_batch)} photos for RLHF (HP: {n_hp}, TM: {n_tm}, EC: {n_ec})")
        return final_batch
