"""End-to-end ROI candidate scan (dry-run) writes the expected outputs."""

from __future__ import annotations

import csv
from pathlib import Path

from bird_roi_scan.pipeline import (
    CANDIDATES_CSV_FIELDS,
    run_candidate_scan,
    seed_to_evidence,
)
from bird_roi_scan.seeds import seed_species


def test_seed_species_deterministic_and_nonempty() -> None:
    seeds = seed_species()
    assert len(seeds) >= 10
    assert seeds == seed_species()  # stable order
    assert all(s.species_id for s in seeds)


def test_seed_to_evidence_preserves_counts() -> None:
    seed = seed_species()[0]
    ev = seed_to_evidence(seed)
    assert ev.occurrences_by_source == dict(seed.occurrences_by_source)
    assert ev.manual_review == seed.manual_review


def test_run_candidate_scan_writes_outputs(tmp_path: Path) -> None:
    result = run_candidate_scan(
        manifests_dir=tmp_path / "manifests",
        reports_dir=tmp_path / "reports",
        current_year=2025,
    )
    assert result.candidates_csv.exists()
    assert result.tiers_csv.exists()
    assert result.report_md.exists()

    with result.candidates_csv.open(newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == CANDIDATES_CSV_FIELDS
        rows = list(reader)
    assert len(rows) == len(seed_species())
    assert {r["tier"] for r in rows} <= {"core", "review", "rejected"}
    # report is candidate-only; must not claim a trained model
    text = result.report_md.read_text().lower()
    assert "no claim" in text or "makes no claim" in text


def test_live_scan_refuses() -> None:
    import pytest

    with pytest.raises(NotImplementedError):
        run_candidate_scan(dry_run=False)
