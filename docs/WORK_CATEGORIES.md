# BirdDex — Work Categories

This document splits the BirdDex project into **eight work categories** and maps each one onto
the existing uv-workspace monorepo. It is the top-level index for planning and division of labour.
It complements — does not replace — [ARCHITECTURE.md](ARCHITECTURE.md) (system design) and the
legacy end-to-end plan in [task_sheet/SEQ_BirdDex_Task_Sheet.md](task_sheet/SEQ_BirdDex_Task_Sheet.md).

Each category has a **separate checklist** under [task_sheet/categories/](task_sheet/categories/).

## Prototype scope

The first build targets a **prototype ROI** of three SEQ corridors, not the full
Bundaberg→Goondiwindi region. This keeps species count tractable so the whole pipeline can be
proven end-to-end before scaling.

| Corridor | Config sub-region | Character |
|----------|-------------------|-----------|
| Lamington NP / Springbrook | `Lamington_Springbrook` | Rainforest plateau; the September field zone |
| Bribie Island → Nudgee → Beerburrum | `Bribie_Nudgee_Beerburrum` | Bay coast, wetlands, Glass House hinterland |
| Noosa → Rainbow Beach → K'gari | `Noosa_RainbowBeach_Kgari` | Cooloola coast, heath, Great Sandy dunes |

- Machine-readable geometry: [`configs/roi/prototype_roi.geojson`](../configs/roi/prototype_roi.geojson)
  (one MultiPolygon = all three corridors; coarse placeholder, **review in QGIS**).
- Config / anchor places / buffer: [`configs/roi/prototype_roi.yaml`](../configs/roi/prototype_roi.yaml).
- The full-region ROI stays in `configs/roi/roi.yaml` for later expansion.

## Modularity rules (inherited from ARCHITECTURE.md)

- Apps depend on shared packages; **shared packages never import app packages**.
- Apps never own their own `configs/`, `data/`, `models/`, `tests/`, or `notebooks/` — those live
  once at the repo root and are shared.
- All code resolves shared locations through `bird_core.paths`, never hardcoded paths.
- **No duplication:** shared configs, schemas, data contracts, geometry, and utilities have exactly
  one home (see category 8). A wire/data format used by two categories is defined once and
  referenced, not copied.

---

## Category map

| # | Category | Primary homes | Owning packages/apps |
|---|----------|---------------|----------------------|
| 1 | ML bird recognition pipeline | `apps/training/`, `packages/bird_ml/`, `configs/training/`, `models/`, `notebooks/{training,model_eval}/` | `bird_training`, `bird_ml` |
| 2 | Dataset acquisition, filtering & ROI validation | `apps/bird_roi_scan/`, `scripts/dataset/`, `packages/bird_geo/`, `packages/bird_data/`, `configs/{roi,scanner}/`, `data/`, `notebooks/{scanner,dataset_review}/` | `bird_roi_scan`, `bird_geo`, `bird_data` |
| 3 | Offline application / UI | `apps/cyberdeck_ui/`, `apps/inference/`, `configs/inference/`, `scripts/inference/` | `bird_ui`, `bird_inference` |
| 4 | Custom OS / system image | `os/` | — (system) |
| 5 | Electronics & microcontroller firmware | `firmware/` | — (firmware) |
| 6 | Camera / sensor integration | `packages/bird_device/`, `apps/inference/camera.py`, `configs/device/`, bridges `firmware/`↔`os/` | `bird_device` |
| 7 | Deployment, testing & field validation | `scripts/{setup,deployment}/`, `tests/`, `data/reports/`, `os/provisioning/` | — (cross-cutting) |
| 8 | Shared configs, schemas, data contracts & docs | `packages/bird_core/`, `packages/bird_data/` (records), `configs/`, `docs/` | `bird_core`, `bird_data` |

Categories 1–3 and 8 are **largely built** (software MVP, 138 offline tests). Categories 4–7 are
**hardware/field** work that is mostly scaffolding today. The status column in each checklist marks
what exists vs. what is a stub.

---

## 1. ML bird recognition pipeline

**Purpose.** Turn the labelled image manifest into deployable offline models: a bird detector, a
species classifier, calibrated confidence, and a geotemporal re-ranker.

**Boundary.** Owns training, evaluation, calibration, and ONNX export. Does **not** acquire data
(category 2) and does **not** run on the device (category 3 consumes its exported artifacts).

**Files / folders.**
- `apps/training/src/bird_training/` — `dataset.py`, `train_classifier.py`, `train_detector.py`,
  `evaluate.py`, `export_onnx.py`.
- `packages/bird_ml/` — `labels.py` (LabelMap), `metrics.py`, `calibration.py`, `transforms.py`.
- `configs/training/` — `classifier.yaml`, `detector.yaml`, `augmentation.yaml`.
- `models/{checkpoints,exports,quantized}/`.

**Inputs → Outputs.**
- In: `data/splits/{train,val,test}.csv`, `data/manifests/images_manifest.csv`, media (category 2).
- Out: `models/exports/{detector.onnx,classifier.onnx,label_map.json}`, eval reports in `data/reports/`.

**Dependencies.** `training`/`vision`/`inference` uv groups (torch, timm, onnx). Runnable skeletons
today — no weights trained yet.

**Interfaces.** `label_map.json` + ONNX I/O signature is the contract with category 3. LabelMap and
metrics come from `bird_ml`; re-ranker priors come from category 2 outputs.

→ [Checklist: 01_ml_recognition_pipeline.md](task_sheet/categories/01_ml_recognition_pipeline.md)

---

## 2. Dataset acquisition, filtering & ROI validation

**Purpose.** Decide which species are present in the ROI (occurrence evidence), build a licensed
image manifest, and produce clean train/val/test splits — all ROI-scoped and reproducible.

**Boundary.** Owns ROI geometry, provider queries, scoring, licensing, dedup, and splits. Stops at
the manifest/splits handed to category 1. Media **retrieval** is explicit/opt-in and not yet
implemented as network calls.

**Files / folders.**
- `apps/bird_roi_scan/src/bird_roi_scan/` — `cli.py`, `pipeline.py`, `scoring.py`, `seeds.py`,
  `occurrences.py`, `providers/{ala,gbif,ebird,inaturalist,web_search,base}.py`.
- `scripts/dataset/00..07_*.py` — ROI → seed → occurrences → keyword scan → score → review tables →
  image manifest → splits.
- `packages/bird_geo/` — `roi.py`, `geometry.py`, `places.py`.
- `packages/bird_data/` — `species.py`, `manifests.py`, `manifest_build.py`, `licensing.py`,
  `splits.py`, `taxonomy.py`, `reports.py`.
- `configs/roi/` (incl. **prototype_roi**), `configs/scanner/{providers,scoring,species_filters}.yaml`.
- `data/{seeds,raw,interim,processed,manifests,splits,reports,roi,media}/`.

**Inputs → Outputs.**
- In: ROI config, taxonomy seed, provider APIs (opt-in), open-licence media metadata.
- Out: `roi_species_candidates.csv`, `species_priority_tiers.csv`, `images_manifest.csv`,
  `splits/*.csv`, licence/class-balance/duplicate/split reports.

**Dependencies.** `scanner`/`vision` groups (polars, geopandas, shapely, duckdb, rapidfuzz).
Providers behind `OccurrenceProviderProtocol` / `KeywordProviderProtocol` — mockable, disabled by default.

**Interfaces.** Feeds category 1 (manifest/splits) and category 3 (ROI priors for re-ranking, species
cards). Record schemas are owned by category 8 (`bird_data`).

→ [Checklist: 02_dataset_acquisition_roi.md](task_sheet/categories/02_dataset_acquisition_roi.md)

---

## 3. Offline application / UI

**Purpose.** Run the recognition pipeline on the device and present it: capture/ingest → detect →
crop → classify → re-rank → species card → confirm → log. Fully offline.

**Boundary.** Owns the runtime pipeline, the Pokédex UI, and the observation log. Consumes models
(cat 1) and species data (cat 2); is launched by the OS image (cat 4); reads sensors via cat 6.

**Files / folders.**
- `apps/inference/src/bird_inference/` — `app.py`, `pipeline.py`, `camera.py`, `detector.py`,
  `cropper.py`, `classifier.py`, `reranker.py`, `species_db.py`, `logging_sink.py`, `schema.py`.
- `apps/cyberdeck_ui/src/bird_ui/` — `server.py`, `data_access.py`, `templates/`.
- `configs/inference/runtime.yaml`; `scripts/inference/run_demo_inference.py`.
- `data/db/observations.sqlite3` (git-ignored).

**Inputs → Outputs.**
- In: frames/JPEGs (cat 6), `models/exports/*`, species DB, thresholds, ROI mode.
- Out: SQLite observation log, exported CSV/JSON, on-screen species cards + top-5.

**Dependencies.** `inference`/`ui` groups (onnxruntime, fastapi, uvicorn, jinja2). Demo inference is a
deterministic mock until real weights exist.

**Interfaces.** Consumes cat-1 ONNX + `label_map.json`; observation schema (`schema.py` /
`bird_data.observation_log`) is the contract with export + field validation (cat 7). UI restyle into
Pokédex chrome is future work.

→ [Checklist: 03_offline_app_ui.md](task_sheet/categories/03_offline_app_ui.md)

---

## 4. Custom OS / system image

**Purpose.** Turn a blank Pi into an appliance that boots into the UI with no terminal: image build,
provisioning, systemd services, Wi-Fi AP, FTP ingest, storage layout.

**Boundary.** Assembles and wires up the app (cat 3) and firmware (cat 5) — does not reimplement
them. See [`os/README.md`](../os/README.md).

**Files / folders.** `os/{image,systemd,provisioning,network,kiosk,overlays}/`. On-device layout
under `/opt/birddex/`.

**Inputs → Outputs.**
- In: app packages, `models/exports/`, `configs/{device,inference}/`.
- Out: flashable image, running `birddex-*` services, first-boot provisioning.

**Dependencies.** pi-gen / rpi-image-gen / packer; hostapd, dnsmasq, vsftpd; systemd. New — scaffold only.

**Interfaces.** systemd units + `/opt/birddex` paths (cat 3); udev rules for MCU/GPS ports (cat 5/6);
image verified by cat 7.

→ [Checklist: 04_os_system_image.md](task_sheet/categories/04_os_system_image.md)

---

## 5. Electronics & microcontroller firmware

**Purpose.** Firmware that runs off-Pi: sensor MCU aggregation (GPS + BME280/680), physical
buttons/rotary/shutdown, status LEDs, and power management.

**Boundary.** Owns only MCU-side code, the wire protocol it speaks, and the hardware it assumes. The
Pi-side consumer is `bird_device` (cat 6). See [`firmware/README.md`](../firmware/README.md).

**Files / folders.** `firmware/{sensor_mcu,input_mcu,power,protocol,hardware,tools}/`. The **shared
wire protocol** lives once in `firmware/protocol/` and is read by both sides.

**Inputs → Outputs.**
- In: pin map / baud / sensor addresses (`configs/device/`), hardware BOM.
- Out: flashed MCU firmware; framed serial/I²C telemetry to the Pi.

**Dependencies.** MCU toolchain (RP2040/ESP32). New — scaffold only.

**Interfaces.** Protocol frames (cat 6 `bird_device`); udev rules (cat 4).

→ [Checklist: 05_firmware.md](task_sheet/categories/05_firmware.md)

---

## 6. Camera / sensor integration

**Purpose.** Bridge physical capture and sensors into the app: camera abstraction (Pi camera + Sony
A7R V FTP JPEGs), GPS/weather/battery telemetry, and the per-observation sensor snapshot.

**Boundary.** Pi-side integration layer. Consumes firmware (cat 5) frames and feeds the inference
pipeline (cat 3). Owns the `CameraProtocol` and telemetry abstractions, not the MCU firmware.

**Files / folders.**
- `packages/bird_device/src/bird_device/` — `camera_base.py` (CameraProtocol), `battery.py`,
  `telemetry.py`.
- `apps/inference/src/bird_inference/camera.py` — concrete capture/ingest.
- `configs/device/cyberdeck.yaml` — camera + sensor + ingest config.

**Inputs → Outputs.**
- In: MCU frames (cat 5), camera frames, FTP ingest folder, EXIF metadata.
- Out: normalized frames + a sensor snapshot (lat/lon/alt/temp/humidity/pressure/light) per observation.

**Dependencies.** `vision` group; serial/GPIO libs on device. `camera_base` + telemetry exist as
Protocols; concrete drivers are stubs.

**Interfaces.** `CameraProtocol` (cat 3 pipeline); protocol frames (cat 5); observation snapshot
fields (cat 3 log schema, owned by cat 8).

→ [Checklist: 06_camera_sensor_integration.md](task_sheet/categories/06_camera_sensor_integration.md)

---

## 7. Deployment, testing & field validation

**Purpose.** Prove it works — from `verify_stack.py` on a laptop through on-device deploy scripts to
scored field trials in the three prototype corridors.

**Boundary.** Owns environment verification, deploy/backup scripts, the test suite, and field-trial
reports. Uses (does not own) the OS image (cat 4) and every other category's outputs.

**Files / folders.**
- `scripts/setup/verify_stack.py`; `scripts/deployment/` (deploy/backup/restore — stub today).
- `tests/` — 138 offline unit tests + fixtures; `tests/integration/`.
- `data/reports/` — eval + field-trial reports; `os/provisioning/` smoke tests.

**Inputs → Outputs.**
- In: built image, models, app, device hardware, prototype ROI.
- Out: pass/fail stack report, CI test results, `field_trial_*.md`, battery/thermal/readability reports.

**Dependencies.** `dev` group (ruff, pyright, pytest, pre-commit). Field validation needs the assembled device.

**Interfaces.** Consumes every category; the acceptance criteria (legacy task sheet §12) gate the
September MVP. Field-trip logs feed back into cat 2 (own-camera test set) and cat 1 (retraining).

→ [Checklist: 07_deployment_testing_field.md](task_sheet/categories/07_deployment_testing_field.md)

---

## 8. Shared configs, schemas, data contracts & documentation

**Purpose.** The single home for cross-cutting shared resources so nothing is duplicated: IDs, enums,
settings, path resolution, record schemas, config files, and docs.

**Boundary.** Owns definitions used by ≥2 other categories. Anything imported by more than one app/
category belongs here, not copied into each. **Shared packages never import app packages.**

**Files / folders.**
- `packages/bird_core/` — `ids.py` (NewType IDs), `config.py` (settings), `paths.py`
  (`get_repo_root`, `get_configs_dir`, `get_data_dir`, `get_models_dir`, `get_reports_dir`,
  `get_app_dir`), `schemas.py`, `logging.py`.
- `packages/bird_data/` — record models (`SpeciesRecord`, `ImageManifestRecord`, observation log),
  taxonomy, storage/csvio — the **data contracts** shared by cats 1/2/3.
- `configs/` — all YAML config (roi, scanner, training, inference, device).
- `docs/` — this file, `ARCHITECTURE.md`, `ENVIRONMENT.md`, `AGENT_README.md`, task sheets.

**Inputs → Outputs.** Definitions in → every category consumes. No runtime pipeline of its own.

**Dependencies.** Minimal (pydantic, pyyaml). Established and tested.

**Interfaces.** Every category imports `bird_core` for IDs/paths/settings and `bird_data` for record
schemas. The **firmware wire protocol** (cat 5, `firmware/protocol/`) and the **observation log
schema** (cat 3/8) are the two data contracts spanning the hardware/software boundary — keep each
defined once.

→ [Checklist: 08_shared_contracts_docs.md](task_sheet/categories/08_shared_contracts_docs.md)

---

## Cross-category interface summary

```
[6 camera/sensor] --frames/telemetry--> [3 app/UI]
[5 firmware] --serial protocol--> [6 camera/sensor]        (protocol defined once in firmware/protocol/)
[2 dataset] --manifest/splits--> [1 ML]  --ONNX + label_map--> [3 app/UI]
[2 dataset] --ROI priors / species cards--> [3 app/UI]
[4 OS image] --systemd + /opt/birddex--> launches [3], stages [1] models, wires [5]/[6] devices
[7 deploy/field] --verifies--> everything;  field logs --feed back--> [2] and [1]
[8 shared] --IDs/paths/settings/schemas--> imported by 1,2,3,6;  data contracts for 3/5
```

All eight checklists live in [task_sheet/categories/](task_sheet/categories/).
