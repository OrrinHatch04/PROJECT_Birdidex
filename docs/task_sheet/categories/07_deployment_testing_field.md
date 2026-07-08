# 7 — Deployment, testing & field validation

**Homes:** `scripts/{setup,deployment}/`, `tests/`, `data/reports/`, `os/provisioning/`.
**Owns:** env verification, deploy/backup scripts, test suite, field-trial reports.
**Uses:** every other category's outputs.
Definition: [WORK_CATEGORIES.md §7](../../WORK_CATEGORIES.md#7-deployment-testing--field-validation).

## Environment & CI
- [x] `scripts/setup/verify_stack.py` — Python + package smoke test (`make verify-stack`).
- [x] `tests/` — 138 offline unit tests pass (`make test`).
- [ ] CI workflow: ruff + pyright + pytest on push.
- [~] `tests/integration/` — end-to-end offline pipeline (dry-run) — expand.
- [ ] Integration test that exercises real ONNX inference once cat-1 weights exist.

## On-device deployment (`scripts/deployment/` — stub today)
- [ ] `deploy_device.sh` — push app + `models/exports/*` + configs to `/opt/birddex` (with cat 4).
- [ ] `backup.sh` / `restore.sh` — sightings DB + model metadata to USB/NVMe.
- [ ] Version stamp: model version + dataset manifest hash recorded per deploy.
- [ ] Smoke test after flashing image (cat 4 handoff).

## Field validation (prototype ROI)
- [ ] Lamington/Springbrook trial → `data/reports/field_trial_lamington.md`.
- [ ] Bribie→Nudgee→Beerburrum trial → `field_trial_bribie.md`.
- [ ] Noosa→Rainbow Beach→K'gari trial → `field_trial_noosa.md`.
- [ ] Battery runtime test (≥4h target) → `battery_runtime.md`.
- [ ] Thermal test → `thermal_test.md`.
- [ ] Screen readability (bright sun) test.
- [ ] FTP transfer reliability + sudden power-loss test (DB integrity).
- [ ] Graceful shutdown test.

## Acceptance gate (September MVP, legacy §12)
- [ ] Boots to UI, own Wi-Fi AP, A7R V JPEG in, auto-crop, offline top-5, species card,
      confirm/wrong/unsure, GPS/weather/time logged, exportable, ≥4h battery.

## Feedback loop
- [ ] Field JPEGs → cat-2 `own_camera_test` set.
- [ ] Confirmed/corrected IDs → cat-1 retraining data.
