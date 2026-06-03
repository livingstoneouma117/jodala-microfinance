from __future__ import annotations

import importlib.util
from pathlib import Path


_app_path = Path(__file__).resolve().parent / "app.py"
_spec = importlib.util.spec_from_file_location("jodala_app_runtime", _app_path)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)

app = _module.app
