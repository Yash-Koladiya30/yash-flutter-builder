"""Flutter CLI tools. Wraps `flutter analyze` and `flutter test` with structured output."""
import subprocess
from pathlib import Path


def run_flutter_analyze(project_dir: str) -> dict:
    """Run `flutter analyze` and return structured issues."""
    p = Path(project_dir)
    if not p.exists():
        return {'status': 'error', 'message': f'Project not found: {project_dir}'}
    try:
        result = subprocess.run(
            ['flutter', 'analyze', '--no-pub'],
            cwd=str(p), capture_output=True, text=True, timeout=180,
        )
        output = result.stdout + result.stderr
        clean = result.returncode == 0
        issues = [
            line.strip() for line in output.splitlines()
            if line.strip() and ('error' in line.lower() or 'warning' in line.lower() or 'info' in line.lower())
        ]
        return {
            'status': 'ok',
            'clean': clean,
            'returncode': result.returncode,
            'issue_count': len(issues),
            'issues': issues[:30],
            'summary': 'No issues found.' if clean else f'{len(issues)} issues detected.',
        }
    except FileNotFoundError:
        return {'status': 'error', 'message': 'flutter CLI not found'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'message': 'flutter analyze timed out'}


def run_flutter_test(project_dir: str) -> dict:
    """Run `flutter test` and parse pass/fail counts."""
    p = Path(project_dir)
    if not p.exists():
        return {'status': 'error', 'message': f'Project not found: {project_dir}'}
    try:
        result = subprocess.run(
            ['flutter', 'test', '--reporter', 'compact'],
            cwd=str(p), capture_output=True, text=True, timeout=300,
        )
        output = result.stdout + result.stderr
        passed = output.count(' +') if ' +' in output else 0
        failed_markers = [line for line in output.splitlines() if ' -' in line and 'failed' in line.lower()]
        return {
            'status': 'ok',
            'passed': result.returncode == 0,
            'returncode': result.returncode,
            'raw_output_tail': '\n'.join(output.splitlines()[-20:]),
            'failure_lines': failed_markers[:10],
        }
    except FileNotFoundError:
        return {'status': 'error', 'message': 'flutter CLI not found'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'message': 'flutter test timed out'}


def run_flutter_pub_get(project_dir: str) -> dict:
    """Run `flutter pub get` to resolve dependencies."""
    p = Path(project_dir)
    if not p.exists():
        return {'status': 'error', 'message': f'Project not found: {project_dir}'}
    try:
        r = subprocess.run(
            ['flutter', 'pub', 'get'],
            cwd=str(p), capture_output=True, text=True, timeout=300,
        )
        output = r.stdout + r.stderr
        return {
            'status':     'ok',
            'returncode': r.returncode,
            'success':    r.returncode == 0,
            'tail':       '\n'.join(output.splitlines()[-30:]),
        }
    except FileNotFoundError:
        return {'status': 'error', 'message': 'flutter CLI not found'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'message': 'pub get timed out'}


def run_flutter_build(project_dir: str, target: str = 'apk',
                      flavor: str = 'debug') -> dict:
    """Run `flutter build <target>` and capture compile errors.

    target: 'apk' (Android, fastest, default), 'ios' (no codesign — needs Xcode),
            'web' (no native toolchain).
    flavor: 'debug' (skip optimization, fastest) or 'release'.
    """
    p = Path(project_dir)
    if not p.exists():
        return {'status': 'error', 'message': f'Project not found: {project_dir}'}

    args = ['flutter', 'build', target]
    if flavor == 'debug':
        args.append('--debug')
    if target == 'ios':
        args.append('--no-codesign')

    try:
        r = subprocess.run(
            args, cwd=str(p), capture_output=True, text=True, timeout=900,
        )
        output = r.stdout + r.stderr
        # Parse error lines for rework context
        error_lines = [
            ln.strip() for ln in output.splitlines()
            if ln.strip() and any(k in ln.lower() for k in (
                'error:', 'fatal:', 'compiler message',
                'phasescript', 'error running', 'undefined name',
                'expected', 'cannot find', 'no such', 'failed to',
            ))
        ]
        return {
            'status':     'ok',
            'target':     target,
            'flavor':     flavor,
            'returncode': r.returncode,
            'success':    r.returncode == 0,
            'tail':       '\n'.join(output.splitlines()[-60:]),
            'error_lines': error_lines[:30],
        }
    except FileNotFoundError:
        return {'status': 'error', 'message': 'flutter CLI not found'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'message': f'flutter build {target} timed out'}


CLI_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'run_flutter_analyze',
            'description': 'Run `flutter analyze` on the project. Returns list of issues.',
            'parameters': {
                'type': 'object',
                'properties': {'project_dir': {'type': 'string'}},
                'required': ['project_dir'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'run_flutter_test',
            'description': 'Run `flutter test` on the project. Returns pass/fail summary.',
            'parameters': {
                'type': 'object',
                'properties': {'project_dir': {'type': 'string'}},
                'required': ['project_dir'],
            },
        },
    },
]

CLI_TOOL_MAP = {
    'run_flutter_analyze': run_flutter_analyze,
    'run_flutter_test':    run_flutter_test,
    'run_flutter_pub_get': run_flutter_pub_get,
    'run_flutter_build':   run_flutter_build,
}
