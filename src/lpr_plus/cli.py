from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from .benchmark import BenchmarkConfig, dry_run_plan, run_benchmark
from .catalog import load_transformations
from .doctor import render_doctor, run_doctor
from .provider import DEFAULT_OPENAI_BASE, ProviderConfig
from .reducer import ReduceConfig, run_reduce
from .summarize import write_summary
from .utils import env_value, language_from_path, load_dotenv, write_json


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as error:  # noqa: BLE001 - CLI prints user-facing errors.
        print(f"error: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lpr-plus",
        description="LPR+ program-reduction CLI and benchmark wrapper.",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check LPR+ and LPR runtime dependencies")
    add_common_lpr_args(doctor)
    doctor.add_argument("--api-key-env", default="OPENAI_API_KEY")
    doctor.add_argument("--json", action="store_true", help="Print JSON diagnostics")
    doctor.set_defaults(func=cmd_doctor)

    reduce_parser = subparsers.add_parser("reduce", help="Reduce one program with an oracle")
    add_common_lpr_args(reduce_parser)
    add_provider_args(reduce_parser)
    reduce_parser.add_argument("--language", choices=["c", "rust", "js"], default=None)
    reduce_parser.add_argument("--source", required=True, type=Path)
    reduce_parser.add_argument("--oracle", required=True)
    reduce_parser.add_argument("--out", required=True, type=Path)
    reduce_parser.add_argument(
        "--transformations",
        default="all35",
        help="base5, refined30, all35, or a JSON file",
    )
    reduce_parser.add_argument(
        "--token-counter",
        choices=["auto", "lpr", "simple"],
        default="auto",
    )
    reduce_parser.add_argument("--oracle-timeout", type=int, default=120)
    reduce_parser.add_argument("--save-raw-api", action="store_true")
    reduce_parser.add_argument("--save-candidates", action="store_true")
    reduce_parser.set_defaults(func=cmd_reduce)

    benchmark = subparsers.add_parser("benchmark", help="Run LPR+ benchmark presets")
    add_common_lpr_args(benchmark)
    add_provider_args(benchmark)
    benchmark.add_argument(
        "--preset",
        choices=["smoke", "selected", "full"],
        default="smoke",
    )
    benchmark.add_argument("--out", required=True, type=Path)
    benchmark.add_argument("--repeats", type=int, default=1)
    benchmark.add_argument("--parallelism", type=int, default=6)
    benchmark.add_argument("--dry-run", action="store_true")
    benchmark.add_argument(
        "--languages",
        default="c,rust,js",
        help="Comma-separated languages: c,rust,js",
    )
    benchmark.add_argument(
        "--token-counter",
        choices=["auto", "lpr", "simple"],
        default="auto",
    )
    benchmark.add_argument("--oracle-timeout", type=int, default=120)
    benchmark.add_argument("--save-raw-api", action="store_true")
    benchmark.add_argument("--save-candidates", action="store_true")
    benchmark.set_defaults(func=cmd_benchmark)

    summarize = subparsers.add_parser("summarize", help="Summarize an LPR+ run directory")
    summarize.add_argument("--run-dir", required=True, type=Path)
    summarize.add_argument("--json", action="store_true", help="Print JSON summary")
    summarize.set_defaults(func=cmd_summarize)

    parser.set_defaults(func=cmd_default)
    return parser


def add_common_lpr_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--lpr-root",
        type=Path,
        default=None,
        help="Path to the LPR artifact root; defaults to LPR_ROOT or /tmp/LPR when present",
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))


def add_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        default="openai-compatible",
        choices=["openai-compatible", "mock"],
    )
    parser.add_argument("--api-base", default=DEFAULT_OPENAI_BASE)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--model", default="gpt-3.5-turbo-0125")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument(
        "--max-tokens-param",
        choices=["max_tokens", "max_completion_tokens"],
        default="max_tokens",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--mock-response-file", type=Path, default=None)


def cmd_default(args: argparse.Namespace) -> int:
    if args.version:
        from . import __version__

        print(__version__)
        return 0
    build_parser().print_help()
    return 0


def resolve_lpr_root(value: Optional[Path]) -> Path:
    candidates = []
    if value:
        candidates.append(value)
    if os.environ.get("LPR_ROOT"):
        candidates.append(Path(os.environ["LPR_ROOT"]))
    candidates.extend([Path("/tmp/LPR"), Path("../LPR"), Path("LPR"), Path("external/LPR")])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (value or Path("/tmp/LPR")).resolve()


def provider_config(args: argparse.Namespace) -> ProviderConfig:
    dotenv = load_dotenv(args.env_file)
    provider = "mock" if args.provider == "mock" else "openai-compatible"
    return ProviderConfig(
        provider=provider,
        model=args.model,
        api_base=args.api_base,
        api_key=env_value(args.api_key_env, dotenv),
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        retries=args.retries,
        max_tokens_param=args.max_tokens_param,
        mock_response_file=args.mock_response_file,
    )


def cmd_doctor(args: argparse.Namespace) -> int:
    result = run_doctor(
        resolve_lpr_root(args.lpr_root),
        api_key_env=args.api_key_env,
        dotenv_path=args.env_file,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_doctor(result), end="")
    return 0 if result["ok"] else 1


def cmd_reduce(args: argparse.Namespace) -> int:
    language = args.language or language_from_path(args.source)
    report = run_reduce(
        ReduceConfig(
            language=language,
            source=args.source,
            oracle=args.oracle,
            out_dir=args.out,
            provider=provider_config(args),
            transformations=load_transformations(args.transformations),
            lpr_root=resolve_lpr_root(args.lpr_root),
            token_counter_mode=args.token_counter,
            oracle_timeout=args.oracle_timeout,
            save_raw_api=args.save_raw_api,
            save_candidates=args.save_candidates,
        )
    )
    print(json.dumps({"report": str(args.out / "report.json"), "valid": report["valid"]}, indent=2))
    return 0 if report["valid"] else 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    languages = [item.strip() for item in args.languages.split(",") if item.strip()]
    config = BenchmarkConfig(
        lpr_root=resolve_lpr_root(args.lpr_root),
        preset=args.preset,
        out_dir=args.out,
        provider=provider_config(args),
        repeats=args.repeats,
        parallelism=args.parallelism,
        token_counter_mode=args.token_counter,
        oracle_timeout=args.oracle_timeout,
        dry_run=args.dry_run,
        save_raw_api=args.save_raw_api,
        save_candidates=args.save_candidates,
        languages=languages,
    )
    if args.dry_run:
        plan = dry_run_plan(config)
        write_json(args.out / "plan.json", plan)
        print(json.dumps(plan, indent=2))
        return 0
    summary = run_benchmark(config)
    print(json.dumps({"summary": str(args.out / "summary.json"), "reports": summary["reportCount"]}, indent=2))
    return 0 if summary["invalidReportCount"] == 0 else 1


def cmd_summarize(args: argparse.Namespace) -> int:
    summary = write_summary(args.run_dir)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Wrote {args.run_dir / 'summary.json'} and {args.run_dir / 'summary.md'}")
    return 0
