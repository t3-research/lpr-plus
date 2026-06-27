from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_OPENAI_BASE = "https://api.openai.com/v1/chat/completions"


@dataclass
class ProviderConfig:
    provider: str
    model: str
    api_base: str = DEFAULT_OPENAI_BASE
    api_key: Optional[str] = None
    temperature: float = 1.0
    max_tokens: int = 4096
    timeout: int = 120
    retries: int = 2
    max_tokens_param: str = "max_tokens"
    mock_response_file: Optional[Path] = None


@dataclass
class ProviderResult:
    ok: bool
    content: str
    response: Optional[Dict[str, Any]]
    error: Optional[str]
    duration_ms: int
    retry_attempts: int


def is_fatal_api_error(message: str) -> bool:
    return bool(
        message
        and (
            "401" in message
            or "403" in message
            or "invalid api key" in message.lower()
            or "quota" in message.lower()
            or "credits" in message.lower()
            or "model_not_found" in message.lower()
            or "model unavailable" in message.lower()
        )
    )


def call_chat_completion(
    config: ProviderConfig,
    messages: List[Dict[str, str]],
) -> ProviderResult:
    if config.provider == "mock":
        started = time.time()
        if config.mock_response_file:
            content = config.mock_response_file.read_text(encoding="utf-8")
        else:
            content = messages[-1]["content"]
        return ProviderResult(
            ok=True,
            content=content,
            response={
                "model": "mock",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
            error=None,
            duration_ms=int((time.time() - started) * 1000),
            retry_attempts=0,
        )

    if not config.api_key:
        return ProviderResult(
            ok=False,
            content="",
            response=None,
            error="API key is missing",
            duration_ms=0,
            retry_attempts=0,
        )

    body: Dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "stream": False,
    }
    body[config.max_tokens_param] = config.max_tokens
    payload = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    last_error: Optional[str] = None
    started = time.time()
    for attempt in range(config.retries + 1):
        request = urllib.request.Request(
            config.api_base,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=config.timeout) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
            return ProviderResult(
                ok=True,
                content=content,
                response=parsed,
                error=None,
                duration_ms=int((time.time() - started) * 1000),
                retry_attempts=attempt,
            )
        except urllib.error.HTTPError as error:
            text = error.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {error.code}: {text}"
            if is_fatal_api_error(last_error):
                break
        except Exception as error:  # noqa: BLE001 - CLI reports provider errors.
            last_error = str(error)
        if attempt < config.retries:
            time.sleep(min(2 ** attempt, 8))

    return ProviderResult(
        ok=False,
        content="",
        response=None,
        error=last_error or "unknown provider error",
        duration_ms=int((time.time() - started) * 1000),
        retry_attempts=config.retries,
    )

