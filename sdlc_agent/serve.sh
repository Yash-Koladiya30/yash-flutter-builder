#!/usr/bin/env bash
# Launches the animated web UI + API server on http://localhost:5001
set -e
cd "$(dirname "$0")"

echo "[check] Ollama server..."
curl -sf http://localhost:11434/api/tags > /dev/null || {
  echo "Ollama not running. Start with: ollama serve"
  exit 1
}

echo "[serve] Opening http://localhost:5001"
python3 server.py
