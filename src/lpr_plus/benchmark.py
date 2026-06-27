from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .catalog import cumulative_suites
from .provider import ProviderConfig
from .reducer import ReduceConfig, run_reduce
from .summarize import summarize_run_dir
from .utils import source_name_for_language, utc_now, write_json


LANGUAGES = ("c", "rust", "js")
SELECTED_CASES = {
    "c": "benchmark_suites/c/perses_rename/gcc-71626",
    "rust": "benchmark_suites/rust/perses_rename/rust-78720",
    "js": "benchmark_suites/js/perses_rename/js-5",
}


@dataclass
class BenchmarkConfig:
    lpr_root: Path
    preset: str
    out_dir: Path
    provider: ProviderConfig
    repeats: int = 1
    parallelism: int = 6
    token_counter_mode: str = "auto"
    oracle_timeout: int = 120
    dry_run: bool = False
    save_raw_api: bool = False
    save_candidates: bool = False
    languages: Optional[List[str]] = None


def discover_cases(lpr_root: Path, preset: str, languages: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    language_filter = set(languages or LANGUAGES)
    cases: List[Dict[str, Any]] = []
    if preset == "smoke":
        selected = {"c": SELECTED_CASES["c"]}
    elif preset == "selected":
        selected = SELECTED_CASES
    elif preset == "full":
        selected = {}
    else:
        raise ValueError(f"Unknown benchmark preset: {preset}")

    if preset in {"smoke", "selected"}:
        for language, relative in selected.items():
            if language not in language_filter:
                continue
            cases.append(_case_from_relative(lpr_root, language, relative))
        return cases

    for language in LANGUAGES:
        if language not in language_filter:
            continue
        suite_dir = lpr_root / "benchmark_suites" / language / "perses_rename"
        source_name = source_name_for_language(language)
        if not suite_dir.exists():
            continue
        for case_dir in sorted(item for item in suite_dir.iterdir() if item.is_dir()):
            if (case_dir / source_name).exists() and (case_dir / "r.sh").exists():
                relative = case_dir.relative_to(lpr_root).as_posix()
                cases.append(_case_from_relative(lpr_root, language, relative))
    return cases


def _case_from_relative(lpr_root: Path, language: str, relative: str) -> Dict[str, Any]:
    source_name = source_name_for_language(language)
    case_dir = lpr_root / relative
    return {
        "language": language,
        "caseId": case_dir.name,
        "relativeCaseDir": relative,
        "source": case_dir / source_name,
        "oracle": str(case_dir / "r.sh"),
    }


def dry_run_plan(config: BenchmarkConfig) -> Dict[str, Any]:
    cases = discover_cases(config.lpr_root, config.preset, config.languages)
    suites = cumulative_suites()
    tasks = [
        {
            "language": case["language"],
            "caseId": case["caseId"],
            "suite": suite["id"],
            "repeat": repeat,
            "transformations": len(suite["transformations"]),
        }
        for case in cases
        for repeat in range(1, config.repeats + 1)
        for suite in suites
    ]
    return {
        "preset": config.preset,
        "lprRoot": str(config.lpr_root),
        "caseCount": len(cases),
        "suiteCount": len(suites),
        "repeatCount": config.repeats,
        "taskCount": len(tasks),
        "cases": [
            {
                "language": case["language"],
                "caseId": case["caseId"],
                "source": str(case["source"]),
                "oracle": case["oracle"],
            }
            for case in cases
        ],
        "tasks": tasks,
    }


def run_benchmark(config: BenchmarkConfig) -> Dict[str, Any]:
    if config.parallelism < 1 or config.parallelism > 8:
        raise ValueError("--parallelism must be between 1 and 8")
    config.out_dir.mkdir(parents=True, exist_ok=True)
    plan = dry_run_plan(config)
    write_json(config.out_dir / "plan.json", plan)
    if config.dry_run:
        return plan

    suites = cumulative_suites()
    cases = discover_cases(config.lpr_root, config.preset, config.languages)
    run_id = f"{config.preset}-{utc_now().replace(':', '-')}"
    jobs = []
    for case in cases:
        for repeat in range(1, config.repeats + 1):
            for suite in suites:
                suite_dir = (
                    config.out_dir
                    / case["language"]
                    / case["caseId"]
                    / f"repeat-{repeat:02d}"
                    / suite["id"]
                )
                jobs.append((case, repeat, suite, suite_dir))

    reports: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.parallelism) as executor:
        future_to_job = {
            executor.submit(
                run_reduce,
                ReduceConfig(
                    language=case["language"],
                    source=case["source"],
                    oracle=case["oracle"],
                    out_dir=suite_dir,
                    provider=config.provider,
                    transformations=suite["transformations"],
                    lpr_root=config.lpr_root,
                    token_counter_mode=config.token_counter_mode,
                    oracle_timeout=config.oracle_timeout,
                    save_raw_api=config.save_raw_api,
                    save_candidates=config.save_candidates,
                    run_id=run_id,
                ),
            ): (case, repeat, suite)
            for case, repeat, suite, suite_dir in jobs
        }
        for future in concurrent.futures.as_completed(future_to_job):
            reports.append(future.result())

    summary = summarize_run_dir(config.out_dir)
    write_json(config.out_dir / "summary.json", summary)
    return summary

