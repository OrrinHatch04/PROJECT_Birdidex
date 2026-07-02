# Bird Pokedex

Offline bird scanner and identifier for South East Queensland — Bundaberg to Goondiwindi.

A cyberdeck project: camera + ONNX models + Raspberry Pi, no internet required in the field.

> **Status: Scaffold only.** Packages import and tests pass. No live API calls, no model training, no image downloads yet.

---

## What it does (eventually)

1. **Scan** — pulls bird occurrence records from ALA, GBIF, eBird, iNaturalist to determine which species are present in the SEQ ROI
2. **Dataset** — builds a labelled image manifest from open-licensed photos
3. **Train** — trains a detector + classifier on the species list
4. **Deploy** — exports to ONNX and runs offline on the cyberdeck
5. **Display** — FastAPI UI shows species name, photo, ID, facts, habitat

---

## Repository layout

```
birdidex/
├── apps/
│   ├── bird_roi_scan/    # CLI + provider stubs (ALA, GBIF, eBird, iNat, web)
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
│   └── dataset/          # 00–05 pipeline scripts (stubs)
│
├── tests/                # 81 passing tests (imports, config, ROI, providers)
└── docs/                 # Architecture, environment, restructure audit
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

Or via conda if uv isn't available yet:

```bash
conda create -n birdidex python=3.11
conda activate birdidex
```

### 3. Set up the environment

```bash
make setup          # creates .venv, syncs dev group
make sync-scanner   # add scanner dependencies (geopandas, shapely, polars…)
```

### 4. Verify the stack

```bash
make verify-stack   # prints pass/fail for Python version + all packages
make test           # runs pytest
```

### 5. Configure secrets

```bash
cp .env.example .env
# edit .env — add EBIRD_API_KEY and SEARCH_API_KEY
```

---

## Dependency groups

| Group | What it's for |
|-------|--------------|
| `dev` | ruff, pyright, pytest, pre-commit |
| `scanner` | polars, geopandas, shapely, duckdb, rapidfuzz |
| `vision` | opencv, pillow, albumentations |
| `training` | torch, torchvision, timm, mlflow |
| `inference` | onnx, onnxruntime, numpy, psutil |
| `ui` | fastapi, uvicorn, jinja2 |

---

## ROI

The region of interest covers Bundaberg → Sunshine Coast → Brisbane → Toowoomba → Warwick → Goondiwindi.

**`configs/roi/roi.example.geojson` is a coarse placeholder polygon.** Review it against a Queensland map before running any scans.

---

## Docs

- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — full setup guide, conda fallback, pre-commit
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
