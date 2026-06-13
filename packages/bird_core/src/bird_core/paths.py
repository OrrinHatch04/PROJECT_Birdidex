"""Project-root-relative path helpers."""

from pathlib import Path

# Resolved once at import time; works regardless of CWD if the package is installed.
_PACKAGE_ROOT = Path(__file__).resolve().parents[4]  # birdidex/


def project_root() -> Path:
    return _PACKAGE_ROOT


def configs_dir() -> Path:
    return _PACKAGE_ROOT / "configs"


def data_dir() -> Path:
    return _PACKAGE_ROOT / "data"


def models_dir() -> Path:
    return _PACKAGE_ROOT / "models"
