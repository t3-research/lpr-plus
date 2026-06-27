import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ)
ENV["PYTHONPATH"] = str(ROOT / "src")


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "lpr_plus", *args],
        cwd=ROOT,
        env=ENV,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class CliTest(unittest.TestCase):
    def test_selected_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "dry"
            result = run_cli(
                "benchmark",
                "--lpr-root",
                "external/LPR",
                "--preset",
                "selected",
                "--dry-run",
                "--out",
                str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads((out / "plan.json").read_text())
            self.assertEqual(plan["caseCount"], 3)
            self.assertEqual(plan["suiteCount"], 2)
            self.assertEqual(plan["taskCount"], 6)

    def test_mock_reduce_accepts_smaller_oracle_passing_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            source = work / "small.c"
            oracle = work / "r.sh"
            response = work / "response.txt"
            out = work / "out"
            source.write_text(
                textwrap.dedent(
                    """
                    int main(void) {
                      int unused = 1;
                      return 0;
                    }
                    """
                ).strip()
                + "\n"
            )
            oracle.write_text("#!/usr/bin/env bash\ngrep -q 'return 0' small.c\n")
            oracle.chmod(0o755)
            response.write_text("```c\nint main(void) { return 0; }\n```\n")
            result = run_cli(
                "reduce",
                "--lpr-root",
                "external/LPR",
                "--provider",
                "mock",
                "--mock-response-file",
                str(response),
                "--token-counter",
                "simple",
                "--language",
                "c",
                "--source",
                str(source),
                "--oracle",
                str(oracle),
                "--transformations",
                "base5",
                "--out",
                str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((out / "report.json").read_text())
            self.assertTrue(report["valid"])
            self.assertGreaterEqual(report["acceptedCount"], 1)
            self.assertLess(report["finalTokens"], report["initialTokens"])


if __name__ == "__main__":
    unittest.main()
