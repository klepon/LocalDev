"""Project folder list, stored in %APPDATA%\\LocalDev\\projects.json."""

import json
import os
from pathlib import Path


def _file() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "LocalDev"
    base.mkdir(parents=True, exist_ok=True)
    return base / "projects.json"


def load() -> list[str]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in data.get("projects", []) if isinstance(p, str)]


def save(paths: list[str]):
    _file().write_text(json.dumps({"projects": paths}, indent=2), encoding="utf-8")
