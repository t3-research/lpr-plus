from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from .utils import utc_now, write_json, write_text


def _read_reports(run_dir: Path) -> List[Dict[str, Any]]:
    reports = []
    for path in sorted(run_dir.rglob("report.json")):
        reports.append(__import__("json").loads(path.read_text(encoding="utf-8")))
    return reports


def summarize_run_dir(run_dir: Path) -> Dict[str, Any]:
    reports = _read_reports(run_dir)
    valid = [item for item in reports if item.get("valid")]
    total_attempts = sum(item.get("attemptCount", 0) for item in reports)
    total_accepted = sum(item.get("acceptedCount", 0) for item in reports)
    total_api = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for report in reports:
        usage = report.get("apiUsage", {})
        for key in total_api:
            total_api[key] += int(usage.get(key) or 0)
    reductions = [float(item.get("reductionPercent", 0)) for item in reports]
    summary = {
        "generatedAt": utc_now(),
        "runDir": str(run_dir),
        "reportCount": len(reports),
        "validReportCount": len(valid),
        "invalidReportCount": len(reports) - len(valid),
        "allFinalInteresting": all(
            item.get("finalOracle", {}).get("passed") is True for item in reports
        )
        if reports
        else False,
        "acceptedCount": total_accepted,
        "attemptCount": total_attempts,
        "acceptedRate": (total_accepted / total_attempts) if total_attempts else 0,
        "apiUsage": total_api,
        "reductionPercent": {
            "mean": mean(reductions) if reductions else 0,
            "min": min(reductions) if reductions else 0,
            "max": max(reductions) if reductions else 0,
        },
        "reports": [
            {
                "language": item.get("language"),
                "source": item.get("source"),
                "model": item.get("model"),
                "initialTokens": item.get("initialTokens"),
                "finalTokens": item.get("finalTokens"),
                "reductionPercent": item.get("reductionPercent"),
                "valid": item.get("valid"),
            }
            for item in reports
        ],
    }
    return summary


def write_summary(run_dir: Path) -> Dict[str, Any]:
    summary = summarize_run_dir(run_dir)
    write_json(run_dir / "summary.json", summary)
    write_text(run_dir / "summary.md", render_summary_markdown(summary))
    return summary


def render_summary_markdown(summary: Dict[str, Any]) -> str:
    lines = [
        "# LPR+ Run Summary",
        "",
        f"- Reports: {summary['validReportCount']}/{summary['reportCount']} valid",
        f"- Invalid reports: {summary['invalidReportCount']}",
        f"- Final oracle: {'all pass' if summary['allFinalInteresting'] else 'not all pass'}",
        f"- Accepted: {summary['acceptedCount']}/{summary['attemptCount']}",
        f"- Total API tokens: {summary['apiUsage']['total_tokens']}",
        f"- Reduction mean/min/max: {summary['reductionPercent']['mean']:.2f}%/"
        f"{summary['reductionPercent']['min']:.2f}%/"
        f"{summary['reductionPercent']['max']:.2f}%",
        "",
        "| Language | Model | Initial | Final | Reduction | Valid | Source |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for item in summary["reports"]:
        lines.append(
            f"| {item['language']} | `{item['model']}` | {item['initialTokens']} | "
            f"{item['finalTokens']} | {float(item['reductionPercent'] or 0):.2f}% | "
            f"{'yes' if item['valid'] else 'no'} | `{item['source']}` |"
        )
    return "\n".join(lines) + "\n"

