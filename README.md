# LPR+

LPR+ is a Python command-line wrapper for LPR-style program reduction. It can
reduce one program with an interestingness oracle, preview benchmark runs, and
run LPR+ transformation suites through an OpenAI-compatible chat-completions
provider.

This repository contains the LPR+ source package only. It does not vendor the
original LPR artifact, Perses, Vulcan, C-Reduce, the LPR token counter jar, or
any API keys.

## Contents

- `src/lpr_plus/`: CLI implementation and bundled transformation catalogs.
- `tests/`: unit and smoke tests.
- `examples/`: a tiny C input and oracle for local demos.
- `docker/Dockerfile`: optional Docker wrapper built on the public LPR image.
- `LICENSE` and `NOTICE`: project and third-party distribution notes.

## Requirements

- Python 3.9 or newer.
- Bash for the example oracle.
- Optional: an existing LPR checkout or the public `m492zhan/lpr:latest` Docker
  image for full LPR integration.
- Optional: an API key for an OpenAI-compatible provider when using real model
  calls.

## Install

From the repository root:

```bash
python3 -m pip install .
lpr-plus --help
```

For development without installing:

```bash
env PYTHONPATH=src python3 -m lpr_plus --help
```

## Quickstart Without API Keys

This offline demo uses the mock provider. It proposes a smaller C program,
runs the oracle, and writes a reduction report under `runs/mock/reduce`.

```bash
mkdir -p runs/mock
printf '```c\nint main(void) { return 0; }\n```\n' > runs/mock/response.md

env PYTHONPATH=src python3 -m lpr_plus reduce \
  --provider mock \
  --mock-response-file runs/mock/response.md \
  --token-counter simple \
  --lpr-root /tmp/LPR \
  --language c \
  --source examples/small.c \
  --oracle examples/r.sh \
  --transformations base5 \
  --out runs/mock/reduce

sed -n '1,120p' runs/mock/reduce/report.md
sed -n '1,80p' runs/mock/reduce/final-small.c
```

Expected behavior: `report.json` and `report.md` are created, the final oracle
passes, and at least one transformation is accepted because the unused local
variable is removed.

## Common Commands

Check the local LPR environment:

```bash
lpr-plus doctor --lpr-root /path/to/LPR
```

Preview a benchmark plan without model calls:

```bash
lpr-plus benchmark \
  --lpr-root /path/to/LPR \
  --preset selected \
  --dry-run \
  --out runs/selected-dry-run
```

Run a single reduction with a real provider:

```bash
export OPENAI_API_KEY=...

lpr-plus reduce \
  --lpr-root /path/to/LPR \
  --provider openai-compatible \
  --api-key-env OPENAI_API_KEY \
  --model <chat-completions-model> \
  --temperature 0 \
  --language c \
  --source examples/small.c \
  --oracle examples/r.sh \
  --transformations all35 \
  --out runs/reduce-real
```

For providers with a custom OpenAI-compatible endpoint, pass `--api-base` and
the matching key environment variable:

```bash
lpr-plus reduce \
  --lpr-root /path/to/LPR \
  --provider openai-compatible \
  --api-base https://example.com/v1/chat/completions \
  --api-key-env PROVIDER_API_KEY \
  --model <provider-model> \
  --language c \
  --source examples/small.c \
  --oracle examples/r.sh \
  --out runs/reduce-provider
```

Use `--max-tokens-param max_completion_tokens` for providers that require that
field name instead of `max_tokens`.

## Docker

The Dockerfile builds a thin LPR+ wrapper on top of the public LPR image:

```bash
docker build -f docker/Dockerfile -t lpr-plus:latest .
docker run --rm -it --cap-add SYS_PTRACE lpr-plus:latest lpr-plus --help
docker run --rm -it --cap-add SYS_PTRACE lpr-plus:latest \
  lpr-plus doctor --lpr-root /tmp/LPR
```

Pass API keys at runtime, never during image build:

```bash
docker run --rm -it \
  --cap-add SYS_PTRACE \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -v "$PWD/runs:/workspace/runs" \
  lpr-plus:latest \
  lpr-plus benchmark --lpr-root /tmp/LPR --preset selected --dry-run --out /workspace/runs/selected
```

## Tests

Run the test suite from the repository root:

```bash
env PYTHONPATH=src python3 -m unittest discover -s tests
```

The tests avoid real API calls. They cover the transformation catalog, dry-run
benchmark planning, and the mock-provider reduction path.

## Outputs

Reduction runs write:

- `report.json`: machine-readable metadata, oracle results, token counts, and
  accepted transformations.
- `report.md`: a compact human-readable report.
- `final-<source>`: the final reduced program.
- Optional raw provider requests, responses, and candidates when
  `--save-raw-api` or `--save-candidates` is used.

Benchmark runs write per-case reports plus `summary.json` and `summary.md`.

## Troubleshooting

- If `lpr-plus` is not found, install with `python3 -m pip install .` or run
  through `env PYTHONPATH=src python3 -m lpr_plus`.
- If `doctor` warns about `/tmp/LPR`, pass `--lpr-root /path/to/LPR` or run
  inside the Docker image.
- If the LPR token counter jar is unavailable, use `--token-counter simple` for
  lightweight local smoke tests.
- If provider calls fail, check `--api-base`, `--api-key-env`, `--model`, and
  whether the key is present in the environment or `.env.local`.
- If an oracle fails unexpectedly, make sure the oracle works when run from the
  source file's directory and that it exits with status 0 for interesting
  candidates.

## Limitations

- LPR+ proposes transformations, but every accepted candidate must still be
  smaller and pass the external interestingness oracle.
- Full benchmark runs can be slow and may spend API credits; run `--dry-run`
  first.
- The source package does not include the original LPR artifact or other
  third-party reducers. Users must obtain those tools under their upstream
  terms.
- The bundled transformation catalogs are research-prototype rules intended for
  reproducible experiments, not a guarantee of optimal reduction.

## Third-Party Notice

LPR+ is distributed as source code under the MIT license. External tools
commonly used with LPR+ include:

- LPR: https://github.com/zhangxiaosa/LPR
- Perses: https://github.com/uw-pluverse/perses
- C-Reduce: https://github.com/csmith-project/creduce
- LPR Docker image: `m492zhan/lpr:latest`

Perses is GPLv3. The inspected local LPR artifact did not include an explicit
license file. Users are responsible for obtaining and using external tools
under their upstream terms.
