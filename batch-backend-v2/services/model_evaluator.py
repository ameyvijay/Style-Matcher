import asyncio
import json
import time
import psutil
import subprocess
import httpx
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from database import ModelRegistry, DatasetSnapshot, Inference, Media, Annotation
from vision_analyst import VisionAnalyst
from config import SYSTEM_TOTAL_RAM_GB, SAFE_VLM_MAX_GB, HEADROOM_GB, MEMORY_GATE_THRESHOLD_PCT

# Shared Evaluation Lock for all heavy model ops
_EVAL_LOCK = asyncio.Lock()

class ResourceReport:
    """Captured during Golden Set evaluation."""
    def __init__(self):
        self.vram_before_mb = 0
        self.vram_after_mb = 0
        self.vram_peak_mb = 0
        self.vram_delta_mb = 0
        self.tokens_per_sec = 0.0
        self.p50_latency_ms = 0.0
        self.p95_latency_ms = 0.0
        self.thermal_throttle_events = 0
        self.total_eval_time_sec = 0.0
        self.images_evaluated = 0

    def passed_hard_gates(self) -> bool:
        """Thresholds derived from SYSTEM_TOTAL_RAM_GB."""
        return (
            self.vram_delta_mb <= SAFE_VLM_MAX_GB * 1024 and 
            self.vram_peak_mb <= (SYSTEM_TOTAL_RAM_GB - HEADROOM_GB) * 1024 and 
            self.p95_latency_ms <= 15000
        )

class ModelEvaluatorService:
    def __init__(self, db: Session):
        self.db = db
        self.ollama_url = "http://127.0.0.1:11434"

    async def _evict_all_models(self):
        """Phase 1: Clear the deck for the M4."""
        print("🧹 [Evaluator] Evicting all Ollama models...")
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{self.ollama_url}/api/tags", timeout=2.0)
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    for m in models:
                        await client.post(f"{self.ollama_url}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=2.0)
            
            # Mandated 3-second kernel reclaim pause
            await asyncio.sleep(3.0)
        except Exception as e:
            print(f"⚠️ Eviction error: {e}")

    def _get_thermal_state(self) -> str:
        try:
            result = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, timeout=2)
            for line in result.stdout.splitlines():
                if "CPU_Speed_Limit" in line:
                    limit = int(line.split("=")[1].strip())
                    if limit >= 95: return "Nominal"
                    if limit >= 80: return "Fair"
                    if limit >= 60: return "Serious"
                    return "Critical"
        except: pass
        return "Unknown"

    async def run_comparative_eval(self, candidate_tag: str, snapshot_version: str) -> Dict:
        """The Serial Handoff Protocol Orchestrator."""
        async with _EVAL_LOCK:
            # 1. Pre-flight Check
            prod_model = self.db.query(ModelRegistry).filter(ModelRegistry.status == 'production', ModelRegistry.model_type == 'vlm').first()
            prod_tag = prod_model.ollama_tag if prod_model else "moondream:latest"
            
            snapshot = self.db.query(DatasetSnapshot).filter(DatasetSnapshot.snapshot_version == snapshot_version).first()
            if not snapshot: 
                return {"error": "Snapshot not found"}
            
            # 2. Production Run
            await self._evict_all_models()
            if psutil.virtual_memory().percent > MEMORY_GATE_THRESHOLD_PCT:
                return {"error": f"Memory pressure too high ({psutil.virtual_memory().percent}%) even after eviction."}
                
            prod_resources, prod_results = await self._evaluate_model(prod_tag, snapshot)
            
            # 3. Candidate Run
            await self._evict_all_models()
            if psutil.virtual_memory().percent > MEMORY_GATE_THRESHOLD_PCT:
                return {"error": "Memory pressure too high before candidate load."}
            
            cand_resources, cand_results = await self._evaluate_model(candidate_tag, snapshot)
            
            # 4. Final Cleanup
            await self._evict_all_models()
            
            # 5. Build Verdict
            verdict = self._compute_upgrade_verdict(prod_results['accuracy'], cand_results['accuracy'], prod_resources, cand_resources)
            
            return {
                "verdict": verdict,
                "production": {
                    "tag": prod_tag, 
                    "accuracy": prod_results['accuracy'], 
                    "resources": prod_resources.__dict__
                },
                "candidate": {
                    "tag": candidate_tag, 
                    "accuracy": cand_results['accuracy'], 
                    "resources": cand_resources.__dict__
                }
            }

    async def _evaluate_model(self, tag: str, snapshot: DatasetSnapshot) -> Tuple[ResourceReport, dict]:
        report = ResourceReport()
        report.vram_before_mb = psutil.virtual_memory().used / (1024 * 1024)
        
        media_ids = json.loads(snapshot.media_id_list)[:30] # Cap for speed
        results = []
        analyst = VisionAnalyst(model=tag)
        
        start_eval = time.time()
        
        for idx, m_id in enumerate(media_ids):
            mem_curr = psutil.virtual_memory().used / (1024 * 1024)
            report.vram_peak_mb = max(report.vram_peak_mb, mem_curr)
            
            if idx == 1: # Capture load delta after first inference
                report.vram_after_mb = mem_curr
                report.vram_delta_mb = report.vram_after_mb - report.vram_before_mb
            
            if self._get_thermal_state() in ["Serious", "Critical"]:
                report.thermal_throttle_events += 1

            media = self.db.query(Media).filter(Media.id == m_id).first()
            annotation = self.db.query(Annotation).filter(Annotation.media_id == m_id).first()
            if not media or not annotation: continue

            start_t = time.time()
            res = analyst.analyze_image(media.proxy_path or media.file_path)
            duration_ms = (time.time() - start_t) * 1000
            
            # Accuracy Check (Simplified keyword match for MVP)
            desc = res['description'].lower()
            decision = "keeper" if any(x in desc for x in ["keep", "great", "excellent", "portfolio"]) else "cull"
            human = "keeper" if "keeper" in annotation.action else "cull"
            
            results.append({
                "latency": duration_ms,
                "correct": decision == human,
                "tokens": len(res['description'].split())
            })
            report.images_evaluated += 1

        report.total_eval_time_sec = time.time() - start_eval

        # Aggregates
        if results:
            latencies = sorted([r['latency'] for r in results])
            report.p50_latency_ms = latencies[len(latencies)//2]
            report.p95_latency_ms = latencies[int(len(latencies)*0.95)]
            report.tokens_per_sec = sum(r['tokens'] for r in results) / (sum(r['latency'] for r in results) / 1000)
            
        summary = {
            "accuracy": sum(1 for r in results if r['correct']) / len(results) if results else 0,
            "count": len(results)
        }
        
        return report, summary

    def _compute_upgrade_verdict(self, prod_acc, cand_acc, prod_repo, cand_repo) -> dict:
        accuracy_delta = cand_acc - prod_acc
        latency_ratio = cand_repo.p95_latency_ms / max(prod_repo.p95_latency_ms, 1)
        
        # Hard gates
        if not cand_repo.passed_hard_gates():
            return {"verdict": "REJECT", "reason": "Hardware limits exceeded (VRAM/Latency)"}
        
        if cand_acc < prod_acc:
            return {"verdict": "REJECT", "reason": "Accuracy regression"}
        
        # Efficiency Score
        efficiency = accuracy_delta / max(latency_ratio, 0.1)
        
        if accuracy_delta >= 0.05 and latency_ratio <= 2.0:
            return {"verdict": "PROMOTE", "reason": "Significant gain with acceptable cost", "efficiency": round(efficiency, 4)}
            
        if accuracy_delta >= 0.10:
            return {"verdict": "PROMOTE_WITH_WARNING", "reason": f"Major gain (+{accuracy_delta:.1%}) justifies {latency_ratio:.1f}x latency"}

        return {"verdict": "NO_DIFFERENCE", "reason": "Insufficient gain to justify resource cost"}
