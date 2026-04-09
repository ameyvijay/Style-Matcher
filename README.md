# AI Image Workbench & Batch Studio

An enterprise-grade, offline-capable Digital Asset Management (DAM) suite built specifically for dynamic photographic styling, high-precision background removal, and massive autonomous offline batch processing natively invoking local OpenCV and LLM/Vision endpoints.

## 🚀 Overview

The system operates across a completely decoupled Docker architecture consisting of two primary components:
1. **Frontend UI Node**: A Next.js (16.2.2) reactive glass-morphic interface handling global environment states (Ollama Local endpoints / Gemini Cloud endpoints) securely.
2. **Backend Engine**: A Python (FastAPI/Uvicorn) pipeline heavily optimized with `opencv-python-headless` and `imagehash`. It executes structural perceptual duplicate detection and mathematically sorts images autonomously, securely breaking out of the container bounds to generate AI Coaching feedback strings.

---

## 🛑 Prerequisites

Before installing the workbench, you must meet the following hardware/software requirements mathematically:
1. **Docker Desktop**: The architecture runs autonomously inside a secure container to prevent polluting your global packages. You must have [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and actively running on your host machine.
2. **Ollama (Optional but Recommended)**: If you desire 100% offline security, install [Ollama](https://ollama.com/) locally to evaluate your photo configurations.

---

## 🛠 Installation Playbook

Because the system is thoroughly containerized natively, installation universally boils down to a single master command!

### Step 1: Open the Project
Open your Terminal and navigate directly into the root folder containing the `docker-compose.yml` file.

### Step 2: Build the Container System
Execute the global Docker instantiation command. This compiles both the `web` and `backend` images seamlessly:
```bash
docker compose up -d --build
```
*(Note: If you run into `command not found` on a Mac despite having Docker Desktop open, ensure you map your binaries by executing: `export PATH=$PATH:/Applications/Docker.app/Contents/Resources/bin` first).*

### Step 3: Verify the Status
Wait for the daemon layers to compile! Once it finishes, you should see:
- `Container style-matcher-backend-1 Started`
- `Container style-matcher-web-1 Started`

---

## 🖥 Usage Guide

### 1. Accessing the Dashboard
Open your local browser to **http://localhost:3001**.
You will see the global Next.js interface!

### 2. Configuration Parameters
Directly on the homepage, scroll specifically down to **Global AI Settings**:
- Select whether you want to use **Gemini (Cloud)** or **Ollama (Local)**.
- Paste your API key or configure your `Ollama Default Model URL` exactly as `http://host.docker.internal:11434` (This network structure is required for the Docker container to seamlessly contact your local Mac hardware out of the sandbox).

### 3. Assign your Benchmark Directory
Pass the literal absolute path of your best curated edited photos (e.g., `/Users/Amey/Desktop/MyBestPhotos`) to the **Global Benchmark Directory** field on the settings page!
- *What this does:* When the Backend processes files, it securely hashes an AI representation array of your specific benchmark folder into a secret `.antigravity_benchmark.json` file protecting your CPU against repetitive metadata abstractions seamlessly!

### 4. Running the Batch Studio
Navigate to the **AI Batch Studio**. 
- Simply provide the absolute path mapping dynamically to any folder holding your un-curated RAWs or JPGs.
- Click **Execute AI Batch Engine**.
- The script uses 1:1 volume mounts structurally enabling the system to evaluate your native Mac folders directly! It mathematically isolates blurry files via **Laplacian Operations** and creates `[Creatively edited by AI]` and `[Rejected]` folders flawlessly.

---

## 💡 Troubleshooting

- **"Target folder could not be mapped locally"**: Ensure the path you passed dynamically is typed as an exact absolute path matching exactly where your folders sit locally (e.g., `/Users/your_name/Downloads/folder`).
- **Ollama Fails to Respond**: Ensure the Ollama App is physically running in your background tray and the model name you typed in Settings (e.g., `gemma4:e4b`) exists locally (run `ollama list` in terminal to confirm availability).
