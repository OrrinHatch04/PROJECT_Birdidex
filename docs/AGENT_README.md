# Agent README

BIRDIDEX is a local offline bird-identification research and engineering project. The intended
device remains a field-use system for South East Queensland birds, but this checkout is currently a
software scaffold for dataset preparation and future model work.

## Current Status

The repo has been collapsed to one Python package under `src/birdidex/` and one CLI:

```bash
uv run birdidex --help
```

Implemented now:

- class-index parsing from `data/processed/birddex/class_index.json`
- ImageFolder-style folder scaffolding under `data/images/`
- metadata-first provider record normalization
- JSONL metadata writing and simple reports
- deterministic train/val/test split symlinks from accepted local records
- thin training, inference, and UI skeleton commands

Not implemented:

- real image download
- model training
- model inference
- production UI behavior
- on-device deployment

## Provider And Data Boundaries

No provider requests or media retrieval run by default. Provider access must be explicit and
metadata-first. Use documented provider APIs only. Do not scrape Google or Bing image results.

Only explicit open-license media metadata is eligible for accepted records. Unknown licences,
missing image URLs, duplicate provider records, ambiguous taxa, and scientific-name mismatches are
quarantined or routed for review.

Private local configuration, retrieved media, raw/interim/processed datasets, generated image
folders, logs, local databases, model checkpoints, exports, cache files, and provider tokens stay
out of version control.

## Safe First Commands

```bash
uv run birdidex doctor
uv run birdidex images scaffold
uv run birdidex images report
uv run pytest
make audit-tree
```

These commands are local checks/scaffolds. They should not retrieve media, train models, make
provider requests, or start deployment work.

## Architecture Boundary

Keep the repo simple: one package, one CLI, one uv environment. Do not add new internal packages,
apps, provider subpackages, or uv workspace members without an explicit request.
