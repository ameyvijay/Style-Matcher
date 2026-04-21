"""
Antigravity Engine v2.0 — Shared Models & Types
All modules import from here. No circular dependencies.
"""
from __future__ import annotations

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel


# ─── API Request Model ───────────────────────────────────────────────
class BatchRequest(BaseModel):
    """Incoming request from the frontend."""
    target_folder: str
    benchmark_folder: Optional[str] = None
    session_id: Optional[str] = None
    api_key: Optional[str] = None
    provider: str = "gemini"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"


# ─── Tier System ─────────────────────────────────────────────────────
class Tier(str, Enum):
    PORTFOLIO = "portfolio"      # Score ≥ 80: Best of the batch
    KEEPER = "keeper"            # Score ≥ 60: Solid shot
    REVIEW = "review"            # Score ≥ 40: Borderline
    CULL = "cull"                # Score < 40: Reject

    @staticmethod
    def from_score(score: float) -> "Tier":
        if score >= 80:
            return Tier.PORTFOLIO
        elif score >= 60:
            return Tier.KEEPER
        elif score >= 40:
            return Tier.REVIEW
        else:
            return Tier.CULL

    @property
    def rank(self) -> int:
        """Numeric rank for comparison (higher is better)."""
        ranks = {
            Tier.PORTFOLIO: 3,
            Tier.KEEPER: 2,
            Tier.REVIEW: 1,
            Tier.CULL: 0
        }
        return ranks.get(self, 0)


# ─── Genre System ──────────────────────────────────────────────────
# Photography genres inferred from EXIF signals for nuanced scoring.

GENRE_PROFILES = {
    "landscape": {
        "name": "Landscape / Scenic",
        "focal_range": (10, 40),       # Wide-angle to normal
        "aperture_range": (5.6, 22),    # Stopped down for depth of field
        "exposure_tolerance": 1.2,      # Wider tolerance (creative underexposure OK)
        "sharpness_weight": 0.30,       # Slightly less — distant subjects can be softer
        "aesthetic_weight": 0.45,       # Composition matters most
        "exposure_weight": 0.25,
    },
    "portrait": {
        "name": "Portrait / Subject",
        "focal_range": (50, 200),       # Normal to telephoto
        "aperture_range": (1.2, 4.0),   # Wide open for bokeh
        "exposure_tolerance": 1.0,
        "sharpness_weight": 0.40,       # Subject sharpness is critical
        "aesthetic_weight": 0.35,
        "exposure_weight": 0.25,
    },
    "street": {
        "name": "Street / Documentary",
        "focal_range": (24, 50),        # Classic street focal lengths
        "aperture_range": (2.8, 8.0),
        "exposure_tolerance": 1.3,      # High tolerance (harsh light common)
        "sharpness_weight": 0.25,       # Slight blur can be artistic
        "aesthetic_weight": 0.45,       # Story and composition matter
        "exposure_weight": 0.30,
    },
    "macro": {
        "name": "Macro / Close-Up",
        "focal_range": (60, 200),
        "aperture_range": (2.8, 16),
        "exposure_tolerance": 1.0,
        "sharpness_weight": 0.50,       # Tack-sharp is everything
        "aesthetic_weight": 0.25,
        "exposure_weight": 0.25,
    },
    "wildlife": {
        "name": "Wildlife / Sports",
        "focal_range": (200, 800),      # Supertele
        "aperture_range": (2.8, 8.0),
        "exposure_tolerance": 1.0,
        "sharpness_weight": 0.45,       # Must nail focus at distance
        "aesthetic_weight": 0.30,
        "exposure_weight": 0.25,
    },
    "architecture": {
        "name": "Architecture / Interior",
        "focal_range": (14, 35),
        "aperture_range": (8.0, 16),    # Stopped down for sharpness
        "exposure_tolerance": 1.1,
        "sharpness_weight": 0.35,
        "aesthetic_weight": 0.40,       # Symmetry and lines matter
        "exposure_weight": 0.25,
    },
    "general": {
        "name": "General",
        "focal_range": (24, 200),
        "aperture_range": (1.4, 22),
        "exposure_tolerance": 1.0,
        "sharpness_weight": 0.35,
        "aesthetic_weight": 0.40,
        "exposure_weight": 0.25,
    },
}


def detect_genre(exif: dict) -> str:
    """Infer photography genre from EXIF metadata (focal length + aperture)."""
    if not exif:
        return "general"
        
    focal_mm = exif.get("FocalLengthMM", 0)
    fnumber = exif.get("FNumber", 0)

    if not focal_mm:
        return "general"

    # Super telephoto → wildlife/sports
    if focal_mm >= 200:
        return "wildlife"

    # Wide angle + stopped down → landscape or architecture
    if focal_mm <= 35:
        if fnumber and fnumber >= 8:
            return "architecture" if focal_mm <= 24 else "landscape"
        elif fnumber and fnumber <= 4.0:
            return "street"  # Wide + open = environmental/street
        return "landscape"

    # 35-70mm range
    if 35 < focal_mm <= 70:
        if fnumber and fnumber <= 2.8:
            return "portrait"
        elif fnumber and fnumber >= 8:
            return "landscape"
        return "street"

    # 70-200mm range
    if 70 < focal_mm < 200:
        if fnumber and fnumber <= 4.0:
            return "portrait"
        return "portrait"

    return "general"


# ─── Tier Configuration (Tags, Ratings, Colors) ─────────────────────
TIER_CONFIG = {
    Tier.PORTFOLIO: {"tag": "Portfolio",  "rating": 5, "label": "Winner",   "color": "Green"},
    Tier.KEEPER:    {"tag": "Keeper",     "rating": 4, "label": "Select",   "color": "Yellow"},
    Tier.REVIEW:    {"tag": "Review",     "rating": 3, "label": "Second",   "color": "Orange"},
    Tier.CULL:      {"tag": "Cull",       "rating": 1, "label": "Rejected", "color": "Red"},
}


# ─── Quality Scoring ─────────────────────────────────────────────────
@dataclass
class QualityScore:
    """Output from the quality_classifier module."""
    sharpness: float = 0.0       # 0-100 normalized Laplacian variance
    aesthetic: float = 0.0       # 0-100 normalized MUSIQ/CLIPIQA score
    exposure: float = 0.0        # 0-100 (50 = perfect midtone)
    composite: float = 0.0       # Weighted average of all signals
    tier: Tier = Tier.CULL
    recovery_potential: str = ""  # "high", "medium", "low", or "" — can bad exposure/aesthetic be fixed?
    processing_time: float = 0.0  # Seconds
    semantic_description: str = "" # Generated by Ollama Vision
    semantic_similarity: float = 0.0 # Similarity to user preference RAG


# ─── Enhancement Profile ─────────────────────────────────────────────
@dataclass
class EnhancementProfile:
    """Configuration for the image_enhancer module."""
    clahe_clip_limit: float = 2.0
    clahe_tile_size: int = 8
    color_boost: float = 1.12     # Pillow Color enhancer factor
    contrast_boost: float = 1.08  # Pillow Contrast enhancer factor
    sharpness_boost: float = 1.05 # Pillow Sharpness enhancer factor
    jpeg_quality: int = 92
    denoise_iso_threshold: int = 1600
    denoise_heavy_iso_threshold: int = 3200
    esrgan_scale: int = 2         # 2x upscale (not 4x — too large)
    esrgan_enabled: bool = True
    max_file_size_mb: float = 0.0 # 0.0 = no limit
    max_resolution_scale: float = 1.0 # Scale factor if file size exceeded

# Predefined Profiles
ENHANCEMENT_PROFILE_MASTER = EnhancementProfile(
    jpeg_quality=100, # 100% quality for masters
    esrgan_enabled=True,
    max_file_size_mb=0.0
)

ENHANCEMENT_PROFILE_RLHF = EnhancementProfile(
    jpeg_quality=90, # 90% quality for PWA/Back-end
    esrgan_enabled=False, # Disable ESRGAN for RLHF to keep size down
    max_file_size_mb=10.0
)


# ─── Per-File Coaching ────────────────────────────────────────────────
@dataclass
class CoachingAdvice:
    """Photography coaching generated from EXIF + scores."""
    exposure_triangle: str = ""
    composition: str = ""
    artistic: str = ""
    improvement_priority: str = ""


# ─── Per-File Assessment (AI Coach output) ────────────────────────────
@dataclass
class ImageAssessment:
    """Complete assessment for a single image. Written to batch_report.json."""
    filename: str = ""
    filepath: str = ""
    format: str = ""               # "ARW", "JPEG", "HEIC", etc.
    tier: str = ""                  # Tier enum value
    genre: str = "general"         # Detected photography genre (portrait, landscape, street…)
    composite_score: float = 0.0
    sharpness_score: float = 0.0
    aesthetic_score: float = 0.0
    exposure_score: float = 0.0
    reasoning: str = ""            # Human-readable summary
    technical_flaws: list = field(default_factory=list)
    recovery_potential: str = ""   # "high"/"medium"/"low" — can this be rescued in post?
    recovery_notes: str = ""       # What specifically can be recovered
    coaching: CoachingAdvice = field(default_factory=CoachingAdvice)
    denoising_applied: bool = False
    enhanced_path: str = ""        # Path to enhanced JPEG (if created)
    rlhf_path: str = ""            # Path to low-res JPEG proxy for UI swiper
    exif: dict = field(default_factory=dict)
    processing_time: float = 0.0
    prompt_version: str = "v1.0"   # AI Coach prompt version that produced this assessment


# ─── Per-File Result (internal pipeline) ──────────────────────────────
@dataclass
class FileResult:
    """Internal result passed between pipeline stages."""
    filename: str = ""
    filepath: str = ""
    format: str = ""               # "ARW", "JPEG", etc.
    preview_jpeg: bytes = b""      # Extracted preview (in memory)
    working_jpeg_path: str = ""    # Path to working JPEG (converted or original)
    quality: QualityScore = field(default_factory=QualityScore)
    exif: dict = field(default_factory=dict)
    enhanced_path: str = ""
    assessment: ImageAssessment = field(default_factory=ImageAssessment)
    error: str = ""


# ─── Batch Result (API response) ─────────────────────────────────────
@dataclass
class BatchResult:
    """Final output from the batch_orchestrator."""
    total_scanned: int = 0
    portfolio: int = 0
    keepers: int = 0
    review: int = 0
    culled: int = 0
    recoverable: int = 0
    duplicates: int = 0
    denoised: int = 0
    enhanced: int = 0
    files: list = field(default_factory=list)  # List[ImageAssessment]
    processing_time: float = 0.0
    batch_coaching: str = ""       # Aggregate coaching summary


# ─── Module Self-Test Result ──────────────────────────────────────────
@dataclass
class SelfTestResult:
    """Returned by each module's self_test() function."""
    module: str = ""
    passed: bool = False
    message: str = ""
    details: str = ""


# ─── Visual RAG / RLHF Telemetry DTO ─────────────────────────────────
@dataclass
class SwipeTelemetry:
    """
    Per-swipe signal bundle captured at decision time.
    Written to table_annotations and forwarded to the MLOps pipeline
    as ground-truth for Visual RAG prompt optimisation and fine-tuning.
    """
    photo_hash: str = ""                    # SHA-256 of filename+size — joins to table_media
    embedding_id: Optional[int] = None      # FK → ChromaDB / table_inferences embedding row
    swipe_duration_ms: Optional[int] = None # Time from card render to swipe gesture (UX signal)
    confidence_weight: Optional[float] = None  # Computed certainty of the decision (0.0–1.0)
    exif_snapshot: Optional[str] = None     # JSON-serialised EXIF at swipe time (genre, ISO, FL)
    genre: Optional[str] = None             # Inferred genre label (portrait, landscape, street…)
    prompt_version: Optional[str] = None    # AI Coach prompt version that produced this assessment


# ─── Supported Formats ───────────────────────────────────────────────
RAW_EXTENSIONS = {'.arw', '.cr2', '.cr3', '.nef', '.orf', '.raf', '.rw2', '.dng'}
JPEG_EXTENSIONS = {'.jpg', '.jpeg'}
IMAGE_EXTENSIONS = RAW_EXTENSIONS | JPEG_EXTENSIONS | {'.png', '.heic', '.tif', '.tiff'}

NEEDS_CONVERSION = RAW_EXTENSIONS | {'.heic', '.tif', '.tiff'}


def get_format_type(filepath: str) -> str:
    """Returns 'RAW', 'JPEG', or the uppercase extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in RAW_EXTENSIONS:
        return "RAW"
    elif ext in JPEG_EXTENSIONS:
        return "JPEG"
    elif ext == '.png':
        return "PNG"
    elif ext == '.heic':
        return "HEIC"
    elif ext in {'.tif', '.tiff'}:
        return "TIFF"
    return ext.upper().replace('.', '')
