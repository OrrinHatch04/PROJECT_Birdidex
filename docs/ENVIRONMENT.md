# Environment Setup

## Python 3.11 Baseline

This project requires Python 3.11. Do not use 3.12+ for the main environment — torch/onnxruntime wheels are more stable on 3.11 at time of writing.

### Option A — uv (recommended)

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Pin Python 3.11 and create venv
uv python install 3.11
uv python pin 3.11
uv sync --group dev

# Verify
python --version   # should print Python 3.11.x
make verify-stack
```

### Option B — conda/micromamba (fallback for native deps)

Use conda when pip wheels fail (common on ARM/Raspberry Pi, or for gdal/geos/torch):

```bash
conda create -n birdidex python=3.11
conda activate birdidex

# Install native-dep packages via conda first
conda install -c conda-forge geopandas shapely pyproj

# Then install the rest via pip/uv inside the conda env
pip install -e .
pip install --group dev
```

---

## Dependency Groups

Install only what you need:

| Group | Command | Contains |
|-------|---------|---------|
| dev | `uv sync --group dev` | ruff, pyright, pytest, hypothesis, pre-commit |
| scanner | `uv sync --group scanner` | polars, geopandas, shapely, duckdb, rapidfuzz, bs4 |
| vision | `uv sync --group vision` | opencv, pillow, albumentations, scikit-image |
| training | `uv sync --group training` | torch, torchvision, timm, mlflow, tensorboard |
| inference | `uv sync --group inference` | onnx, onnxruntime, numpy, opencv, psutil |
| ui | `uv sync --group ui` | fastapi, uvicorn, jinja2 |

Combine groups:

```bash
uv sync --group dev --group scanner
uv sync --group dev --group inference --group ui
```

---

## Smoke Tests

```bash
# Quick: run verify_stack.py (no network, no GPU, no data)
python scripts/setup/verify_stack.py

# Full unit tests
python -m pytest tests/unit/ -v

# Or via Makefile
make verify-stack
make test
```

---

## When to Use conda as Fallback

Use conda instead of pip when:
- Installing `torch`/`torchvision` on ARM (Raspberry Pi, Apple Silicon)
- Installing `geopandas` (needs GDAL/GEOS native libs)
- Installing `onnxruntime` on non-standard platforms
- Any package that fails with a pip wheel error mentioning native compilation

In all other cases, uv + pip wheels is preferred.

---

## Pre-commit Hooks (optional)

```bash
pre-commit install
pre-commit run --all-files
```

Runs ruff and pyright before each commit.
