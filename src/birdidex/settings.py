"""Environment-backed settings for local BIRDIDEX commands."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BirdidexSettings(BaseSettings):
    """Local runtime settings.

    Provider access remains opt-in. Empty provider values mean commands should stay
    in dry-run or metadata-from-input mode.
    """

    model_config = SettingsConfigDict(env_prefix="BIRDIDEX_", env_file=".env", extra="ignore")

    ebird_api_key: str = ""
    search_api_key: str = ""
    class_index_path: str = "data/processed/birddex/class_index.json"
    roi_config: str = "configs/roi/roi.yaml"
    providers_config: str = "configs/scanner/providers.yaml"
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> BirdidexSettings:
    return BirdidexSettings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
