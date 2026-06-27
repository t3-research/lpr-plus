from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .utils import env_value, load_dotenv


@dataclass
class Check:
    name: str
    status: str
    detail: str

    def to_json(self) -> Dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def run_doctor(
    lpr_root: Path,
    api_key_env: str = "OPENAI_API_KEY",
    dotenv_path: Optional[Path] = None,
) -> Dict[str, object]:
    dotenv = load_dotenv(dotenv_path)
    checks: List[Check] = []

    checks.append(Check("python", "pass", sys.version.split()[0]))

    if lpr_root.exists():
        checks.append(Check("lpr-root", "pass", str(lpr_root)))
    else:
        checks.append(Check("lpr-root", "fail", f"not found: {lpr_root}"))

    jar = lpr_root / "tools" / "token_counter_deploy.jar"
    checks.append(
        Check(
            "token-counter",
            "pass" if jar.exists() else "fail",
            str(jar),
        )
    )

    for language in ("c", "rust", "js"):
        suite = lpr_root / "benchmark_suites" / language / "perses_rename"
        checks.append(
            Check(
                f"benchmark-{language}",
                "pass" if suite.exists() else "fail",
                str(suite),
            )
        )

    java = shutil.which("java")
    checks.append(Check("java", "pass" if java else "fail", java or "not found"))

    docker = shutil.which("docker")
    docker_detail = docker or "not found; this is expected inside some experiment containers"
    checks.append(Check("docker", "pass" if docker else "warn", docker_detail))

    key = env_value(api_key_env, dotenv)
    checks.append(
        Check(
            "api-key",
            "pass" if key else "warn",
            f"{api_key_env} {'is set' if key else 'is not set'}",
        )
    )

    if jar.exists() and java:
        try:
            result = subprocess.run(
                ["java", "-jar", str(jar), "--help"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
            )
            status = "pass" if result.returncode in {0, 1} else "warn"
            detail = (result.stdout or result.stderr or "").strip().splitlines()[:1]
            checks.append(Check("token-counter-exec", status, detail[0] if detail else "ran"))
        except Exception as error:  # noqa: BLE001 - doctor reports diagnostics.
            checks.append(Check("token-counter-exec", "warn", str(error)))

    failed = [item for item in checks if item.status == "fail"]
    return {
        "ok": not failed,
        "checks": [item.to_json() for item in checks],
        "cwd": os.getcwd(),
    }


def render_doctor(result: Dict[str, object]) -> str:
    lines = ["LPR+ doctor"]
    for item in result["checks"]:  # type: ignore[index]
        status = item["status"].upper()
        lines.append(f"- [{status}] {item['name']}: {item['detail']}")
    return "\n".join(lines) + "\n"

