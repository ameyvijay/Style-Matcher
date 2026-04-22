import sqlite3
import os

DB_PATH = "batch-backend-v2/mlops_registry.db"

def seed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    models = [
        ('nima_v1', 'heuristics', 1, 'musiq+clipiqa'),
        ('clip_vit_b32', 'embedding', 1, 'openai/clip'),
        ('ollama_vlm', 'vlm', 1, 'moondream:latest')
    ]
    
    for name, m_type, is_prod, arch in models:
        try:
            cursor.execute("""
                INSERT INTO table_models (name, model_type, is_production, architecture, status) 
                VALUES (?, ?, ?, ?, 'production')
            """, (name, m_type, is_prod, arch))
            print(f"✅ Seeded model: {name}")
        except sqlite3.IntegrityError:
            print(f"ℹ️ Model already exists: {name}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    seed()
