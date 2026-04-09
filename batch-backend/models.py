from __future__ import annotations
from enum import Enum
from pydantic import BaseModel

class BatchTarget(BaseModel):
    target_folder: str
    benchmark_folder: str | None = None
    api_key: str | None = None
    provider: str = "gemini"
    ollama_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "gemma4:e4b"

class ProcessingStatus(str, Enum):
    ACCEPTED = "accepted"
    REVIEW_NEEDED = "review_needed"
    REJECTED_BLUR = "rejected_blur"
    REJECTED_EXPOSURE = "rejected_exposure"
    REJECTED_DUPLICATE = "rejected_duplicate"
    ERROR = "error"
