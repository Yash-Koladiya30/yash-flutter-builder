#!/usr/bin/env bash
# Convenience runner. Usage: ./run.sh "your app idea here"
set -e

cd "$(dirname "$0")"

echo "[check] Ollama server..."
curl -sf http://localhost:11434/api/tags > /dev/null || {
  echo "Ollama not running. Start with: ollama serve"
  exit 1
}

echo "[check] Models..."
ollama list | grep -q "qwen2.5-coder" || ollama pull qwen2.5-coder:7b
ollama list | grep -q "nomic-embed-text" || ollama pull nomic-embed-text

echo "[ingest] Seeding knowledge base..."
python3 ingest_patterns.py

echo "[run] SDLC pipeline..."
if [ $# -eq 0 ]; then
  python3 main.py
else
  python3 main.py "$@"
fi
