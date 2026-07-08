# 8 — Shared configs, schemas, data contracts & docs

**Homes:** `packages/bird_core/`, `packages/bird_data/`, `configs/`, `docs/`.
**Owns:** anything used by ≥2 categories — IDs, settings, paths, record schemas, config, docs.
**Rule:** shared packages never import app packages; nothing is duplicated.
Definition: [WORK_CATEGORIES.md §8](../../WORK_CATEGORIES.md#8-shared-configs-schemas-data-contracts--documentation).

## Core primitives (`bird_core`)
- [x] `ids.py` — NewType IDs; `config.py` — settings; `logging.py`.
- [x] `paths.py` — `get_repo_root/_configs_dir/_data_dir/_models_dir/_reports_dir/_app_dir`.
- [~] `schemas.py` — shared schema definitions.
- [ ] Audit: no app hardcodes a path or redefines an ID/enum that lives here.

## Data contracts (`bird_data` — shared by cats 1/2/3)
- [x] `species.py` (SpeciesRecord), `manifests.py` (ImageManifestRecord), `observation_log.py`.
- [x] `taxonomy.py`, `licensing.py`, `splits.py`, `storage.py`, `csvio.py`, `reports.py`.
- [ ] Freeze + version the manifest, splits, and observation-log schemas (cross-category contract).
- [ ] (Optional) export JSON Schema for non-Python consumers (UI, firmware tooling).

## Two cross-boundary data contracts (define once, reference everywhere)
- [ ] **Observation log schema** — shared by cat 3 (writer) and cat 7 (export/validate). Single home: `bird_data.observation_log`.
- [ ] **Firmware wire protocol** — shared by cat 5 (MCU) and cat 6 (`bird_device`). Single home: `firmware/protocol/`.

## Configs (`configs/`)
- [x] `roi/` (incl. `prototype_roi.{geojson,yaml}`), `scanner/`, `training/`, `inference/`, `device/`.
- [ ] Every YAML has a documented schema + example; no config duplicated across apps.

## Documentation (`docs/`)
- [x] `ARCHITECTURE.md`, `ENVIRONMENT.md`, `AGENT_README.md`, `RESTRUCTURE_AUDIT.md`.
- [x] `WORK_CATEGORIES.md` + `task_sheet/categories/` (this set).
- [ ] Keep the category map current when files move; link from root `README.md`.
- [ ] Reconcile legacy `SEQ_BirdDex_Task_Sheet.md` phases with the category checklists (avoid drift).

## Acceptance
- [ ] Grep shows shared IDs/paths/schemas imported, not re-declared, across all categories.
