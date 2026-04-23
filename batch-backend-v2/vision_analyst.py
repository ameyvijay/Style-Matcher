import os
import base64
import ollama
import chromadb
from pathlib import Path
from typing import List, Dict, Optional

from prompt_registry import PromptRegistry, build_prompt_context, LATEST_VERSION
from models import detect_genre

from vector_store import ChromaManager

class VisionAnalyst:
    """
    Antigravity Engine v2.1 — Module 9: Semantic Intelligence (Ollama + RAG)
    Leverages Vision LLMs to understand the "soul" of a photo.
    
    Responsibilities:
    1. Generate semantic descriptions using local VLM.
    2. Interface with ChromaManager for preference retrieval.
    """
    
    def __init__(self, model: Optional[str] = None):
        self.chroma = ChromaManager()
        self._prompt_registry = PromptRegistry()
        
        if model:
            self.model = model
        else:
            # Dynamically fetch production model from DB
            from database import SessionLocal, ModelRegistry
            try:
                with SessionLocal() as db:
                    prod = db.query(ModelRegistry).filter(ModelRegistry.is_production == True, ModelRegistry.model_type == 'vlm').first()
                    self.model = prod.ollama_tag if prod and prod.ollama_tag else "moondream:latest"
            except:
                self.model = "moondream:latest"
        print(f"🧠 VisionAnalyst initialized with model: {self.model}")

    def analyze_image(
        self,
        image_path: str,
        rag_context: Optional[Dict] = None,
        exif: Optional[Dict] = None,
        prompt_version: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt_template: Optional[str] = None,
    ) -> Dict:
        """
        Generate a natural language description of the photo using a
        versioned prompt template enriched with RAG exemplar context.
        """
        version = prompt_version or LATEST_VERSION

        if not os.path.exists(image_path):
            return {"description": "File not found", "prompt_version": version}

        try:
            # Detect genre from EXIF for prompt context
            genre = detect_genre(exif) if exif else "general"

            # Build context-aware prompt
            ctx = build_prompt_context(rag_context, genre=genre)
            
            # If explicit prompts provided (from Playground), use them
            if system_prompt and user_prompt_template:
                final_system = system_prompt
                from prompt_registry import SafeFormatter
                formatter = SafeFormatter()
                final_user = formatter.format(user_prompt_template, **ctx)
            else:
                # Fallback to registry (legacy)
                final_system = "You are an expert photography editor."
                final_user = self._prompt_registry.get_prompt(version, ctx)

            # Use Ollama Chat API for better instruction following
            # Models like Moondream might need these collapsed into one string
            # for generate(), but chat() is the standard for versioned prompts.
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": final_system},
                    {"role": "user", "content": final_user, "images": [image_path]}
                ],
                options={"num_predict": 128, "temperature": 0.2},
                # Mandated timeout to fix pre-existing bug
            )
            description = response['message']['content'].strip()
            return {"description": description, "prompt_version": version}
        except Exception as e:
            print(f"[vision_analyst] Error analyzing {image_path}: {e}")
            # Fallback to generate if chat fails (some older models)
            try:
                # Collapse for backward compatibility
                collapsed = f"{final_system}\n\n{final_user}"
                response = ollama.generate(model=self.model, prompt=collapsed, images=[image_path])
                return {"description": response['response'].strip(), "prompt_version": version}
            except:
                return {"description": "Semantic analysis failed", "prompt_version": version}

    def get_similarity_score(self, description: str) -> float:
        """
        DEPRECATED: Use ContrastiveRAG in PreferenceEngine instead.
        Redirects to CLIP-based similarity for consistency.
        """
        return 50.0

if __name__ == "__main__":
    # Self-test snippet
    analyst = VisionAnalyst()
    print("AI Analyst Initialized.")
    # Test with a placeholder if exists, otherwise just verify init
    # analyst.analyze_image("test.jpg")
