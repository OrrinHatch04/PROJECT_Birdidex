"""Open-licence helpers for media manifests.

Only open Creative Commons licences (and public-domain markers) are eligible for
retrieval and training. Licence codes follow the lower-case iNaturalist convention
(e.g. ``cc-by``, ``cc0``). Anything not recognised as open is treated as closed so the
default is conservative.
"""

from __future__ import annotations

from bird_data.manifests import ImageManifestRecord

# Codes that permit reuse (attribution and non-commercial variants included).
# ``cc-by-nd`` / ``cc-by-nc-nd`` are excluded: no-derivatives blocks crop/augment use.
OPEN_LICENSE_CODES: frozenset[str] = frozenset(
    {
        "cc0",
        "cc-by",
        "cc-by-sa",
        "cc-by-nc",
        "cc-by-nc-sa",
        "pd",
        "publicdomain",
    }
)

# Human-readable labels for reporting.
LICENSE_LABELS: dict[str, str] = {
    "cc0": "CC0 (public domain dedication)",
    "cc-by": "CC BY",
    "cc-by-sa": "CC BY-SA",
    "cc-by-nc": "CC BY-NC",
    "cc-by-nc-sa": "CC BY-NC-SA",
    "cc-by-nd": "CC BY-ND (no derivatives — excluded)",
    "cc-by-nc-nd": "CC BY-NC-ND (no derivatives — excluded)",
    "pd": "Public domain",
    "publicdomain": "Public domain",
}


def normalise_license(code: str | None) -> str | None:
    """Normalise a licence code to the lower-case hyphenated convention."""
    if not code:
        return None
    return code.strip().lower().replace("_", "-").replace(" ", "-")


def is_open_license(code: str | None) -> bool:
    """Return True if the licence code permits reuse with derivatives."""
    return normalise_license(code) in OPEN_LICENSE_CODES


def filter_open_licensed(
    records: list[ImageManifestRecord],
) -> tuple[list[ImageManifestRecord], list[ImageManifestRecord]]:
    """Split records into ``(kept, rejected)`` by open-licence eligibility."""
    kept: list[ImageManifestRecord] = []
    rejected: list[ImageManifestRecord] = []
    for record in records:
        if is_open_license(record.license):
            kept.append(record)
        else:
            rejected.append(record)
    return kept, rejected


def license_counts(records: list[ImageManifestRecord]) -> dict[str, int]:
    """Count records grouped by normalised licence code (``"unknown"`` if missing)."""
    counts: dict[str, int] = {}
    for record in records:
        code = normalise_license(record.license) or "unknown"
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))
