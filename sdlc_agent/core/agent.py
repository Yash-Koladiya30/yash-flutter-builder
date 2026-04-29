"""Shared ReAct loop (Day 1 pattern).

Keeps a provider-neutral message history; llm.chat() translates it per-provider.
"""
from core.llm import chat


def run_agent(task: str, tools: list, tool_map: dict,
              system: str = None, max_steps: int = 20,
              verbose: bool = True, stage: str = 'default') -> dict:
    messages = [{'role': 'user', 'content': task}]
    trace = []

    for step in range(max_steps):
        resp = chat(messages, tools=tools, system=system, stage=stage)

        if verbose:
            print(f'  [step {step + 1}] stop_reason={resp["stop_reason"]}')

        if resp['stop_reason'] == 'end_turn':
            return {'text': resp['text'], 'trace': trace, 'steps': step + 1}

        # Neutral-format assistant message with tool calls
        messages.append({
            'role': 'assistant',
            'text': resp['text'] or '',
            'tool_calls': resp['tool_calls'],
        })

        # Execute each tool and collect neutral-format results
        results = []
        for call in resp['tool_calls']:
            name = call['name']
            args = call['arguments']
            if verbose:
                preview = str(args)[:100]
                print(f'    -> {name}({preview})')

            if name not in tool_map:
                output = {'status': 'error', 'message': f'Unknown tool: {name}'}
            else:
                try:
                    output = tool_map[name](**args)
                except TypeError as e:
                    output = {'status': 'error', 'message': f'Bad arguments: {e}'}
                except Exception as e:
                    output = {'status': 'error', 'message': str(e)}

            trace.append({'tool': name, 'args': args, 'output': output})
            results.append({
                'tool_call_id': call['id'],
                'name':         name,
                'content':      str(output)[:4000],
            })

        messages.append({'role': 'tool_results', 'results': results})

    return {'text': 'Max steps reached', 'trace': trace, 'steps': max_steps}
