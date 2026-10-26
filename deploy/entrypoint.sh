#!/bin/sh
set -e

# Fallback to port 8000 if Render or the environment did not set PORT
PORT="${PORT:-8000}"

# Run uvicorn on the configured port
if [ "$#" -eq 0 ] || [ "$1" = "python" -a "$2" = "-m" -a "$3" = "uvicorn" ]; then
    # Resolve the same configured paths as the API, before importing app.main.
    python bootstrap_runtime.py
    echo "[Entrypoint] Starting TechQuery FastAPI server on port $PORT..."
    exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers --forwarded-allow-ips "*" --no-server-header --timeout-graceful-shutdown 90
fi

exec "$@"
