from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_checker():
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_notebook_static.py"
    spec = importlib.util.spec_from_file_location("check_notebook_static", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_notebook(path: Path, sources: list[str]) -> Path:
    payload = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": source} for source in sources
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_static_notebook_checker_accepts_required_headings(tmp_path: Path) -> None:
    checker = _load_checker()
    notebook = _write_notebook(tmp_path / "good.ipynb", list(checker.REQUIRED_HEADINGS))

    assert checker.validate_notebook(notebook) == []


def test_static_notebook_checker_flags_secret_and_local_path(tmp_path: Path) -> None:
    checker = _load_checker()
    notebook = _write_notebook(
        tmp_path / "bad.ipynb",
        [
            *checker.REQUIRED_HEADINGS,
            "EBIRD_API_KEY = 'abcdefghi12345'",
            "Example bad path: /home/example/private/data",
        ],
    )

    issues = checker.validate_notebook(notebook)

    assert any("API key" in issue for issue in issues)
    assert any("absolute local path" in issue for issue in issues)
