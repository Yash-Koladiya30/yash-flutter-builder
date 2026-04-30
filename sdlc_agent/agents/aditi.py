"""Stage 2 — Planning. Pure LLM call, no tools."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.llm import chat
from core.state import validate_stage_input


SYSTEM_PROMPT = '''You are a Flutter planning agent.
Decompose the analysed feature into a numbered list of concrete Flutter implementation steps.

Rules:
- Output ONLY a numbered list. No headers, no explanations.
- Each step must be concrete enough to execute against a Flutter project.
- Maximum 8 steps.
- Steps must cover:
  1. `flutter create` project scaffold
  2. pubspec.yaml dependencies (flutter_bloc, equatable, go_router, hive, http — pick what's needed)
  3. Dart data model classes (with fromJson/toJson, Equatable)
  4. Flutter screen widgets (extends StatelessWidget or StatefulWidget)
  5. BLoC files (events, states, bloc) using flutter_bloc
  6. go_router navigation graph in main.dart
  7. Hive or SharedPreferences for local persistence
  8. flutter_test widget tests

Every step must reference Flutter/Dart concepts. Do NOT mention other frameworks.'''


def run(state: dict) -> dict:
    if not validate_stage_input(state, 'analysis'):
        return state
    print('\n[STAGE 2] Planning starting...')

    prompt = (
        f'Original idea: {state["idea"]}\n\n'
        f'Analysis:\n{state["analysis"]}\n\n'
        f'Produce the numbered task list.'
    )
    resp = chat(
        messages=[{'role': 'user', 'content': prompt}],
        system=SYSTEM_PROMPT, max_tokens=800, temperature=0.2, stage='planning',
    )
    raw = resp['text'] or ''
    steps = []
    for line in raw.split('\n'):
        line = line.strip()
        if line and line[0].isdigit():
            parts = line.split('.', 1)
            step = parts[1].strip() if len(parts) > 1 else line
            if step:
                steps.append(step)

    state['plan'] = steps
    state['status'] = 'plan_done'
    print(f'[STAGE 2] Done. {len(steps)} steps.')
    for i, s in enumerate(steps, 1):
        print(f'  {i}. {s[:90]}')
    return state
