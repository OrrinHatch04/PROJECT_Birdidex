"""Tests for the species class-index builder (deterministic IDs, dedup, name splitting).

Uses tiny in-memory observation rows — no real CSVs required.
"""

from __future__ import annotations

from bird_data.ebird_ingest import (
    F_COMMON_NAME,
    F_LOCALITY,
    F_OBSERVATION_COUNT,
    F_SCIENTIFIC_NAME,
    F_SOURCE_FILE,
    normalise_ebird_columns,
    split_species_name,
)
from bird_data.species_classes import build_species_catalog, canonicalise_species_name


def _obs(common, scientific=None, count="1", region="Region A", source="a.csv"):
    return {
        F_COMMON_NAME: common,
        F_SCIENTIFIC_NAME: scientific,
        F_OBSERVATION_COUNT: count,
        F_LOCALITY: region,
        F_SOURCE_FILE: source,
    }


def test_canonical_label_is_stable_slug():
    assert canonicalise_species_name("Rainbow Bee-eater") == "rainbow_bee_eater"
    assert canonicalise_species_name("Australian Brushturkey") == "australian_brushturkey"


def test_split_species_name_variants():
    assert split_species_name("Australian Brushturkey Alectura lathami") == (
        "Australian Brushturkey",
        "Alectura lathami",
    )
    assert split_species_name("curlew sp. Numenius sp.") == ("curlew sp.", "Numenius sp.")
    assert split_species_name("Silvereye") == ("Silvereye", None)


def test_duplicates_collapse_and_counts_sum():
    obs = [
        _obs("Australian Brushturkey", "Alectura lathami", count="15", region="Region A"),
        _obs("Australian Brushturkey", "Alectura lathami", count="3", region="Region B"),
    ]
    species = build_species_catalog(obs)
    assert len(species) == 1
    sp = species[0]
    assert sp.observation_count == 18
    assert sp.known_regions == ["Region A", "Region B"]


def test_class_ids_are_deterministic_and_alphabetical_without_taxon_order():
    obs = [_obs("Willie Wagtail"), _obs("Australian Magpie"), _obs("Noisy Miner")]
    a = build_species_catalog(obs)
    b = build_species_catalog(list(reversed(obs)))
    # Same class_id regardless of input order.
    assert {s.label: s.class_id for s in a} == {s.label: s.class_id for s in b}
    # Alphabetical by label -> australian_magpie is class 0.
    assert a[0].label == "australian_magpie"
    assert a[0].class_id == 0


def test_missing_scientific_name_does_not_crash():
    species = build_species_catalog([_obs("Silvereye", scientific=None)])
    assert species[0].label == "silvereye"
    assert species[0].scientific_name is None


def test_simplified_export_row_is_split_on_normalise():
    rows = [{"Species Name": "Australian Brushturkey Alectura lathami", "Count": "2",
             "Location": "Region A"}]
    norm = normalise_ebird_columns(rows, source="a.csv")
    assert norm[0][F_COMMON_NAME] == "Australian Brushturkey"
    assert norm[0][F_SCIENTIFIC_NAME] == "Alectura lathami"
