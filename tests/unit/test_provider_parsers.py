"""Provider fixture parsing → normalised occurrences → evidence aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from bird_roi_scan.occurrences import aggregate_to_evidence
from bird_roi_scan.providers import ala, ebird, gbif, inaturalist

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "providers"


def _load(name: str) -> list[dict]:
    return json.loads((FIX / name).read_text())


def test_ala_parser_reads_fields_and_captive() -> None:
    occ = ala.parse_occurrences(_load("ala_occurrences.json"))
    assert len(occ) == 3
    assert occ[0].source == "ala"
    assert occ[0].scientific_name == "Dacelo novaeguineae"
    assert occ[0].event_date is not None and occ[0].event_date.year == 2024
    # establishmentMeans == cultivated marks captive
    assert occ[2].captive_or_cultivated is True


def test_gbif_parser_handles_year_month_day() -> None:
    occ = gbif.parse_occurrences(_load("gbif_occurrences.json"))
    assert len(occ) == 3
    ymd = occ[1]
    assert ymd.event_date is not None and (ymd.event_date.year, ymd.event_date.month) == (2023, 9)
    assert occ[2].captive_or_cultivated is True  # LIVING_SPECIMEN


def test_inat_parser_parses_location_and_captive() -> None:
    occ = inaturalist.parse_occurrences(_load("inat_occurrences.json"))
    assert occ[0].latitude == -27.48 and occ[0].longitude == 152.98
    assert occ[1].captive_or_cultivated is True


def test_ebird_parser_parses_datetime() -> None:
    occ = ebird.parse_occurrences(_load("ebird_recent.json"))
    assert len(occ) == 2
    assert occ[0].source == "ebird"
    assert occ[0].event_date is not None and occ[0].event_date.year == 2025


def test_aggregate_excludes_captive_and_computes_roi_fraction() -> None:
    occ = ala.parse_occurrences(_load("ala_occurrences.json"))
    ev = aggregate_to_evidence(occ, exclude_captive=True)
    # 3 records, 1 captive excluded -> 2 counted, both inside roi
    assert ev.occurrences_by_source["ala"] == 2
    assert ev.inside_roi_fraction == 1.0
    assert 2024 in ev.recent_years
