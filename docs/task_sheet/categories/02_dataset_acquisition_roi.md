# 2 — Dataset acquisition, filtering & ROI validation

**Homes:** `apps/bird_roi_scan/`, `scripts/dataset/`, `packages/{bird_geo,bird_data}/`,
`configs/{roi,scanner}/`, `data/`.
**Owns:** ROI geometry, occurrence evidence, scoring, licensing, dedup, splits.
**Produces:** manifest + splits (cat 1), ROI priors + species cards (cat 3).
Definition: [WORK_CATEGORIES.md §2](../../WORK_CATEGORIES.md#2-dataset-acquisition-filtering--roi-validation).

## Prototype ROI validation (do first)
- [x] `configs/roi/prototype_roi.geojson` — three corridors as one MultiPolygon.
- [x] `configs/roi/prototype_roi.yaml` — sub-regions, anchor places, buffer.
- [ ] **Refine each corridor in QGIS** — placeholders are coarse rectangles.
- [ ] Add prototype anchor places to `bird_geo/places.py` (currently full-region only).
- [ ] `scripts/dataset/00_build_roi.py --config configs/roi/prototype_roi.yaml` → `data/roi/prototype_roi.wkt`.
- [ ] Confirm each corridor loads via `bird_geo.load_roi_shape` (MultiPolygon, valid).
- [ ] 10 km buffer variant for boundary/vagrant records.

## Species candidates (occurrence evidence)
- [~] `scripts/dataset/01_seed_species.py` — IOC/Clements seed.
- [~] `02_pull_structured_occurrences.py` — ALA/GBIF/eBird/iNat (opt-in, `--live`).
- [~] `03_run_keyword_scan.py` — web keyword scan (opt-in, weak evidence).
- [~] `04_score_species.py` — `configs/scanner/scoring.yaml` weights.
- [~] `05_export_review_tables.py` → `roi_species_candidates.csv` + `species_priority_tiers.csv`.
- [ ] Human review of Tier-1 species for the three corridors (target 100–200).
- [ ] Verify providers stay behind Protocols and are disabled by default.

## Image manifest (licensed media)
- [~] `06_build_image_manifest.py` — iNat fixture → `images_manifest.csv` (retrieval refuses).
- [ ] Implement opt-in `--retrieve-media` open-licence download (currently documents intent only).
- [ ] `bird_data/licensing.py` — persist source/licence/attribution/taxon per image.
- [~] Reports: `license_report.md`, `class_balance_report.md`, `duplicate_audit.md`.
- [ ] Near-duplicate removal across splits; split by observation/user/date (not naive random).

## Splits
- [~] `07_build_splits.py` → `data/splits/{train,val,test}.csv` + `split_report.md`.
- [ ] Keep hard images in val/test; track class imbalance for cat 1.

## Interfaces / handoff
- [ ] Manifest + splits schema stable (owned by `bird_data`, cat 8).
- [ ] Export ROI occurrence + month priors for cat 3 re-ranker.
- [ ] Provide species-card fields (habitat/climate/similar species) for cat 3 DB.
