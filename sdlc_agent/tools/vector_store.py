"""Centralized ChromaDB access. One process, one client, one embedder.

Every module that reads or writes vectors goes through get_collection() here.
Creating multiple PersistentClient instances pointing at the same path leads
to race conditions on writes — so we enforce a singleton.
"""
from pathlib import Path
from threading import RLock
from typing import Optional
import chromadb
from chromadb.api.types import EmbeddingFunction, Embeddings, Documents

from config import CHROMA_PATH, COLLECTIONS
from core.llm import embed


# Ensure the persistence directory exists before Chroma touches it.
Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)


class _OllamaEmbedder(EmbeddingFunction):
    """Wraps llm.embed() in ChromaDB's EmbeddingFunction interface."""
    def __call__(self, inputs: Documents) -> Embeddings:
        return [embed(text) for text in inputs]


_lock = RLock()
_client: Optional[chromadb.PersistentClient] = None
_embedder: Optional[_OllamaEmbedder] = None
_collections: dict = {}


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def _get_embedder() -> _OllamaEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = _OllamaEmbedder()
    return _embedder


def get_collection(name: str):
    """Return (and cache) a ChromaDB collection by name.

    Pass either a logical key from COLLECTIONS ('patterns', 'memory') or a raw name.
    """
    resolved = COLLECTIONS.get(name, name)
    if resolved in _collections:
        return _collections[resolved]
    with _lock:
        if resolved not in _collections:
            _collections[resolved] = _get_client().get_or_create_collection(
                name=resolved,
                embedding_function=_get_embedder(),
                metadata={'hnsw:space': 'cosine'},
            )
    return _collections[resolved]


def delete_collection(name: str) -> None:
    """Drop a collection and clear our cache entry."""
    resolved = COLLECTIONS.get(name, name)
    try:
        _get_client().delete_collection(resolved)
    except Exception:
        pass
    _collections.pop(resolved, None)


def stats() -> dict:
    """Return summary stats for every collection listed in config.COLLECTIONS."""
    out = {
        'path': CHROMA_PATH,
        'collections': {},
    }
    for key, name in COLLECTIONS.items():
        try:
            col = get_collection(key)
            out['collections'][key] = {
                'name': name,
                'count': col.count(),
            }
        except Exception as e:
            out['collections'][key] = {'name': name, 'error': str(e)}
    return out
