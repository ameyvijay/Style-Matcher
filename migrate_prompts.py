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
        print("Creating table_prompt_versions...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_prompt_versions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            version         TEXT    NOT NULL UNIQUE,
            system_prompt   TEXT    NOT NULL,
            user_prompt     TEXT    NOT NULL,
            template_hash   TEXT    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'draft',
            is_production   INTEGER NOT NULL DEFAULT 0,
            author          TEXT    NOT NULL DEFAULT 'system',
            parent_version  TEXT,
            change_notes    TEXT,
            total_inferences    INTEGER NOT NULL DEFAULT 0,
            golden_success_rate REAL,
            training_success_rate REAL,
            avg_confidence      REAL,
            avg_processing_ms   REAL,
            created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
            promoted_at     DATETIME,
            retired_at      DATETIME,
            FOREIGN KEY(parent_version) REFERENCES table_prompt_versions(version)
        );
        """)

        print("Adding prompt_version column to table_inferences...")
        try:
            cursor.execute("ALTER TABLE table_inferences ADD COLUMN prompt_version TEXT REFERENCES table_prompt_versions(version);")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Column prompt_version already exists.")
            else:
                raise e

        # Initialize with the current production prompt if possible
        # We'll pull from prompt_registry.py as a seed
        print("Seeding initial production prompt (v1.0)...")
        seed_version = "v1.0"
        # Dummy content for now, the app will update this
        cursor.execute("SELECT count(*) FROM table_prompt_versions WHERE version = ?", (seed_version,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO table_prompt_versions (version, system_prompt, user_prompt, template_hash, status, is_production)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (seed_version, "You are an expert photography editor.", "Evaluate this photo for style and technical quality: {placeholders}", "initial_seed_hash", "production", 1))

        conn.commit()
        print("Migration successful.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
