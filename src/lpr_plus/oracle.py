from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class OracleResult:
    passed: bool
    status: Optional[int]
    duration_ms: int
    stdout: str
    stderr: str
    error: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "passed": self.passed,
            "status": self.status,
            "durationMs": self.duration_ms,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
        }


def _copy_seed(seed_dir: Path, dest: Path) -> None:
    for item in seed_dir.iterdir():
        target = dest / item.name
        if item.is_dir():
            if item.name in {".git", "__pycache__"}:
                continue
            shutil.copytree(item, target, symlinks=True)
        elif item.is_file():
            shutil.copy2(item, target)


def run_oracle(
    program_text: str,
    source_path: Path,
    oracle: str,
    timeout: int = 120,
) -> OracleResult:
    started = time.time()
    source_path = source_path.resolve()
    seed_dir = source_path.parent
    with tempfile.TemporaryDirectory(prefix="lpr-plus-oracle-") as temp:
        workdir = Path(temp)
        _copy_seed(seed_dir, workdir)
        candidate_path = workdir / source_path.name
        candidate_path.write_text(program_text, encoding="utf-8")

        oracle_path = Path(oracle)
        if oracle_path.exists():
            oracle_resolved = oracle_path.resolve()
            try:
                relative = oracle_resolved.relative_to(seed_dir.resolve())
                command = f"bash {relative}"
            except ValueError:
                command = f"bash {oracle_resolved}"
        else:
            command = oracle
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=workdir,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            return OracleResult(
                passed=result.returncode == 0,
                status=result.returncode,
                duration_ms=int((time.time() - started) * 1000),
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except Exception as error:  # noqa: BLE001 - CLI reports oracle errors.
            return OracleResult(
                passed=False,
                status=None,
                duration_ms=int((time.time() - started) * 1000),
                stdout="",
                stderr="",
                error=str(error),
            )

