"""
Antigravity Engine v2.1 — Module C.1: CLIP Embedder
Hardware-accelerated CLIP embedding pipeline for Visual RAG.

Key Design:
- Apple Silicon MPS (Metal Performance Shaders) auto-detection with CPU fallback
- ViT-B-32 backbone pretrained on LAION-2B for 512-dim visual embeddings
- Normalised L2 vectors suitable for cosine-similarity retrieval
"""
from __future__ import annotations

import torch
import open_clip
from PIL import Image


class ClipEmbedder:
    """
    Generates normalised 512-dimensional CLIP embeddings for images.
    Automatically selects the fastest available compute device:
      MPS (Apple Silicon GPU) → CPU fallback.
    """

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    def __init__(self):
        # ── Device Selection ──────────────────────────────────────────
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
            print("⚡ ClipEmbedder: Using Apple Silicon MPS (Metal Performance Shaders)")
        else:
            self.device = torch.device("cpu")
            print("🐢 ClipEmbedder: MPS unavailable — falling back to CPU")

        # ── Model + Preprocessing ─────────────────────────────────────
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            self.MODEL_NAME,
            pretrained=self.PRETRAINED,
            device=self.device,
        )
        self.model.eval()
        print(f"✅ ClipEmbedder: {self.MODEL_NAME} ({self.PRETRAINED}) loaded on {self.device}")

    def generate_embedding(self, image_path: str) -> list[float]:
        """
        Load an image, preprocess it through the CLIP vision encoder,
        L2-normalise the resulting vector, and return a plain Python
        list of 512 floats.

        Args:
            image_path: Absolute path to a JPEG/PNG image file.

        Returns:
            A list of 512 float values (unit-normalised embedding).
        """
        image = Image.open(image_path).convert("RGB")
        tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad(), torch.amp.autocast(device_type=str(self.device)):
            features = self.model.encode_image(tensor)

        # L2 normalise so downstream cosine similarity = dot product
        features = features / features.norm(dim=-1, keepdim=True)

        return features.squeeze(0).cpu().tolist()
