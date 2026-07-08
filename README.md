# BIRDIDEX

Local bird image-dataset and model scaffold for South East Queensland field use.

Status: simplified Python package. The repo now has one installable package, one CLI, and one uv
environment. It can scaffold an ImageFolder-style dataset from the existing `class_index.json`,
write metadata-first image manifests, create deterministic local-file splits, and expose thin
training/inference/UI skeleton commands. It does not train models, run inference, retrieve media, or
make provider requests by default.

Restrictive coding agents should read [docs/AGENT_README.md](docs/AGENT_README.md) before making
changes.

## Layout

```text
birdidex/
├── src/birdidex/
│   ├── cli.py
│   ├── paths.py
│   ├── settings.py
│   ├── taxonomy.py
│   ├── roi.py
│   ├── providers.py
│   ├── images.py
│   ├── splits.py
│   ├── train.py
│   ├── infer.py
│   ├── db.py
│   └── ui/
├── configs/
├── data/
├── models/
├── notebooks/
├── scripts/
├── tests/
├── docs/
├── pyproject.toml
├── Makefile
└── README.md
```

## Quick Start

```bash
uv python install 3.11
uv sync --all-groups
uv run birdidex --help
uv run birdidex doctor
```

Common checks:

```bash
uv run birdidex images scaffold
uv run birdidex images report
uv run pytest
make test
```

## CLI

```bash
uv run birdidex doctor
uv run birdidex scan-candidates
uv run birdidex images scaffold
uv run birdidex images fetch-manifest
uv run birdidex images split --train 0.75 --val 0.15 --test 0.10 --seed 42
uv run birdidex images report
uv run birdidex train --help
uv run birdidex infer --help
uv run birdidex ui --help
```

`images fetch-manifest` is metadata-only. Without `--live`, it makes no provider requests and writes
empty manifest/report files. With `--live`, provider functions call documented APIs and store
normalized metadata records only; media download is still not implemented.

## Image Dataset

The only class source of truth is:

```text
data/processed/birddex/class_index.json
```

`birdidex images scaffold` creates:

```text
data/images/raw/{class_id:03d}.{label}/
data/images/review/{class_id:03d}.{label}/
data/images/quarantine/{class_id:03d}.{label}/
data/images/processed/{class_id:03d}.{label}/
data/images/splits/train/{class_id:03d}.{label}/
data/images/splits/val/{class_id:03d}.{label}/
data/images/splits/test/{class_id:03d}.{label}/
```

Classes are never inferred from folders. Ambiguous taxa are marked as not clean classifier classes
and excluded from fetching by default when common or scientific names contain `sp.` or `/`.

Generated outputs include:

- `data/images/class_folder_index.csv`
- `data/images/image_dataset_manifest.json`
- `data/images/metadata/image_records.jsonl`
- `data/images/reports/class_counts.csv`
- `data/images/reports/license_summary.csv`
- `data/images/reports/provider_summary.csv`
- `data/images/reports/review_queue.html`

Generated image data, local databases, logs, model weights, caches, provider tokens, and retrieved
media stay out of version control.

## Dependency Groups

The uv groups are intentionally small and named by workflow:

| Group | Purpose |
| --- | --- |
| `dev` | tests, linting, type checking, notebooks |
| `scanner` | ROI/geospatial and provider-support tools |
| `vision` | local image inspection and corruption checks |
| `training` | future training stack |
| `inference` | future local inference runtime |
| `ui` | local FastAPI UI scaffold |

## Docs

- [docs/AGENT_README.md](docs/AGENT_README.md) - agent boundaries and safe commands
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - current single-package architecture
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) - uv and dependency-group notes
- [docs/WORK_CATEGORIES.md](docs/WORK_CATEGORIES.md) - current work areas
