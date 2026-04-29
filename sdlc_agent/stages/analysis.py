"""Stage 1 — Analysis. ReAct agent with RAG + market research tools."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from agent import run_agent
from llm import chat
from tools.knowledge import KNOWLEDGE_TOOL_SCHEMAS, KNOWLEDGE_TOOL_MAP
from tools.market_research import MARKET_TOOL_SCHEMAS, MARKET_TOOL_MAP
from tools.memory import MEMORY_TOOL_SCHEMAS, MEMORY_TOOL_MAP
from tools.jira import JIRA_TOOL_SCHEMAS, JIRA_TOOL_MAP


TOOLS = KNOWLEDGE_TOOL_SCHEMAS + MARKET_TOOL_SCHEMAS + MEMORY_TOOL_SCHEMAS + JIRA_TOOL_SCHEMAS
TOOL_MAP = {**KNOWLEDGE_TOOL_MAP, **MARKET_TOOL_MAP, **MEMORY_TOOL_MAP, **JIRA_TOOL_MAP}


SYSTEM_PROMPT = '''You are a Flutter mobile app analyst at AppAspect.
The output of this pipeline is a cross-platform Flutter application (Dart, Material 3, BLoC pattern).
Every analysis you produce should assume Flutter is the target stack.

You have these tools:
- retrieve_past_run(query): check if we've built something similar before. CALL THIS FIRST.
- retrieve_pattern(query): search AppAspect Flutter engineering patterns.
- retrieve_similar_app(idea): find the closest past Flutter project template.
- get_play_store_reviews(app_id): see what users want/complain about.
- search_jira_issues(jql): find requirements or user stories in Jira.
- get_jira_issue(issue_key): get detailed requirements from a specific Jira ticket.

Workflow:
1. Call retrieve_past_run first to see if a prior run informs this idea.
2. Use at least one of retrieve_pattern / retrieve_similar_app.
3. Use get_play_store_reviews for market signal.
4. Synthesize and output ONLY a JSON object with these keys:
   problem_statement, target_users, core_features, nice_to_have,
   competitor_insights, tech_constraints, prior_runs_reused.

tech_constraints MUST include: "Flutter 3.x", "Dart 3.x null safety", "Material 3", "BLoC state management".
No prose outside the JSON.'''


def run(state: dict) -> dict:
    print('\n[STAGE 1] Analysis starting...')
    idea = state['idea']

    task = f'Analyse this app idea and produce the JSON analysis:\n\n"{idea}"'
    result = run_agent(task, TOOLS, TOOL_MAP, system=SYSTEM_PROMPT, max_steps=6, stage='analysis')

    raw = result['text'] or ''
    analysis = _extract_json(raw) or _fallback_analysis(idea, raw)

    state['analysis'] = analysis
    state['status'] = 'analysis_done'
    print(f'[STAGE 1] Done. {result["steps"]} steps, {len(result["trace"])} tool calls.')
    return state


def _extract_json(text: str):
    import json, re
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _fallback_analysis(idea: str, raw: str) -> dict:
    resp = chat(
        messages=[{'role': 'user', 'content':
            f'Convert this text into a JSON object with keys problem_statement, '
            f'target_users (list), core_features (list), nice_to_have (list), '
            f'competitor_insights (list), tech_constraints (list). '
            f'Return ONLY the JSON.\n\nOriginal idea: {idea}\n\nText:\n{raw[:2000]}'}],
        temperature=0.1, max_tokens=1024, stage='analysis',
    )
    return _extract_json(resp['text']) or {
        'problem_statement': idea,
        'target_users': ['end users'],
        'core_features': ['primary feature'],
        'nice_to_have': [],
        'competitor_insights': [],
        'tech_constraints': ['Flutter 3.x', 'null safety', 'BLoC pattern'],
        '_note': 'Fallback analysis — LLM output could not be parsed.',
    }
