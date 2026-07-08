# Restructure Audit — 2026-06-13

Reorganised BIRDIDEX from a half-migrated state (a clean root workspace **plus** a leftover
nested `bird-roi-scan/` project **plus** a mis-named `apps/scanner/`) into a single clean
monorepo/uv-workspace. This document records exactly what changed.

Backup location: `audit_backups/restructure_20260613_145441/`

---

## 1. Original duplicate / problem folders found

| Problem | Detail |
|---------|--------|
| Nested second project | `bird-roi-scan/` at the repo root duplicated root resources: its own `configs/`, `data/`, `notebooks/`, `scripts/`, `src/`, `tests/`, `pyproject.toml`, `.gitignore`, `.env.example`. |
| Mis-named scanner app | The ROI scanner already lived at `apps/scanner/` with package `bird_scanner`, but the target layout requires `apps/bird_roi_scan/` with package `bird_roi_scan`. |
| Broken old source | Every `__init__.py` under `bird-roi-scan/src/` had a **leading space** in its filename (` __init__.py`) — not importable as a package. Mostly empty stubs plus a typo'd `search_occurences`. |
| Embedded git repo | `bird-roi-scan/data/raw/inaturalist/` was a tracked **git submodule gitlink** (a clone of the public `inaturalist/inaturalist-open-data` repo) sitting inside `data/raw/`. |

The root already had the correct shared folders (`configs/ data/ models/ notebooks/ scripts/ tests/ packages/ docs/`) and shared packages, so the work was to **finish** the migration and remove the duplicates — not to build the layout from scratch.

---

## 2. Files moved (into the root layout)

| From | To | Method |
|------|----|--------|
| `apps/scanner/` | `apps/bird_roi_scan/` | `git mv` (history preserved) |
| `apps/scanner/src/bird_scanner/` | `apps/bird_roi_scan/src/bird_roi_scan/` | `git mv` |
| `bird-roi-scan/notebooks/01_roi_visual_check.ipynb` | `notebooks/scanner/01_roi_visual_check.ipynb` | `git mv` |
| `bird-roi-scan/notebooks/02_occurrence_sanity_check.ipynb` | `notebooks/scanner/02_occurrence_sanity_check.ipynb` | `git mv` |
| `bird-roi-scan/notebooks/03_species_score_review.ipynb` | `notebooks/scanner/03_species_score_review.ipynb` | `git mv` |
| `bird-roi-scan/data/roi/region_of_interest.png` | `data/roi/region_of_interest.png` | `git mv` (337 KB ROI render — a real asset, kept tracked) |

---

## 3. Files preserved in place / relocated but not deleted

| Item | Disposition |
|------|-------------|
| `bird-roi-scan/data/raw/inaturalist/` (216 KB, incl. nested `.git`) | Un-tracked from the index (`git rm --cached`) and **moved** to `data/raw/inaturalist/`. `data/raw/*` is gitignored, so it lives on disk but is no longer committed. It is a re-cloneable public repo (`https://github.com/inaturalist/inaturalist-open-data.git`). |
| Root `configs/`, `data/`, `scripts/dataset/`, `tests/fixtures/` | Kept — these are the canonical versions and are strictly better than the old nested copies (see §6). |
| `SEQ_BirdDex_Model_Training_Skeleton.ipynb` | Already at repo root; the target wants it under `notebooks/training/`. **Left in place** this pass to avoid touching the notebook — flagged in §10 (unresolved). |
| `docs/AWC135 User Guide.pdf`, `docs/task_sheet/` | Device manual + task sheet, left untouched. |

---

## 4. Files backed up

Everything removed from `bird-roi-scan/` was copied to `audit_backups/restructure_20260613_145441/` first:

- `bird-roi-scan-src/` — the entire old `src/` tree (broken ` __init__.py` files and all), 29 files.
- `configs/` — old `providers.yaml`, `roi.yaml`, `scoring.yaml`.
- `scripts/` — old `00`–`05` dataset scripts (17–49 bytes each, i.e. empty placeholders).
- `tests/` — old `test_*.py` (all 0 bytes) + the old fixtures.
- `meta/` — old `README.md`, `pyproject.toml`, `.env.example`, `.gitignore`, `.directory`.

**Why backed up rather than merged:** the old `src/` is a broken, mostly-empty early skeleton.
Its useful *ideas* already exist, better expressed, in the new structure:

| Old idea | Where it lives now |
|----------|--------------------|
| `models/species.py` (`Species`) | `packages/bird_data/.../species.py` (`SpeciesRecord`, typed + IDs) |
| `providers/base.py` (`Provider` ABC, typo'd) | `apps/bird_roi_scan/.../providers/base.py` (`OccurrenceProviderProtocol`, `KeywordProviderProtocol`) |
| `providers/web_search.py` (query templates) | `apps/bird_roi_scan/.../providers/web_search.py` (templates preserved) |
| `models/occurrence.py`, `models/evidence.py` | represented by `EvidenceSource` enum + manifest models (full models TODO) |

---

## 5. Imports changed

Renaming the package `bird_scanner → bird_roi_scan` and the app dir `apps/scanner → apps/bird_roi_scan` required edits in:

- `apps/bird_roi_scan/src/bird_roi_scan/pipeline.py` — `from bird_scanner.providers.base` → `from bird_roi_scan.providers.base`
- `tests/conftest.py` — sys.path entry `apps/scanner/src` → `apps/bird_roi_scan/src`
- `tests/unit/test_imports.py` — all `bird_scanner.*` → `bird_roi_scan.*`; **added** `bird_training.*`, `bird_inference.*`, and `bird_ui` import checks
- `tests/unit/test_provider_protocol.py` — all `bird_scanner.providers.*` → `bird_roi_scan.providers.*`
- `scripts/dataset/02_pull_structured_occurrences.py` and `03_run_keyword_scan.py` — sys.path `apps/scanner/src` → `apps/bird_roi_scan/src`
- `scripts/setup/verify_stack.py` — imports now cover `bird_roi_scan`, `bird_training`, `bird_inference`, `bird_ui`
- `pyproject.toml` — `[tool.uv.workspace] members` `apps/scanner` → `apps/bird_roi_scan`; pyright `exclude` no longer references the deleted `bird-roi-scan/`

**Import policy** (enforced by structure, documented in `ARCHITECTURE.md`): shared packages never import apps; `bird_roi_scan` → `bird_core`/`bird_geo`/`bird_data`; `bird_training` → `bird_core`/`bird_data`/`bird_ml`; `bird_inference` → `+ bird_device`; `bird_ui` minimal.

---

## 6. Configs changed

No root config content was changed — the root configs are canonical. The old nested configs were
**superseded** (backed up only) because the root versions are strictly better:

| Old (`bird-roi-scan/configs/`) | Root (`configs/`) |
|--------------------------------|-------------------|
| `scoring.yaml` was **empty** (just `weights:`/`penalties:`/`thresholds:` headers) | `configs/scanner/scoring.yaml` has real placeholder weights |
| `roi.yaml` had typos (`Goondiwini`, `SEQ_..._Goondiwini_ROI`) and pointed at a non-existent `data/roi/roi.geojson` | `configs/roi/roi.yaml` is correct and points at `configs/roi/roi.example.geojson` |
| `providers.yaml` had a mis-set `web_search.engine` (an iNat URL) | `configs/scanner/providers.yaml` is consistent and documented |

`verify_stack.py` now parses all 9 root YAML configs; all parse and are non-empty.

---

## 7. Path helpers changed

`packages/bird_core/src/bird_core/paths.py` gained the required repo-root-relative helpers
(skeleton only, `pathlib.Path`, no hardcoded user paths):

`get_repo_root()`, `get_configs_dir()`, `get_data_dir()`, `get_models_dir()`,
`get_reports_dir()` (→ `data/reports`), `get_app_dir(app_name)` (→ `apps/<app_name>`).

The previous short names (`project_root`, `configs_dir`, `data_dir`, `models_dir`) are kept as
thin aliases for back-compat.

---

## 8. Makefile targets changed

Added: `format`, `run-scanner-help`, `run-ui-dev`, `clean-caches`, `audit-tree`.
Repointed: `audit` now prints this file. Existing targets retained: `setup`, `sync-dev`,
`sync-scanner`, `sync-training`, `sync-inference`, `sync-ui`, `lint`, `typecheck`, `test`,
`verify-stack`, `help`.

`audit-tree` prints the top-level layout and **fails** if a stray `bird-roi-scan/` reappears or
if any app grows its own `configs/`, `data/`, `tests/`, `notebooks/`, or `models/` dir.
No target retrieves data/media, makes provider requests, or trains.

---

## 9. Tests / checks run and results

Environment note: this machine has **only Python 3.14.5** and `pytest`; `uv`, `python3.11`,
`ruff`, and `pyright` are **not installed**. Checks were run with what is available.

| Check | Command | Result |
|-------|---------|--------|
| Unit tests | `python3 -m pytest -q` | **81 passed, 1 skipped** (skip = WKT export, needs shapely) |
| Stack smoke test | `python3 scripts/setup/verify_stack.py` | All checks PASS **except** `Python 3.11.x` (running 3.14) and a shapely WARN. All 17 internal package imports, 9 config parses, path-helper and app/shared-dir checks pass. Exits 1 only due to the version gate. |
| Tree audit | `make audit-tree` | `[OK] no duplicate nested workspace folders`, exit 0 |
| Ruff | `ruff check .` | **Not run** — ruff not installed |
| Pyright | `pyright` | **Not run** — pyright not installed |
| `uv sync --group dev[ --group scanner]` | — | **Not run** — uv not installed |

---

## 10. Unresolved issues / follow-ups

1. **Toolchain not installed locally:** no `uv`, `python3.11`, `ruff`, or `pyright`. Install uv
   (`curl -LsSf https://astral.sh/uv/install.sh | sh`), then `uv python install 3.11` and
   `make sync-dev` to run lint/typecheck/3.11 tests. Code already targets 3.11 (`requires-python`
   `>=3.11,<3.12`, ruff `py311`, pyright `3.11`).
2. **`SEQ_BirdDex_Model_Training_Skeleton.ipynb`** is still at the repo root; the target layout
   places it under `notebooks/training/`. Left untouched this pass to avoid editing the notebook —
   move it (and re-check any relative paths inside) as a small follow-up.
3. **iNaturalist clone** now lives under the gitignored `data/raw/inaturalist/` and retains its own
   nested `.git`. It is re-cloneable; consider deleting it locally if disk/clarity matters.
4. **No console entry points** declared for the app CLIs yet (`bird-roi-scan`, etc.); `run-scanner-help`
   falls back to `python -m bird_roi_scan.cli --help`.
5. **`docs/AUDIT_STACK_SCAFFOLD.md`** is the earlier scaffold report; this file supersedes its
   structural sections.

---

## 11. Does the final tree match the intended monorepo layout?

**Yes.** Top level is exactly `apps/ packages/ configs/ data/ models/ notebooks/ scripts/ tests/
docs/` (plus `audit_backups/`). `apps/` contains `bird_roi_scan/ training/ inference/ cyberdeck_ui/
tools/`; `packages/` contains `bird_core/ bird_geo/ bird_data/ bird_ml/ bird_device/`. There is **no**
active nested `bird-roi-scan/` project and **no** app owns a shared (`configs/data/tests/...`) folder.
This is a skeleton: modules import and entrypoints are health-check/`NotImplementedError` stubs —
the scanner, training, inference, and UI are **not** functional yet.
