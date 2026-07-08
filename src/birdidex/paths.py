"""Repo-root-relative path helpers for the single BIRDIDEX package."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    """Return the repository root."""
    return _REPO_ROOT


def configs_dir() -> Path:
    return _REPO_ROOT / "configs"


def data_dir() -> Path:
    return _REPO_ROOT / "data"


def models_dir() -> Path:
    return _REPO_ROOT / "models"


def notebooks_dir() -> Path:
    return _REPO_ROOT / "notebooks"


def scripts_dir() -> Path:
    return _REPO_ROOT / "scripts"


def docs_dir() -> Path:
    return _REPO_ROOT / "docs"


def images_dir() -> Path:
    return data_dir() / "images"


def manifests_dir() -> Path:
    return data_dir() / "manifests"


def reports_dir() -> Path:
    return data_dir() / "reports"


def db_dir() -> Path:
    return data_dir() / "db"


def default_class_index_path() -> Path:
    """Return the canonical classifier class index path."""
    return data_dir() / "processed" / "birddex" / "class_index.json"


# Back-compatible names for scripts and docs that still prefer explicit getters.
get_repo_root = repo_root
get_configs_dir = configs_dir
get_data_dir = data_dir
get_models_dir = models_dir
get_images_dir = images_dir
get_manifests_dir = manifests_dir
get_reports_dir = reports_dir
get_db_dir = db_dir
