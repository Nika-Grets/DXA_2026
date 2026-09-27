from __future__ import annotations
from pathlib import Path
import yaml

_DEFAULT = Path(__file__).resolve().with_name("terminology_catalog.yaml")
_CACHE: dict | None = None

def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        with _DEFAULT.open("r", encoding="utf-8") as f:
            _CACHE = yaml.safe_load(f) or {}
    return _CACHE

def term_name(code: str) -> str:
    data = _load()
    for group in ("violations", "findings"):
        item = data.get(group, {}).get(code)
        if item:
            return item.get("display_name", code)
    return code
