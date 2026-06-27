from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _load_package_json(name: str) -> Any:
    data = (Path(__file__).with_name("data") / name).read_text(encoding="utf-8")
    return json.loads(data)


def load_base_transformations() -> List[Dict[str, Any]]:
    return _load_package_json("base-transformations.json")


def load_refined_transformations() -> List[Dict[str, Any]]:
    return _load_package_json("refined-transformations.json")


def load_generalized_transformations() -> List[Dict[str, Any]]:
    return _load_package_json("generalized-transformations.json")


def load_transformations(spec: str) -> List[Dict[str, Any]]:
    base = load_base_transformations()
    refined = load_refined_transformations()
    if spec == "base5":
        return base
    if spec == "refined30":
        return refined
    if spec == "all35":
        return base + refined
    path = Path(spec)
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"Transformation file must contain a JSON list: {path}")
        return loaded
    raise ValueError(
        f"Unknown transformation set {spec!r}; use base5, refined30, all35, or a JSON file"
    )


def cumulative_suites() -> List[Dict[str, Any]]:
    base = load_base_transformations()
    refined = load_refined_transformations()
    return [
        {
            "id": "base-only",
            "transformations": base,
            "addedRefinedCount": 0,
        },
        {
            "id": "base-plus-30",
            "transformations": base + refined,
            "addedRefinedCount": 30,
        },
    ]
