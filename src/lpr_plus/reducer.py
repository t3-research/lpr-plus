from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .code_extract import extract_code
from .oracle import run_oracle
from .provider import ProviderConfig, call_chat_completion
from .token_counter import TokenCounter
from .utils import fence_aliases, fence_language, utc_now, write_json, write_text


@dataclass
class ReduceConfig:
    language: str
    source: Path
    oracle: str
    out_dir: Path
    provider: ProviderConfig
    transformations: List[Dict[str, Any]]
    lpr_root: Optional[Path] = None
    token_counter_mode: str = "auto"
    oracle_timeout: int = 120
    save_raw_api: bool = False
    save_candidates: bool = False
    run_id: str = "reduce"


def _adapter_key(language: str) -> str:
    return {"c": "cAdapter", "rust": "rustAdapter", "js": "jsAdapter"}[language]


def _render_prompt(language: str, transformation: Dict[str, Any], program: str) -> str:
    template = transformation.get("promptTemplate") or transformation.get("summary") or ""
    adapter = transformation.get(_adapter_key(language), "")
    return (
        f"Apply one program-reduction transformation to this {language} program.\n\n"
        f"Transformation id: {transformation.get('id') or transformation.get('name')}\n"
        f"Transformation name: {transformation.get('name') or transformation.get('id')}\n"
        f"Rule: {template.replace('{{language}}', language)}\n"
        f"Language adapter: {adapter}\n\n"
        "Return exactly one complete program in a fenced code block. "
        "If the rule is not applicable, return the original program unchanged. "
        "Do not include explanations outside the fenced code block.\n\n"
        f"```{fence_language(language)}\n{program}\n```"
    )


def _messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are LPR+, a program-reduction assistant. Produce only complete "
                "candidate programs. Smaller candidates are accepted only after an "
                "external interestingness oracle passes."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def _usage(response: Optional[Dict[str, Any]]) -> Dict[str, int]:
    usage = (response or {}).get("usage") or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def run_reduce(config: ReduceConfig) -> Dict[str, Any]:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    source = config.source.resolve()
    original = source.read_text(encoding="utf-8")
    current = original
    counter = TokenCounter(config.token_counter_mode, config.lpr_root)

    initial_tokens = counter.count_text(original, source.name)
    initial_oracle = run_oracle(original, source, config.oracle, timeout=config.oracle_timeout)
    attempts: List[Dict[str, Any]] = []

    write_text(config.out_dir / f"input-{source.name}", original)

    for index, transformation in enumerate(config.transformations, start=1):
        before_tokens = counter.count_text(current, source.name)
        prompt = _render_prompt(config.language, transformation, current)
        result = call_chat_completion(config.provider, _messages(prompt))
        response_path = None
        request_path = None
        if config.save_raw_api:
            request_path = f"{index:02d}-{transformation.get('id', 'rule')}-request.json"
            response_path = f"{index:02d}-{transformation.get('id', 'rule')}-response.json"
            write_json(config.out_dir / request_path, {"messages": _messages(prompt)})
            write_json(
                config.out_dir / response_path,
                result.response if result.response is not None else {"error": result.error},
            )

        candidate = None
        candidate_tokens = None
        oracle_result = None
        accepted = False
        candidate_file = None
        if result.ok:
            candidate = extract_code(result.content, fence_aliases(config.language))
            if candidate is not None:
                candidate_tokens = counter.count_text(candidate, source.name)
                if candidate_tokens < before_tokens:
                    oracle_result = run_oracle(
                        candidate,
                        source,
                        config.oracle,
                        timeout=config.oracle_timeout,
                    )
                    accepted = oracle_result.passed
                if config.save_candidates:
                    candidate_file = f"{index:02d}-{transformation.get('id', 'rule')}-candidate-{source.name}"
                    write_text(config.out_dir / candidate_file, candidate)
        if accepted and candidate is not None and candidate_tokens is not None:
            current = candidate
            after_tokens = candidate_tokens
        else:
            after_tokens = before_tokens

        attempts.append(
            {
                "order": index,
                "transformation": transformation.get("id") or transformation.get("name"),
                "name": transformation.get("name") or transformation.get("id"),
                "source": transformation.get("source") or transformation.get("parentFamily"),
                "beforeTokens": before_tokens,
                "candidateTokens": candidate_tokens,
                "afterTokens": after_tokens,
                "accepted": accepted,
                "api": {
                    "ok": result.ok,
                    "durationMs": result.duration_ms,
                    "retryAttempts": result.retry_attempts,
                    "error": result.error,
                    "model": (result.response or {}).get("model"),
                    "usage": _usage(result.response),
                },
                "oracle": oracle_result.to_json() if oracle_result else None,
                "requestFile": request_path,
                "responseFile": response_path,
                "candidateFile": candidate_file,
            }
        )

    final_tokens = counter.count_text(current, source.name)
    final_oracle = run_oracle(current, source, config.oracle, timeout=config.oracle_timeout)
    final_file = f"final-{source.name}"
    write_text(config.out_dir / final_file, current)

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for attempt in attempts:
        usage = attempt["api"]["usage"]
        for key in total_usage:
            total_usage[key] += usage[key]

    report = {
        "runId": config.run_id,
        "generatedAt": utc_now(),
        "language": config.language,
        "source": str(source),
        "oracle": config.oracle,
        "provider": config.provider.provider,
        "model": config.provider.model,
        "temperature": config.provider.temperature,
        "transformations": [item.get("id") or item.get("name") for item in config.transformations],
        "initialTokens": initial_tokens,
        "finalTokens": final_tokens,
        "reductionTokens": initial_tokens - final_tokens,
        "reductionPercent": (
            ((initial_tokens - final_tokens) / initial_tokens) * 100 if initial_tokens else 0
        ),
        "initialOracle": initial_oracle.to_json(),
        "finalOracle": final_oracle.to_json(),
        "valid": initial_oracle.passed and final_oracle.passed,
        "acceptedCount": sum(1 for item in attempts if item["accepted"]),
        "attemptCount": len(attempts),
        "apiFailureCount": sum(1 for item in attempts if not item["api"]["ok"]),
        "apiUsage": total_usage,
        "attempts": attempts,
        "finalFile": final_file,
    }
    write_json(config.out_dir / "report.json", report)
    write_text(config.out_dir / "report.md", render_report_markdown(report))
    return report


def render_report_markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"# LPR+ {report['language']} Reduction Report",
        "",
        f"- Model: `{report['model']}`",
        f"- Provider: `{report['provider']}`",
        f"- Source: `{report['source']}`",
        f"- Initial tokens: {report['initialTokens']}",
        f"- Final tokens: {report['finalTokens']}",
        f"- Reduction: {report['reductionTokens']} tokens ({report['reductionPercent']:.2f}%)",
        f"- Accepted: {report['acceptedCount']}/{report['attemptCount']}",
        f"- Initial oracle: {'pass' if report['initialOracle']['passed'] else 'fail'}",
        f"- Final oracle: {'pass' if report['finalOracle']['passed'] else 'fail'}",
        "",
        "| # | Transformation | Before | Candidate | After | Oracle | Accepted | API tokens |",
        "|---:|---|---:|---:|---:|---|---|---:|",
    ]
    for attempt in report["attempts"]:
        oracle = attempt["oracle"]
        lines.append(
            f"| {attempt['order']} | `{attempt['transformation']}` | "
            f"{attempt['beforeTokens']} | {attempt['candidateTokens'] or '-'} | "
            f"{attempt['afterTokens']} | "
            f"{'pass' if oracle and oracle['passed'] else ('fail' if oracle else '-')} | "
            f"{'yes' if attempt['accepted'] else 'no'} | "
            f"{attempt['api']['usage']['total_tokens']} |"
        )
    return "\n".join(lines) + "\n"

