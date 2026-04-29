"""Thin entry-point so `python3 server.py` still works after refactor.

Real Flask app lives in api/server.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from api.server import app, WEBAPP_DIR  # noqa: F401

if __name__ == '__main__':
    print("[SERVER] Yash's Agent UI starting on http://localhost:5001")
    print(f'[SERVER] Webapp dir: {WEBAPP_DIR}')
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
