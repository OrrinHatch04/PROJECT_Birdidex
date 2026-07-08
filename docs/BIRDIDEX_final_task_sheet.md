# BIRDIDEX Final Task Sheet

Generated: 2026-07-08

## Project summary

BIRDIDEX is an offline field device that captures or imports bird images, identifies the species locally, displays a compact species profile, and logs observations with time/location/context metadata. The project is split into independent assessment-style work packages so each stream can be built, tested, and reviewed separately.

## Assessment 1 — Dataset and taxonomy foundation

**Objective:** Build the stable species/class catalogue and region priors.

**Main work:**

- Maintain `class_index.json` as the source of truth.
- Keep stable `class_id` values and deterministic folder names.
- Track common name, scientific name, aliases, known regions, and observation counts.
- Mark ambiguous taxa as non-clean classifier classes.
- Maintain region/species presence and rarity scaffold files.

**Deliverables:**

- `class_index.json`
- `species_catalog.csv`
- `region_species_presence.csv`
- `species_region_summary.json`
- `rarity_scaffold.json`
- `dataset_manifest.json`
- `ingest_report.md`

**Acceptance criteria:**

- Classes are deterministic and repeatable.
- Ambiguous taxa are flagged.
- Region/species mappings are generated.
- No training folder is inferred without a class-index entry.

## Assessment 2 — Image dataset acquisition and audit

**Objective:** Build a labelled, open-license, species-specific image dataset.

**Main work:**

- Scaffold ImageFolder-style class folders.
- Fetch candidate image metadata and images using public APIs.
- Target 150–200 accepted images per clean species class.
- Store images at balanced resolution and quality: default longest edge 1024 px, JPEG/WebP quality 85.
- Record license, attribution, provider, source URL, hashes, and validation status.
- Quarantine uncertain or bad images.
- Generate dataset audit reports.

**Approved sources:**

1. iNaturalist
2. Atlas of Living Australia
3. GBIF
4. Wikimedia Commons
5. Openverse as fallback only

**Deliverables:**

- `data/images/raw/{class_id:03d}.{label}/`
- `data/images/review/{class_id:03d}.{label}/`
- `data/images/quarantine/{class_id:03d}.{label}/`
- `data/images/metadata/image_records.jsonl`
- `data/reports/dataset_audit.html`
- `data/reports/species_coverage.csv`

**Acceptance criteria:**

- No Google/Bing result scraping.
- All accepted images have explicit compatible licenses.
- Duplicate images are detected by SHA256/perceptual hash where possible.
- Weak classes are reported.
- Ambiguous taxa are excluded from automatic fetching.

## Assessment 3 — Big Bird auxiliary dataset

**Objective:** Audit and optionally import the Big Bird UAV dataset without polluting the main classifier dataset.

**Main work:**

- Inspect the 41 GB zip without full extraction where possible.
- Determine species overlap with BIRDIDEX classes.
- Report image counts, annotation counts, annotation formats, and resolution distribution.
- Import overlapping species as auxiliary top-down data only.
- Preserve annotations and mark domain metadata.

**Deliverables:**

- `data/reports/bigbird_audit.json`
- `data/reports/bigbird_overlap.csv`
- `data/images/auxiliary/bigbird/{class_id:03d}.{label}/`
- `data/images/metadata/bigbird_records.jsonl`

**Acceptance criteria:**

- Big Bird data is marked `dataset_role = auxiliary`.
- Big Bird data is marked `view_type = uav_top_down`.
- It is not included in normal train/val/test splits unless explicitly requested.
- Species-level annotation is required for import.

## Assessment 4 — Machine learning: detector and classifier

**Objective:** Train and evaluate the visual recognition pipeline.

**Main work:**

- Train or fine-tune a bird detector/cropper.
- Train species classifier using accepted ground-level images.
- Use region/season priors only as post-classification context, not as a replacement for visual evidence.
- Implement confidence states: high, medium, low, multi-subject, out-of-set.
- Export models for offline inference.

**Deliverables:**

- Detector model.
- Classifier model.
- Training config.
- Evaluation report.
- Confusion matrix.
- Top-k accuracy report.
- Exported on-device model format.

**Acceptance criteria:**

- Train/val/test split has no duplicate leakage.
- Evaluation reports top-1, top-5, weighted F1, per-class performance, and confusion clusters.
- Model can abstain or return low-confidence state.
- Similar species errors are reviewed explicitly.

## Assessment 5 — Species profile and information system

**Objective:** Build offline species pages for the UI.

**Main work:**

- Generate one profile per clean species class.
- Populate known fields from structured data.
- Leave unknown facts as null/TODO instead of hallucinating.
- Add representative image and attribution when available.
- Prepare profile nodes for UI cards.

**Deliverables:**

- `data/profiles/species_profiles.json`
- `data/profiles/{class_id:03d}.{label}.json`
- Profile completeness report.

**Acceptance criteria:**

- Each classifier class has a profile stub.
- Each profile has source metadata.
- UI can load profile by `class_id`.
- Unknown facts are explicitly marked, not fabricated.

## Assessment 6 — Device build and electronics

**Objective:** Build the portable offline hardware platform.

**Main work:**

- Select central compute: Raspberry Pi 5 or equivalent.
- Add optional AI accelerator for inference.
- Integrate Pi camera and imported-image pathway.
- Add display and physical navigation buttons.
- Add GPS module.
- Add optional environmental sensors.
- Add battery and power-management system.
- Add local storage sized for models, profiles, captures, and logs.
- Add optional speaker/amp for future voice readout.

**Deliverables:**

- Hardware block diagram.
- Bill of materials.
- Wiring/power diagram.
- Bench test report.
- Field power estimate.
- Thermal and enclosure notes.

**Acceptance criteria:**

- Device boots offline.
- Camera or import path works.
- Display and buttons work.
- Power system supports field operation.
- Storage can hold model, profiles, and observation logs.

## Assessment 7 — Runtime software integration

**Objective:** Implement the end-to-end device logic.

**Main work:**

- Build capture queue.
- Implement quality sorter.
- Run detector/cropper.
- Select best evidence image and crop.
- Run classifier.
- Apply field context/ROI priors.
- Load species profile.
- Push result into UI card stack.
- Save observation record.

**Runtime flow:**

```text
Bird target → camera/import → capture queue → quality sorter → detector/cropper → best evidence selector → classifier → context prior → confidence gate → species profile → UI stack → observation log
```

**Deliverables:**

- Capture packet schema.
- Evidence packet schema.
- Prediction packet schema.
- Observation record schema.
- Runtime state machine.
- Integration test/demo.

**Acceptance criteria:**

- Pi camera path supports near-instant capture-to-result flow.
- A7RV/import path supports high-resolution images.
- Low-confidence images do not force a fake ID.
- The system stores enough metadata to debug each result.

## Assessment 8 — UI, controls, and future voice output

**Objective:** Make the device usable in the field.

**Main work:**

- Build simple card-based UI.
- Add button navigation.
- Show result, image, ID marks, behaviour, habitat/region, similar species, and observation log.
- Add confirmation/rejection workflow.
- Add future voice readout hook.

**UI cards:**

1. Result
2. Best image/crop
3. ID marks
4. Behaviour
5. Region/habitat
6. Similar species
7. Observation log

**Deliverables:**

- UI prototype.
- Button map.
- Species-card renderer.
- Confirmation/rejection workflow.
- Voice text template.

**Acceptance criteria:**

- User can identify, scroll, save, reject, and retake using buttons.
- UI remains usable offline.
- Voice feature is optional and does not block v1.

## Assessment 9 — Observation logging, export, and field review

**Objective:** Turn each scan into useful field data.

**Main work:**

- Store observation records locally.
- Include image path, crop path, top-k predictions, confidence, user confirmation, GPS/time/season/weather/device metadata.
- Support uncertain-image review.
- Export logs for desktop review or future training.

**Deliverables:**

- SQLite or JSONL observation database.
- Observation schema.
- Export command.
- Review folder/workflow.

**Acceptance criteria:**

- Missing GPS/weather never blocks classification.
- User corrections are stored.
- Observations can be exported.
- Captures can be reused as future training/review candidates.

## Assessment 10 — Testing, deployment, and documentation

**Objective:** Make the project reproducible and maintainable.

**Main work:**

- Keep one simple package and CLI.
- Add tests for class parsing, folder scaffolding, metadata writing, duplicate detection, profile generation, Big Bird audit fixtures, and observation schemas.
- Update README with dataset setup instructions for users with their own classes.
- Add `.gitignore` rules for large/generated files.
- Validate offline setup commands.

**Deliverables:**

- Root README dataset section.
- `docs/` setup notes.
- Tests.
- Makefile commands.
- Device setup notes.

**Acceptance commands:**

```text
uv sync --all-groups
uv run birdidex doctor
uv run birdidex images scaffold
uv run birdidex images report
uv run birdidex profiles build
uv run birdidex observations schema
uv run birdidex bigbird audit --zip tests/fixtures/tiny_bigbird.zip
uv run pytest
make test
```

## Suggested build order

1. Simplify repo into one `src/birdidex` package.
2. Lock class index and folder scaffold.
3. Implement image metadata/download/audit pipeline.
4. Implement species profile generation.
5. Implement observation schemas.
6. Build first classifier baseline.
7. Build device capture/import queue.
8. Add quality sorter and detector/cropper.
9. Integrate classifier with profile lookup and UI stack.
10. Add Big Bird auxiliary import.
11. Optimise model and device runtime.
12. Add GPS/weather/voice features.

## Definition of first complete prototype

The first complete prototype does not need every future feature. It is complete when:

```text
Pi/import image → best image selected → bird crop generated → species predicted → confidence shown → profile card displayed → observation saved
```

Minimum success criteria:

- Works offline.
- Uses stable class IDs.
- Does not force low-confidence IDs.
- Shows useful species information.
- Saves a reviewable observation.
- Keeps generated datasets and models out of git.
