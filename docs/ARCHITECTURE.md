# Architecture

## System Overview

The Bird Pokedex is an offline cyberdeck that identifies birds in South East Queensland (Bundaberg to Goondiwindi) using a camera, an ONNX detector+classifier, and a pre-built species database.

```
[ Camera ] → [ Detector ] → [ Classifier ] → [ Species DB ] → [ Cyberdeck UI ]
                                                   ↑
                                        [ Training Pipeline ]
                                                   ↑
                                        [ Dataset Builder ]
                                                   ↑
                                        [ ROI Scanner ]
```

---

## Components

### 1. ROI Scanner (`apps/scanner/`)

**Purpose:** Determine which bird species are present in the SEQ ROI.

**Primary evidence (structured occurrence APIs):**
- **ALA** — Atlas of Living Australia. Best coverage for Australian records. Free, no auth.
- **GBIF** — Global Biodiversity Information Facility. International aggregate. Free, no auth.
- **eBird** — Cornell Lab. High quality checklists. Requires API key. Recent data only (30 days).
- **iNaturalist** — Community observations. Research-grade filter. Free, no auth.

**Why structured APIs are primary:** These APIs provide georeferenced, timestamped, independently verified records with taxonomy IDs. The data is structured and directly filterable by the ROI polygon.

**Secondary/weak evidence (web keyword scan):**
- **web_search provider** — Runs keyword queries against a legitimate search API (Serper/Brave/SerpAPI). Returns URLs and snippets mentioning the species + ROI place names.
- Why this is weak: Web content is noisy, unverified, hard to date, and subject to SEO manipulation. It is useful for discovering species that appear in field guides or birding blogs but have few formal occurrence records in the APIs (e.g., rare visitors, vagrant records).
- Weight conservatively in `configs/scanner/scoring.yaml`.
- **Never raw-scrape Google.** Use a legitimate API.

**Output:** A scored species list (`data/processed/species_scored.parquet`) with `accepted`, `review`, and `rejected` categories.

---

### 2. Dataset Builder (`scripts/dataset/`)

**Purpose:** Build an `ImageManifestRecord` dataset for training.

Steps:
1. `00_build_roi.py` — export ROI polygon as WKT
2. `01_seed_species.py` — build species seed list from IOC/Clements taxonomy
3. `02_pull_structured_occurrences.py` — pull occurrence records
4. `03_run_keyword_scan.py` — run web keyword scan (optional, requires API key)
5. `04_score_species.py` — apply scoring weights
6. `05_export_review_tables.py` — export human-readable review CSVs

Image collection (NOT YET IMPLEMENTED): After species are accepted, pull labelled images from iNaturalist (CC-licensed) and any other open sources, write to `data/manifests/`.

---

### 3. Training Pipeline (`apps/training/`)

**Purpose:** Train detector + classifier on the image manifest dataset.

- **Detector:** Binary bird / not-bird detector. Outputs bounding boxes. Suggested: YOLO-family or RT-DETR for edge latency.
- **Classifier:** Multi-class species classifier over detector crops. Suggested: EfficientNet-B3 or ViT-Tiny from `timm`.
- **ONNX Export:** Both models exported to ONNX for deployment.
- **Calibration:** Temperature scaling on a held-out calibration split to get reliable confidence scores.

Configuration: `configs/training/classifier.yaml`, `detector.yaml`, `augmentation.yaml`

---

### 4. Edge Inference (`apps/inference/`)

**Purpose:** Run on the cyberdeck. Capture frames, detect birds, classify species.

Flow:
```
Camera.capture_frame()
  → pre-process (resize, normalize)
  → BirdDetector.detect() → list[BoundingBox]
  → for each box: BirdClassifier.classify() → top-k (species_id, confidence)
  → SpeciesDB.lookup(species_id) → SpeciesRecord
  → notify UI
```

All inference runs offline via ONNX Runtime. No network calls at inference time.

---

### 5. Cyberdeck UI (`apps/cyberdeck_ui/`)

**Purpose:** Display detected species information on the cyberdeck screen.

Minimal FastAPI server. Routes:
- `GET /health` — liveness check
- `GET /` — species display page (Jinja2 template)

TODO: Add WebSocket for real-time inference-to-UI push, photo thumbnails, and species facts (type, climate zone, habitat).

---

### 6. Shared Packages

| Package | Purpose |
|---------|---------|
| `bird_core` | IDs (NewType), enums, settings, paths, logging |
| `bird_geo` | ROI loading, shapely geometry, SEQ place names |
| `bird_data` | SpeciesRecord, ImageManifestRecord, taxonomy, storage |
| `bird_ml` | LabelMap, metrics, calibration, image transforms |
| `bird_device` | CameraProtocol, battery telemetry, device telemetry |

Packages are independent of apps and can be used across the scanner, training, and inference pipelines without circular dependencies.

---

## Data Flow

```
configs/roi/roi.example.geojson
    ↓ 00_build_roi.py
data/roi/roi.wkt

data/seeds/species_seed.parquet
    ↓ 02_pull_structured_occurrences.py
data/raw/occurrences_*.jsonl

data/raw/ + data/interim/
    ↓ 04_score_species.py
data/processed/species_scored.parquet

[image collection — not yet implemented]
data/manifests/train.jsonl + val.jsonl + test.jsonl

data/manifests/
    ↓ apps/training/
models/checkpoints/ → models/exports/detector.onnx
                    → models/exports/classifier.onnx
                    → models/exports/label_map.json

models/exports/
    ↓ apps/inference/ (on cyberdeck)
[live camera detections]
    ↓ apps/cyberdeck_ui/
[display on screen]
```

---

## Key Design Decisions

1. **uv over conda as default** — uv is significantly faster and produces reproducible lockfiles. conda is documented as a fallback for native dep problems (GDAL, ARM torch).
2. **ONNX for edge deployment** — avoids PyTorch runtime on the cyberdeck. onnxruntime is available for ARM.
3. **Structured occurrence APIs as primary evidence** — avoids legal/ToS issues with web scraping. ALA/GBIF/iNat are designed for this use case.
4. **Web keyword scan as weak supplementary evidence** — kept behind a disabled flag and requires a legitimate search API key.
5. **Protocol interfaces** — `OccurrenceProviderProtocol` and `KeywordProviderProtocol` allow providers to be swapped, mocked in tests, or disabled without changing the pipeline.
6. **src-layout** — prevents accidental imports of uninstalled package directories.
