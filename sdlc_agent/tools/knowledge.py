"""RAG tools over the curated pattern knowledge base."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from tools.vector_store import get_collection


COLLECTION_KEY = 'patterns'


def retrieve_pattern(query: str, top_k: int = 5) -> dict:
    """Search the pattern knowledge base for chunks semantically similar to the query."""
    try:
        col = get_collection(COLLECTION_KEY)
        if col.count() == 0:
            return {'status': 'error', 'message': 'Knowledge base empty. Run ingest_patterns.py first.'}
        results = col.query(query_texts=[query], n_results=min(top_k, col.count()))
        chunks = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            chunks.append({
                'text':   doc[:600],
                'source': meta.get('source', 'unknown'),
            })
        return {'status': 'ok', 'query': query, 'chunks': chunks, 'count': len(chunks)}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def retrieve_similar_app(idea: str) -> dict:
    """Return the single most relevant pattern for a given app idea."""
    result = retrieve_pattern(idea, top_k=1)
    if result['status'] != 'ok' or not result.get('chunks'):
        return {'status': 'error', 'message': 'No similar patterns found.'}
    top = result['chunks'][0]
    return {'status': 'ok', 'source': top['source'], 'excerpt': top['text']}


KNOWLEDGE_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'retrieve_pattern',
            'description': 'Search pattern knowledge base (BLoC, auth, Hive, null-safety, etc).',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'},
                    'top_k': {'type': 'integer', 'description': 'Results to return. Default 5.'},
                },
                'required': ['query'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'retrieve_similar_app',
            'description': 'Find the closest past project pattern for a given app idea.',
            'parameters': {
                'type': 'object',
                'properties': {'idea': {'type': 'string'}},
                'required': ['idea'],
            },
        },
    },
]

KNOWLEDGE_TOOL_MAP = {
    'retrieve_pattern': retrieve_pattern,
    'retrieve_similar_app': retrieve_similar_app,
}
