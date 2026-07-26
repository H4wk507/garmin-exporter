from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

VOLATILE_DAYS = 3


def _default_cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
    else:
        base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "garmin-exporter"


def is_volatile(day: str) -> bool:
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return False
    return (date.today() - d).days < VOLATILE_DAYS


class Cache:
    def __init__(self, root: Path | None = None, enabled: bool = True) -> None:
        self.enabled = enabled
        self.root = root or _default_cache_dir()
        self.hits = 0
        self.misses = 0

    def get_or_fetch(
        self,
        endpoint: str,
        key: str,
        fetch: Callable[[], Any],
        volatile: bool = False,
    ) -> Any:
        if not self.enabled:
            self.misses += 1
            return fetch()
        path = self.root / endpoint / f"{key}.json"
        if not volatile and path.exists():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                self.hits += 1
                return value
            except (OSError, json.JSONDecodeError):
                pass
        value = fetch()
        self.misses += 1
        self._write(path, value)
        return value

    def _write(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(path)
