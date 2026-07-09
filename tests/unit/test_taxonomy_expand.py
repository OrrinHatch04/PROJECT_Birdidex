"""Tests for ambiguous-class expansion, aliases, and safe class-index regeneration."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from birdidex import taxonomy_expand as tx
from birdidex import taxonomy_sources as ts
from birdidex.taxonomy import (
    ambiguity_reasons,
    clean_classifier_classes,
    find_taxon,
    is_ambiguous_taxon,
    load_class_index,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "providers"


# --------------------------------------------------------------------------- #
# Synthetic class index                                                        #
# --------------------------------------------------------------------------- #


def _write_index(tmp_path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 0,
                "label": "rainbow_bee_eater",
                "common_name": "Rainbow Bee-eater",
                "scientific_name": "Merops ornatus",
            },
            {
                "class_id": 1,
                "label": "gray_teal",
                "common_name": "Gray Teal",
                "scientific_name": "Anas gracilis",
            },
            {
                "class_id": 2,
                "label": "chestnut_teal",
                "common_name": "Chestnut Teal",
                "scientific_name": "Anas castanea",
            },
            {
                "class_id": 3,
                "label": "sacred_kingfisher",
                "common_name": "Sacred Kingfisher",
                "scientific_name": "Todiramphus sanctus",
            },
            {
                "class_id": 4,
                "label": "albert_s_lyrebird",
                "common_name": "Albert's Lyrebird",
                "scientific_name": "Menura alberti",
            },
            {
                "class_id": 5,
                "label": "teal_sp",
                "common_name": "teal sp.",
                "scientific_name": "Anatidae sp. (teal sp.)",
            },
            {
                "class_id": 6,
                "label": "kingfisher_sp",
                "common_name": "kingfisher sp.",
                "scientific_name": "Alcedinidae sp.",
            },
            {
                "class_id": 7,
                "label": "fairy_tree_martin",
                "common_name": "Fairy/Tree Martin",
                "scientific_name": "Petrochelidon ariel/nigricans",
            },
            {
                "class_id": 8,
                "label": "curlew_sp",
                "common_name": "curlew sp.",
                "scientific_name": "Numenius sp.",
            },
            {
                "class_id": 9,
                "label": "bush_thick_knee",
                "common_name": "Bush Thick-knee",
                "scientific_name": "Burhinus grallarius",
            },
        ],
    }
    path = tmp_path / "class_index.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _expand(tmp_path: Path, roi: dict[str, list[str]] | None = None) -> Any:
    classes = load_class_index(_write_index(tmp_path))
    expansion = tx.expand_ambiguous(classes, roi_presence=roi or {})
    return classes, expansion


# --------------------------------------------------------------------------- #
# Detection                                                                    #
# --------------------------------------------------------------------------- #


def test_detects_sp_and_label_suffix() -> None:
    reasons = ambiguity_reasons("teal sp.", "Anatidae sp. (teal sp.)", label="teal_sp")
    assert "common_name_sp" in reasons
    assert "scientific_name_sp" in reasons
    assert "label_sp_suffix" in reasons
    assert "family_or_subfamily_level" in reasons


def test_detects_slash_taxa() -> None:
    reasons = ambiguity_reasons("Fairy/Tree Martin", "Petrochelidon ariel/nigricans")
    assert reasons == ["common_name_slash", "scientific_name_slash"]
    assert is_ambiguous_taxon("Duck/Goose", "Anas/Chenonetta")


def test_detects_genus_only_scientific_name() -> None:
    assert ambiguity_reasons("Some Falcon", "Falco") == ["genus_only"]
    assert ambiguity_reasons(None, "Accipiter") == ["genus_only"]
    # A real binomial is not genus-only.
    assert ambiguity_reasons("Rainbow Bee-eater", "Merops ornatus") == []


def test_detects_family_and_subfamily_level() -> None:
    assert "family_or_subfamily_level" in ambiguity_reasons("kingfisher sp.", "Alcedinidae sp.")
    assert "family_or_subfamily_level" in ambiguity_reasons("tern sp.", "Sterninae sp.")
    # A genus that merely contains letters is not a family match.
    swallow = ambiguity_reasons("Welcome Swallow", "Hirundo neoxena")
    assert "family_or_subfamily_level" not in swallow


def test_detects_group_words_and_rank() -> None:
    assert "group_word" in ambiguity_reasons("Mallard hybrid", "Anas platyrhynchos hybrid")
    assert "group_word" in ambiguity_reasons("Some complex", "Genus species complex")
    assert "rank_above_species" in ambiguity_reasons(
        "Something", "Genus species", taxon_rank="genus"
    )
    assert "rank_above_species" not in ambiguity_reasons(
        "Something", "Genus species", taxon_rank="subspecies"
    )


def test_clean_binomial_is_not_ambiguous() -> None:
    for common, sci in [
        ("Laughing Kookaburra", "Dacelo novaeguineae"),
        ("Great Crested Tern", "Thalasseus bergii"),
        ("Eastern Cattle-Egret", "Ardea coromanda"),
    ]:
        assert ambiguity_reasons(common, sci) == []


# --------------------------------------------------------------------------- #
# Alias generation                                                             #
# --------------------------------------------------------------------------- #


def test_grey_gray_variants_both_directions() -> None:
    assert "Gray Teal" in tx.generate_common_name_variants("Grey Teal")
    assert "Grey Teal" in tx.generate_common_name_variants("Gray Teal")
    assert tx._swap_grey_gray("Grey Goshawk") == ["Gray Goshawk"]


def test_hyphen_and_apostrophe_variants() -> None:
    hyphen = tx.generate_common_name_variants("Rainbow Bee-eater")
    assert "Rainbow Bee eater" in hyphen
    apostrophe = tx.generate_common_name_variants("Albert's Lyrebird")
    assert "Alberts Lyrebird" in apostrophe


def test_alias_record_uses_curated_overrides(tmp_path: Path) -> None:
    classes = load_class_index(_write_index(tmp_path))
    teal = find_taxon(classes, "Gray Teal")
    assert teal is not None
    record = tx.build_alias_record(teal)
    assert record.confidence == "high"
    assert "Grey Teal" in record.aliases
    # The scientific name leads the search terms; the epithet is a low-confidence tail term.
    assert record.search_terms[0] == "Anas gracilis"
    assert "gracilis" in record.search_terms


def test_manual_override_add_and_reject_aliases(tmp_path: Path) -> None:
    override_file = tmp_path / "manual_overrides.local.toml"
    override_file.write_text(
        '[aliases."Merops ornatus"]\nadd = ["Rainbowbird"]\nreject = ["Rainbow Bee eater"]\n',
        encoding="utf-8",
    )
    overrides = tx.load_manual_overrides(override_file)
    classes = load_class_index(_write_index(tmp_path))
    bee_eater = find_taxon(classes, "Rainbow Bee-eater")
    assert bee_eater is not None
    record = tx.build_alias_record(bee_eater, overrides=overrides)
    assert "Rainbowbird" in record.aliases
    assert "Rainbow Bee eater" not in record.aliases


# --------------------------------------------------------------------------- #
# Expansion + candidate index                                                  #
# --------------------------------------------------------------------------- #


def test_expansion_links_existing_classes_and_proposes_new(tmp_path: Path) -> None:
    _, expansion = _expand(tmp_path)
    by_sci = {c.candidate_scientific_name: c for c in expansion}

    # teal_sp resolves to the two existing teal classes (linked, not re-added).
    gray = by_sci["Anas gracilis"]
    assert gray.existing_class_id == 1
    assert gray.add_to_candidate_index is False

    # The slash class splits into two concrete martins (new here).
    fairy = by_sci["Petrochelidon ariel"]
    assert fairy.existing_class_id is None
    assert fairy.add_to_candidate_index is True

    # The name-collision candidate is rejected and never added.
    bush = by_sci["Burhinus grallarius"]
    assert bush.status == "reject"
    assert bush.add_to_candidate_index is False


def test_local_roi_upgrades_status_to_confirmed(tmp_path: Path) -> None:
    _, expansion = _expand(tmp_path, roi={"anas gracilis": ["Kakadu Beach (Bribie Island)"]})
    gray = next(c for c in expansion if c.candidate_scientific_name == "Anas gracilis")
    assert gray.status == "confirmed_roi"
    assert ts.SOURCE_ROI_LOCAL in gray.evidence


def test_candidate_index_has_no_duplicate_labels_or_scientific_names(tmp_path: Path) -> None:
    classes, expansion = _expand(tmp_path)
    aliases = tx.build_alias_lexicon(classes)
    candidate = tx.build_candidate_index(classes, expansion, alias_records=aliases)

    out = tmp_path / "class_index_candidate.json"
    out.write_text(json.dumps(candidate), encoding="utf-8")
    # load_class_index raises on duplicate ids / labels / folders.
    reloaded = load_class_index(out)

    active = [t for t in reloaded if not t.is_deprecated]
    labels = [t.label for t in active]
    sci = [t.scientific_name for t in active if t.scientific_name]
    assert len(labels) == len(set(labels))
    assert len(sci) == len(set(sci))

    # The ambiguous classes are deprecated (never deleted) and carry replacements.
    deprecated = [t for t in reloaded if t.is_deprecated]
    assert {t.label for t in deprecated} == {
        "teal_sp",
        "kingfisher_sp",
        "fairy_tree_martin",
        "curlew_sp",
    }
    for taxon in deprecated:
        assert taxon.raw.get("replacement_class_ids")

    # curlew_sp maps to the two real Numenius classes but NOT the reject name-collision
    # (Bush Thick-knee / Burhinus grallarius, class 9).
    curlew = next(t for t in deprecated if t.label == "curlew_sp")
    assert 9 not in curlew.raw["replacement_class_ids"]


def test_existing_class_ids_are_preserved(tmp_path: Path) -> None:
    classes, expansion = _expand(tmp_path)
    candidate = tx.build_candidate_index(classes, expansion)
    by_label = {c["label"]: c for c in candidate["classes"]}
    assert by_label["gray_teal"]["class_id"] == 1
    assert by_label["sacred_kingfisher"]["class_id"] == 3
    # New species get appended ids beyond the current maximum.
    new_ids = [c["class_id"] for c in candidate["classes"] if c.get("status") == "proposed_new"]
    assert new_ids
    assert min(new_ids) >= 8


# --------------------------------------------------------------------------- #
# Replacement map                                                              #
# --------------------------------------------------------------------------- #


def test_replacement_map_writes_old_to_new_rows(tmp_path: Path) -> None:
    _, expansion = _expand(tmp_path)
    rows = tx.build_replacement_rows(expansion)
    out = tmp_path / "class_replacement_map.csv"
    tx._write_csv(out, tx.REPLACEMENT_MAP_FIELDS, rows)

    with out.open(encoding="utf-8", newline="") as handle:
        parsed = list(csv.DictReader(handle))

    teal_row = next(
        r for r in parsed if r["old_label"] == "teal_sp" and r["replacement_label"] == "gray_teal"
    )
    assert teal_row["old_scientific_name"] == "Anatidae sp. (teal sp.)"
    assert teal_row["replacement_scientific_name"] == "Anas gracilis"
    assert teal_row["replacement_status"] in {"likely_roi", "confirmed_roi"}
    assert "ebird_taxonomy" in teal_row["evidence_sources"]


# --------------------------------------------------------------------------- #
# Candidate validation                                                         #
# --------------------------------------------------------------------------- #


def test_validate_candidate_accepts_clean_index(tmp_path: Path) -> None:
    classes, expansion = _expand(tmp_path)
    candidate = tx.build_candidate_index(classes, expansion)
    out = tmp_path / "class_index_candidate.json"
    out.write_text(json.dumps(candidate), encoding="utf-8")

    report = tx.validate_candidate_index(out, images_root=tmp_path / "images")
    assert report.ok, report.errors
    assert report.summary["n_deprecated"] == 4


def test_validate_candidate_flags_duplicate_scientific_names(tmp_path: Path) -> None:
    payload = {
        "version": 2,
        "classes": [
            {
                "class_id": 0,
                "label": "gray_teal",
                "common_name": "Gray Teal",
                "scientific_name": "Anas gracilis",
            },
            {
                "class_id": 1,
                "label": "grey_teal_dup",
                "common_name": "Grey Teal",
                "scientific_name": "Anas gracilis",
            },
        ],
    }
    out = tmp_path / "candidate.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    report = tx.validate_candidate_index(out, images_root=tmp_path / "images")
    assert not report.ok
    assert any("duplicate scientific name" in err for err in report.errors)


def test_validate_candidate_flags_ambiguous_not_deprecated(tmp_path: Path) -> None:
    payload = {
        "version": 2,
        "classes": [
            {
                "class_id": 0,
                "label": "kingfisher_sp",
                "common_name": "kingfisher sp.",
                "scientific_name": "Alcedinidae sp.",
            }
        ],
    }
    out = tmp_path / "candidate.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    report = tx.validate_candidate_index(out, images_root=tmp_path / "images")
    assert not report.ok
    assert any("not marked deprecated" in err for err in report.errors)


# --------------------------------------------------------------------------- #
# Image-download / folder safety                                               #
# --------------------------------------------------------------------------- #


def test_deprecated_classes_excluded_from_download(tmp_path: Path) -> None:
    payload = {
        "version": 2,
        "classes": [
            {
                "class_id": 0,
                "label": "laughing_kookaburra",
                "common_name": "Laughing Kookaburra",
                "scientific_name": "Dacelo novaeguineae",
            },
            {
                "class_id": 1,
                "label": "kingfisher_sp",
                "common_name": "kingfisher sp.",
                "scientific_name": "Alcedinidae sp.",
                "deprecated": True,
                "status": "deprecated_ambiguous",
            },
        ],
    }
    index = tmp_path / "class_index.json"
    index.write_text(json.dumps(payload), encoding="utf-8")
    classes = load_class_index(index)

    clean = clean_classifier_classes(classes)
    assert [t.label for t in clean] == ["laughing_kookaburra"]

    from birdidex.download import collect_images

    summary = collect_images(
        class_index_path=index,
        images_root=tmp_path / "images",
        provider_names=("inaturalist",),
        only_classes=("1",),  # explicitly request the deprecated class
        dry_run=True,
    )
    assert summary.classes_processed == 0


def test_ambiguous_folder_images_not_moved_without_flag(tmp_path: Path) -> None:
    from birdidex import images as im

    payload = {
        "version": 2,
        "classes": [
            {
                "class_id": 0,
                "label": "kingfisher_sp",
                "common_name": "kingfisher sp.",
                "scientific_name": "Alcedinidae sp.",
            }
        ],
    }
    index = tmp_path / "class_index.json"
    index.write_text(json.dumps(payload), encoding="utf-8")
    root = tmp_path / "images"

    im.scaffold_image_dataset(class_index_path=index, images_root=root)
    raw = root / "raw" / "000.kingfisher_sp"
    (raw / "obs1.jpg").write_bytes(b"fake")
    assert (raw / im.DEPRECATED_MARKER).exists()

    # Default scaffold reports but never moves.
    im.scaffold_image_dataset(class_index_path=index, images_root=root, move_reviewed=False)
    assert (raw / "obs1.jpg").exists()
    report = (root / "reports" / im.DEPRECATED_FOLDER_REPORT).read_text(encoding="utf-8")
    assert "raw/000.kingfisher_sp" in report

    # Opt-in quarantine moves the file out of the training stages.
    im.scaffold_image_dataset(class_index_path=index, images_root=root, move_reviewed=True)
    assert not (raw / "obs1.jpg").exists()
    assert (root / "quarantine" / "000.kingfisher_sp" / "obs1.jpg").exists()


# --------------------------------------------------------------------------- #
# Provider taxonomy-search normalization (mocked)                              #
# --------------------------------------------------------------------------- #


class MockResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


class MockClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> MockResponse:
        self.calls.append((url, kwargs))
        return MockResponse(self.payload)


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_ebird_taxonomy_normalization() -> None:
    hits = ts.normalize_ebird_taxonomy(_fixture("ebird_taxonomy_search.json"))
    superb = next(h for h in hits if h.scientific_name == "Malurus cyaneus")
    assert superb.common_name == "Superb Fairywren"
    assert superb.provider_taxon_id == "supfai1"
    assert superb.provider == "ebird"
    assert superb.is_bird
    assert superb.is_species_level
    # The 'spuh' group row is a genus-level placeholder, not species level.
    spuh = next(h for h in hits if h.rank == "spuh")
    assert not spuh.is_species_level


def test_ebird_taxonomy_search_filters_by_query() -> None:
    client = MockClient(_fixture("ebird_taxonomy_search.json"))
    hits = ts.search_ebird_taxonomy(
        "Malurus melanocephalus", api_key="TESTKEY", client=client, live=True
    )
    assert client.calls
    assert [h.scientific_name for h in hits] == ["Malurus melanocephalus"]
    # Auth header is sent; the key is never logged here but must be forwarded.
    _, kwargs = client.calls[0]
    assert kwargs["headers"]["X-eBirdApiToken"] == "TESTKEY"


def test_inaturalist_taxa_normalization_keeps_birds_only() -> None:
    hits = ts.normalize_inaturalist_taxa(_fixture("inat_taxa.json"))
    banksia = next(h for h in hits if h.scientific_name == "Banksia serrata")
    assert not banksia.is_bird

    client = MockClient(_fixture("inat_taxa.json"))
    searched = ts.search_inaturalist_taxa("kookaburra", client=client, live=True)
    names = {h.scientific_name for h in searched}
    assert "Dacelo novaeguineae" in names
    assert "Banksia serrata" not in names  # plants filtered out


def test_ala_autocomplete_normalization() -> None:
    hits = ts.normalize_ala_names(_fixture("ala_autocomplete.json"))
    superb = next(h for h in hits if h.scientific_name == "Malurus cyaneus")
    assert superb.common_name == "Superb Fairy-wren"
    assert superb.provider == "ala"
    assert superb.provider_taxon_id.endswith("superb")
    assert superb.is_bird

    client = MockClient(_fixture("ala_autocomplete.json"))
    searched = ts.search_ala_names("fairywren", client=client, live=True)
    # The non-bird wattle row is filtered out of live search results.
    assert all(h.is_bird for h in searched)
    assert "Acacia cyanophylla" not in {h.scientific_name for h in searched}


def test_offline_provider_searches_return_empty() -> None:
    assert ts.search_ebird_taxonomy("x", api_key="k", live=False) == []
    assert ts.search_inaturalist_taxa("x", live=False) == []
    assert ts.search_ala_names("x", live=False) == []


def test_no_unmatched_ambiguous_groups_in_real_index() -> None:
    """Every ambiguous class in the shipped index maps to a curated group."""
    from birdidex.paths import default_class_index_path

    classes = load_class_index(default_class_index_path())
    for record in tx.detect_ambiguous(classes):
        assert record.group is not None, f"no curated group for {record.taxon.label}"


# --------------------------------------------------------------------------- #
# "Add every Australian species" (always_include) + field notes               #
# --------------------------------------------------------------------------- #


def _fairywren_index(tmp_path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 0,
                "label": "fairywren_sp",
                "common_name": "fairywren sp.",
                "scientific_name": "Malurus sp.",
            }
        ],
    }
    path = tmp_path / "class_index.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_all_australian_fairywrens_are_addable(tmp_path: Path) -> None:
    classes = load_class_index(_fairywren_index(tmp_path))
    expansion = tx.expand_ambiguous(classes, roi_presence={})
    names = {c.candidate_scientific_name for c in expansion if c.add_to_candidate_index}
    # Every Australian Malurus fairywren becomes a class, including non-SEQ ones.
    assert "Malurus cyaneus" in names  # likely_roi
    assert "Malurus splendens" in names  # australian_but_not_roi but always included
    assert "Malurus leucopterus" in names
    assert len([c for c in expansion if c.add_to_candidate_index]) >= 10

    candidate = tx.build_candidate_index(classes, expansion)
    labels = {c["label"] for c in candidate["classes"] if c.get("status") == "proposed_new"}
    assert "splendid_fairywren" in labels
    assert "purple_crowned_fairywren" in labels


def test_field_notes_seeded_for_beloved_species(tmp_path: Path) -> None:
    from birdidex.taxonomy import TaxonClass

    stork = TaxonClass(
        class_id=0,
        label="black_necked_stork",
        common_name="Black-necked Stork",
        scientific_name="Ephippiorhynchus asiaticus",
    )
    record = tx.build_alias_record(stork)
    assert "iris" in record.field_notes.lower()
    assert "Jabiru" in record.aliases


# --------------------------------------------------------------------------- #
# Live-scour normalizers + orchestration (mocked; no network)                 #
# --------------------------------------------------------------------------- #


def test_inaturalist_all_names_normalization_english_only() -> None:
    payload = {
        "results": [
            {
                "id": 12083,
                "name": "Malurus splendens",
                "names": [
                    {"name": "Splendid Fairywren", "locale": "en"},
                    {"name": "Splendid Fairy-wren", "locale": "en"},
                    {"name": "Blue Wren", "locale": "en-AU"},
                    {"name": "Prachtstaffelschwanz", "locale": "de"},
                    {"name": "Splendid Fairywren", "locale": "en"},
                ],
            }
        ]
    }
    names = ts.normalize_inaturalist_names(payload)
    assert names == ["Splendid Fairywren", "Splendid Fairy-wren", "Blue Wren"]


def test_wikipedia_summary_normalization() -> None:
    ok = {
        "type": "standard",
        "title": "Splendid fairywren",
        "extract": "The splendid fairywren is a passerine bird.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Splendid_fairywren"}},
    }
    summary = ts.normalize_wikipedia_summary(ok)
    assert summary is not None
    assert summary["url"].endswith("Splendid_fairywren")
    assert ts.normalize_wikipedia_summary({"type": ".../not_found"}) is None
    assert ts.normalize_wikipedia_summary({"title": "x"}) is None  # no extract


class RoutingMockClient:
    """Returns a payload chosen by a matcher against the requested URL."""

    def __init__(self, routes: list[tuple[str, Any]]) -> None:
        self.routes = routes

    def get(self, url: str, **kwargs: Any) -> MockResponse:
        for needle, payload in self.routes:
            if needle in url:
                return MockResponse(payload)
        return MockResponse({})

    def close(self) -> None:  # matches httpx.Client interface used by enrichment
        return None


def test_scour_one_merges_inaturalist_names_and_wikipedia() -> None:
    taxa_search = {
        "results": [
            {
                "id": 12083,
                "name": "Malurus splendens",
                "preferred_common_name": "Splendid Fairywren",
                "iconic_taxon_name": "Aves",
            }
        ]
    }
    all_names = {
        "results": [
            {
                "id": 12083,
                "name": "Malurus splendens",
                "names": [
                    {"name": "Splendid Fairywren", "locale": "en"},
                    {"name": "Banded Superb-Warbler", "locale": "en"},
                ],
            }
        ]
    }
    wiki = {
        "type": "standard",
        "title": "Splendid fairywren",
        "extract": "The splendid fairywren is a passerine bird of the family Maluridae.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Splendid_fairywren"}},
    }
    inat = RoutingMockClient([("/v1/taxa/12083", all_names), ("/v1/taxa", taxa_search)])
    wikic = RoutingMockClient([("wikipedia", wiki)])

    blob = tx._scour_one(
        "Splendid Fairywren",
        "Malurus splendens",
        inat_client=inat,
        wiki_client=wikic,
        use_inaturalist=True,
        use_wikipedia=True,
    )
    assert blob["inat_taxon_id"] == "12083"
    assert "Banded Superb-Warbler" in blob["inat_names"]
    assert blob["wikipedia"]["url"].endswith("Splendid_fairywren")
    assert not blob["errors"]


def test_enrich_aliases_live_offline_is_noop() -> None:
    from birdidex.taxonomy import TaxonClass

    record = tx.build_alias_record(
        TaxonClass(0, "splendid_fairywren", "Splendid Fairywren", "Malurus splendens")
    )
    before = list(record.aliases)
    # No eBird key and both live sources disabled -> no cache read, no network, no change.
    errors = tx.enrich_aliases_live(
        [record],
        ebird_api_key=None,
        use_inaturalist=False,
        use_wikipedia=False,
        cache=False,
    )
    assert errors == []
    assert record.aliases == before
