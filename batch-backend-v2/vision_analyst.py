import os
import base64
import ollama
import chromadb
from pathlib import Path
from typing import List, Dict, Optional

from prompt_registry import PromptRegistry, build_prompt_context, LATEST_VERSION
from models import detect_genre

class VisionAnalyst:
    """
    Antigravity Engine v2.1 — Module 9: Semantic Intelligence (Ollama + RAG)
    Leverages Vision LLMs to understand the "soul" of a photo.
    
    Responsibilities:
    1. Generate semantic descriptions using local VLM (Moondream).
    2. Store accepted/rejected patterns in ChromaDB.
    3. Calculate semantic similarity for personalized culling.
    """
    
    def __init__(self, model: str = "moondream", vector_db_path: str = ".antigravity_intelligence"):
        self.model = model
        self.db_path = vector_db_path
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.chroma_client.get_or_create_collection(
            name="user_preferences",
            metadata={"hnsw:space": "cosine"}
        )
        self._prompt_registry = PromptRegistry()

    def analyze_image(
        self,
        image_path: str,
        rag_context: Optional[Dict] = None,
        exif: Optional[Dict] = None,
        prompt_version: Optional[str] = None,
    ) -> Dict:
        """
        Generate a natural language description of the photo using a
        versioned prompt template enriched with RAG exemplar context.

        Args:
            image_path:      Absolute path to the image file.
            rag_context:     Output of SemanticRAG.get_few_shot_context(), or None.
            exif:            EXIF metadata dict (used for genre detection).
            prompt_version:  Explicit prompt version to use; defaults to LATEST_VERSION.

        Returns:
            dict with keys:
                'description'    – str, natural language description from VLM
                'prompt_version' – str, version of the prompt template used
        """
        version = prompt_version or LATEST_VERSION

        if not os.path.exists(image_path):
            return {"description": "File not found", "prompt_version": version}

        try:
            # Detect genre from EXIF for prompt context
            genre = detect_genre(exif) if exif else "general"

            # Build context-aware prompt via the registry
            ctx = build_prompt_context(rag_context, genre=genre)
            prompt_text = self._prompt_registry.get_prompt(version, ctx)

            # Use Ollama Python client with the versioned prompt
            response = ollama.generate(
                model=self.model,
                prompt=prompt_text,
                images=[image_path],
            )
            description = response['response'].strip()
            return {"description": description, "prompt_version": version}
        except Exception as e:
            print(f"[vision_analyst] Error analyzing {image_path}: {e}")
            return {"description": "Semantic analysis failed", "prompt_version": version}

    def store_preference(self, photo_id: str, description: str, score: float, is_accepted: bool):
        """Add a photo's semantic pattern to the RAG store."""
        # Simple RAG: accepted photos get higher weights in our search
        metadata = {
            "score": score,
            "decision": "accepted" if is_accepted else "rejected",
            "timestamp": os.path.getmtime(self.db_path) if os.path.exists(self.db_path) else 0
        }
        
        self.collection.add(
            documents=[description],
            metadatas=[metadata],
            ids=[photo_id]
        )

    def get_similarity_score(self, description: str) -> float:
        """
        Query the RAG store: 'How much does the user love this kind of photo?'
        Returns 0-100 score.
        """
        try:
            # Query the collection for the closest "Accepted" matches
            results = self.collection.query(
                query_texts=[description],
                n_results=5,
                where={"decision": "accepted"}
            )
            
            if not results or not results['distances'] or not results['distances'][0]:
                return 50.0 # Neutral if no history
            
            # Distance is cosine distance (0.0 = identical, 2.0 = opposite)
            avg_distance = sum(results['distances'][0]) / len(results['distances'][0])
            
            # Convert to 0-100 score (1.0 distance -> 50 score, 0.0 -> 100 score)
            similarity = max(0.0, (1.0 - avg_distance)) * 100.0
            return round(similarity, 1)
            
        except Exception as e:
            # Likely no "accepted" documents yet
            print(f"[vision_analyst] Similarity check skipped: {e}")
            return 50.0

if __name__ == "__main__":
    # Self-test snippet
    analyst = VisionAnalyst()
    print("AI Analyst Initialized.")
    # Test with a placeholder if exists, otherwise just verify init
    # analyst.analyze_image("test.jpg")
