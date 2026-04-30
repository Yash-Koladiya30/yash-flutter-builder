"""Multi-provider LLM wrapper.

Routes by model name:
- "claude-*"  → Anthropic API (needs ANTHROPIC_API_KEY env var)
- anything else → Ollama on localhost:11434

Embeddings always go to Ollama — Anthropic does not provide an embeddings endpoint.

All stages import chat() and embed() from here. Agent history is kept in a
provider-neutral format; this module translates it per-provider before calling.

Transient network errors (Ollama down, connection reset, read timeout) are retried
with exponential backoff so a flaky connection doesn't abort a 15-minute run.
"""
import json
import os
import time
import uuid
import httpx
import ollama

from config import model_for


# Exceptions we consider worth retrying
_RETRYABLE = (
    ConnectionError,
    TimeoutError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.TransportError,
    ollama.ResponseError,  # often transient on first load
)
MAX_RETRIES = 5
BASE_BACKOFF = 2.0  # seconds


def _retry(fn, *args, **kwargs):
    """Call fn with exponential backoff. Retries transient network errors only."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except _RETRYABLE as e:
            last_err = e
            wait = BASE_BACKOFF * (2 ** attempt)
            print(f'  [LLM] Network error ({type(e).__name__}): {e}. '
                  f'Retry {attempt + 1}/{MAX_RETRIES} in {wait:.0f}s')
            time.sleep(wait)
    raise RuntimeError(
        f'LLM call failed after {MAX_RETRIES} retries. Last error: {last_err}'
    )

try:
    import anthropic as _anthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

OLLAMA_HOST = 'http://localhost:11434'

_anthropic_client = None


def _is_anthropic(model_name: str) -> bool:
    return model_name.startswith('claude-')


def _get_anthropic():
    global _anthropic_client
    if not _ANTHROPIC_OK:
        raise RuntimeError(
            'anthropic SDK not installed. Run: pip install anthropic'
        )
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise RuntimeError(
            'ANTHROPIC_API_KEY not set. Export it or edit config.py to use an '
            'Ollama model for this stage.'
        )
    if _anthropic_client is None:
        _anthropic_client = _anthropic.Anthropic()
    return _anthropic_client


def check_ollama_running() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Message / tool format translation
# --------------------------------------------------------------------------

def _ollama_messages(messages: list, system: str):
    """Convert neutral-format history to Ollama shape."""
    out = []
    if system:
        out.append({'role': 'system', 'content': system})
    for m in messages:
        role = m['role']
        if role == 'user':
            out.append({'role': 'user', 'content': m.get('content', '')})
        elif role == 'assistant':
            msg = {'role': 'assistant', 'content': m.get('text', '') or ''}
            if m.get('tool_calls'):
                msg['tool_calls'] = [
                    {'function': {'name': c['name'], 'arguments': c['arguments']}}
                    for c in m['tool_calls']
                ]
            out.append(msg)
        elif role == 'tool_results':
            for r in m.get('results', []):
                out.append({
                    'role': 'tool',
                    'name': r.get('name', ''),
                    'content': r['content'],
                })
    return out


def _anthropic_messages(messages: list):
    """Convert neutral-format history to Anthropic content-block shape."""
    out = []
    for m in messages:
        role = m['role']
        if role == 'user':
            out.append({'role': 'user', 'content': m.get('content', '')})
        elif role == 'assistant':
            blocks = []
            text = m.get('text', '') or ''
            if text:
                blocks.append({'type': 'text', 'text': text})
            for c in m.get('tool_calls', []):
                blocks.append({
                    'type': 'tool_use',
                    'id':   c['id'],
                    'name': c['name'],
                    'input': c['arguments'],
                })
            if not blocks:
                blocks.append({'type': 'text', 'text': ' '})
            out.append({'role': 'assistant', 'content': blocks})
        elif role == 'tool_results':
            blocks = []
            for r in m.get('results', []):
                blocks.append({
                    'type': 'tool_result',
                    'tool_use_id': r['tool_call_id'],
                    'content': r['content'],
                })
            out.append({'role': 'user', 'content': blocks})
    return out


def _anthropic_tools(tools: list):
    """Unwrap Ollama-style tool schemas into Anthropic's {name, description, input_schema}."""
    converted = []
    for t in tools:
        fn = t.get('function', t)
        converted.append({
            'name':        fn['name'],
            'description': fn.get('description', ''),
            'input_schema': fn.get('parameters') or fn.get('input_schema') or {
                'type': 'object', 'properties': {},
            },
        })
    return converted


# --------------------------------------------------------------------------
# Provider entry points
# --------------------------------------------------------------------------

def chat(messages: list, tools: list = None, system: str = None,
         max_tokens: int = 2048, temperature: float = 0.2,
         model: str = None, stage: str = 'default') -> dict:
    """Unified chat call. Returns {text, tool_calls, stop_reason}.

    tool_calls: list of {id, name, arguments} — provider-neutral.
    """
    m = model or model_for(stage)
    if _is_anthropic(m):
        return _chat_anthropic(messages, tools, system, max_tokens, temperature, m)
    return _chat_ollama(messages, tools, system, max_tokens, temperature, m)


def _chat_ollama(messages, tools, system, max_tokens, temperature, model):
    kwargs = {
        'model':    model,
        'messages': _ollama_messages(messages, system),
        'options':  {'num_predict': max_tokens, 'temperature': temperature},
    }
    if tools:
        kwargs['tools'] = tools  # already in Ollama-compatible shape

    response = _retry(ollama.chat, **kwargs)
    msg = response['message']

    raw_calls = msg.get('tool_calls') or []
    tool_calls = []
    for tc in raw_calls:
        fn = tc.get('function', {}) if isinstance(tc, dict) else tc.function
        name = fn.get('name') if isinstance(fn, dict) else fn.name
        args = fn.get('arguments') if isinstance(fn, dict) else fn.arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        tool_calls.append({
            'id':        f'toolu_{uuid.uuid4().hex[:12]}',
            'name':      name,
            'arguments': args or {},
        })

    return {
        'text': msg.get('content', '') or '',
        'tool_calls': tool_calls,
        'stop_reason': 'tool_use' if tool_calls else 'end_turn',
    }


def _chat_anthropic(messages, tools, system, max_tokens, temperature, model):
    client = _get_anthropic()

    kwargs = {
        'model':      model,
        'max_tokens': max_tokens,
        'messages':   _anthropic_messages(messages),
    }
    if system:
        kwargs['system'] = system
    if tools:
        kwargs['tools'] = _anthropic_tools(tools)

    # Opus 4.7 removed `temperature`/`top_p`/`top_k` — sending any returns 400.
    if not model.startswith('claude-opus-4-7'):
        kwargs['temperature'] = temperature

    response = _retry(client.messages.create, **kwargs)

    text_parts = []
    tool_calls = []
    for block in response.content:
        if getattr(block, 'type', None) == 'text':
            text_parts.append(block.text)
        elif getattr(block, 'type', None) == 'tool_use':
            tool_calls.append({
                'id':        block.id,
                'name':      block.name,
                'arguments': dict(block.input) if block.input else {},
            })

    return {
        'text': ''.join(text_parts),
        'tool_calls': tool_calls,
        'stop_reason': 'tool_use' if tool_calls else 'end_turn',
    }


def embed(text: str) -> list:
    """Embeddings always go to Ollama. Anthropic has no embeddings endpoint."""
    response = _retry(ollama.embeddings, model=model_for('embeddings'), prompt=text)
    return response['embedding']
