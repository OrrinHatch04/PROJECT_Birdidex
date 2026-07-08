# Work Categories

The repo is intentionally small. Work should stay inside the existing single package until real
requirements justify new structure.

| Area | Current home | Current status |
| --- | --- | --- |
| Class taxonomy | `src/birdidex/taxonomy.py` | Parses `class_index.json`; owns folder names |
| ROI helpers | `src/birdidex/roi.py`, `configs/roi/` | GeoJSON loading helpers only |
| Provider metadata | `src/birdidex/providers.py` | Normalizes metadata; no media download |
| Image dataset scaffold | `src/birdidex/images.py` | Creates folders, JSONL, reports |
| Splits | `src/birdidex/splits.py` | Deterministic symlink/copy splits from accepted local files |
| Training | `src/birdidex/train.py`, `configs/training/`, `models/` | Skeleton only |
| Inference | `src/birdidex/infer.py`, `configs/inference/` | Skeleton only |
| UI | `src/birdidex/ui/` | Minimal local scaffold |
| Local observation DB | `src/birdidex/db.py`, `data/db/` | SQLite utility |
| Tooling and docs | `Makefile`, `scripts/`, `tests/`, `docs/` | Local checks and focused tests |

## Current Priority

1. Keep the package import surface stable: `birdidex.*`.
2. Preserve `class_index.json` as the only class source of truth.
3. Keep provider work metadata-first and explicit.
4. Keep generated images, manifests, databases, logs, caches, and model artifacts out of git.
5. Add real ingestion/training/inference only when explicitly requested.
