.PHONY: help setup sync-dev sync-scanner sync-training sync-inference sync-ui \
        lint format typecheck test verify-stack \
        run-scanner-help run-ui-dev clean-caches audit-tree audit

# uv is the default manager. PYTHON/PYTEST are fallbacks for when uv is absent.
UV     := uv
PYTHON := python3.11
PYFALL := python3

help:
	@echo "Bird Pokedex (BIRDIDEX) — available targets:"
	@echo "  setup            Pin Python 3.11 and sync the dev dependency group (uv)"
	@echo "  sync-dev         Sync dev dependency group"
	@echo "  sync-scanner     Sync dev + scanner dependency groups"
	@echo "  sync-training    Sync dev + training dependency groups"
	@echo "  sync-inference   Sync dev + inference dependency groups"
	@echo "  sync-ui          Sync dev + ui dependency groups"
	@echo "  lint             Run ruff check"
	@echo "  format           Run ruff format"
	@echo "  typecheck        Run pyright"
	@echo "  test             Run pytest"
	@echo "  verify-stack     Run scripts/setup/verify_stack.py (offline smoke test)"
	@echo "  run-scanner-help Show the bird_roi_scan CLI help (no network calls)"
	@echo "  run-ui-dev       Start the cyberdeck UI dev server (uvicorn, local only)"
	@echo "  clean-caches     Remove __pycache__ and tool caches"
	@echo "  audit-tree       Print the top-level layout and check for stray nested projects"
	@echo "  audit            Print docs/RESTRUCTURE_AUDIT.md"

# ── Environment ───────────────────────────────────────────────────────────────
setup:
	$(UV) python pin 3.11 || echo "uv not found — install via: curl -LsSf https://astral.sh/uv/install.sh | sh"
	$(UV) sync --group dev

sync-dev:
	$(UV) sync --group dev

sync-scanner:
	$(UV) sync --group dev --group scanner

sync-training:
	$(UV) sync --group dev --group training

sync-inference:
	$(UV) sync --group dev --group inference

sync-ui:
	$(UV) sync --group dev --group ui

# ── Quality ───────────────────────────────────────────────────────────────────
lint:
	$(UV) run ruff check . || ruff check .

format:
	$(UV) run ruff format . || ruff format .

typecheck:
	$(UV) run pyright || pyright

test:
	$(UV) run pytest || pytest

verify-stack:
	$(UV) run python scripts/setup/verify_stack.py || $(PYTHON) scripts/setup/verify_stack.py || $(PYFALL) scripts/setup/verify_stack.py

# ── App entrypoints (health/help only — never download data, call APIs, or train) ──
run-scanner-help:
	$(UV) run python -m bird_roi_scan.cli --help \
	  || PYTHONPATH=apps/bird_roi_scan/src:packages/bird_core/src:packages/bird_geo/src:packages/bird_data/src $(PYFALL) -m bird_roi_scan.cli --help

run-ui-dev:
	$(UV) run uvicorn bird_ui.server:app --reload --host 127.0.0.1 --port 8000

# ── Housekeeping ──────────────────────────────────────────────────────────────
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
