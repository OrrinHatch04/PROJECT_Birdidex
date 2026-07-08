.PHONY: help setup sync sync-all sync-dev sync-scanner sync-training sync-inference sync-ui sync-pi \
        lint format typecheck mypy test doctor verify-stack \
        run-scanner-help run-ui-dev clean clean-caches audit-tree audit \
        scan-candidates build-manifest build-splits demo-inference \
        export-observations dry-run-pipeline

# uv is the environment manager for this workspace.
UV     := uv
PYTHON := python3.11
PYFALL := python3

help:
	@echo "Bird Pokedex (BIRDIDEX) — available targets:"
	@echo "  setup            Pin Python 3.11 and sync the dev dependency group"
	@echo "  sync             uv sync"
	@echo "  sync-all         uv sync --all-groups"
	@echo "  sync-dev         Sync dev dependency group"
	@echo "  sync-scanner     Sync dev + scanner dependency groups"
	@echo "  sync-training    Sync dev + vision + training dependency groups"
	@echo "  sync-inference   Sync dev + inference dependency groups"
	@echo "  sync-ui          Sync dev + ui dependency groups"
	@echo "  sync-pi          Sync inference + ui dependency groups for Pi deployment"
	@echo "  lint             Run ruff check"
	@echo "  format           Run ruff format"
	@echo "  typecheck        Run pyright"
	@echo "  mypy             Run optional mypy checks"
	@echo "  test             Run pytest"
	@echo "  doctor           Print environment/package/backend diagnostics"
	@echo "  verify-stack     Run scripts/setup/verify_stack.py (offline smoke test)"
	@echo "  run-scanner-help Show the bird_roi_scan CLI help (no provider requests)"
	@echo "  run-ui-dev       Start the cyberdeck UI dev server (uvicorn, local only)"
	@echo "  --- offline dry-run pipeline (no provider requests, no media retrieval) ---"
	@echo "  scan-candidates   Score ROI species candidates -> manifests + report"
	@echo "  build-manifest    Build licensed image manifest from the iNat fixture"
	@echo "  build-splits      Generate train/val/test splits + validation report"
	@echo "  demo-inference    Mock inference -> SQLite observation log (for the UI)"
	@echo "  export-observations  Export the observation log to CSV + JSON"
	@echo "  dry-run-pipeline  Run scan -> manifest -> splits -> demo-inference end to end"
	@echo "  clean            Remove __pycache__ and tool caches"
	@echo "  audit-tree       Print the top-level layout and check for stray nested projects"
	@echo "  audit            Print docs/RESTRUCTURE_AUDIT.md"

# ── Environment ───────────────────────────────────────────────────────────────
setup:
	$(UV) python pin 3.11
	$(UV) sync --group dev

sync:
	$(UV) sync

sync-all:
	$(UV) sync --all-groups

sync-dev:
	$(UV) sync --group dev

sync-scanner:
	$(UV) sync --group dev --group scanner

sync-training:
	$(UV) sync --group dev --group vision --group training

sync-inference:
	$(UV) sync --group dev --group inference

sync-ui:
	$(UV) sync --group dev --group ui

sync-pi:
	$(UV) sync --group inference --group ui

# ── Quality ───────────────────────────────────────────────────────────────────
lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run pyright

mypy:
	$(UV) run mypy packages apps tests

test:
	$(UV) run pytest

doctor:
	BIRDIDEX_DOCTOR_REQUIRE_PROJECT_VENV=1 $(UV) run python scripts/env/doctor.py

verify-stack:
	$(UV) run python scripts/setup/verify_stack.py || $(PYTHON) scripts/setup/verify_stack.py || $(PYFALL) scripts/setup/verify_stack.py

# ── App entrypoints (health/help only — never retrieve data/media, make provider requests, or train) ──
run-scanner-help:
	$(UV) run python -m bird_roi_scan.cli --help \
	  || PYTHONPATH=apps/bird_roi_scan/src:packages/bird_core/src:packages/bird_geo/src:packages/bird_data/src $(PYFALL) -m bird_roi_scan.cli --help

run-ui-dev:
	$(UV) run uvicorn bird_ui.server:app --reload --host 127.0.0.1 --port 8000

# ── Offline dry-run pipeline (no provider requests, no media retrieval) ─────────
scan-candidates:
	$(UV) run python scripts/dataset/04_score_species.py

build-manifest:
	$(UV) run python scripts/dataset/06_build_image_manifest.py

build-splits:
	$(UV) run python scripts/dataset/07_build_splits.py

demo-inference:
	$(UV) run python scripts/inference/run_demo_inference.py

export-observations:
	$(UV) run python -c "from pathlib import Path; from bird_data.observation_log import ObservationLog; \
	l=ObservationLog(Path('data/db/observations.sqlite3')); \
	l.export_csv(Path('data/reports/observations_export.csv')); \
	l.export_json(Path('data/reports/observations_export.json')); l.close(); \
	print('exported to data/reports/observations_export.{csv,json}')"

dry-run-pipeline: scan-candidates build-manifest build-splits demo-inference
	@echo "Dry-run pipeline complete — see data/manifests, data/splits, data/reports, data/db."

# ── Housekeeping ──────────────────────────────────────────────────────────────
clean: clean-caches

clean-caches:
	find . -path ./.git -prune -o -name '__pycache__' -type d -print -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .pyright .mypy_cache htmlcov .coverage coverage.xml
	@echo "caches cleaned"

audit-tree:
	@echo "== Top-level workspace =="
	@ls -1 -d */ 2>/dev/null
	@echo ""
	@echo "== apps/ =="
	@ls -1 apps
	@echo "== packages/ =="
	@ls -1 packages
	@echo ""
	@echo "== Stray-nested-project check =="
	@bad=0; \
	if [ -e bird-roi-scan ]; then echo "  [FAIL] stray bird-roi-scan/ present at root"; bad=1; fi; \
	for d in apps/*/configs apps/*/data apps/*/tests apps/*/notebooks apps/*/models; do \
	  if [ -e "$$d" ]; then echo "  [FAIL] app owns a shared dir: $$d"; bad=1; fi; \
	done; \
	if [ $$bad -eq 0 ]; then echo "  [OK] no duplicate nested workspace folders"; fi; \
	exit $$bad

audit:
	@cat docs/RESTRUCTURE_AUDIT.md
