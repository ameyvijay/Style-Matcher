import os
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func

# Initialize Base and Engine
# Using SQLite locally. Can easily swap "sqlite:///..." with "postgresql://..." later
DB_PATH = os.path.join(os.path.dirname(__file__), "mlops_registry.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
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
    name = Column(String(100), unique=True, nullable=False)  # e.g., "laplacian_v1", "ollama_llava_v2", "lora_dark_moody_v1.0"
    model_type = Column(String(50), nullable=False)          # e.g., "heuristics", "vlm", "lora_weights"
    is_production = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    inferences = relationship("Inference", back_populates="model")


class Inference(Base):
    """
    AI Outputs (Scores, Labels, and Latent Embeddings/Feature Store).
    """
    __tablename__ = 'table_inferences'

    id = Column(Integer, primary_key=True, index=True)
    media_id = Column(Integer, ForeignKey('table_media.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('table_models.id'), nullable=False)
    
    # Store string labels, JSON dicts, or comma separated tags
    inference_value = Column(Text, nullable=True)
    
    # Vector Embedding Blob (Feature Store logic)
    # In SQLite we use Text or LargeBinary. In Postgres this would be a pgvector Vector() column.
    embedding_blob = Column(Text, nullable=True) 
    
    confidence = Column(Float, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    media = relationship("Media", back_populates="inferences")
    model = relationship("ModelRegistry", back_populates="inferences")


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
    timestamp = Column(DateTime, default=func.now())

    media = relationship("Media", back_populates="annotations")


class DatasetSnapshot(Base):
    """
    Immunitable dataset snapshots for training and evaluations.
    """
    __tablename__ = 'table_dataset_snapshots'

    id = Column(Integer, primary_key=True, index=True)
    snapshot_version = Column(String(50), unique=True, nullable=False) # e.g. "dataset_v1.0"
    purpose = Column(String(20), nullable=False)                      # 'train', 'eval', 'test_golden'
    
    # JSON list of media_ids locked in this snapshot. 
    # Use JSON to prevent needing a massive associative table for millions of photos.
    media_id_list = Column(Text, nullable=False) 
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
