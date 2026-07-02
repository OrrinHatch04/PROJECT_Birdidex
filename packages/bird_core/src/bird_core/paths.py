"""Repo-root-relative path helpers.

All apps and packages must resolve shared resources through these helpers rather than
hardcoding paths or computing them relative to an app directory. Paths are resolved
relative to the repository root, never to a user-specific absolute location.

Skeleton only: these helpers return paths; they do not create directories or validate
contents. Add `mkdir`/validation behaviour later if needed.
"""

from __future__ import annotations

from pathlib import Path

# This file lives at packages/bird_core/src/bird_core/paths.py, so the repo root is
# five parents up. Resolved once at import time and independent of the current CWD.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def get_repo_root() -> Path:
    """Return the absolute path to the repository root (the BIRDIDEX/ workspace)."""
    return _REPO_ROOT


def get_configs_dir() -> Path:
    """Return the shared ``configs/`` directory at the repo root."""
    return _REPO_ROOT / "configs"


def get_data_dir() -> Path:
    """Return the shared ``data/`` directory at the repo root."""
    return _REPO_ROOT / "data"


def get_models_dir() -> Path:
    """Return the shared ``models/`` directory at the repo root."""
    return _REPO_ROOT / "models"


def get_reports_dir() -> Path:
    """Return the shared reports directory (``data/reports/``)."""
    return _REPO_ROOT / "data" / "reports"


def get_app_dir(app_name: str) -> Path:
    """Return the directory for an app under ``apps/`` (e.g. ``bird_roi_scan``).

    The app name is not validated here — callers pass the directory name as it appears
    under ``apps/``.
    """
    return _REPO_ROOT / "apps" / app_name


# ── Back-compat short aliases (kept so existing imports keep working) ─────────────────
def project_root() -> Path:
    return get_repo_root()


def configs_dir() -> Path:
    return get_configs_dir()


def data_dir() -> Path:
    return get_data_dir()


def models_dir() -> Path:
    return get_models_dir()
