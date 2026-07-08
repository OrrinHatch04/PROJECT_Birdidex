# Audit, Stack, and Scaffold Report

> **Historical (superseded).** This report describes the initial scaffold. The repo was later
> reorganised (2026-06-13): the scanner app moved from `apps/scanner/` (package `bird_scanner`)
> to `apps/bird_roi_scan/` (package `bird_roi_scan`), and the nested `bird-roi-scan/` project was
> removed. References to `apps/scanner/` below are kept as-written for the record — see
> [RESTRUCTURE_AUDIT.md](RESTRUCTURE_AUDIT.md) for the current layout.

**Date:** 2026-06-13  
**Task:** Initial scaffold of Bird Pokedex monorepo  
**Status:** Scaffold complete. Python 3.11 not yet installed. uv not yet installed.

---

## 1. Existing Files Found (pre-scaffold)

### Root level
| File | Status | Notes |
|------|--------|-------|
| `SEQ_BirdDex_Task_Sheet.md` | Preserved | Project specification document |
| `SEQ_BirdDex_Task_Sheet.tex` | Preserved | LaTeX source of specification |
| `SEQ_BirdDex_Model_Training_Skeleton.ipynb` | Preserved | Training skeleton notebook |

### `bird-roi-scan/` sub-project
This was an early prototype. All files preserved. Key findings:

| File | Condition | Notes |
|------|-----------|-------|
| `pyproject.toml` | Incomplete | Missing `name`, `version`, `requires-python`, no build system, no dev groups |
| `src/bird_roi_scan/__init__.py` | **BUG: leading space in filename** | File is named ` __init__.py` — Python cannot discover this package |
| All `src/**/__init__.py` | **BUG: leading space** | Same leading-space filename bug across all modules |
| `src/models/species.py` | Good | Pydantic Species model — content ported to `packages/bird_data/` |
| `src/models/occurrence.py` | Good | Pydantic Occurrence model — content preserved in bird-roi-scan |
| `src/models/evidence.py` | Good | Pydantic EvidenceRecord — preserved |
| `src/providers/base.py` | Good | ABC provider — upgraded to Protocol in new scaffold |
| `src/providers/ala.py` | Bug: imports cv2 | `import cv2` has no relation to ALA — likely copy/paste error |
| `src/providers/gbif.py` | Bug: imports pandas | Stub only — `import pandas` not needed at module level |
| `src/providers/ebird.py` | Same pandas import | Stub |
| `src/providers/inaturalist.py` | Same pandas import | Stub |
| `src/providers/web_search.py` | Good content | ROI place names and query templates preserved in new scaffold |
| `configs/roi.yaml` | Good | Incorporated into new `configs/roi/roi.yaml` |
| `configs/providers.yaml` | Good | Note: `web_search.engine` had an iNaturalist URL (copy/paste error) — fixed in new scaffold |
| `configs/scoring.yaml` | Empty | Only headers, no values — replaced with populated template |
| `.env.example` | Incorrect content | File contained only ".env.example" string — replaced |
| `.gitignore` | Incorrect content | File contained only "gitignore" — replaced |
| `tests/fixtures/sample_roi.geojson` | Invalid | Contained `{"region": ["SEQ"]}` — not a GeoJSON Feature — replaced |
| `tests/test_*.py` | All empty stubs | Replaced with real tests in new scaffold |
| `data/roi/region_of_interest.png` | Preserved | ROI image — keep for reference |
| `notebooks/01-03 *.ipynb` | Preserved | Sanity-check notebooks — keep |

### Files backed up
No files were deleted. The entire `bird-roi-scan/` directory is preserved as-is.

---

## 2. Files Created

### Root
- `.python-version` — pins 3.11
- `.env.example` — local runtime configuration template
- `.gitignore` — proper Python/data/model gitignore
- `pyproject.toml` — main workspace manifest with dependency groups
- `Makefile` — setup/sync/lint/typecheck/test/verify-stack/audit targets

### packages/
- `bird_core/` — NewType IDs, enums, settings, paths, logging
- `bird_geo/` — ROI loading, shapely geometry, SEQ place names
- `bird_data/` — SpeciesRecord, ImageManifestRecord, taxonomy helpers, storage
- `bird_ml/` — LabelMap, metrics, calibration (TemperatureScaler), transforms
- `bird_device/` — CameraProtocol, BatteryState, DeviceTelemetry

### apps/
- `apps/scanner/` — CLI, pipeline stub, provider Protocol + 5 provider stubs
- `apps/training/` — train_classifier, train_detector, export_onnx, evaluate stubs
- `apps/inference/` — camera, detector, classifier, species_db, app stubs
- `apps/cyberdeck_ui/` — FastAPI server with `/health` and `/` routes, Jinja2 template
- `apps/tools/` — README placeholder

### configs/
- `configs/roi/roi.yaml`, `roi.example.geojson` — approximate SEQ polygon (review before use)
- `configs/scanner/providers.yaml`, `scoring.yaml`, `species_filters.yaml`
- `configs/training/classifier.yaml`, `detector.yaml`, `augmentation.yaml`
- `configs/inference/runtime.yaml`
- `configs/device/cyberdeck.yaml`

### data/, models/, notebooks/
- All directories created with `.gitkeep` placeholders
- gitignore configured to exclude raw/interim/processed/manifests/reports/checkpoints/exports/quantized content but preserve `.gitkeep`

### scripts/
- `scripts/setup/verify_stack.py` — environment smoke-test, exits nonzero on failure
- `scripts/dataset/00_build_roi.py` — validate + export ROI WKT
- `scripts/dataset/01_seed_species.py` — species seed list stub
- `scripts/dataset/02_pull_structured_occurrences.py` — occurrence pull stub
- `scripts/dataset/03_run_keyword_scan.py` — keyword scan stub
- `scripts/dataset/04_score_species.py` — scoring stub
- `scripts/dataset/05_export_review_tables.py` — report export stub

### tests/
- `tests/conftest.py` — adds all src dirs to sys.path for uninstalled packages
- `tests/unit/test_imports.py` — 36 parametrised import checks
- `tests/unit/test_config.py` — 22 config existence + YAML validity checks
- `tests/unit/test_roi.py` — 5 ROI loading checks
- `tests/unit/test_provider_protocol.py` — 9 provider Protocol checks
- `tests/fixtures/sample_roi.geojson` — valid Polygon Feature for SEQ area
- `tests/fixtures/sample_occurrences.json` — 2 Kookaburra occurrence fixtures
- `tests/fixtures/sample_search_hits.json` — 1 keyword evidence fixture

### docs/
- `docs/AUDIT_STACK_SCAFFOLD.md` — this file
- `docs/ENVIRONMENT.md` — setup instructions
- `docs/ARCHITECTURE.md` — system architecture

---

## 3. Test Results (2026-06-13)

Run against **Python 3.14.5** (system Python — 3.11 not yet installed):

```
72 tests collected
71 passed
1 skipped  (test_export_roi_wkt_requires_shapely — shapely not installed)
0 failed
```

`verify_stack.py` result:
- 1 critical failure: `Python 3.11.x` (system has 3.14.5)
- All other critical checks: PASS
- 2 warnings: shapely not installed (install scanner group)

---

## 4. Commands Run

| Command | Result |
|---------|--------|
| `python3 --version` | Python 3.14.5 |
| `python3.11 --version` | Not found |
| `uv --version` | Not found |
| `python3 scripts/setup/verify_stack.py` | 1 critical fail (Python version), rest pass |
| `python3 -m pytest tests/unit/` | 71 passed, 1 skipped |

---

## 5. Dependency Risks and Notes

| Package | Risk | Notes |
|---------|------|-------|
| `torch` / `torchvision` | High — platform-sensitive | Training workstations use the uv ROCm source mapping. Raspberry Pi deployment should not install the training group. |
| `onnxruntime` | Medium | ARM builds exist but are separate packages (`onnxruntime-rpi` or compile from source). |
| `fiftyone` | High — complex native deps | Excluded from `vision` group — install manually if needed. |
| `opencv-python-headless` | Medium | The headless wheel is the repo standard; GUI OpenCV is excluded. |
| `geopandas` | Low-medium | Depends on GDAL/GEOS. Keep it in the scanner group rather than Pi deployment installs. |
| `postgis` | Removed | Was in old `bird-roi-scan/pyproject.toml` — not needed for current scope. |
| `dvc` | Removed | Was in old `bird-roi-scan/pyproject.toml` — add back if DVC is needed for data versioning. |
| `streamlit` | Removed | Was in old project — replaced with FastAPI for cyberdeck UI. |

---

## 6. Items Requiring Human Review

1. **Install uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Install Python 3.11**: `uv python install 3.11`.
3. **ROI polygon** (`configs/roi/roi.example.geojson`): The polygon is a coarse placeholder. Review the polygon against a Queensland map before running scans. Adjust to match the precise Bundaberg–Goondiwindi–SEQ boundary.
4. **eBird provider config**: Register at https://ebird.org/api/keygen and set `EBIRD_API_KEY` only in local `.env` if you choose to use eBird.
5. **Search provider config**: Choose a documented search provider API (Serper, Brave, SerpAPI) for the `web_search` provider and set `SEARCH_API_KEY` only in local `.env`. Do not scrape search result pages directly.
6. **`bird-roi-scan/` `__init__.py` filenames**: All `__init__.py` files in `bird-roi-scan/src/` have a leading space character in their filename (` __init__.py`). This prevents Python from treating them as package init files. Rename them: `mv " __init__.py" __init__.py` in each affected directory. These are listed below:
   - `bird-roi-scan/src/bird_roi_scan/ __init__.py`
   - `bird-roi-scan/src/geo/ __init__.py`
   - `bird-roi-scan/src/main/ __init__.py`
   - `bird-roi-scan/src/models/ __init__.py`
   - `bird-roi-scan/src/providers/ __init__.py`
   - `bird-roi-scan/src/reports/ __init__.py`
   - `bird-roi-scan/src/scan/ __init__.py`
   - `bird-roi-scan/src/score/ __init__.py`
   - `bird-roi-scan/src/storage/ __init__.py`
   - `bird-roi-scan/src/taxonomy/ __init__.py`
   - `bird-roi-scan/src/utils/ __init__.py`
7. **`bird-roi-scan/src/providers/ala.py`**: Contains `import cv2` — this is wrong. Needs real ALA API implementation.
8. **torch/onnxruntime for Raspberry Pi**: Use `make sync-pi` for deployment dependencies. Document any target-specific runtime gap in `configs/device/cyberdeck.yaml`.
9. **Species seed list**: `scripts/dataset/01_seed_species.py` needs a real species source. IOC World Bird List for Australia, Clements taxonomy, or an eBird Queensland checklist export are all viable starting points.

---

## 7. Unresolved Issues

- Python 3.11 is not installed on this machine. All scaffold and tests run on Python 3.14.5. The scaffold is compatible with 3.11 (no 3.12+ syntax used), but the official baseline is 3.11 per spec.
- uv is not installed. The Makefile targets degrade gracefully but `make setup` will print an error.
- shapely is not installed — `export_roi_wkt()` will raise ImportError until the scanner group is synced.
- No `.git` repository has been initialised at the repo root. Run `git init && git add . && git commit -m "Initial scaffold"` when ready.
