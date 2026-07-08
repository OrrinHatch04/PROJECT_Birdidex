.PHONY: help setup sync sync-all sync-dev sync-scanner sync-training sync-inference sync-ui sync-pi \
        lint format typecheck mypy test doctor verify-stack run-scanner-help run-ui-dev \
        clean clean-caches audit-tree scan-candidates images-scaffold images-report \
        images-fetch-manifest images-split train-help infer-help ui-help

UV := uv
PYTHON := python3.11
PYFALL := python3

help:
	@echo "BIRDIDEX targets:"
	@echo "  setup                Pin Python 3.11 and sync dev dependencies"
	@echo "  sync-all             uv sync --all-groups"
	@echo "  test                 Run pytest"
	@echo "  doctor               uv run birdidex doctor"
	@echo "  verify-stack         Run local smoke checks"
	@echo "  scan-candidates      Write offline candidate CSV from class_index.json"
	@echo "  images-scaffold      Create data/images ImageFolder scaffold"
	@echo "  images-fetch-manifest  Write metadata-first provider manifest"
	@echo "  images-split         Create train/val/test symlinks from accepted local records"
	@echo "  images-report        Regenerate image reports"
	@echo "  run-ui-dev           Start local UI dev server"
	@echo "  clean                Remove local tool caches"

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

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run pyright

mypy:
	$(UV) run mypy src tests

test:
	$(UV) run pytest

doctor:
	$(UV) run birdidex doctor

verify-stack:
	$(UV) run python scripts/setup/verify_stack.py || $(PYTHON) scripts/setup/verify_stack.py || $(PYFALL) scripts/setup/verify_stack.py

run-scanner-help:
	$(UV) run birdidex scan-candidates --help

run-ui-dev:
	$(UV) run birdidex ui serve

scan-candidates:
	$(UV) run birdidex scan-candidates

images-scaffold:
	$(UV) run birdidex images scaffold

images-fetch-manifest:
	$(UV) run birdidex images fetch-manifest

images-split:
	$(UV) run birdidex images split --train 0.75 --val 0.15 --test 0.10 --seed 42

images-report:
	$(UV) run birdidex images report

train-help:
	$(UV) run birdidex train --help

infer-help:
	$(UV) run birdidex infer --help

ui-help:
	$(UV) run birdidex ui --help

clean: clean-caches

clean-caches:
	find . \( -path ./.git -o -path ./.venv \) -prune -o -name '__pycache__' -type d -print -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .pyright .mypy_cache htmlcov .coverage coverage.xml
	@echo "caches cleaned"

audit-tree:
	@echo "== Top-level =="
	@ls -1 -d */ 2>/dev/null
	@echo ""
	@echo "== Single package =="
	@find src/birdidex -maxdepth 2 -type f | sort
	@echo ""
	@bad=0; \
	if [ -e apps ]; then echo "  [FAIL] apps/ still exists"; bad=1; fi; \
	if [ -e packages ]; then echo "  [FAIL] packages/ still exists"; bad=1; fi; \
	if [ $$bad -eq 0 ]; then echo "  [OK] single-package layout"; fi; \
	exit $$bad
