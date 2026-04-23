import os
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, backref
from sqlalchemy.sql import func

# Initialize Base and Engine
# Using SQLite locally. Can easily swap "sqlite:///..." with "postgresql://..." later
DB_PATH = os.path.join(os.path.dirname(__file__), "mlops_registry.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 15},
)

# Enable WAL mode so the Firestore callback thread and FastAPI request threads
# can read/write concurrently without "Database is locked" errors.
from sqlalchemy import event as _sa_event

@_sa_event.listens_for(engine, "connect")
def _set_sqlite_wal(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Media(Base):
    """
    Immutable source of truth. The original RAW or JPEG files.
    """
    __tablename__ = 'table_media'

    id = Column(Integer, primary_key=True, index=True)
    photo_hash = Column(String(64), unique=True, index=True, nullable=False)
    file_path = Column(Text, nullable=False)           # Absolute path to the immutable read-only original
    source_node = Column(String(100), default="local_m4") # For Tailscale/NAS future-proofing
    
    # Logical Role (Partitioning)
    # 'rag', 'golden', 'benchmark', 'audit_shadow'
    logical_role = Column(String(50), default='rag', index=True)
    is_manual_entry = Column(Boolean, default=False)
    
    proxy_path = Column(Text, nullable=True)           # Path to lightweight extracted JPEG for models to use
    enhanced_path = Column(Text, nullable=True)        # Path to AI Enhanced version (ESRGAN/Color bumped)
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    format = Column(String(10), nullable=True)
    capture_date = Column(DateTime, nullable=True)
    added_at = Column(DateTime, default=func.now())

    inferences = relationship("Inference", back_populates="media")
    annotations = relationship("Annotation", back_populates="media")


class ModelRegistry(Base):
    """
    Registry of AI Models (Base models and fine-tuned LoRAs).
    """
    __tablename__ = 'table_models'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # e.g., "moondream", "lora_v1"
    model_type = Column(String(50), nullable=False)          # e.g., "heuristics", "vlm", "lora_weights"
    is_production = Column(Boolean, default=False)
    
    # ── Model Agility v2 ──
    ollama_tag = Column(Text, nullable=True)                 # "moondream:latest", "llava:13b"
    architecture = Column(Text, nullable=True)               # "moondream", "llava"
    param_count_b = Column(Float, nullable=True)             # 1.8, 7.0, 13.0
    quantization = Column(Text, nullable=True)               # "q4_K_M", "q8_0"
    
    parent_model_id = Column(Integer, ForeignKey('table_models.id'), nullable=True)
    lineage_type = Column(String(50), nullable=True)         # "base", "lora_finetune"
    lora_adapter_path = Column(Text, nullable=True)          # /path/to/adapter.gguf
    
    status = Column(String(20), default='candidate', nullable=False) # 'candidate', 'production', 'retired'
    
    # ── Resource & Quality KPIs ──
    vram_mb = Column(Integer, nullable=True)
    tokens_per_sec = Column(Float, nullable=True)
    golden_accuracy = Column(Float, nullable=True)
    eval_report = Column(Text, nullable=True)                # JSON blob
    
    created_at = Column(DateTime, default=func.now())
    promoted_at = Column(DateTime, nullable=True)
    retired_at = Column(DateTime, nullable=True)

    inferences = relationship("Inference", back_populates="model")


class PromptVersion(Base):
    """
    System and User prompt versioning for VLM supervision.
    """
    __tablename__ = 'table_prompt_versions'

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(50), unique=True, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    template_hash = Column(String(64), nullable=False)
    
    # 'draft' | 'testing' | 'production' | 'retired'
    status = Column(String(20), default='draft', nullable=False)
    is_production = Column(Boolean, default=False, nullable=False)
    
    author = Column(String(50), default='system', nullable=False)
    parent_version = Column(String(50), ForeignKey('table_prompt_versions.version'), nullable=True)
    change_notes = Column(Text, nullable=True)
    
    total_inferences = Column(Integer, default=0, nullable=False)
    golden_success_rate = Column(Float, nullable=True)
    training_success_rate = Column(Float, nullable=True)
    avg_confidence = Column(Float, nullable=True)
    avg_processing_ms = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    promoted_at = Column(DateTime, nullable=True)
    retired_at = Column(DateTime, nullable=True)

    inferences = relationship("Inference", back_populates="prompt")


class Inference(Base):
    """
    AI Outputs (Scores, Labels, and Latent Embeddings/Feature Store).
    """
    __tablename__ = 'table_inferences'

    id = Column(Integer, primary_key=True, index=True)
    media_id = Column(Integer, ForeignKey('table_media.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('table_models.id'), nullable=False)
    prompt_version = Column(String(50), ForeignKey('table_prompt_versions.version'), nullable=True)
    
    # Store string labels, JSON dicts, or comma separated tags
    inference_value = Column(Text, nullable=True)
    
    # Vector Embedding Blob (Feature Store logic)
    embedding_blob = Column(Text, nullable=True) 
    
    confidence = Column(Float, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    media = relationship("Media", back_populates="inferences")
    model = relationship("ModelRegistry", back_populates="inferences")
    prompt = relationship("PromptVersion", back_populates="inferences")


class Annotation(Base):
    """
    Human Truth (RLHF Swipes).
    """
    __tablename__ = 'table_annotations'

    id = Column(Integer, primary_key=True, index=True)
    media_id = Column(Integer, ForeignKey('table_media.id'), nullable=False)
    user_id = Column(String(50), nullable=False)       # For multi-user Cohen's Kappa checks
    
    # E.g., 'swipe_right_keeper', 'swipe_left_cull', 'rescue'
    action = Column(String(50), nullable=False)
    
    # Any textual additions the user made (e.g. tagging 'vacation')
    custom_tags = Column(Text, nullable=True)

    # ── Visual RAG Telemetry (Phase B) ──────────────────────────────
    # JSON-serialised EXIF snapshot captured at swipe time (genre, ISO, focal length, etc.)
    exif_snapshot = Column(Text, nullable=True)
    # FK reference to the ChromaDB / table_inferences embedding that was active at swipe time
    embedding_id = Column(Integer, nullable=True)
    # Milliseconds from card render to swipe gesture — UX confidence signal
    swipe_duration_ms = Column(Integer, nullable=True)
    # Computed certainty weight for RLHF dataset balancing (0.0 uncertain → 1.0 definitive)
    confidence_weight = Column(Float, nullable=True)

    # ── Manual Override Telemetry (Admin / HiLT correction layer) ───
    # True when a human manually adjusted one or more AI scores before swiping
    is_manual_override = Column(Boolean, default=False, nullable=False)
    # JSON dict storing {"original": {...}, "updated": {...}} score deltas
    score_delta = Column(Text, nullable=True)

    timestamp = Column(DateTime, default=func.now())

    media = relationship("Media", back_populates="annotations")


class DatasetSnapshot(Base):
    """
    Immutable dataset snapshots for training and evaluations.
    """
    __tablename__ = 'table_dataset_snapshots'

    id = Column(Integer, primary_key=True, index=True)
    snapshot_version = Column(String(50), unique=True, nullable=False) # e.g. "dataset_v1.0"
    purpose = Column(String(20), nullable=False)                      # 'train', 'eval', 'test_golden'
    
    # Lineage Metadata
    parent_snapshot_id = Column(Integer, ForeignKey('table_dataset_snapshots.id'), nullable=True)
    model_id = Column(Integer, ForeignKey('table_models.id'), nullable=True)
    prompt_version = Column(String(50), ForeignKey('table_prompt_versions.version'), nullable=True)
    
    # JSON list of media_ids locked in this snapshot. 
    # Use JSON to prevent needing a massive associative table for millions of photos.
    media_id_list = Column(Text, nullable=False) 
    created_at = Column(DateTime, default=func.now())


class SyncQueue(Base):
    """
    Mandate 1 Durable Storage Spool: Handles isolated TrueNAS synchronization tracking.
    """
    __tablename__ = 'table_sync_queue'

    id = Column(Integer, primary_key=True, index=True)
    enhanced_dir_path = Column(Text, unique=True, nullable=False)
    status = Column(String(20), default="PENDING")  # PENDING, SYNCING, COMPLETED, FAILED
    retry_count = Column(Integer, default=0)
    last_attempt_timestamp = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())


def init_db():
    """Initializes the database entirely, creating tables if they don't exist."""
    print(f"Initializing database at {DATABASE_URL}")
    Base.metadata.create_all(bind=engine)

def get_db():
    """Generator for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Base database models initialized successfully.")
