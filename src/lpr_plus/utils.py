from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_dotenv(path: Optional[Path]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path or not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def env_value(name: str, dotenv: Optional[Mapping[str, str]] = None) -> Optional[str]:
    return os.environ.get(name) or (dotenv or {}).get(name)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value)
    return value.strip("-") or "item"


def language_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".c":
        return "c"
    if suffix == ".rs":
        return "rust"
    if suffix in {".js", ".mjs", ".cjs"}:
        return "js"
    raise ValueError(f"Cannot infer language from extension: {path}")


def source_name_for_language(language: str) -> str:
    return {"c": "small.c", "rust": "small.rs", "js": "small.js"}[language]


def fence_language(language: str) -> str:
    return {"c": "c", "rust": "rust", "js": "javascript"}[language]


def fence_aliases(language: str) -> Iterable[str]:
    if language == "c":
        return ("c", "cc", "cpp", "c++", "")
    if language == "rust":
        return ("rust", "rs", "")
    if language == "js":
        return ("javascript", "js", "")
    return ("",)

