from __future__ import annotations

import re
from typing import Iterable, Optional


FENCE_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)


def extract_code(text: str, aliases: Iterable[str]) -> Optional[str]:
    alias_set = {item.strip().lower() for item in aliases}
    fallback: Optional[str] = None
    for match in FENCE_RE.finditer(text):
        language = match.group(1).strip().lower()
        body = match.group(2).strip()
        if fallback is None:
            fallback = body
        if language in alias_set:
            return body
    if fallback is not None:
        return fallback
    stripped = text.strip()
    return stripped or None

