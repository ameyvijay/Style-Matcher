import pytest
from fastapi.testclient import TestClient
import numpy as np
import cv2
import os

# Import the FastAPI app
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app

@pytest.fixture(scope="session")
def client():
    # Use TestClient for API endpoints
    return TestClient(app)

@pytest.fixture
def temp_target_dir(tmp_path):
    # Pytest built-in tmp_path fixture gives a unique temp directory per test function
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    return str(target_dir)

@pytest.fixture
def generate_test_image():
    def _generator(path, img_type="sharp"):
        # Image dimensions
        width, height = 400, 400
        
        if img_type == "sharp":
            # Create a mid-gray image with sharp high-contrast edges (a checkerboard)
            image = np.ones((height, width, 3), dtype=np.uint8) * 128
            image[100:300, 100:300] = 0
            image[150:250, 150:250] = 255
            
        elif img_type == "blur":
            # Create a uniform gray image with no edges
            image = np.ones((height, width, 3), dtype=np.uint8) * 128
            
        elif img_type == "overexposed":
            # Almost pure white
            image = np.ones((height, width, 3), dtype=np.uint8) * 250
            
        elif img_type == "underexposed":
            # Almost pure black
            image = np.ones((height, width, 3), dtype=np.uint8) * 10
            
        else:
            image = np.ones((height, width, 3), dtype=np.uint8) * 128

        # Write out with OpenCV
        cv2.imwrite(path, image)
        return path

    return _generator
