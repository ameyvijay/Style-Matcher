const path = require('path');

module.exports = {
  apps: [
    {
      name: "antigravity-backend",
      cwd: path.join(__dirname, "batch-backend-v2"),
      script: path.join(__dirname, "batch-backend-v2", ".venv", "bin", "uvicorn"),
      args: "main:app --host 0.0.0.0 --port 8000",
      interpreter: "none", // Using the binary directly
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: path.join(__dirname, "logs", "backend-err.log"),
      out_file: path.join(__dirname, "logs", "backend-out.log"),
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONDONTWRITEBYTECODE: "1"
      },
      restart_delay: 5000,
      max_memory_restart: "2G"
    },
    {
      name: "antigravity-worker",
      cwd: path.join(__dirname, "batch-backend-v2"),
      script: "sync_watchdog.py",
      interpreter: path.join(__dirname, "batch-backend-v2", ".venv", "bin", "python3"),
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: path.join(__dirname, "logs", "worker-err.log"),
      out_file: path.join(__dirname, "logs", "worker-out.log"),
      env: {
        PYTHONUNBUFFERED: "1"
      },
      restart_delay: 3000
    },
    {
      name: "antigravity-frontend",
      cwd: __dirname,
      script: "npm",
      args: "run dev",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: path.join(__dirname, "logs", "frontend-err.log"),
      out_file: path.join(__dirname, "logs", "frontend-out.log"),
      env: {
        NODE_ENV: "development",
        NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000"
      }
    }
  ]
};
