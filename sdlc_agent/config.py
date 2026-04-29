"""Per-stage model configuration. Edit this file to change which model runs each task.

ROUTING RULE (see llm.py):
  - Model name starts with "claude-" → Anthropic API (needs ANTHROPIC_API_KEY)
  - Anything else → Ollama on localhost:11434

Swap any entry below after `ollama pull <model>`.
"""
from pathlib import Path


# Where ChromaDB keeps all persistent state.
CHROMA_PATH = str(Path(__file__).resolve().parent / 'chroma_db')

# Two collections, one database.
COLLECTIONS = {
    'patterns': 'appaspect_patterns',  # static engineering knowledge (ingest_patterns.py)
    'memory':   'agent_memory',        # dynamic run history (auto-written by pipeline)
}


# ============================================================================
# LOCAL MODEL RECOMMENDATIONS (by RAM)
# ============================================================================
#
# Baseline (8 GB RAM)      — what you have now
#   coding:   qwen2.5-coder:7b
#   design:   qwen2.5-coder:7b        (fine; 7b handles JSON output well)
#
# Better (16 GB RAM) — RECOMMENDED upgrade for coding + design
#   coding:   qwen2.5-coder:7b       ollama pull qwen2.5-coder:7b
#   design:   qwen2.5:14b             ollama pull qwen2.5:14b
#     (the non-coder 14b is better at structured-text reasoning)
#
# Best (32 GB+ RAM) — significantly stronger coding
#   coding:   qwen2.5-coder:32b       ollama pull qwen2.5-coder:32b
#   design:   qwen2.5:32b             ollama pull qwen2.5:32b
#
# Alternative for coding:
#   deepseek-coder-v2:16b             ollama pull deepseek-coder-v2:16b
#     (strong at reasoning about existing code; more RAM than qwen 14b)
#
# If you later want Claude (needs ANTHROPIC_API_KEY in env):
#   coding:   claude-opus-4-7         — best code generation
#   design:   claude-sonnet-4-6       — great structured JSON, cheaper/faster
#
# ============================================================================

MODELS = {
    # Stage 1 — needs tool calling (RAG + market research). Keep on 7b for speed.
    'analysis':        'qwen2.5-coder:7b',

    # Stage 2 — plain-text planning. 7b is plenty.
    'planning':        'qwen2.5-coder:7b',

    # Stage 3 — structured JSON output. Upgraded to 14b for better schemas.
    'design':          'qwen2.5-coder:7b',

    # Stage 4 — code generation. Upgraded to 14b for better Dart quality.
    'coding':          'qwen2.5-coder:7b',
    'coding_fix_loop': 'qwen2.5-coder:7b',

    # Stage 5 — test code generation. Upgraded to 14b to match coding.
    'testing':         'qwen2.5-coder:7b',

    # Meta layer — short prompts, 7b is fine.
    'meta_planner':    'qwen2.5-coder:7b',
    'meta_executor':   'qwen2.5-coder:7b',

    # Embeddings — Ollama only (Anthropic has no embeddings endpoint)
    'embeddings':      'nomic-embed-text',

    'default':         'qwen2.5-coder:7b',
}


def model_for(stage: str) -> str:
    return MODELS.get(stage, MODELS['default'])
