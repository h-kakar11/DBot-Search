"""Tiny JSON file persistence helpers used for local caches/state.

Deliberately simple (no locking) since this bot runs as a single process
and these files are only touched from the event loop, never concurrently
from multiple processes.
"""

import json
from pathlib import Path
from typing import Any, Union


def load_json(path: Union[str, Path], default: Any) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Union[str, Path], data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
