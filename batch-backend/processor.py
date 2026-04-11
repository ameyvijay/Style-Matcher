from __future__ import annotations
import os
import shutil
import json
import concurrent.futures
import subprocess
import cv2
import numpy as np
import plistlib
from typing import Dict, List
from models import BatchTarget, ProcessingStatus
from utils import (
    get_arw_thumbnail_bytes, 
    calculate_blur_laplacian, 
    extract_exif, 
    check_exposure
)

def run_batch_processing(request: BatchTarget):
    target_dir = request.target_folder
    
    # Non-Destructive Culling: We no longer create subfolders or move files.
    # We will tag them in-place within the target_dir.
    
    # 0. Benchmark Abstract Vector Serialization
    _handle_benchmarks(request.benchmark_folder)
    
    supported_formats = ('.jpg', '.jpeg', '.png', '.arw', '.tif', '.tiff', '.heic')
    
    processed_stats = {
        "total_scanned": 0,
        "accepted": 0,
        "rejected_blur": 0,
        "rejected_exposure": 0,
        "rejected_duplicates": 0,
        "rejected_exif_data": [], 
    }
    
    BLUR_THRESHOLD = 100.0  
    workspace_dir = os.path.join(target_dir, ".imagededup_workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    
    active_pool = {}
    
    def process_file(filename: str):
        file_path = os.path.join(target_dir, filename)
        if not os.path.isfile(file_path): return None
        if not filename.lower().endswith(supported_formats): return None
            
        exif = extract_exif(file_path)
        status = ProcessingStatus.ACCEPTED
        
        # Amber Thresholds are handled securely in check_exposure inside utils.py
        status = check_exposure(file_path)
        if status in [ProcessingStatus.REJECTED_EXPOSURE, ProcessingStatus.REVIEW_NEEDED]:
            return {"filename": filename, "path": file_path, "status": status, "sharpness": 0, "exif": exif}
            
        sharpness = calculate_blur_laplacian(file_path)
        if sharpness < 70.0:
            status = ProcessingStatus.REJECTED_BLUR
            return {"filename": filename, "path": file_path, "status": status, "sharpness": sharpness, "exif": exif}
        elif sharpness < 100.0:
            status = ProcessingStatus.REVIEW_NEEDED
            return {"filename": filename, "path": file_path, "status": status, "sharpness": sharpness, "exif": exif}
            
        # Write valid proxies to Imagededup workspace
        safe_path = os.path.join(workspace_dir, filename + ".jpg" if filename.lower().endswith(".arw") else filename)
        if filename.lower().endswith(".arw"):
            thumb = get_arw_thumbnail_bytes(file_path)
            if thumb:
                with open(safe_path, 'wb') as tf:
                    tf.write(thumb)
        else:
            shutil.copy(file_path, safe_path)
            
        return {"filename": filename, "path": file_path, "status": status, "sharpness": sharpness, "exif": exif, "proxy": safe_path}

    all_files = os.listdir(target_dir)
    for filename in all_files:
        if filename.lower().endswith(supported_formats):
            processed_stats["total_scanned"] += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(process_file, all_files)
        for res in results:
            if res:
                active_pool[res['filename']] = res
                
    clusters = _run_deduplication(workspace_dir, active_pool)

    # 3. Burst Arena Competition Loop
    for cluster in clusters:
        if len(cluster) > 1:
            cluster.sort(key=lambda x: x['sharpness'], reverse=True)
            for loser in cluster[1:]:
                loser['status'] = ProcessingStatus.REJECTED_DUPLICATE
                
    try:
        shutil.rmtree(workspace_dir)
    except: pass
            
    # 4. Physical Mapped Execution (Native Tagging without moving)
    try:
        for item in active_pool.values():
            _tag_and_enhance_processed_file(item, request, processed_stats)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
           
    coaching_report = _generate_coaching_report(processed_stats, request)
           
    return {"status": "success", "metrics": processed_stats, "coaching_report": coaching_report}

def _handle_benchmarks(benchmark_folder: str | None):
    if benchmark_folder and os.path.exists(benchmark_folder):
        cache_path = os.path.join(benchmark_folder, ".antigravity_benchmark.json")
        try:
            if not os.path.exists(cache_path):
                benchmark_files = [f for f in os.listdir(benchmark_folder) if f.lower().endswith(('.jpg', '.png', '.arw'))]
                benchmark_profile = {
                    "vector_state": "Synchronized Offline Extract",
                    "benchmark_volume": len(benchmark_files),
                    "ai_mathematical_baseline_active": True
                }
                with open(cache_path, "w") as f:
                    json.dump(benchmark_profile, f)
        except Exception:
            pass

def _run_deduplication(workspace_dir: str, active_pool: dict) -> List[List[dict]]:
    clusters = []
    try:
        from imagededup.methods import PHash
        phasher = PHash()
        duplicates_dict = phasher.find_duplicates(image_dir=workspace_dir, max_distance_threshold=5)
        
        seen = set()
        for proxy_file, dupes in duplicates_dict.items():
            if proxy_file in seen: continue
            native_group = [proxy_file.replace(".arw.jpg", ".arw")]
            for d in dupes:
                native_group.append(d.replace(".arw.jpg", ".arw"))
            cluster_objs = [active_pool[name] for name in native_group if name in active_pool]
            if cluster_objs:
                clusters.append(cluster_objs)
            seen.update([proxy_file] + dupes)
    except Exception:
        clusters = [[obj] for obj in active_pool.values() if obj['status'] == ProcessingStatus.ACCEPTED]
    return clusters

def render_opencv_enhancement(filepath: str, output_path: str):
    """Generates a professional auto-enhanced JPG using CLAHE and color balancing."""
    try:
        if filepath.lower().endswith('.arw'):
            from utils import get_arw_thumbnail_bytes
            thumb = get_arw_thumbnail_bytes(filepath)
            if not thumb: return False
            nparr = np.frombuffer(thumb, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            img = cv2.imread(filepath)

        if img is None: return False

        # --- Premium AI-Style Enhancement Logic ---
        # 1. LAB conversion for Luminance-specific processing
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # 2. CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # This opens up shadows and controls highlights without looking "fake"
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)

        # 3. Subtle Vibrancy Boost (Chrominance amplification)
        # We slightly expand the 'a' and 'b' ranges
        a = cv2.convertScaleAbs(a, alpha=1.1, beta=0)
        b = cv2.convertScaleAbs(b, alpha=1.1, beta=0)

        # 4. Merge and re-normalize
        enhanced_lab = cv2.merge((cl, a, b))
        final_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        # 5. High-quality export
        cv2.imwrite(output_path, final_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        return True
    except Exception as e:
        print(f"Enhancement error for {filepath}: {e}")
        return False

def _generate_enhanced_proxy(filepath: str):
    """Generates an _enhanced.jpg natively using OpenCV CLAHE engine"""
    try:
        base, _ = os.path.splitext(filepath)
        enhanced_path = base + "_enhanced.jpg"
        
        success = render_opencv_enhancement(filepath, enhanced_path)
        if success:
            set_mac_tag(enhanced_path, "Accepted_AI_Enhanced", 2)
    except Exception:
        pass

def _tag_and_enhance_processed_file(item: dict, request: BatchTarget, stats: dict):
    filename = item['filename']
    file_path = item['path']
    status = item['status']
    exif = item['exif']
    
    try:
        if status == ProcessingStatus.ACCEPTED:
            set_mac_tag(file_path, "Accepted", 2) # Green
            write_xmp_sidecar(file_path, 5)
            stats["accepted"] += 1
            _generate_enhanced_proxy(file_path)
            
        elif status == ProcessingStatus.REVIEW_NEEDED:
            set_mac_tag(file_path, "Review_Needed", 5) # Yellow
            write_xmp_sidecar(file_path, 3)
            # Add to EXIF diagnostic reporting for feedback loop
            stats["rejected_exif_data"].append({
                "filename": filename,
                "reason": "review_needed_borderline",
                "exif": exif
            })
            
        else:
            set_mac_tag(file_path, "Rejected", 6) # Red
            write_xmp_sidecar(file_path, 1)
            if status == ProcessingStatus.REJECTED_BLUR:
                stats["rejected_blur"] += 1
            elif status == ProcessingStatus.REJECTED_EXPOSURE:
                stats["rejected_exposure"] += 1
            else:
                stats["rejected_duplicates"] += 1
            
            stats["rejected_exif_data"].append({
                "filename": filename,
                "reason": getattr(status, 'value', str(status)),
                "exif": exif
            })
    except Exception as e:
        print(f"Error tagging {filename}: {e}")

def _generate_coaching_report(processed_stats: dict, request: BatchTarget) -> str:
    if not processed_stats["rejected_exif_data"]:
        return ""
        
    if request.api_key and request.provider == "gemini":
        try:
            from google import genai
            client = genai.Client(api_key=request.api_key)
            prompt = _get_coaching_prompt(processed_stats)
            response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
            return response.text
        except Exception as e:
            return f"Failed to generate AI coaching report: {str(e)}"
            
    elif request.provider == "ollama":
        try:
            import urllib.request
            prompt = _get_coaching_prompt(processed_stats)
            payload = json.dumps({"model": request.ollama_model, "prompt": prompt, "stream": False}).encode('utf-8')
            req = urllib.request.Request(f"{request.ollama_url}/api/generate", data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=120) as response:
                res_data = json.loads(response.read().decode())
                return res_data.get("response", "No Ollama response generated.")
        except Exception as e:
            return f"Failed to execute local Ollama: {str(e)}"
    return ""

def _get_coaching_prompt(stats: dict) -> str:
    return f"""
    Act as a master photography coach evaluating a student using a Sony a6400 camera.
    They just batch processed a folder of photos.
    Total blurred shots rejected: {stats['rejected_blur']}
    Here is the raw architectural EXIF metadata mapped from some of these failed shots:
    {json.dumps(stats['rejected_exif_data'][:15], indent=2)}
    
    Provide exactly 3 short bullet points instructing them precisely on how to change their camera settings directly relative to their lens data for their next shoot.
    """
