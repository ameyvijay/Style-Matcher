from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

# Internal Imports
from models import BatchTarget
from processor import run_batch_processing

app = FastAPI(title="Antigravity AI Engine", description="Massive Parallel Image Batch Processor")

# Allow web interface to communicate seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Secure Local AI OpenCV modular engine online"}

@app.post("/api/batch-process")
def process_batch(request: BatchTarget):
    # Security Validation
    if not os.path.exists(request.target_folder):
        raise HTTPException(status_code=400, detail="Target folder could not be mapped locally. Check Docker mounts.")
        
    try:
        return run_batch_processing(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
