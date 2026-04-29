"""Jira REST API v3 tool wrappers.

Reads creds from environment (auto-loads .env if python-dotenv installed):
  JIRA_BASE_URL      e.g. https://your-org.atlassian.net
  JIRA_EMAIL         account email
  JIRA_API_TOKEN     API token from id.atlassian.com/manage-profile/security/api-tokens
  JIRA_PROJECT_KEY   project key for new issues, e.g. SDLC

All functions return {'status': 'ok', ...} or {'status': 'error', 'message': ...}.
"""
import os
import requests
from typing import Optional

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except Exception:
    pass


def _config() -> dict:
    return {
        'base_url':    (os.environ.get('JIRA_BASE_URL') or '').rstrip('/'),
        'email':       os.environ.get('JIRA_EMAIL') or '',
        'token':       os.environ.get('JIRA_API_TOKEN') or '',
        'project_key': os.environ.get('JIRA_PROJECT_KEY') or '',
    }


def jira_enabled() -> bool:
    """Master switch — when False, all Jira create/transition calls become no-ops.
    Default: enabled if creds are configured. Override via JIRA_ENABLED env var
    ('1'/'true' = on, '0'/'false' = off)."""
    raw = (os.environ.get('JIRA_ENABLED') or '').strip().lower()
    if raw in ('1', 'true', 'yes', 'on'):
        return True
    if raw in ('0', 'false', 'no', 'off'):
        return False
    # Auto: enabled iff creds exist
    cfg = _config()
    return bool(cfg['base_url'] and cfg['email'] and cfg['token'])


def _check(cfg: dict, need_project: bool = False) -> Optional[dict]:
    if not cfg['base_url'] or not cfg['email'] or not cfg['token']:
        return {'status': 'error', 'message': 'JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN missing in .env'}
    if need_project and not cfg['project_key']:
        return {'status': 'error', 'message': 'JIRA_PROJECT_KEY missing in .env'}
    return None


def _auth(cfg: dict):
    return (cfg['email'], cfg['token'])


def _adf(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format (required by API v3)."""
    paragraphs = []
    for line in (text or '').split('\n'):
        if line.strip():
            paragraphs.append({
                'type': 'paragraph',
                'content': [{'type': 'text', 'text': line}],
            })
        else:
            paragraphs.append({'type': 'paragraph', 'content': []})
    return {'type': 'doc', 'version': 1, 'content': paragraphs or [{'type': 'paragraph', 'content': []}]}


def search_jira_issues(jql: str, max_results: int = 20) -> dict:
    cfg = _config()
    if err := _check(cfg):
        return err
    try:
        url = f"{cfg['base_url']}/rest/api/3/search"
        r = requests.get(
            url,
            params={'jql': jql, 'maxResults': max_results,
                    'fields': 'summary,status,issuetype,priority,assignee'},
            auth=_auth(cfg), timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        issues = []
        for it in data.get('issues', []):
            f = it.get('fields', {})
            issues.append({
                'key':       it.get('key'),
                'summary':   f.get('summary'),
                'status':    (f.get('status') or {}).get('name'),
                'type':      (f.get('issuetype') or {}).get('name'),
                'priority':  (f.get('priority') or {}).get('name'),
                'assignee':  ((f.get('assignee') or {}).get('displayName')) if f.get('assignee') else None,
            })
        return {'status': 'ok', 'total': data.get('total', len(issues)), 'issues': issues}
    except requests.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP {e.response.status_code}: {e.response.text[:300]}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def get_jira_issue(issue_key: str) -> dict:
    cfg = _config()
    if err := _check(cfg):
        return err
    try:
        url = f"{cfg['base_url']}/rest/api/3/issue/{issue_key}"
        r = requests.get(url, auth=_auth(cfg), timeout=20)
        r.raise_for_status()
        d = r.json()
        f = d.get('fields', {})
        desc = f.get('description')
        if isinstance(desc, dict):
            chunks = []
            for block in desc.get('content', []):
                for sub in block.get('content', []):
                    if sub.get('type') == 'text':
                        chunks.append(sub.get('text', ''))
                chunks.append('\n')
            desc = ''.join(chunks).strip()
        return {
            'status':      'ok',
            'key':         d.get('key'),
            'summary':     f.get('summary'),
            'description': desc,
            'issue_status': (f.get('status') or {}).get('name'),
            'type':        (f.get('issuetype') or {}).get('name'),
            'priority':    (f.get('priority') or {}).get('name'),
            'labels':      f.get('labels', []),
            'url':         f"{cfg['base_url']}/browse/{d.get('key')}",
        }
    except requests.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP {e.response.status_code}: {e.response.text[:300]}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def create_jira_issue(summary: str, description: str = '', issue_type: str = 'Task') -> dict:
    cfg = _config()
    if err := _check(cfg, need_project=True):
        return err
    try:
        url = f"{cfg['base_url']}/rest/api/3/issue"
        payload = {
            'fields': {
                'project':     {'key': cfg['project_key']},
                'summary':     summary,
                'description': _adf(description),
                'issuetype':   {'name': issue_type},
            }
        }
        r = requests.post(url, json=payload, auth=_auth(cfg), timeout=20)
        r.raise_for_status()
        d = r.json()
        return {
            'status': 'ok',
            'key':    d.get('key'),
            'id':     d.get('id'),
            'url':    f"{cfg['base_url']}/browse/{d.get('key')}",
        }
    except requests.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP {e.response.status_code}: {e.response.text[:300]}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def create_jira_subtask(parent_key: str, summary: str, description: str = '') -> dict:
    cfg = _config()
    if err := _check(cfg, need_project=True):
        return err
    try:
        url = f"{cfg['base_url']}/rest/api/3/issue"
        payload = {
            'fields': {
                'project':     {'key': cfg['project_key']},
                'parent':      {'key': parent_key},
                'summary':     summary,
                'description': _adf(description),
                'issuetype':   {'name': 'Subtask'},
            }
        }
        r = requests.post(url, json=payload, auth=_auth(cfg), timeout=20)
        r.raise_for_status()
        d = r.json()
        return {
            'status':     'ok',
            'key':        d.get('key'),
            'id':         d.get('id'),
            'parent_key': parent_key,
            'url':        f"{cfg['base_url']}/browse/{d.get('key')}",
        }
    except requests.HTTPError as e:
        msg = f'HTTP {e.response.status_code}: {e.response.text[:300]}'
        if e.response.status_code == 400 and 'Subtask' in (e.response.text or ''):
            msg += ' (try issuetype "Sub-task" — Jira instances differ)'
        return {'status': 'error', 'message': msg}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def list_transitions(issue_key: str) -> dict:
    cfg = _config()
    if err := _check(cfg):
        return err
    try:
        url = f"{cfg['base_url']}/rest/api/3/issue/{issue_key}/transitions"
        r = requests.get(url, auth=_auth(cfg), timeout=20)
        r.raise_for_status()
        items = r.json().get('transitions', [])
        return {
            'status': 'ok',
            'issue_key': issue_key,
            'transitions': [
                {'id': t.get('id'), 'name': t.get('name'),
                 'to': (t.get('to') or {}).get('name')}
                for t in items
            ],
        }
    except requests.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP {e.response.status_code}: {e.response.text[:300]}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def transition_to_status(issue_key: str, target_status: str) -> dict:
    cfg = _config()
    if err := _check(cfg):
        return err
    try:
        listing = list_transitions(issue_key)
        if listing.get('status') != 'ok':
            return listing
        match = None
        for t in listing['transitions']:
            if (t.get('to') or '').lower() == target_status.lower() or \
               (t.get('name') or '').lower() == target_status.lower():
                match = t
                break
        if not match:
            available = ', '.join(t.get('name') or '?' for t in listing['transitions'])
            return {'status': 'error',
                    'message': f"No transition to '{target_status}'. Available: {available}"}

        url = f"{cfg['base_url']}/rest/api/3/issue/{issue_key}/transitions"
        r = requests.post(url, json={'transition': {'id': match['id']}},
                          auth=_auth(cfg), timeout=20)
        r.raise_for_status()
        return {'status': 'ok', 'issue_key': issue_key,
                'transitioned_to': match.get('to') or match.get('name')}
    except requests.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP {e.response.status_code}: {e.response.text[:300]}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


JIRA_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'search_jira_issues',
            'description': 'Search Jira with a JQL query. Returns matching issues with key, summary, status, type.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'jql':         {'type': 'string', 'description': 'JQL query, e.g. "project = SDLC AND status = \\"To Do\\""'},
                    'max_results': {'type': 'integer', 'description': 'Max issues to return. Default 20.'},
                },
                'required': ['jql'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_jira_issue',
            'description': 'Fetch a single Jira issue by key. Returns summary, description, status, type, priority.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'issue_key': {'type': 'string', 'description': 'Issue key, e.g. "SDLC-12"'},
                },
                'required': ['issue_key'],
            },
        },
    },
]

JIRA_TOOL_MAP = {
    'search_jira_issues': search_jira_issues,
    'get_jira_issue':     get_jira_issue,
}


def test_connection(base_url: str = None, email: str = None, api_token: str = None) -> dict:
    """Probe /rest/api/3/myself to verify creds. Doesn't save anything.
    If args omitted, uses currently-set os.environ values."""
    cfg = _config()
    bu = (base_url or cfg['base_url'] or '').rstrip('/')
    em = email or cfg['email']
    tk = api_token or cfg['token']
    if not (bu and em and tk):
        return {'status': 'error', 'message': 'Missing base_url, email, or api_token.'}
    try:
        r = requests.get(
            f'{bu}/rest/api/3/myself',
            auth=(em, tk),
            headers={'Accept': 'application/json'},
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            return {
                'status':  'ok',
                'user':    d.get('displayName') or d.get('emailAddress'),
                'account': d.get('accountId'),
            }
        return {'status': 'error', 'message': f'HTTP {r.status_code}: {r.text[:200]}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
