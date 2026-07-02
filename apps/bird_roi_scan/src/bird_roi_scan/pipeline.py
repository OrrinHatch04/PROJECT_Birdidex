"""Top-level scan pipeline: coordinate providers and aggregate evidence.

TODO: Implement run_scan() to orchestrate all enabled providers.
TODO: Merge occurrence and keyword evidence into a scored species list.
TODO: Persist results to data/processed/ via DuckDB or parquet.
"""

from __future__ import annotations

from pathlib import Path

from bird_roi_scan.providers.base import OccurrenceProviderProtocol


def run_scan(
    roi_geojson: Path,
    providers: list[OccurrenceProviderProtocol],
    species_seed: Path | None = None,
) -> None:
    """Run the full scan pipeline (stub — not yet implemented).

    TODO: Load seed species list, iterate providers, score evidence, persist.
    """
    raise NotImplementedError("run_scan is not yet implemented")
