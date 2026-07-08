# BIRDIDEX Project Log

Generated: 2026-07-08

## 1. Project intent

BIRDIDEX is an offline bird-identification cyberdeck for South East Queensland and nearby target regions. The device should capture or receive bird images, identify the species locally, show a field-guide-style species profile, and log the observation with useful metadata for later review.

Core product goal:

```text
capture/import image → rank best evidence → detect/crop bird → classify species → apply local context → show species card → save observation
```

The project is intentionally offline-first. Internet is only used during dataset construction, enrichment, updates, or optional desktop sync.

## 2. Current dataset state

Uploaded/generated data artefacts currently include:

| File | Purpose |
|---|---|
| `class_index.json` | Stable classifier class list. |
| `species_catalog.csv` | Species table derived from eBird-style records. |
| `region_species_presence.csv` | Region/species presence table. |
| `species_region_summary.json` | Region-to-species and species-to-region mappings. |
| `rarity_scaffold.json` | Prototype rarity/anomaly scaffold. |
| `dataset_manifest.json` | Ingest metadata and output inventory. |
| `ingest_report.md` | Human-readable ingest report. |

Current class-index summary:

- Species/classes: 199.
- Regions: 5.
- Source CSVs: 8.
- Observation rows loaded: 574.
- Class ID policy: stable sorted by taxonomic order then common name.
- Known ambiguous/non-strict species labels: `curlew_sp`, `fairy_tree_martin`, `fairywren_sp`, `kingfisher_sp`, `swallow_sp`, `teal_sp`, `tern_sp`.

Decision: ambiguous taxa should be excluded from automatic supervised image fetching by default. They may remain as optional fallback, review, or higher-level unknown classes later.

## 3. Repository direction

Earlier prompts over-expanded the repo into multiple apps/packages. The chosen direction is now simplification:

```text
PROJECT_Birdidex/
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
├── uv.lock
├── Makefile
└── README.md
```

Direction:

- One installable Python package: `birdidex`.
- One CLI: `uv run birdidex ...`.
- Keep `uv`.
- Keep root resource folders.
- Avoid creating new app/package boundaries unless real complexity demands it.
- Keep provider logic simple and API-backed, not a nested framework.

## 4. Dataset image-acquisition policy

The dataset should be built from labelled, open-license, species-specific images.

Primary target:

```text
candidate fetch target: 250 images/class
accepted training target: 150–200 images/class
stored longest edge: 1024 px default
format: JPEG or WebP
quality: 85 default
full-res originals: not retained unless explicitly requested
```

Do not resize images to model input size at ingestion. Fine-grained bird ID needs detail: beak geometry, plumage, eye and face markings, wing/tail pattern, talons, body shape, posture, and habitat context.

Approved source strategy:

1. iNaturalist
2. Atlas of Living Australia
3. GBIF
4. Wikimedia Commons
5. Openverse as fallback only

Rules:

- Use scientific names first.
- Use common names only as fallback.
- Do not scrape arbitrary Google/Bing image pages.
- Only accept records with explicit compatible open-license metadata.
- Store provenance and attribution per image.
- Quarantine uncertain images rather than silently accepting them.

Image folder structure:

```text
data/images/raw/{class_id:03d}.{label}/
data/images/review/{class_id:03d}.{label}/
data/images/quarantine/{class_id:03d}.{label}/
data/images/processed/{class_id:03d}.{label}/
data/images/splits/train/{class_id:03d}.{label}/
data/images/splits/val/{class_id:03d}.{label}/
data/images/splits/test/{class_id:03d}.{label}/
```

Metadata output:

```text
data/images/metadata/image_records.jsonl
```

Each image record should store local path, class ID, species names, provider, source URL, license, attribution, dimensions, format, hash, perceptual hash, location/time if available, validation status, rejection reason, and raw provider metadata.

## 5. Big Bird dataset decision

The dataset "Big Bird: A global dataset of birds in drone imagery annotated to species level" is downloading as a large 41 GB zip.

Decision:

- Treat Big Bird as auxiliary data.
- Do not mix it into the main ground-level classifier dataset by default.
- Use it for detector training, localisation, aerial/top-down robustness, and optional auxiliary evaluation.
- Import only overlapping species with species-level annotations.
- Mark all imported records with `view_type = "uav_top_down"` and `dataset_role = "auxiliary"`.

Reason:

The target device will mostly see birds from human/camera angles. Big Bird is top-down UAV imagery, so it is useful but domain-shifted. A classifier trained too heavily on top-down silhouettes may learn the wrong representation for field use.

Planned Big Bird commands:

```text
uv run birdidex bigbird audit --zip /path/to/bigbird.zip
uv run birdidex bigbird import --zip /path/to/bigbird.zip --mode auxiliary
```

Big Bird audit should report zip structure, annotation formats, species overlap with `class_index.json`, image resolution distribution, annotation counts, empty/non-empty image counts, and recommended import plan.

## 6. Species profiles

Species profiles will back the offline Pokédex UI.

Output paths:

```text
data/profiles/species_profiles.json
data/profiles/{class_id:03d}.{label}.json
```

Each profile should include:

- `class_id`
- `label`
- `common_name`
- `scientific_name`
- `aliases`
- `known_regions`
- `habitat`
- `behaviour`
- `diet`
- `breeding_notes`
- `seasonal_notes`
- `similar_species`
- `rarity_notes`
- `conservation_status`
- `representative_image_path`
- `representative_image_attribution`
- `data_sources`
- `generated_at`

Important decision: do not hallucinate species facts. Start from structured local data, then enrich later from ALA, GBIF, Wikidata/Wikipedia, field-guide sources, or manually curated notes. Unknown fields should remain null or TODO.

## 7. Device runtime architecture

Clean process flow:

```text
Bird target
  ↓
Image source
  ├── Pi 5 camera: live capture / near-instant ID
  └── A7RV import: high-resolution imported image / batch ID
  ↓
Capture queue
  ↓
Quality sorter
  ↓
Bird detector + cropper
  ↓
Best evidence selector
  ↓
Classifier
  ↓
Field context / ROI prior filter
  ↓
Confidence gate
  ↓
Species profile lookup
  ↓
UI stack
  ↓
Observation log
  ↓
Review / export / dataset feedback
```

Runtime state machine:

```text
IDLE
  → PREVIEW
  → CAPTURE_BURST or IMPORT_IMAGE
  → QUEUE_IMAGE
  → QUALITY_SORT
  → DETECT_BIRD
  → SELECT_BEST_EVIDENCE
  → CLASSIFY
  → APPLY_CONTEXT_PRIORS
  → CONFIDENCE_GATE
      ├── HIGH_CONFIDENCE → RESULT_UI
      ├── MEDIUM_CONFIDENCE → RESULT_WITH_ALTERNATIVES
      ├── LOW_CONFIDENCE → RETAKE_UI
      └── MULTI_SUBJECT → CROP_SELECTION_UI
  → PROFILE_LOOKUP
  → OBSERVATION_LOG
  → USER_CONFIRM / USER_REJECT / EXPORT
```

## 8. Capture and evidence packets

Recommended internal packets:

```text
CapturePacket
- capture_id
- source: pi_camera | a7rv_import | phone_import
- raw_image_path
- timestamp_utc
- camera_model
- lens_info
- gps_lat
- gps_lon
- gps_accuracy_m
- weather_snapshot
```

```text
EvidencePacket
- capture_id
- best_full_image_path
- best_crop_path
- backup_crop_paths
- quality_score
- sharpness_score
- exposure_score
- subject_size_score
- detector_boxes
- detector_confidence
```

```text
PredictionPacket
- capture_id
- top_k_predictions
- visual_confidence
- context_adjusted_confidence
- predicted_class_id
- predicted_label
- confidence_state: high | medium | low | multi_subject | out_of_set
```

```text
ObservationRecord
- observation_id
- capture_id
- predicted_class_id
- confirmed_class_id
- confidence
- image_path
- crop_path
- timestamp_utc
- local_time
- season
- latitude
- longitude
- region_guess
- weather_summary
- user_notes
```

## 9. Quality sorter logic

The quality sorter should choose the best frame/image before detector/classifier work.

Suggested factors:

```text
sharpness_score       edge/Laplacian detail
motion_blur_score     directional blur penalty
exposure_score        under/over-exposure penalty
subject_size_score    bird crop area relative to frame
noise_score           high ISO/noise penalty
pose_score            full-body/face/wing visibility proxy
duplicate_score       burst near-duplicate removal
```

Decision: choose the highest useful-detail image, not necessarily the largest file. Store the best full frame, best crop, and a few backups.

## 10. Classifier and confidence gate

Classifier output should include top-k predictions. Region/season priors may re-rank weak or medium predictions, but must not override strong visual evidence.

Confidence states:

```text
HIGH_CONFIDENCE       show species page immediately
MEDIUM_CONFIDENCE     show likely species + alternatives
LOW_CONFIDENCE        ask for better image/view/call
MULTI_SUBJECT         user selects crop or device handles per-crop ID
OUT_OF_SET            possible species outside current model
```

The device must be allowed to abstain. Forced guesses create bad logs and bad user trust.

## 11. UI stack

UI cards:

1. Result card: species name, confidence, best image, top alternative.
2. ID marks: beak, face/eye pattern, colour, wings/tail, posture.
3. Behaviour: feeding, movement, calls, social behaviour.
4. Region/habitat: known regions, local likelihood, seasonal notes.
5. Similar species: likely confusions and differences.
6. Observation: time, GPS, weather, save/reject/export.

Future voice hook:

```text
"{common_name}. {type_or_family}. Confidence {confidence_percent} percent.
Often found in {habitat_short}. Fun fact: {fun_fact_short}."
```

Use deterministic profile text. Do not require a live LLM for field voice readout.

## 12. Observation logging

Observation logging is future-ready but should not block v1.

Fields:

- observation ID
- UTC capture time
- local time/timezone
- season
- GPS location and accuracy
- region guess
- weather summary
- temperature, humidity, wind, pressure
- device ID
- camera ID
- image and thumbnail paths
- detector/classifier model IDs
- predicted class and confidence
- top-k predictions
- user-confirmed class
- user feedback and notes

Weather sources can be added in layers:

```text
v1: null/manual
v2: onboard sensor pack
v3: cached weather API sync when internet is available
```

## 13. Hardware concept

Core electronic components:

- Raspberry Pi 5 or similar central compute.
- Optional AI accelerator for detector/classifier inference.
- Pi camera or compatible camera module for direct capture.
- A7RV import pathway via SD/USB/Wi-Fi workflow.
- Small display.
- Buttons/D-pad for UI navigation.
- GPS module.
- Optional environmental sensors: temperature, humidity, pressure, light.
- Battery/power-management board.
- Storage sized for offline profiles, model weights, and observations.
- Optional speaker/amp for future voice readout.

## 14. Planned CLI commands

```text
uv run birdidex doctor
uv run birdidex images scaffold
uv run birdidex images fetch --all --per-class 250 --target-accepted 200
uv run birdidex images report
uv run birdidex images split --train 0.75 --val 0.15 --test 0.10 --seed 42
uv run birdidex bigbird audit --zip /path/to/bigbird.zip
uv run birdidex bigbird import --zip /path/to/bigbird.zip --mode auxiliary
uv run birdidex profiles build
uv run birdidex observations schema
uv run birdidex audit dataset
uv run pytest
make test
```

## 15. README requirements

Root README should explain:

- How to install with `uv`.
- How `class_index.json` works.
- Minimum `class_index.json` schema for custom datasets.
- How to scaffold folders.
- How to fetch API-backed images.
- How to control target count, image size, format, quality, and disk usage.
- How to audit the dataset.
- How to review/quarantine images.
- How to split train/val/test.
- How to import Big Bird as auxiliary data.
- Why top-down UAV imagery should not be mixed into normal classifier splits by default.
- How to build species profiles.
- How future observation logs will work.
- What not to commit.

Important `.gitignore` entries:

```text
data/images/
data/external/
data/cache/
data/db/
data/reports/
data/profiles/
models/
*.zip
*.onnx
*.pt
*.pth
*.ckpt
.env
```

## 16. Immediate next tasks

1. Simplify repo structure into one `src/birdidex` package.
2. Implement class scaffold and ambiguous-taxon filtering.
3. Implement API-backed image metadata fetch and optional media download.
4. Implement dataset audit reports.
5. Add Big Bird audit/import as auxiliary-only.
6. Generate species profiles with null/TODO unknown fields.
7. Define observation schemas.
8. Build first image → classify → profile → log flow.
9. Build minimal UI card stack.
10. Only then optimise on-device inference.
