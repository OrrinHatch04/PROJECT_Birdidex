# Architecture

BIRDIDEX now uses one Python package and one CLI.

```text
src/birdidex/
├── cli.py        # Typer command tree: doctor, scan-candidates, images, train, infer, ui
├── paths.py      # repo-root-relative paths
├── settings.py   # local runtime settings
├── taxonomy.py   # class_index.json parsing and class folder names
├── roi.py        # GeoJSON helpers
├── providers.py  # metadata normalization for documented provider APIs
├── images.py     # ImageFolder scaffold, metadata JSONL, reports
├── splits.py     # deterministic local-file train/val/test links
├── train.py      # training skeleton
├── infer.py      # inference skeleton
├── db.py         # local SQLite observation log
└── ui/           # minimal local UI scaffold
```

Root-owned resources remain:

```text
configs/ data/ models/ notebooks/ scripts/ tests/ docs/
```

## Data Flow

```text
data/processed/birddex/class_index.json
    -> birdidex.taxonomy.load_class_index
    -> birdidex images scaffold
    -> data/images/class_folder_index.csv

documented provider API metadata, when explicitly requested
    -> birdidex.providers normalized records
    -> birdidex.images validation
    -> data/images/metadata/image_records.jsonl
    -> data/images/reports/*

accepted records with local_path
    -> birdidex images split
    -> data/images/splits/{train,val,test}/{class_id:03d}.{label}/
```

## Class Rules

Classifier classes come only from `class_index.json`. The filesystem is output, not input.

Folder names are deterministic:

```text
{class_id:03d}.{label}
```

Taxa are not clean classifier classes when common or scientific names contain `sp.` or `/`. Those
taxa are excluded from provider metadata fetching by default.

## Provider Rules

Provider functions return metadata records only:

- iNaturalist
- ALA
- GBIF
- Wikimedia Commons
- Openverse

Records must preserve provider ID, image URL, source page URL, licence, attribution, dimensions when
available, observed date, coordinates when available, and raw provider metadata.

Unknown licence, missing image URL, duplicate provider record, ambiguous taxon, or scientific-name
mismatch prevents automatic acceptance.

## Design Decision

The project is deliberately below a multi-app threshold. The current goal is to keep the shape small
until real image ingestion, review, and training requirements justify more structure.
