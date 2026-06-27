from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|==|!=|<=|>=|&&|\|\||[^\s]")


@dataclass
class TokenCounter:
    mode: str
    lpr_root: Optional[Path] = None

    def count_text(self, text: str, source_name: str = "small.c") -> int:
        if self.mode == "simple":
            return len(TOKEN_RE.findall(text))
        if self.mode not in {"auto", "lpr"}:
            raise ValueError(f"Unknown token counter mode: {self.mode}")
        jar = self.jar_path()
        if jar and jar.exists():
            with tempfile.TemporaryDirectory(prefix="lpr-plus-tokens-") as temp:
                path = Path(temp) / source_name
                path.write_text(text, encoding="utf-8")
                return self.count_file(path)
        if self.mode == "lpr":
            raise FileNotFoundError("LPR token_counter_deploy.jar was not found")
        return len(TOKEN_RE.findall(text))

    def count_file(self, path: Path) -> int:
        if self.mode == "simple":
            return len(TOKEN_RE.findall(path.read_text(encoding="utf-8")))
        jar = self.jar_path()
        if not jar or not jar.exists():
            if self.mode == "auto":
                return len(TOKEN_RE.findall(path.read_text(encoding="utf-8")))
            raise FileNotFoundError("LPR token_counter_deploy.jar was not found")
        result = subprocess.run(
            ["java", "-jar", str(jar), "--", str(path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        match = re.search(r"(\d+)\s*$", result.stdout)
        if not match:
            raise RuntimeError(f"Could not parse token counter output: {result.stdout!r}")
        return int(match.group(1))

    def jar_path(self) -> Optional[Path]:
        if not self.lpr_root:
            return None
        return self.lpr_root / "tools" / "token_counter_deploy.jar"

