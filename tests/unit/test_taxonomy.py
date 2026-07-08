from __future__ import annotations

import json
from pathlib import Path

from birdidex.taxonomy import (
    class_folder_name,
    clean_classifier_classes,
    is_ambiguous_taxon,
    load_class_index,
)


def write_class_index(path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 0,
                "label": "rainbow_bee_eater",
                "common_name": "Rainbow Bee-eater",
                "scientific_name": "Merops ornatus",
                "observation_count": 10,
            },
            {
                "class_id": 1,
                "label": "falco_sp",
                "common_name": "Falco sp.",
                "scientific_name": "Falco sp.",
            },
            {
                "class_id": 2,
                "label": "duck_goose",
                "common_name": "Duck/Goose",
                "scientific_name": "Anas/Chenonetta",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_class_index_parsing_and_folder_names(tmp_path: Path) -> None:
    classes = load_class_index(write_class_index(tmp_path / "class_index.json"))

    assert [taxon.class_id for taxon in classes] == [0, 1, 2]
    assert classes[0].folder_name == "000.rainbow_bee_eater"
    assert class_folder_name(12, "Pale-headed Rosella") == "012.pale_headed_rosella"


def test_ambiguous_taxa_are_filtered_from_clean_classes(tmp_path: Path) -> None:
    classes = load_class_index(write_class_index(tmp_path / "class_index.json"))

    assert is_ambiguous_taxon("Falco sp.", "Falco sp.")
    assert is_ambiguous_taxon("Duck/Goose", "Anas/Chenonetta")
    assert [taxon.label for taxon in clean_classifier_classes(classes)] == ["rainbow_bee_eater"]
