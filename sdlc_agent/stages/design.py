"""Stage 3 — Design. Produces structured JSON spec (Day 5 spec stage)."""
import json
import re
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from llm import chat
from state import validate_stage_input


SYSTEM_PROMPT = '''You are a Flutter solution architect designing a Flutter mobile app.
Target stack: Flutter 3.x, Dart 3.x with null safety, Material 3, flutter_bloc, go_router.

Produce a complete Flutter app specification as a single JSON object with these keys:
  app_name (snake_case — becomes the flutter create project name),
  package_name (e.g. "com.appaspect.receipt_tracker"),
  screens (list of {name: ends with "Screen", purpose, widgets: [Flutter widget names]}),
  data_models (list of {name, fields:[{name, type}]}),
  blocs (list of {name: ends with "Bloc", events:[...], states:[...]}),
  dependencies (list of pub.dev packages),
  acceptance_criteria (list of Flutter-specific criteria).

Rules:
- Output ONLY the JSON. No markdown fences, no prose.
- Use null-safe Dart types only: "String", "String?", "int", "double", "bool",
  "DateTime", "List<String>", "Map<String, dynamic>".
- Screen names MUST end in "Screen" (e.g. "HomeScreen", "LoginScreen").
- BLoC names MUST end in "Bloc" (e.g. "AuthBloc", "PostBloc").
- Widgets listed must be valid Flutter widgets: Scaffold, AppBar, ListView, GridView,
  Column, Row, Text, Card, ListTile, TextFormField, FilledButton, IconButton, Image,
  CircleAvatar, BlocBuilder, StreamBuilder, FutureBuilder, SafeArea.
- Keep it minimal but complete — 2–6 screens, 1–4 BLoCs, 1–4 data models.
- Dependencies MUST come from this whitelist ONLY:
  flutter_bloc, equatable, go_router, hive, hive_flutter, path_provider,
  intl, http, shared_preferences, cached_network_image, image_picker.
- Acceptance criteria must reference Flutter behaviors (e.g. "Screen renders
  without errors", "BlocBuilder shows loading state", "flutter test passes").'''


def run(state: dict) -> dict:
    if not validate_stage_input(state, 'plan'):
        return state
    print('\n[STAGE 3] Design starting...')

    prompt = (
        f'App idea: {state["idea"]}\n\n'
        f'Analysis: {state["analysis"]}\n\n'
        f'Plan:\n' + '\n'.join(f'- {s}' for s in state['plan']) +
        '\n\nWrite the JSON specification.'
    )

    design = _call_and_parse(prompt)
    if design is None:
        print('[STAGE 3] First parse failed, retrying with stricter prompt...')
        design = _call_and_parse(prompt + '\n\nReturn ONLY valid JSON. No other text.')

    if design is None:
        state['errors'].append('Design stage produced invalid JSON')
        return state

    state['design'] = design
    state['status'] = 'design_done'
    print(f'[STAGE 3] Done. Design for app: {design.get("app_name", "?")}')
    print(f'  Screens: {len(design.get("screens", []))}, '
          f'Models: {len(design.get("data_models", []))}, '
          f'BLoCs: {len(design.get("blocs", []))}')
    return state


def _call_and_parse(prompt: str):
    resp = chat(
        messages=[{'role': 'user', 'content': prompt}],
        system=SYSTEM_PROMPT, max_tokens=2048, temperature=0.2, stage='design',
    )
    text = resp['text'] or ''
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
