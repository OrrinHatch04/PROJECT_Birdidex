# 3 — Offline application / UI

**Homes:** `apps/inference/`, `apps/cyberdeck_ui/`, `configs/inference/`, `scripts/inference/`.
**Owns:** on-device pipeline, Pokédex UI, observation log. **Consumes:** models (cat 1), species
data (cat 2), sensors (cat 6). **Launched by:** cat 4.
Definition: [WORK_CATEGORIES.md §3](../../WORK_CATEGORIES.md#3-offline-application--ui).

## Inference pipeline (bird_inference)
- [~] `pipeline.py` — capture → detect → crop → classify → rerank → lookup → log.
- [~] `detector.py` / `classifier.py` — ONNX Runtime wrappers (mock until cat-1 weights).
- [~] `cropper.py` — pad-safe crop of detector boxes.
- [~] `reranker.py` — visual + ROI occurrence + month + habitat priors (from cat 2).
- [~] `species_db.py` — species-card lookup by id.
- [~] `schema.py` / `logging_sink.py` — observation record → SQLite.
- [ ] Replace deterministic mock with real ONNX inference once `models/exports/*` exist.
- [ ] Load `label_map.json`; assert preprocessing matches cat-1 export signature.
- [ ] Unknown/uncertainty logic: low-confidence, small top1–top2 margin, rare-but-possible warning.
- [ ] Ingest-folder watcher for Sony A7R V JPEGs (with cat 6).

## Runtime config
- [~] `configs/inference/runtime.yaml` — thresholds, model paths, ROI mode.
- [ ] Strict-local vs wide/vagrant ROI toggle.

## UI (bird_ui)
- [~] `server.py` — FastAPI `GET /health`, `GET /` (Jinja2), reads local DB via `data_access.py`.
- [ ] Screens: home / incoming photo / prediction / species card / confirm / logbook / export / settings.
- [ ] Top-5 display with confidence + warnings (per legacy §9.2).
- [ ] Confirm / wrong / unsure actions → write `user_verdict`.
- [ ] WebSocket push from inference → UI; thumbnails.
- [ ] Pokédex-style chrome (scanline, entry cards) — deferred styling pass.
- [ ] Physical-button events (from cat 5/6) mapped to UI actions.

## Observation log / export (contract with cat 7)
- [~] `data/db/observations.sqlite3` written by demo inference.
- [~] `make export-observations` → CSV + JSON in `data/reports/`.
- [ ] SQLite WAL mode + graceful-shutdown safety (field robustness).
- [ ] Log GPS/weather/time/image/crop/prediction/model-version per observation (with cat 6).

## Acceptance
- [ ] New JPEG auto-processed → crop → offline top-5 → species card → logged, no terminal.
