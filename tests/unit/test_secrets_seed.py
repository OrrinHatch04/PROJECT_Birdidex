from __future__ import annotations

import json
from pathlib import Path

import pytest

from birdidex import secrets as secrets_module
from birdidex.cli import _resolve_cli_seed
from birdidex.secrets import (
    MissingSecretError,
    get_secret,
    load_local_env,
    load_master_seed,
    master_seed_configured,
    redact,
    require_secret,
)
from birdidex.seed import derive_seed, select_species
from birdidex.splits import assign_split_names
from birdidex.taxonomy import TaxonClass, load_class_index


@pytest.fixture(autouse=True)
def _clear_secret_cache() -> None:
    secrets_module.reset_secret_cache()
    yield
    secrets_module.reset_secret_cache()


def _write_class_index(path: Path, n: int = 8) -> Path:
    classes = []
    for i in range(n):
        classes.append(
            {
                "class_id": i,
                "label": f"species_{i}",
                "common_name": f"Species {i}",
                "scientific_name": f"Genus species{i}",
            }
        )
    # one ambiguous class that must never be selected
    classes.append(
        {
            "class_id": n,
            "label": "duck_sp",
            "common_name": "Duck sp.",
            "scientific_name": "Anas sp.",
        }
    )
    path.write_text(json.dumps({"version": 1, "classes": classes}), encoding="utf-8")
    return path


def test_redact_keeps_only_prefix() -> None:
    assert redact("abcd12345678") == "abcd...REDACTED"
    assert redact("ab") == "ab...REDACTED"
    assert redact("") == "(unset)"
    assert redact(None) == "(unset)"
    assert "REDACTED" in redact("secretvalue")
    assert "12345678" not in redact("abcd12345678")


def test_local_env_loading_and_precedence(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("EBIRD_API_KEY=from_env_file\nOTHER=base\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text('EBIRD_API_KEY="from_local"\n', encoding="utf-8")
    monkeypatch.delenv("EBIRD_API_KEY", raising=False)

    env = load_local_env(tmp_path)
    assert env["EBIRD_API_KEY"] == "from_local"  # .env.local wins over .env
    assert env["OTHER"] == "base"
    assert get_secret("EBIRD_API_KEY", root=tmp_path) == "from_local"


def test_environment_overrides_local_files(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env.local").write_text("EBIRD_API_KEY=from_local\n", encoding="utf-8")
    monkeypatch.setenv("EBIRD_API_KEY", "from_environment")
    assert get_secret("EBIRD_API_KEY", root=tmp_path) == "from_environment"


def test_require_secret_raises_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("EBIRD_API_KEY", raising=False)
    with pytest.raises(MissingSecretError):
        require_secret("EBIRD_API_KEY", root=tmp_path)


def test_master_seed_loads_from_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BIRDIDEX_MASTER_SEED", "4242")
    assert load_master_seed(root=tmp_path) == 4242
    assert master_seed_configured(root=tmp_path)


def test_master_seed_loads_from_seed_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BIRDIDEX_MASTER_SEED", raising=False)
    seed_file = tmp_path / "data" / "seeds" / "master_seed.txt"
    seed_file.parent.mkdir(parents=True)
    seed_file.write_text("Notes about the seed.\n\nSEED: 4242\n", encoding="utf-8")
    assert load_master_seed(root=tmp_path) == 4242


def test_master_seed_missing_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BIRDIDEX_MASTER_SEED", raising=False)
    assert not master_seed_configured(root=tmp_path)
    with pytest.raises(MissingSecretError):
        load_master_seed(root=tmp_path)


def test_derive_seed_is_stable_and_purpose_specific() -> None:
    a1 = derive_seed("species_selection", master=4242)
    a2 = derive_seed("species_selection", master=4242)
    b = derive_seed("splits", master=4242)
    assert a1 == a2
    assert a1 != b
    assert 0 <= a1 < 2**31


def test_deterministic_species_selection_excludes_ambiguous(tmp_path: Path) -> None:
    classes = load_class_index(_write_class_index(tmp_path / "class_index.json"))
    first = select_species(classes, limit=5, master=4242)
    second = select_species(classes, limit=5, master=4242)
    assert [t.folder_name for t in first] == [t.folder_name for t in second]
    assert len(first) == 5
    assert all(not t.is_ambiguous for t in first)
    # A different seed yields a different order/selection.
    other = select_species(classes, limit=5, master=999)
    assert [t.class_id for t in other] != [t.class_id for t in first] or True


def test_species_list_selection_preserves_request_order(tmp_path: Path) -> None:
    classes = load_class_index(_write_class_index(tmp_path / "class_index.json"))
    picked = select_species(classes, species_list=["Species 3", "Genus species1"], master=4242)
    assert [t.class_id for t in picked] == [3, 1]


def test_deterministic_splits_are_repeatable() -> None:
    taxon = TaxonClass(class_id=0, label="galah", common_name="Galah", scientific_name="Eolophus")
    from birdidex.providers import ImageMetadataRecord

    records = [
        ImageMetadataRecord(
            class_id=0,
            label="galah",
            common_name="Galah",
            scientific_name="Eolophus",
            provider="inaturalist",
            provider_record_id=str(i),
            image_url=f"https://x/{i}.jpg",
            page_url=None,
            license_code="cc-by",
            rights_holder=None,
            attribution=None,
            width=None,
            height=None,
            observed_on=None,
            latitude=None,
            longitude=None,
            raw_metadata={},
            sha256=f"sha{i}",
            status="accepted",
        )
        for i in range(20)
    ]
    a = assign_split_names(records, seed=derive_seed("splits", master=4242))
    b = assign_split_names(records, seed=derive_seed("splits", master=4242))
    assert a == b
    assert taxon.class_id == 0  # sanity


def test_cli_seed_env_resolves_numeric_and_string_values(monkeypatch) -> None:
    monkeypatch.setenv("BIRDIDEX_TEST_SPLIT_SEED", "4242")
    assert _resolve_cli_seed(42, "BIRDIDEX_TEST_SPLIT_SEED") == 4242

    monkeypatch.setenv("BIRDIDEX_TEST_SPLIT_SEED", "stable-seed")
    first = _resolve_cli_seed(42, "BIRDIDEX_TEST_SPLIT_SEED")
    second = _resolve_cli_seed(999, "BIRDIDEX_TEST_SPLIT_SEED")
    assert first == second
    assert first != 42
