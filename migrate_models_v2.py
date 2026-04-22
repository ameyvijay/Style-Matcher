import sqlite3
import os

DB_PATH = "batch-backend-v2/mlops_registry.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("Migrating table_models to v2 schema...")
        
        # New columns with safe defaults
        columns = [
            ("ollama_tag", "TEXT"),
            ("architecture", "TEXT"),
            ("param_count_b", "REAL"),
            ("quantization", "TEXT"),
            ("parent_model_id", "INTEGER"),
            ("lineage_type", "TEXT"),
            ("lora_adapter_path", "TEXT"),
            ("status", "TEXT DEFAULT 'candidate'"),
            ("vram_mb", "INTEGER"),
            ("tokens_per_sec", "REAL"),
            ("golden_accuracy", "REAL"),
            ("eval_report", "TEXT"),
            ("promoted_at", "DATETIME"),
            ("retired_at", "DATETIME")
        ]

        for col_name, col_type in columns:
            try:
                cursor.execute(f"ALTER TABLE table_models ADD COLUMN {col_name} {col_type};")
                print(f"Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"Column {col_name} already exists.")
                else:
                    raise e

        # Initialize existing models as 'production' if they were already in the registry
        cursor.execute("UPDATE table_models SET status = 'production' WHERE status IS NULL OR status = 'candidate';")
        
        # Seed Moondream metadata if it's there
        cursor.execute("UPDATE table_models SET architecture = 'moondream', ollama_tag = 'moondream:latest', param_count_b = 1.8 WHERE name = 'moondream';")

        conn.commit()
        print("Migration successful.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
