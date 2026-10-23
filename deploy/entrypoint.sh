#!/bin/sh
set -e

# First-time boot: restore the verified default library (C, C++, Java, Python) into /data if fresh
if [ -f /data/techquery.db ]; then
    echo "[Entrypoint] Existing database detected at /data/techquery.db; skipping default library restore."
elif [ -d /app/seed ]; then
    echo "[Entrypoint] Fresh container or persistent disk detected."
    echo "[Entrypoint] Restoring verified 4-book default library (C, C++, Java, Python)..."
    python manage_release.py restore --bundle /app/seed --target /data
    echo "[Entrypoint] Default library restored successfully into /data."
else
    echo "[Entrypoint] Notice: /app/seed directory not present; skipping default library restore."
fi


# Fallback to port 8000 if Render or the environment did not set PORT
PORT="${PORT:-8000}"

# Run uvicorn on the configured port
if [ "$#" -eq 0 ] || [ "$1" = "python" -a "$2" = "-m" -a "$3" = "uvicorn" ]; then
    echo "[Entrypoint] Starting TechQuery FastAPI server on port $PORT..."
    exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers --forwarded-allow-ips "*" --no-server-header --timeout-graceful-shutdown 90
fi

exec "$@"
