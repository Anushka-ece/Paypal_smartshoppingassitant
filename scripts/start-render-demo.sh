#!/usr/bin/env bash
set -euo pipefail

cd /app/project_ver_1/backend
python -m alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!

cleanup() {
    kill "$api_pid" 2>/dev/null || true
    wait "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
        break
    fi
    sleep 1
done

if ! curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    echo "Backend failed to become healthy; refusing to start the frontend." >&2
    exit 1
fi

cd /app/project_ver_1/frontend
npm run start -- --hostname 0.0.0.0 --port "${PORT:-10000}"
