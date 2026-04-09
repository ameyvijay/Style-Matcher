# Technical Design Document: AI Batch Image Studio

## 1. System Architecture Overview

The AI Batch Image Studio operates on a completely decoupled **Microservices Architecture** hosted inside a local Docker network sandbox. It bridges web-based configurations dynamically with native machine-level python binaries.

### Microservice Orchestration
- **Service A (Frontend):** `Next.js 16.2.2 (Turbopack)` wrapped natively in a `node:20-alpine` environment exposed on port `3001`. Handles all State, user configurations, and visual feedback mapping.
- **Service B (Backend):** `Python 3.10-slim` wrapper operating a `FastAPI` instance exposed on port `8000`. Acts as the powerhouse executing OpenCV binary matrices, perceptual hashes, and File I/O operations without crushing the Node.js event loop.
- **Hypervisor Networking:** Both engines communicate seamlessly via internal REST requests over `localhost`. 

---

## 2. File Systems & Volume Mounting

To execute logic against local Mac files without uploading gigabytes of `.ARW` (RAW) formats into the container memory dynamically, we execute a **1:1 Strict Absolute Bind Mount** inside `docker-compose.yml`:
```yaml
volumes:
  - /Users/Amey:/Users/Amey
```
When the Frontend sends a string indicating `/Users/Amey/Desktop/Directory`, the Python container physically intercepts that *exact* identical native path mapping natively, preventing massive memory duplication.

> [!TIP]
> **Delta Architecture (Incremental States)** 
> The system is heavily idempotent. It scans the dynamic directory for existing `Creatively edited by AI` and `Rejected` folders. If a file exists in the destination node, `main.py` explicitly issues a `continue` operator, mapping around it. This natively supports dumping new SD card fragments consecutively without breaking or executing duplicate compute!

---

## 3. Computer Vision Constraints (OpenCV)

Relying on LLMs to visually filter images locally is incredibly taxing on RAM. The engine offloads visual diagnostics natively to pure Mathematical Logic pipelines using `cv2`:

### Blur Rejection Algorithm
- **Mechanism:** `Variance of the Laplacian`.
- **Logic:** The image is natively pushed down to greyscale to isolate pure pixel bounds avoiding color abstraction. `cv2.Laplacian(gray, cv2.CV_64F).var()` executes a fast-fourier variance. Low variance heavily indicates a lack of edge detection (out-of-focus blur).

### Structure Deduplication
- **Mechanism:** Block Hashing (Perceptual Hashes).
- **Logic:** Executed via the `imagehash` library. Bypasses metadata spoofing or file manipulation. It assigns hexadecimal boundaries; matching hashes immediately triggers a file rejection avoiding duplicates.

---

## 4. The AI Configurations and Networks

### Benchmark Abstract Vector DB (`.antigravity_benchmark.json`)
Processing huge reference constraints continuously is inefficient. 
- On first execution, the backend extracts the reference metrics natively.
- It caches these metrics invisibly inside the source directory as `.antigravity_benchmark.json`.
- All subsequent runs directly bypass the entire `benchmark` folder checking logic entirely, deserializing the vector graph locally.

### Local Ollama Tunneling (`host.docker.internal:11434`)
Because Ollama operates as a native macOS daemon, trying to hit `localhost:11434` inside a Docker container strictly bounces back natively inside the container itself.
- **Escape Route:** The Next.js frontend pushes the `http://host.docker.internal:11434` environment string logically into the Python REST query. 
- **Execution:** Python utilizes a synchronous `urllib.request` payload, tunneling precisely out of its Docker isolation onto the native Mac IP tables to process the Photo Coaching Report offline using `gemma4` or `llava` interchangeably. 

---

## 5. Metadata Mapping Strategy (XMP & EXIF)

> [!WARNING]
> **RAW Image Laws**  
> We never systematically "edit" or alter `.ARW` bytes directly. 

Our AI diagnostics function entirely on extracted string metadata (`exifread`) filtering out thousands of irrelevant EXIF tags dynamically and trapping exactly the **Exposure Triangle** markers (`EXIF ISOSpeedRatings`, `EXIF ExposureTime`, `EXIF FNumber`, `EXIF FocalLength`). 

We pass this highly condensed JSON block directly to the LLM. Synthesizing these text matrices forces the offline `gemma4` mathematical AI to accurately deduce physical light behavior significantly faster than running multi-modal Base64 visual encoding!
