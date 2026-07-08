"""Secret and master-seed handling for BIRDIDEX.

Secrets (API keys, tokens, the project seed) are read only from environment variables
or from gitignored local files (``.env.local`` then ``.env``). They are never written to
tracked config, logs, reports, or test output. Any value that is surfaced to a human is
passed through :func:`redact` first, which keeps a 4-character prefix and drops the rest.

Recognised names:

* ``EBIRD_API_KEY`` — eBird API token (sent as the ``X-eBirdApiToken`` header).
* ``INATURALIST_ACCESS_TOKEN`` — optional iNaturalist OAuth token.
* ``BIRDIDEX_MASTER_SEED`` — deterministic project seed (source of truth is the
  gitignored ``data/seeds/master_seed.txt``).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from birdidex.paths import repo_root

EBIRD_API_KEY_ENV = "EBIRD_API_KEY"
INATURALIST_ACCESS_TOKEN_ENV = "INATURALIST_ACCESS_TOKEN"
MASTER_SEED_ENV = "BIRDIDEX_MASTER_SEED"

# Local, gitignored files that may hold secrets, most specific first.
LOCAL_ENV_FILES: tuple[str, ...] = (".env.local", ".env")
MASTER_SEED_FILE = "data/seeds/master_seed.txt"

REDACTED_SUFFIX = "...REDACTED"


class MissingSecretError(RuntimeError):
    """Raised when a required secret is not configured."""


def redact(value: str | None) -> str:
    """Return a log-safe rendering of a secret: first 4 chars + ``...REDACTED``.

    ``None`` / empty values render as ``(unset)`` so diagnostics never imply a secret is
    present when it is not, and never leak the full value when it is.
    """
    if not value:
        return "(unset)"
    return f"{value[:4]}{REDACTED_SUFFIX}"


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.lower().startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


@lru_cache(maxsize=1)
def _local_env(root_str: str) -> dict[str, str]:
    root = Path(root_str)
    merged: dict[str, str] = {}
    # Iterate least-specific first so more-specific files win.
    for name in reversed(LOCAL_ENV_FILES):
        merged.update(_parse_env_file(root / name))
    return merged


def load_local_env(root: Path | None = None) -> dict[str, str]:
    """Return the merged contents of the gitignored local env files (``.env.local`` wins)."""
    return dict(_local_env(str(root or repo_root())))


def reset_secret_cache() -> None:
    _local_env.cache_clear()


def get_secret(name: str, *, root: Path | None = None) -> str | None:
    """Resolve a secret from the environment, then local env files."""
    env_value = os.environ.get(name)
    if env_value:
        return env_value
    return _local_env(str(root or repo_root())).get(name) or None


def require_secret(name: str, *, root: Path | None = None) -> str:
    value = get_secret(name, root=root)
    if not value:
        raise MissingSecretError(
            f"{name} is not set. Add it to .env.local or export it in your shell."
        )
    return value


def get_ebird_api_key(*, root: Path | None = None) -> str | None:
    return get_secret(EBIRD_API_KEY_ENV, root=root)


def get_inaturalist_access_token(*, root: Path | None = None) -> str | None:
    return get_secret(INATURALIST_ACCESS_TOKEN_ENV, root=root)


def _coerce_seed(value: str) -> int:
    """Turn a seed string into a stable int (numeric values pass through directly)."""
    text = value.strip()
    try:
        return int(text)
    except ValueError:
        import hashlib

        return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**31)


def _read_seed_file(root: Path) -> str | None:
    path = root / MASTER_SEED_FILE
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.search(r"SEED\s*[:=]\s*(\S+)", text)
    if match:
        return match.group(1)
    stripped = text.strip()
    return stripped or None


def load_master_seed(*, root: Path | None = None, default: int | None = None) -> int:
    """Load the deterministic master seed.

    Resolution order: ``BIRDIDEX_MASTER_SEED`` (env or local env file), then the private
    ``data/seeds/master_seed.txt`` (a ``SEED: <value>`` line or a bare value). Neither the
    seed file nor the resolved value is ever committed or logged in full.
    """
    base = root or repo_root()
    env_value = get_secret(MASTER_SEED_ENV, root=base)
    if env_value:
        return _coerce_seed(env_value)
    file_value = _read_seed_file(base)
    if file_value:
        return _coerce_seed(file_value)
    if default is not None:
        return default
    raise MissingSecretError(
        f"{MASTER_SEED_ENV} is not set and {MASTER_SEED_FILE} is missing. "
        "Provide the project seed via .env.local or the private seed file."
    )


def master_seed_configured(*, root: Path | None = None) -> bool:
    base = root or repo_root()
    if get_secret(MASTER_SEED_ENV, root=base):
        return True
    return _read_seed_file(base) is not None
