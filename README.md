# Bird Pokedex

Offline bird scanner and identifier for South East Queensland — Bundaberg to Goondiwindi.

A cyberdeck project: camera + ONNX models + Raspberry Pi, no internet required in the field.

> **Status: Software MVP (offline dry-run).** An end-to-end *software* pipeline runs locally with
> no provider tokens and no media retrieval: ROI species candidates → licensed image manifest →
> dataset splits → training/inference skeletons → SQLite logging → cyberdeck UI.
> **No model has been trained** — the classifier/detector are runnable skeletons and the inference
> demo uses a deterministic mock. No provider requests, model training, or media retrieval happen by
> default; those remain explicit, opt-in commands.

Restrictive coding agents should read [docs/AGENT_README.md](docs/AGENT_README.md) before making
changes. It records the local-only boundaries, provider rules, and safe first commands for this repo.

---

## What it does (eventually)

1. **Scan** — retrieves biodiversity occurrence records from ALA, GBIF, eBird, and iNaturalist when explicitly configured to determine which species are present in the SEQ ROI
2. **Dataset** — builds a licensed image manifest from open-licence media metadata and explicitly requested media retrieval
3. **Train** — trains a detector + classifier on the species list
4. **Deploy** — exports to ONNX and runs offline on the cyberdeck
5. **Display** — FastAPI UI shows species name, photo, ID, facts, habitat

---

## Repository layout

```
birdidex/
├── apps/
│   ├── bird_roi_scan/    # CLI + provider stubs (ALA, GBIF, eBird, iNat, documented search APIs)
│   ├── training/         # Detector + classifier training pipeline
│   ├── inference/        # Edge inference: camera → detect → classify → lookup
│   ├── cyberdeck_ui/     # FastAPI UI for the cyberdeck screen
│   └── tools/            # Misc developer utilities
│
├── packages/
│   ├── bird_core/        # Shared IDs, enums, settings, logging
│   ├── bird_geo/         # ROI loading, shapely geometry, SEQ place names
│   ├── bird_data/        # SpeciesRecord, ImageManifestRecord, taxonomy
│   ├── bird_ml/          # Label maps, metrics, calibration, transforms
│   └── bird_device/      # Camera Protocol, battery, device telemetry
│
├── configs/
│   ├── roi/              # ROI polygon (REVIEW roi.example.geojson before use)
│   ├── scanner/          # Provider config, scoring weights, species filters
│   ├── training/         # Classifier, detector, augmentation config
│   ├── inference/        # Runtime config for cyberdeck
│   └── device/           # Cyberdeck hardware config
│
├── scripts/
│   ├── setup/            # verify_stack.py — smoke-test the environment
│   ├── dataset/          # 00–07: ROI, seed, occurrences, scoring, manifest, splits
│   └── inference/        # run_demo_inference.py — offline mock inference → SQLite log
│
├── os/                   # Custom OS / system image: image build, systemd, Wi-Fi AP, FTP (scaffold)
├── firmware/             # MCU firmware + electronics: sensors, buttons, power, wire protocol (scaffold)
├── tests/                # 148 passing offline tests, 2 skipped training-boundary tests
└── docs/                 # Architecture, work categories, environment, restructure audit
```

---

## Quick start

### 1. Install uv (package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Python 3.11

```bash
uv python install 3.11
```

### 3. Set up and verify the environment

```bash
uv sync --all-groups
make doctor
make test
```

For smaller installs:

```bash
make sync-dev       # development tools and tests
make sync-training  # dev + vision + PyTorch ROCm training stack on Linux x86_64
make sync-pi        # inference + UI stack for Raspberry Pi deployment
```

### 4. VSCodium

Use this interpreter:

`${workspaceFolder}/.venv/bin/python`

The repo includes `.vscode/settings.json` and `.vscode/launch.json` for that interpreter and
F5 debug configurations.

### 5. Configure local runtime settings

```bash
cp .env.example .env
# edit .env only if you choose to use configured providers
```

Provider tokens and private local runtime values stay in `.env` and must not be committed.

---

## Run the offline MVP pipeline

Every step below is **offline and deterministic** — no network, no provider tokens, no media
downloads. Outputs land in `data/manifests/`, `data/splits/`, `data/reports/`, and `data/db/`
(all git-ignored).

```bash
make dry-run-pipeline     # scan-candidates → build-manifest → build-splits → demo-inference
```

Or run the stages individually:

```bash
make scan-candidates      # ROI species scoring → data/manifests/roi_species_candidates.csv
                          #   + species_priority_tiers.csv + candidates report
make build-manifest       # iNat fixture → data/manifests/images_manifest.csv
                          #   + licence / class-balance / duplicate reports
make build-splits         # train/val/test CSVs + data/reports/split_report.md
make demo-inference       # mock detect→crop→classify→log → data/db/observations.sqlite3
make export-observations  # observation log → CSV + JSON under data/reports/
make run-ui-dev           # cyberdeck UI at http://127.0.0.1:8000/ (reads the local DB)
```

The scanner CLI is also available directly:

```bash
uv run python -m bird_roi_scan.cli candidates        # offline dry-run scan
uv run python -m bird_roi_scan.cli pull-occurrences  # refuses without --live (not implemented)
```

**Optional, explicit-only steps** (not run by default, not implemented as network calls in this MVP):

```bash
uv run python scripts/dataset/06_build_image_manifest.py --retrieve-media   # refuses (documents intent)
uv run python -m bird_roi_scan.cli pull-occurrences --live                  # refuses (not implemented)
```

Training and ONNX export are runnable **skeletons** — they fail fast with an install hint unless the
`training` / `inference` dependency groups are synced. No trained weights ship with the repo.

---

## Dependency groups

| Group | What it's for |
|-------|--------------|
| `dev` | ruff, pyright, pytest, mypy, pre-commit, notebooks |
| `scanner` | polars, pyarrow, duckdb, geopandas, shapely, provider parsing |
| `vision` | opencv-python-headless, pillow, albumentations, scikit-image |
| `training` | ROCm-routed torch, torchvision, torchaudio, timm, lightning, mlflow |
| `tensorflow` | tensorflow, keras |
| `inference` | onnx, onnxruntime, openvino, opencv-python-headless, psutil |
| `ui` | fastapi, uvicorn, jinja2 |
| `exporter` | onnx, onnxruntime, openvino |

---

## ROI

Two ROIs are defined:

- **Prototype ROI** (first build) — three SEQ corridors, encoded as one MultiPolygon in
  [configs/roi/prototype_roi.geojson](configs/roi/prototype_roi.geojson)
  ([config](configs/roi/prototype_roi.yaml)):
  - Lamington National Park / Springbrook
  - Bribie Island → Nudgee → Beerburrum
  - Noosa → Rainbow Beach → K'gari
- **Full ROI** (later) — Bundaberg → Sunshine Coast → Brisbane → Toowoomba → Warwick → Goondiwindi
  ([configs/roi/roi.yaml](configs/roi/roi.yaml)).

**Both GeoJSON polygons are coarse placeholders.** Review them against a Queensland map (QGIS)
before running any scans.

## Work categories

The project is split into eight work categories (ML pipeline, dataset/ROI, offline app/UI, custom
OS image, firmware, camera/sensor integration, deployment/field validation, shared contracts/docs).
See [docs/WORK_CATEGORIES.md](docs/WORK_CATEGORIES.md) for the mapping and per-category task sheets
in [docs/task_sheet/categories/](docs/task_sheet/categories/).

---

## Docs

- [docs/WORK_CATEGORIES.md](docs/WORK_CATEGORIES.md) — eight work categories mapped to the repo, with per-category task sheets
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — uv setup, Makefile commands, VSCodium, PyTorch ROCm notes
- [docs/AGENT_README.md](docs/AGENT_README.md) — agent-safe project boundaries and safe first commands
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design, data flow, design decisions
- [docs/RESTRUCTURE_AUDIT.md](docs/RESTRUCTURE_AUDIT.md) — 2026-06-13 monorepo restructure: what moved, merged, backed up
- [docs/AUDIT_STACK_SCAFFOLD.md](docs/AUDIT_STACK_SCAFFOLD.md) — earlier scaffold report (historical)

---

## History

The earlier root-level `bird-roi-scan/` prototype (working Pydantic models, web_search query
templates, and a lot of broken empty stubs) was folded into `apps/bird_roi_scan/` and the shared
packages during the **2026-06-13 restructure**, then removed from the tree. Its original source —
including the broken space-prefixed ` __init__.py` files — is archived under
`audit_backups/restructure_<timestamp>/`. Full details in
[docs/RESTRUCTURE_AUDIT.md](docs/RESTRUCTURE_AUDIT.md).
