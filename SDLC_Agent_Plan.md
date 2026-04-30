# Flutter SDLC Agent — Implementation Plan

An agentic system that takes a one-line app idea and produces a working Flutter project by walking through the five classical SDLC stages: **Analysis → Planning → Design → Coding → Testing**.

Built on the patterns from the Agentic AI training.
**Runs 100% locally via [Ollama](https://ollama.com) — no API keys, no cloud calls.**

---

## Pattern Mapping — Which Day Teaches What

| SDLC Stage | Pattern Used | Why |
|---|---|---|
| Analysis | ReAct loop + RAG | Agent needs to explore tools (fetch reviews, read similar projects) and retrieve learned patterns |
| Planning | Planner | Decompose the idea into a numbered, executable task list |
| Design | Stage (spec) | Pure LLM call — takes research + plan, writes screens, data model, API |
| Coding | ReAct loop with write tools | Agent makes many tool calls: create project, write files, check output |
| Testing | Stage (tests) + tool loop | LLM writes tests, tool runs `flutter test`, loops if failures |

The overall orchestrator is the **sequential pipeline with a shared state dict** — each stage reads upstream keys and writes exactly one new key.

---

## Local LLM Stack (Ollama)

No Anthropic API, no OpenAI, no network egress. Everything runs on `http://localhost:11434`.

| Role | Model | Why |
|---|---|---|
| Tool-calling agent (Stages 1, 4, 5) | `qwen2.5-coder:7b` or `llama3.1:8b` | Both support native function calling and handle Dart well |
| Planner / Designer (Stages 2, 3) | `qwen2.5:7b` or `llama3.1:8b` | Reliable structured-text output |
| Embeddings (RAG) | `nomic-embed-text` | 768-dim, fast, good quality on technical text |

**One-time install:**

```bash
# 1. Install Ollama from https://ollama.com (or `brew install ollama` on macOS)
ollama serve &                          # runs on localhost:11434

# 2. Pull the models
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text

# 3. Python client
pip install ollama chromadb python-dotenv
```

**Minimal client wrapper (replaces `anthropic.Anthropic()` everywhere):**

```python
# llm.py — single Ollama client used by every stage
import ollama

CHAT_MODEL  = 'qwen2.5-coder:7b'
EMBED_MODEL = 'nomic-embed-text'

def chat(messages: list[dict], tools: list[dict] | None = None,
         system: str | None = None, max_tokens: int = 2048) -> dict:
    """Unified chat call. Returns {'text': str, 'tool_calls': list, 'stop_reason': str}."""
    msgs = []
    if system:
        msgs.append({'role': 'system', 'content': system})
    msgs.extend(messages)

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=msgs,
        tools=tools,
        options={'num_predict': max_tokens, 'temperature': 0.2},
    )
    msg = response['message']
    tool_calls = msg.get('tool_calls') or []
    stop = 'tool_use' if tool_calls else 'end_turn'
    return {'text': msg.get('content', ''), 'tool_calls': tool_calls, 'stop_reason': stop}

def embed(text: str) -> list[float]:
    """Real embedding — replaces the fake MD5-hash embedding."""
    return ollama.embeddings(model=EMBED_MODEL, prompt=text)['embedding']
```

This wrapper is the **only** file that talks to Ollama. Stages and tools import `chat` and `embed` — they never see Ollama directly. Swapping models later = one edit.

### ReAct loop adapted for Ollama

```python
# agent.py — ReAct loop, now Ollama-native
from llm import chat

def run_agent(task: str, tools: list, tool_map: dict, max_steps: int = 15) -> str:
    messages = [{'role': 'user', 'content': task}]
    for step in range(max_steps):
        resp = chat(messages, tools=tools)
        if resp['stop_reason'] == 'end_turn':
            return resp['text']
        # Execute every tool call returned in this step
        messages.append({'role': 'assistant', 'content': resp['text'],
                         'tool_calls': resp['tool_calls']})
        for call in resp['tool_calls']:
            name = call['function']['name']
            args = call['function']['arguments']
            output = tool_map[name](**args)
            messages.append({'role': 'tool', 'name': name, 'content': str(output)})
    return 'Max steps reached'
```

Tool schemas use the OpenAI-compatible format Ollama expects (same shape as Anthropic's, just wrapped under `function`):

```python
TOOLS = [
  {'type': 'function', 'function': {
    'name': 'write_dart_file',
    'description': 'Create or overwrite a .dart file at the given path.',
    'parameters': {
      'type': 'object',
      'properties': {
        'path':    {'type': 'string'},
        'content': {'type': 'string'},
      },
      'required': ['path', 'content'],
    },
  }},
]
```

---

## File Structure

```
sdlc_agent/
├─ state.py                ← state dict + validators
├─ tools/
│  ├─ __init__.py
│  ├─ flutter_cli.py       ← flutter create / analyze / test
│  ├─ file_ops.py          ← read_dart_file, write_dart_file, list_dir
│  ├─ knowledge.py         ← RAG retrieval over patterns
│  └─ market_research.py   ← Play Store reviews, competitor lookup
├─ stages/
│  ├─ __init__.py
│  ├─ analysis.py          ← Stage 1
│  ├─ planning.py          ← Stage 2
│  ├─ design.py            ← Stage 3
│  ├─ coding.py            ← Stage 4
│  └─ testing.py           ← Stage 5
├─ llm.py                  ← ONE file that talks to Ollama (chat + embed)
├─ agent.py                ← shared ReAct loop (Stages 1 & 4 use it)
├─ pipeline.py             ← runs all 5 stages in order
├─ knowledge_base/         ← seeded docs (auth patterns, BLoC, etc.)
└─ main.py                 ← entry point — accepts the app idea
```

---

## State Dict Contract

```python
# state.py
def initial_state(idea: str) -> dict:
    return {
        'idea':      idea,    # STAGE 0: raw input — read-only after this
        'analysis': None,     # Stage 1 writes
        'plan':     None,     # Stage 2 writes
        'design':   None,     # Stage 3 writes
        'code':     None,     # Stage 4 writes — list of {path, content}
        'tests':    None,     # Stage 5 writes
        'project_dir': None,  # set by coding stage after `flutter create`
        'status':   'started',
        'errors':   [],
    }
```

Every stage **reads the full state, writes one key, returns the full state.** No stage mutates upstream keys.

---

## Tools (principles — every tool passes all 5)

### File & CLI tools

| Tool | Signature | Purpose |
|---|---|---|
| `create_flutter_project` | `(name: str, org: str) -> dict` | Runs `flutter create` in a controlled directory |
| `write_dart_file` | `(path: str, content: str) -> dict` | Creates or overwrites a `.dart` file |
| `read_dart_file` | `(path: str) -> dict` | Returns file content with line numbers |
| `list_project_files` | `(project_dir: str) -> list[dict]` | Tree listing filtered to `lib/` and `test/` |
| `run_flutter_analyze` | `(project_dir: str) -> dict` | Runs `flutter analyze`, returns issues |
| `run_flutter_test` | `(project_dir: str) -> dict` | Runs `flutter test`, parses pass/fail counts |

### Knowledge tools (RAG)

| Tool | Signature | Purpose |
|---|---|---|
| `retrieve_pattern` | `(query: str, top_k: int = 5) -> list[dict]` | Searches patterns (auth, BLoC, charts, navigation) |
| `retrieve_similar_app` | `(idea: str) -> dict` | Finds the closest past project for reference |

### Market tools (examples, reused)

| Tool | Signature | Purpose |
|---|---|---|
| `get_play_store_reviews` | `(app_id: str, limit: int = 10) -> list[dict]` | Competitor review mining during Analysis |

All tools return structured dicts with a `status` key — never raw strings, never `None`.

---

## Stage-by-Stage Design

### Stage 1 — Analysis (ReAct agent — pattern)

**Reads:** `idea`
**Writes:** `analysis`

The agent has access to `get_play_store_reviews`, `retrieve_similar_app`, and `retrieve_pattern`. It loops through tool calls until it has enough context to produce an analysis document.

**Output shape:**
```
{
  "problem_statement": "...",
  "target_users": [...],
  "core_features": [...],        # MVP features
  "nice_to_have": [...],
  "competitor_insights": [...],  # from Play Store reviews
  "similar_projects": [...],
  "tech_constraints": [...]      # Flutter version, null safety, BLoC
}
```

**Why ReAct here:** the agent doesn't know in advance how many competitors to look up or which patterns to retrieve. Multi-step tool use is required.

### Stage 2 — Planning (Planner pattern)

**Reads:** `idea`, `analysis`
**Writes:** `plan`

Pure LLM call with a tight system prompt — **no tool access**. Output is a numbered list of implementation steps, bounded at 8 steps.

**Output shape:**
```
[
  "1. Create Flutter project named <slug>",
  "2. Define the <Entity> data model with typed fields",
  "3. Build <Screen1> widget with BLoC",
  "4. Build <Screen2> widget with BLoC",
  "5. Wire navigation using go_router",
  "6. Add local persistence with Hive",
  "7. Add unit tests for BLoC logic",
  "8. Add widget tests for each screen"
]
```

### Stage 3 — Design (single LLM call — spec stage)

**Reads:** `analysis`, `plan`
**Writes:** `design`

No tools. Structured output enforced by prompt.

**Output shape:**
```
{
  "app_name": "...",
  "package_name": "com.example.<slug>",
  "screens": [
    {"name": "HomeScreen", "purpose": "...", "widgets": [...]}
  ],
  "data_models": [
    {"name": "...", "fields": [{"name": "...", "type": "..."}]}
  ],
  "blocs": [
    {"name": "...", "events": [...], "states": [...]}
  ],
  "navigation_graph": [...],
  "dependencies": ["flutter_bloc", "hive", "go_router", ...],
  "acceptance_criteria": [...]
}
```

### Stage 4 — Coding (ReAct agent — the heavy stage)

**Reads:** `design`
**Writes:** `code`, `project_dir`

The agent loops:
1. Call `create_flutter_project` once.
2. For each screen/bloc/model in `design`, call `write_dart_file` with generated Dart code.
3. After each write, call `run_flutter_analyze`.
4. If analyze returns errors, read the file and rewrite it.
5. Stop when analyze is clean.

**Guardrail:** `max_steps = 40`. Log every tool call to `state['code']` as `[{path, action, analyze_status}]`.

### Stage 5 — Testing (ReAct agent, smaller scope)

**Reads:** `design`, `code`, `project_dir`
**Writes:** `tests`

For each BLoC and screen in `design`, agent writes a test file, then calls `run_flutter_test`. On failure, it reads the failing test and the source, rewrites the test (not the source — fixing source belongs to a rework pass), and retries once.

**Output:** a dict of `{test_file: {status, failures}}` and a final pass/fail summary.

---

## Pipeline Orchestrator

```python
# pipeline.py
from state import initial_state
from stages import analysis, planning, design, coding, testing

STAGES = [
    ('analysis', analysis),
    ('plan',     planning),
    ('design',   design),
    ('code',     coding),
    ('tests',    testing),
]

def run_sdlc(idea: str) -> dict:
    state = initial_state(idea)
    for name, module in STAGES:
        try:
            state = module.run(state)
        except Exception as e:
            state['errors'].append(f'{name}: {e}')
            break
        if state['errors']:
            break
        if state.get(name) is None:
            state['errors'].append(f'{name} produced no output')
            break
    return state
```

---

## Entry Point

```python
# main.py
from dotenv import load_dotenv
load_dotenv()

from pipeline import run_sdlc

idea = 'Build a Flutter app that lets users scan grocery receipts and track monthly spending by category.'

state = run_sdlc(idea)

# Persist every stage output for inspection
import json, pathlib
out = pathlib.Path('sdlc_output')
out.mkdir(exist_ok=True)
for key in ['analysis', 'plan', 'design', 'code', 'tests']:
    (out / f'{key}.json').write_text(json.dumps(state.get(key), indent=2, default=str))
print(f"[DONE] project at {state['project_dir']} — status: {state['status']}")
```

---

## Knowledge Base (seed content)

Before the agent runs, ingest these into ChromaDB `engineering_patterns` collection:

- `patterns/bloc_pattern.md` — how We use BLoC
- `patterns/auth_jwt.md` — JWT + flutter_secure_storage pattern
- `patterns/hive_persistence.md` — local DB with Hive
- `patterns/go_router_nav.md` — navigation template
- `patterns/fl_chart_usage.md` — chart widget conventions
- `patterns/null_safety_rules.md` — crash fixes from v2.1.3 history
- `patterns/widget_test_template.md` — standard widget test boilerplate

The Analysis and Coding stages both query this collection — Analysis to plan around known patterns, Coding to follow them when writing Dart.

---

## Execution Order

```bash
# one-time setup
ollama serve &                          # local LLM server on :11434
ollama pull qwen2.5-coder:7b            # tool-calling model
ollama pull nomic-embed-text            # embedding model
pip install ollama chromadb python-dotenv
flutter --version                       # must be installed
python3 ingest_patterns.py              # seed the knowledge base

# every run
python3 main.py
```

**No API keys anywhere.** No `.env` needed for LLM access — the client talks to `http://localhost:11434` by default. Keep `.env` only if you add optional services (e.g. a real Play Store scraper) later.

---

## Success Criteria

- [ ] Pipeline completes all 5 stages with `state['errors'] == []`
- [ ] `state['project_dir']` contains a Flutter project that passes `flutter analyze`
- [ ] `flutter test` passes in the generated project
- [ ] The Analysis stage made at least one RAG call and one Play Store call
- [ ] The Planning stage produced a numbered list — no free text, no tool calls
- [ ] The Design stage output matches the schema exactly (valid JSON)
- [ ] Coding stage used `state['design']` as primary input — not the raw idea
- [ ] Each generated Dart file has a matching test file
- [ ] `sdlc_output/` contains one JSON per stage for audit

---

## Guardrails & Failure Modes

| Risk | Mitigation |
|---|---|
| Coding stage loops forever on analyze errors | `max_steps=40`, write partial output to state on abort |
| LLM invents packages that don't exist | Restrict Design stage to a whitelist in the prompt |
| `flutter create` fails (wrong path, existing dir) | Tool returns `{status: 'error', message}` — pipeline halts cleanly |
| Testing stage infinite retries | One retry per test file, then record as failed |
| Design JSON malformed | Retry the Design stage once with a stricter prompt before failing |
| Cross-stage data leakage | Every stage calls `validate_stage_input(state, required_key)` first |
| Ollama server not running | `main.py` pings `http://localhost:11434/api/tags` at startup and aborts with a clear message if down |
| Small local model confuses tool schemas | Keep tool count per stage ≤ 4, give each tool a one-sentence description, prefer `qwen2.5-coder` over smaller variants |
| Slow generation on CPU-only machines | Use `qwen2.5-coder:1.5b` for Planning/Design (plain text), reserve 7b only for Coding |

---

## Extension Points (post-MVP)

1. **Stage 6 — Deployment:** add `flutter build apk` + upload to a staging channel.
2. **Human-in-the-loop review gate** between Design and Coding — a CLI prompt to approve the design JSON.
3. **Rework loop:** if Testing fails hard, spawn a fix agent with read access to the test output and the source file.
4. **Memory of past runs:** store every completed run's `design.json` back into ChromaDB so future analyses learn from delivered work.
5. **Cost/token tracing:** wrap the Anthropic client to log tokens per stage, dump totals at the end.
