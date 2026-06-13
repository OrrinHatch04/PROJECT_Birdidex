.PHONY: setup sync-dev sync-scanner sync-training sync-inference sync-ui \
        lint typecheck test verify-stack audit help

PYTHON := python3.11
UV     := uv

help:
	@echo "Bird Pokedex — available targets:"
	@echo "  setup          Create .venv and sync dev dependencies (requires uv)"
	@echo "  sync-dev       Sync dev dependency group"
	@echo "  sync-scanner   Sync scanner dependency group"
	@echo "  sync-training  Sync training dependency group"
	@echo "  sync-inference Sync inference dependency group"
	@echo "  sync-ui        Sync UI dependency group"
	@echo "  lint           Run ruff linter"
	@echo "  typecheck      Run pyright type checker"
	@echo "  test           Run pytest"
	@echo "  verify-stack   Run scripts/setup/verify_stack.py"
	@echo "  audit          Print docs/AUDIT_STACK_SCAFFOLD.md"

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

lint:
	$(UV) run ruff check . || ruff check .

typecheck:
	$(UV) run pyright || pyright

test:
	$(UV) run pytest tests/ || pytest tests/

verify-stack:
	$(PYTHON) scripts/setup/verify_stack.py || python3 scripts/setup/verify_stack.py

audit:
	@cat docs/AUDIT_STACK_SCAFFOLD.md
