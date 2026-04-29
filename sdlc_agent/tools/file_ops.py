"""File operation tools. Day 2 principles: single purpose, typed, deterministic, observable, idempotent."""
import os
import subprocess
from pathlib import Path


_DEFAULT_WORKSPACE = Path.home() / 'Documents' / 'claude ai'
_DEFAULT_ORG = 'com.appaspect'


def workspace_root() -> Path:
    """Read FLUTTER_OUTPUT_DIR env var fresh on every call so UI changes
    take effect immediately. Falls back to ~/Documents/claude ai/."""
    raw = os.environ.get('FLUTTER_OUTPUT_DIR') or str(_DEFAULT_WORKSPACE)
    p = Path(raw).expanduser()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to default if user gave invalid path
        p = _DEFAULT_WORKSPACE
        p.mkdir(parents=True, exist_ok=True)
    return p


def flutter_org() -> str:
    return os.environ.get('FLUTTER_ORG') or _DEFAULT_ORG


# Backwards-compat: existing callers reference WORKSPACE_ROOT directly.
# Lazy property-like attribute via module __getattr__.
def __getattr__(name):
    if name == 'WORKSPACE_ROOT':
        return workspace_root()
    raise AttributeError(name)


def _resolve_safe(path: str) -> Path:
    """Resolve a path and ensure it stays inside the workspace root."""
    root = workspace_root()
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise ValueError(f'Path escapes workspace: {p}')
    return p


def create_flutter_project(name: str, org: str = None) -> dict:
    """Run `flutter create` to scaffold a new project inside the workspace.
    org defaults to FLUTTER_ORG env var or 'com.appaspect'."""
    org = org or flutter_org()
    root = workspace_root()
    safe_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name).lower()
    if not safe_name or safe_name[0].isdigit():
        safe_name = 'app_' + safe_name

    project_path = root / safe_name
    if project_path.exists():
        return {
            'status': 'ok',
            'project_dir': str(project_path),
            'message': 'Project already exists, reusing.',
            'created': False,
        }

    try:
        result = subprocess.run(
            ['flutter', 'create', '--org', org, '--project-name', safe_name, safe_name],
            cwd=str(root),
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            return {'status': 'error', 'message': result.stderr or result.stdout}
        return {
            'status': 'ok',
            'project_dir': str(project_path),
            'created': True,
            'message': f'Created Flutter project at {project_path}',
        }
    except FileNotFoundError:
        return {'status': 'error', 'message': 'flutter CLI not found in PATH'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'message': 'flutter create timed out'}


def write_dart_file(path: str, content: str) -> dict:
    """Create or overwrite any project file (Dart source or pubspec.yaml). Creates parent dirs."""
    try:
        p = _resolve_safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return {
            'status': 'ok',
            'path': str(p),
            'bytes_written': len(content),
            'message': f'Wrote {len(content)} bytes to {p.name}',
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e), 'path': path}


def read_dart_file(path: str) -> dict:
    """Return file contents with line numbers."""
    try:
        p = _resolve_safe(path)
        if not p.exists():
            return {'status': 'error', 'message': f'File not found: {p}', 'path': str(p)}
        text = p.read_text(encoding='utf-8')
        numbered = '\n'.join(
            f'{i + 1:4d}: {line}' for i, line in enumerate(text.splitlines())
        )
        return {'status': 'ok', 'path': str(p), 'content': numbered, 'lines': text.count('\n') + 1}
    except Exception as e:
        return {'status': 'error', 'message': str(e), 'path': path}


def list_project_files(project_dir: str) -> dict:
    """List .dart files under lib/ and test/ of the given project."""
    try:
        base = _resolve_safe(project_dir)
        if not base.exists():
            return {'status': 'error', 'message': f'Project not found: {base}'}

        files = []
        for sub in ('lib', 'test'):
            folder = base / sub
            if not folder.exists():
                continue
            for root, dirs, names in os.walk(folder):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for name in names:
                    if name.endswith('.dart'):
                        rel = Path(root, name).relative_to(base)
                        files.append(str(rel))
        return {'status': 'ok', 'project_dir': str(base), 'files': sorted(files), 'count': len(files)}
    except Exception as e:
        return {'status': 'error', 'message': str(e), 'project_dir': project_dir}


FILE_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'create_flutter_project',
            'description': 'Scaffold a new Flutter project using `flutter create`.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'description': 'Project name (snake_case)'},
                    'org': {'type': 'string', 'description': 'Organization, e.g. com.appaspect'},
                },
                'required': ['name'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'write_dart_file',
            'description': 'Create or overwrite a project file (Dart source, pubspec.yaml, etc). Parent dirs auto-created.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'Absolute or workspace-relative path'},
                    'content': {'type': 'string', 'description': 'Full Dart source code'},
                },
                'required': ['path', 'content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_dart_file',
            'description': 'Read a Dart file and return its contents with line numbers.',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string'}},
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'list_project_files',
            'description': 'List all .dart files under lib/ and test/ of a Flutter project.',
            'parameters': {
                'type': 'object',
                'properties': {'project_dir': {'type': 'string'}},
                'required': ['project_dir'],
            },
        },
    },
]

FILE_TOOL_MAP = {
    'create_flutter_project': create_flutter_project,
    'write_dart_file': write_dart_file,
    'read_dart_file': read_dart_file,
    'list_project_files': list_project_files,
}
