# Environment Setup

BirdIDEX is a Python 3.11 uv workspace. The root `.python-version` pins `3.11`, and
`pyproject.toml` requires `>=3.11,<3.12`.

Do not use Conda for this repo. The reproducible path is uv plus the root `uv.lock`.

## Quick Start

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11

uv sync --all-groups
make doctor
make test
```

The project interpreter is:

```text
${workspaceFolder}/.venv/bin/python
```

From a shell, activate it only when you need an interactive environment:

```bash
source .venv/bin/activate
```

For commands, prefer `uv run ...` or the root `Makefile` targets so the workspace lockfile and
editable internal packages are respected.

## VSCodium

Use the workspace interpreter:

```text
${workspaceFolder}/.venv/bin/python
```

The repo includes:

- `.vscode/settings.json` for the interpreter, pytest, and import analysis paths
- `.vscode/launch.json` for F5 debugging of current files and common repo entrypoints

## Dependency Groups

Install the smallest group set that matches the job.

| Group | Command | Contains |
|-------|---------|----------|
| base | `uv sync` | core config/CLI/schema deps, numpy, pandas, internal workspace packages |
| dev | `uv sync --group dev` | pytest, ruff, pyright, mypy, pre-commit, notebooks |
| scanner | `uv sync --group scanner` | polars, pyarrow, duckdb, geopandas, shapely, provider parsing |
| vision | `uv sync --group vision` | opencv-python-headless, pillow, image tools, augmentation tools |
| training | `uv sync --group training` | torch, torchvision, torchaudio, timm, lightning, mlflow |
| tensorflow | `uv sync --group tensorflow` | tensorflow, keras |
| inference | `uv sync --group inference` | onnx, onnxruntime, openvino, opencv-python-headless, psutil |
| ui | `uv sync --group ui` | fastapi, uvicorn, jinja2 |
| exporter | `uv sync --group exporter` | onnx, onnxruntime, openvino |

Common combinations:

```bash
make sync-dev
make sync-training
make sync-pi
make sync-all
```

## PyTorch Backend

Linux x86_64 training workstations use the PyTorch ROCm 6.4 wheel index for AMD GPUs:

```toml
[[tool.uv.index]]
name = "pytorch-rocm64"
url = "https://download.pytorch.org/whl/rocm6.4"
explicit = true
```

The training group pins the matched triplet:

- `torch==2.9.0`
- `torchvision==0.24.0`
- `torchaudio==2.9.0`

On ROCm, PyTorch still reports GPU access through `torch.cuda` APIs. Check the actual backend with:

```bash
make doctor
```

Raspberry Pi deployment should use `make sync-pi`, not the full training group.

## OpenCV Policy

Use `opencv-python-headless` only. GUI OpenCV windows are not required, and the GUI wheel conflicts
with the headless wheel. The uv configuration excludes `opencv-python` so transitive packages cannot
pull it into the locked environment.

## Makefile Commands

| Target | What it does |
|--------|--------------|
| `make help` | Print available targets |
| `make sync` | `uv sync` |
| `make sync-all` | `uv sync --all-groups` |
| `make sync-dev` | Sync `dev` group |
| `make sync-training` | Sync `dev` + `vision` + `training` groups |
| `make sync-pi` | Sync `inference` + `ui` groups |
| `make test` | `uv run pytest` |
| `make lint` | `uv run ruff check .` |
| `make format` | `uv run ruff format .` |
| `make typecheck` | `uv run pyright` |
| `make mypy` | Optional `uv run mypy packages apps tests` |
| `make doctor` | Run `scripts/env/doctor.py` |
| `make clean` | Remove Python and test caches only |

`make clean` does not delete `.venv`, `data/`, models, notebooks, or generated runtime artifacts.

## Smoke Tests

```bash
make doctor
make test
```

`make doctor` exits nonzero only for hard environment failures: wrong Python minor version or not
running from the project `.venv` when invoked through Make. Missing optional ML packages are reported
as diagnostics, not hard failures.

## Pre-commit Hooks

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```
