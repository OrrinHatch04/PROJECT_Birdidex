"""Shared application settings loaded from environment / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class BirdidexSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIRDIDEX_", env_file=".env", extra="ignore")

    ebird_api_key: str = ""
    search_api_key: str = ""
    roi_config: str = "configs/roi/roi.yaml"
    providers_config: str = "configs/scanner/providers.yaml"
    log_level: str = "INFO"


# Lazily instantiated singleton — avoids reading .env at import time in tests.
_settings: BirdidexSettings | None = None


def get_settings() -> BirdidexSettings:
    global _settings
    if _settings is None:
        _settings = BirdidexSettings()
    return _settings
