from __future__ import annotations
import os
import cv2
import numpy as np
import exifread
from typing import Dict
from models import ProcessingStatus

def get_arw_thumbnail_bytes(image_path: str):
    """Securely extracts the embedded JPEG from native Sony ARW RAWs without requiring massive RawPy decoders."""
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f)
            if 'JPEGThumbnail' in tags:
                return tags['JPEGThumbnail']
    except Exception:
        pass
    return None

def calculate_blur_laplacian(image_path: str) -> float:
    """Uses OpenCV's variance of the Laplacian to mathematically score image focus/sharpness."""
    if image_path.lower().endswith('.arw'):
        thumb = get_arw_thumbnail_bytes(image_path)
        if not thumb: return 1000.0 # Gracefully bypass if no preview explicitly exists
        nparr = np.frombuffer(thumb, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        # Read ignoring orient / specific color channels for pure structure
        image = cv2.imread(image_path)
        
    if image is None: return 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def extract_exif(image_path: str) -> Dict[str, str]:
    """Securely pulls metadata tags focusing on Exposure, ISO, Shutter, and Camera Model."""
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            filtered = {k: str(v) for k, v in tags.items() if k in [
                'Image Model', 'EXIF ISOSpeedRatings', 
                'EXIF ExposureTime', 'EXIF FNumber',
                'Image Orientation', 'EXIF FocalLength'
            ]}
            return filtered
    except Exception as e:
        return {}

def check_exposure(image_path: str) -> ProcessingStatus:
    """Uses native optical OpenCV luminance matrices to dynamically flag severely underexposed or blown-out photos."""
    try:
        if image_path.lower().endswith('.arw'):
            thumb = get_arw_thumbnail_bytes(image_path)
            if not thumb: return ProcessingStatus.ACCEPTED 
            nparr = np.frombuffer(thumb, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        else:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            
        if img is None: return ProcessingStatus.ACCEPTED
        luminance = np.mean(img)
        # 15 is basically entirely black, 245 is over-blown white
        if luminance < 15.0 or luminance > 245.0:
            return ProcessingStatus.REJECTED_EXPOSURE
        # Amber / Review Zone
        if (15.0 <= luminance < 30.0) or (230.0 < luminance <= 245.0):
            return ProcessingStatus.REVIEW_NEEDED
            
        return ProcessingStatus.ACCEPTED
    except Exception:
        return ProcessingStatus.ACCEPTED
