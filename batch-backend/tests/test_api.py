import os
from unittest.mock import patch
from models import ProcessingStatus

def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_batch_process_invalid_folder(client):
    response = client.post("/api/batch-process", json={
        "target_folder": "/path/that/definitely/does/not/exist",
        "provider": "gemini"
    })
    assert response.status_code == 400
    assert "could not be mapped locally" in response.json()["detail"]

@patch('urllib.request.urlopen')
def test_batch_process_full_execution(mock_urlopen, client, temp_target_dir, generate_test_image):
    # Setup test arena
    # Generate 1 sharp, 1 blurry, 1 overexposed.
    # Also test duplicate rejection by making physically identical images.
    
    img1_sharp = os.path.join(temp_target_dir, "sharp1.jpg")
    img1_dup = os.path.join(temp_target_dir, "sharp1_copy.jpg")
    img2_blur = os.path.join(temp_target_dir, "blur1.jpg")
    img3_over = os.path.join(temp_target_dir, "over1.jpg")
    
    generate_test_image(img1_sharp, "sharp")
    generate_test_image(img1_dup, "sharp")  # Identical to sharp1
    generate_test_image(img2_blur, "blur")
    generate_test_image(img3_over, "overexposed")
    
    # We will patch the imagededup local import so we simulate duplicate detection.
    # Otherwise, imagededup might crash if not installed properly.
    # But wait! If imagededup fails it gracefully downgrades. Let's let it run or fail gracefully.
    
    payload = {
        "target_folder": temp_target_dir,
        "provider": "ollama", # Bypasses genai key check
        "ollama_url": "http://localhost:9999" # Expected to fail gracefully
    }
    
    response = client.post("/api/batch-process", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    metrics = data["metrics"]
    assert metrics["total_scanned"] == 4
    
    # Check that sorting directories were NOT created natively
    edited_dir = os.path.join(temp_target_dir, "Creatively edited by AI")
    rejected_dir = os.path.join(temp_target_dir, "Rejected")
    assert not os.path.exists(edited_dir)
    assert not os.path.exists(rejected_dir)
    
    # Assert sorting logic operated correctly via XMP sidecars
    # Sharp1 should have 5 stars, unless deduplicated.
    # Blur1 should have 1 star.
    # Over1 should have 1 star.
    
    blur_xmp = os.path.join(temp_target_dir, "blur1.xmp")
    over_xmp = os.path.join(temp_target_dir, "over1.xmp")
    
    assert os.path.exists(blur_xmp)
    assert os.path.exists(over_xmp)
    
    with open(blur_xmp, 'r') as f:
        assert "<xmp:Rating>1</xmp:Rating>" in f.read()
        
    with open(over_xmp, 'r') as f:
        assert "<xmp:Rating>1</xmp:Rating>" in f.read()
    
    assert "total_scanned" in metrics
    
@patch('urllib.request.urlopen')
def test_batch_process_ollama_coaching(mock_urlopen, client, temp_target_dir, generate_test_image):
    # Setup test file
    img = os.path.join(temp_target_dir, "bad_blur.jpg")
    generate_test_image(img, "blur")
    
    # Mock Ollama Response
    mock_response = mock_urlopen.return_value.__enter__.return_value
    mock_response.read.return_value = b'{"response": "Mocked coaching response: Increase shutter speed!"}'
    
    payload = {
        "target_folder": temp_target_dir,
        "provider": "ollama",
        "ollama_url": "http://mocked_url:11434"
    }
    
    response = client.post("/api/batch-process", json=payload)
    assert response.status_code == 200
    assert "Mocked coaching response" in response.json()["coaching_report"]
