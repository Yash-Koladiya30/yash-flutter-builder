"""Long-term agent memory. Dynamic run history, separate from the static pattern KB.

On pipeline completion, store {idea, design, outcome} so future runs can learn.
During analysis of a new idea, retrieve similar past runs to reuse decisions.
"""
import json
import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from vector_store import get_collection, delete_collection


COLLECTION_KEY = 'memory'


def _summarise_run(state: dict) -> str:
    """Build a searchable text blob for embedding."""
    design = state.get('design') or {}
    analysis = state.get('analysis') or {}

    parts = [
        f"Idea: {state.get('idea', '')}",
        f"App: {design.get('app_name', 'unknown')}",
    ]
    if isinstance(analysis, dict):
        if analysis.get('problem_statement'):
            parts.append(f"Problem: {analysis['problem_statement']}")
        if analysis.get('core_features'):
            parts.append(f"Features: {', '.join(map(str, analysis['core_features']))}")
    if design.get('screens'):
        screens = [s.get('name', '?') for s in design['screens']]
        parts.append(f"Screens: {', '.join(screens)}")
    if design.get('data_models'):
        models = [m.get('name', '?') for m in design['data_models']]
        parts.append(f"Models: {', '.join(models)}")
    parts.append(f"Outcome: {state.get('status', 'unknown')}")
    return '\n'.join(parts)


def store_run(state: dict) -> dict:
    """Persist a completed pipeline run to memory."""
    try:
        col = get_collection(COLLECTION_KEY)
        run_id = f"run_{int(time.time() * 1000)}"
        summary = _summarise_run(state)

        design = state.get('design') or {}
        metadata = {
            'idea':         (state.get('idea') or '')[:500],
            'app_name':     design.get('app_name', 'unknown'),
            'status':       state.get('status', 'unknown'),
            'project_dir':  state.get('project_dir') or '',
            'screen_count': len(design.get('screens', [])),
            'model_count':  len(design.get('data_models', [])),
            'bloc_count':   len(design.get('blocs', [])),
            'error_count':  len(state.get('errors') or []),
            'timestamp':    time.strftime('%Y-%m-%d %H:%M:%S'),
            'full_design':  json.dumps(design)[:4000],
        }
        col.add(ids=[run_id], documents=[summary], metadatas=[metadata])
        return {'status': 'ok', 'run_id': run_id, 'memory_size': col.count()}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def retrieve_past_run(query: str, top_k: int = 3) -> dict:
    """Search past runs for ones semantically similar to the query."""
    try:
        col = get_collection(COLLECTION_KEY)
        if col.count() == 0:
            return {'status': 'ok', 'runs': [], 'message': 'No past runs stored yet.'}
        results = col.query(query_texts=[query], n_results=min(top_k, col.count()))
        runs = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            runs.append({
                'summary':   doc[:500],
                'app_name':  meta.get('app_name'),
                'idea':      meta.get('idea'),
                'status':    meta.get('status'),
                'timestamp': meta.get('timestamp'),
            })
        return {'status': 'ok', 'runs': runs, 'count': len(runs)}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def list_recent_runs(limit: int = 10) -> dict:
    """List all stored runs (useful for the memory CLI)."""
    try:
        col = get_collection(COLLECTION_KEY)
        result = col.get(limit=limit)
        runs = []
        for rid, meta in zip(result['ids'], result['metadatas']):
            runs.append({
                'run_id':    rid,
                'app_name':  meta.get('app_name'),
                'idea':      meta.get('idea'),
                'status':    meta.get('status'),
                'timestamp': meta.get('timestamp'),
            })
        runs.sort(key=lambda r: r.get('timestamp') or '', reverse=True)
        return {'status': 'ok', 'total': col.count(), 'runs': runs}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def clear_memory() -> dict:
    """Wipe the memory collection. Destructive."""
    try:
        delete_collection(COLLECTION_KEY)
        return {'status': 'ok', 'message': 'Memory cleared.'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


MEMORY_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'retrieve_past_run',
            'description': 'Search agent memory for past app runs similar to the query. Returns app names, ideas, and outcomes.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'Description of the app idea to match against past runs'},
                    'top_k': {'type': 'integer', 'description': 'Max runs to return. Default 3.'},
                },
                'required': ['query'],
            },
        },
    },
]

MEMORY_TOOL_MAP = {
    'retrieve_past_run': retrieve_past_run,
}
