import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Get the absolute path to the backend directory
backend_path = os.path.abspath("batch-backend-v2")
sys.path.insert(0, backend_path)

print(f"DEBUG: sys.path[0] = {sys.path[0]}")

try:
    from database import Base, ModelRegistry, Inference, Media, Annotation, DatasetSnapshot
    print("✅ Successfully imported database models.")
    
    # Trigger mapper initialization
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    print("✅ Successfully initialized mappers and created schema.")
    
except Exception as e:
    import traceback
    print("❌ Failed to initialize mappers:")
    traceback.print_exc()
