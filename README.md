# BIRDIDEX

Local, offline-first bird image-dataset and model scaffold for South East Queensland (SEQ)
field use. BIRDIDEX turns a stable species catalogue (`class_index.json`) into a labelled,
open-license image dataset, enriches it with regional context, builds offline species profiles,
and exposes thin training / inference / UI skeletons — all from **one installable package and one
CLI**.

- **eBird** provides regional **occurrence / season / locality priors** (context only — no images).
- **iNaturalist** provides labelled, **open-license photo metadata and image downloads**.
- Provider calls are **opt-in**: nothing hits the network during install, tests, or normal use —
  only the explicit `providers`, `images fetch*/download/pipeline` commands do.
- Every randomised step is **deterministic** under a private master seed.

It does **not** yet train models or run real inference.

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Configuration and secrets](#configuration-and-secrets)
- [The class index](#the-class-index)
- [CLI reference](#cli-reference)
- [Dataset collection workflow](#dataset-collection-workflow)
- [Image dataset scaffold](#image-dataset-scaffold)
- [Auditing and reports](#auditing-and-reports)
- [Train / val / test splits](#train--val--test-splits)
- [Species profiles](#species-profiles)
- [Big Bird auxiliary dataset](#big-bird-auxiliary-dataset)
- [Observation schema](#observation-schema)
- [Testing](#testing)
- [Development](#development)
- [What not to commit](#what-not-to-commit)

## Requirements

- Python **3.11** (pinned via `.python-version`).
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management.
- Network access **only** when you run a provider command.
- An [eBird API token](https://ebird.org/api/keygen) for eBird priors. iNaturalist works without a
  token for public endpoints.

## Install

```bash
uv python install 3.11
uv sync --all-groups
uv run birdidex --help
```

Dependency groups are small and workflow-named; `--all-groups` installs everything:

| Group | Purpose |
| --- | --- |
| `dev` | tests, linting, type checking, notebooks |
| `scanner` | ROI/geospatial and provider-support tools |
| `vision` | image inspection, resize/convert, perceptual hashing (Pillow + imagehash) |
| `training` | future training stack (torch/timm/lightning) |
| `inference` | future local inference runtime (onnx/openvino) |
| `ui` | local FastAPI UI scaffold |

The dataset collector, Big Bird audit, and dataset audit need the `vision` group.

## Quick start

```bash
# 1. install
uv sync --all-groups

# 2. sanity check (offline)
uv run birdidex doctor
uv run pytest

# 3. configure secrets for provider commands
cp .env.example .env.local            # then fill in EBIRD_API_KEY etc.
uv run birdidex providers doctor      # confirms keys resolve (values redacted)

# 4. scaffold folders and collect a small deterministic dataset
uv run birdidex images scaffold
uv run birdidex images pipeline --species-limit 5 --per-class 25 --target-accepted 10

# 5. inspect
uv run birdidex images report
uv run birdidex audit dataset
```

## Repository layout

```text
birdidex/
├── src/birdidex/
│   ├── cli.py            # the single Typer CLI
│   ├── paths.py          # repo-root-relative path helpers
│   ├── settings.py       # pydantic settings
│   ├── secrets.py        # secret + master-seed loading, redaction
│   ├── seed.py           # deterministic seed derivation + species selection
│   ├── taxonomy.py       # class_index parsing, folder naming, ambiguity rules
│   ├── providers.py      # eBird priors + iNaturalist/ALA/GBIF/… normalization
│   ├── images.py         # scaffold, metadata JSONL, reports
│   ├── download.py       # opt-in image download, validate, resize, dedupe
│   ├── pipeline.py       # end-to-end deterministic collection pipeline
│   ├── splits.py         # deterministic train/val/test splits
│   ├── bigbird.py        # Big Bird UAV audit + auxiliary import
│   ├── profiles.py       # offline species profiles
│   ├── observations.py   # cyberdeck observation schema
│   ├── audit.py          # dataset coverage audit
│   ├── roi.py, train.py, infer.py, db.py, ui/
├── configs/              # yaml/toml configs + *.example.* skeletons
├── data/                 # class index (tracked); generated data (gitignored)
├── models/               # model artefacts (gitignored)
├── notebooks/  scripts/  tests/  docs/
├── pyproject.toml  uv.lock  Makefile  README.md
```

## Configuration and secrets

Secrets and the project seed are read, in order, from:

1. the **environment**,
2. `.env.local` (gitignored),
3. `.env` (gitignored).

They are **never** written to tracked config, logs, reports, or test output. Any value shown to a
human is redacted to `first4...REDACTED` by `birdidex.secrets.redact`.

### Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `EBIRD_API_KEY` | for eBird | eBird API token, sent as the `X-eBirdApiToken` header. |
| `INATURALIST_ACCESS_TOKEN` | optional | iNaturalist OAuth token; public photo endpoints work without it. |
| `BIRDIDEX_MASTER_SEED` | recommended | Deterministic project seed; overrides `data/seeds/master_seed.txt`. |

Set them up:

```bash
cp .env.example .env.local
# edit .env.local:
#   EBIRD_API_KEY=...
#   INATURALIST_ACCESS_TOKEN=...      # optional
#   BIRDIDEX_MASTER_SEED=...          # or rely on data/seeds/master_seed.txt
uv run birdidex providers doctor      # verify (redacted); reports master-seed status
```

### The master seed

The deterministic master seed lives in `BIRDIDEX_MASTER_SEED` or the gitignored
`data/seeds/master_seed.txt` (a `SEED: <value>` line, or a bare value). It drives species-selection
order, train/val/test splits, candidate sampling, duplicate tie-breaking, and audit subsets, so a
fixed seed makes the whole pipeline reproducible. Rotating it changes dataset selection/splits —
regenerate downstream artefacts afterwards.

### Skeletons: what is safe to commit

For every private file there is a committable `*.example.*` skeleton that names variables only —
copy it to the real (gitignored) name and fill it in:

| Skeleton (commit) | Real file (gitignored) |
| --- | --- |
| `.env.example` | `.env.local` |
| `configs/scanner/providers.example.yaml` | `configs/scanner/providers.yaml` |
| `configs/providers.example.toml` | `configs/providers.local.toml` |
| `configs/dataset_search.example.toml` | `configs/dataset_search.local.toml` |
| `data/seeds/master_seed.example.txt` | `data/seeds/master_seed.txt` |
| `AGENT.example.md` | `AGENT.local.md` |
| `README_PRIVATE.example.md` | `README_PRIVATE.local.md` |

The `.gitignore` rule is simple: **anything named `*.local` / `*.local.*`, plus `.env*`, the real
`configs/scanner/providers.yaml`, and `data/seeds/master_seed.txt`, is never committed**; the
`*.example.*` skeletons always are.

## The class index

The single source of truth for classes is:

```text
data/processed/birddex/class_index.json
```

Folder names and the classifier label space are derived **only** from this file — classes are never
inferred from folders. Minimum schema:

```json
{
  "version": 1,
  "classes": [
    {
      "class_id": 0,
      "label": "albert_s_lyrebird",
      "common_name": "Albert's Lyrebird",
      "scientific_name": "Menura alberti",
      "aliases": [],
      "known_regions": [],
      "observation_count": 2
    }
  ]
}
```

- `class_id`, `label`, `common_name`, and `scientific_name` are required; `class_id` must be unique
  and non-negative; `label` and folder name (`{class_id:03d}.{label}`) must be unique.
- A taxon is **ambiguous** (not a clean classifier class, excluded from fetching by default) when its
  common or scientific name contains `sp.` or `/`.

## CLI reference

```text
uv run birdidex doctor                          # local package + dataset diagnostics
uv run birdidex scan-candidates                 # offline candidate CSV from the class index

# providers (opt-in network; secrets required)
uv run birdidex providers doctor [--provider ebird|inaturalist]
uv run birdidex providers dry-run --provider ebird       --species "Rainbow Lorikeet" [--region seq]
uv run birdidex providers dry-run --provider inaturalist --species "Rainbow Lorikeet" [--limit 5]

# image dataset
uv run birdidex images scaffold
uv run birdidex images fetch-metadata --provider inaturalist --species "Rainbow Lorikeet" --limit 25
uv run birdidex images fetch-metadata --provider ebird       --species "Rainbow Lorikeet" --region seq
uv run birdidex images download  --species "Rainbow Lorikeet" --target-accepted 150
uv run birdidex images pipeline  --species-limit 5 --per-class 25 --target-accepted 10
uv run birdidex images pipeline  --all --per-class 250 --target-accepted 200
uv run birdidex images report
uv run birdidex images split --train 0.75 --val 0.15 --test 0.10 --seed 42
# legacy multi-provider commands (iNaturalist/ALA/GBIF/Wikimedia/Openverse):
uv run birdidex images fetch-manifest
uv run birdidex images fetch --all --per-class 250 --target-accepted 200

# audit / profiles / observations / Big Bird
uv run birdidex audit dataset
uv run birdidex profiles build
uv run birdidex observations schema
uv run birdidex bigbird audit  --zip /path/to/bigbird.zip
uv run birdidex bigbird import --zip /path/to/bigbird.zip --mode auxiliary

# skeleton subsystems
uv run birdidex train --help
uv run birdidex infer --help
uv run birdidex ui serve
```

Most `make` targets mirror these (`make help` lists them): `providers-doctor`, `images-scaffold`,
`images-pipeline`, `images-pipeline-all`, `images-report`, `audit-dataset`, `profiles-build`,
`bigbird-audit`, `test`, `test-live`.

## Dataset collection workflow

The focused, seed-driven workflow: **eBird** for regional context priors, **iNaturalist** for
open-license images.

### 1. Verify auth (no downloads)

```bash
uv run birdidex providers doctor
uv run birdidex providers doctor --provider ebird
uv run birdidex providers dry-run --provider ebird       --species "Rainbow Lorikeet"
uv run birdidex providers dry-run --provider inaturalist --species "Rainbow Lorikeet" --limit 5
```

- **eBird dry-run** validates the token and returns normalized regional occurrence metadata for one
  species: `species_code`, resolved region, observation/individual counts, distinct localities,
  a month histogram, and top localities.
- **iNaturalist dry-run** resolves the taxon and prints a few open-license photo records
  (license, URL, attribution). Neither downloads image files.

Regions accept eBird codes (e.g. `AU-QLD`, `AU-NSW`) or the alias `seq` → `AU-QLD` (SEQ has no single
eBird region code).

### 2. One species

```bash
# iNaturalist photo metadata (no download)
uv run birdidex images fetch-metadata --provider inaturalist --species "Rainbow Lorikeet" --limit 25
# eBird regional priors -> data/profiles/region_priors.jsonl
uv run birdidex images fetch-metadata --provider ebird --species "Rainbow Lorikeet" --region seq --limit 25
# download accepted open-license images
uv run birdidex images download --species "Rainbow Lorikeet" --target-accepted 150 \
  --max-edge 1024 --format jpg --quality 85
```

### 3. Deterministic pipeline (5 species or all)

`images pipeline` selects clean, non-ambiguous species deterministically from the master seed,
fetches eBird priors per species, fetches iNaturalist photo metadata, downloads **accepted
open-license images only**, and regenerates reports and profiles. Provider errors are caught per
species — one bad response never aborts the run.

```bash
# small, repeatable integration run
uv run birdidex images pipeline --species-limit 5 --per-class 25 --target-accepted 10 \
  --max-edge 1024 --format jpg --quality 85

# full dataset (aim 150-200 accepted per class)
uv run birdidex images pipeline --all --per-class 250 --target-accepted 200 \
  --max-edge 1024 --format jpg --quality 85

# override selection with explicit species, or preview without downloading
uv run birdidex images pipeline --species-list "Rainbow Lorikeet,Laughing Kookaburra"
uv run birdidex images pipeline --species-limit 5 --dry-run --no-ebird
```

### Image size / format / quality

Stored images default to a **1024 px longest edge**, **jpg**, **quality 85**, converted to RGB with
unsafe/unneeded EXIF stripped. Fetch ~250 candidates per class to accept 150–200 — license,
taxonomy, duplicate, and quality checks reject the rest. Images are **not** resized to model input
size at ingestion (fine-grained ID needs detail), and full-resolution originals are discarded unless
you pass `--keep-originals`.

> iNaturalist photo URLs are automatically upgraded from the 75 px `square` thumbnail to the
> full-size (`large`) variant, so downloads carry real detail.

### License policy

Accepted by default: `cc0`, `cc-by`, `cc-by-sa`, `public-domain`, and the non-commercial CC variants
(`cc-by-nc`, `cc-by-nc-sa`). Rejected: missing, unknown, all-rights-reserved, and no-derivatives
licenses. Records are also rejected/quarantined for missing image URLs, scientific-name mismatch,
ambiguous taxa, duplicate provider records, sha256 and perceptual (phash) duplicates, corrupt or
animated files, very small images, and non-photo media. **You are responsible for honouring each
image's attribution and license terms.**

### Outputs

```text
data/images/metadata/image_records.jsonl     # per-image records (status + rejection_reason)
data/images/reports/class_counts.csv
data/images/reports/license_summary.csv
data/images/reports/provider_summary.csv
data/images/reports/review_queue.html
data/profiles/region_priors.jsonl            # eBird priors per species
```

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| `not configured` / auth fails | Put `EBIRD_API_KEY` in `.env.local`; re-run `providers doctor`. iNaturalist needs no token. |
| Rate limits (HTTP 429) | The pipeline logs the issue and continues; retry later or lower `--per-class`. |
| No images found | Use the scientific name, widen the region, or raise `--limit` / `--per-class`. |
| Many rejected licenses | Expected; raise `--per-class` to reach the accepted target. |
| Duplicate-heavy classes | sha256/phash duplicates are quarantined automatically — raise `--per-class`. |
| Disk usage | Keep the 1024 px / jpg / 85 defaults; avoid `--keep-originals`. |

## Image dataset scaffold

```bash
uv run birdidex images scaffold
```

Creates ImageFolder-style directories for every class (derived from the class index only):

```text
data/images/raw/{class_id:03d}.{label}/
data/images/review/{class_id:03d}.{label}/
data/images/quarantine/{class_id:03d}.{label}/
data/images/processed/{class_id:03d}.{label}/
data/images/splits/{train,val,test}/{class_id:03d}.{label}/
data/images/class_folder_index.csv
```

## Auditing and reports

```bash
uv run birdidex images report      # regenerate the metadata/reports above
uv run birdidex audit dataset      # full coverage audit
```

`audit dataset` writes `data/reports/dataset_audit.{json,html}` and
`data/reports/species_coverage.csv`: accepted/candidate/quarantined counts per class, provider and
license distributions, resolution distribution, duplicate counts, missing profile fields, weak
coverage (< 150 accepted), classes with no representative image, Big Bird overlap, and ambiguous
classes.

## Train / val / test splits

```bash
uv run birdidex images split --train 0.75 --val 0.15 --test 0.10 --seed 42
```

Splits are class-stratified and deterministic. Records that share an image (sha256 or provider id)
are grouped so duplicates never leak across train/val/test. Files are symlinked by default
(`--copy` to copy).

## Species profiles

```bash
uv run birdidex profiles build
```

Writes `data/profiles/species_profiles.json` and one `data/profiles/{class_id:03d}.{label}.json` per
class for the offline UI. Profiles are built **only** from structured local data — the class index,
accepted image records, and optional curated notes in `data/profiles/notes/{folder}.json`.
Natural-history fields (habitat, diet, behaviour, …) are never invented; unknown fields stay `null`
for a later enrichment pass.

## Big Bird auxiliary dataset

The Big Bird UAV dataset ships as a large (tens of GB) zip. Audit it without extracting:

```bash
uv run birdidex bigbird audit  --zip /path/to/bigbird.zip
uv run birdidex bigbird import --zip /path/to/bigbird.zip --mode auxiliary
```

Audit reports zip size, file/image counts, annotation formats/types, per-species counts, resolution
distribution, overlap with `class_index.json`, and a recommended import plan
(`data/reports/bigbird_audit.json`, `data/reports/bigbird_overlap.csv`). Import brings only
overlapping, species-level frames into `data/images/auxiliary/bigbird/…`, each marked
`view_type=uav_top_down` and `dataset_role=auxiliary`.

**Why UAV/top-down imagery is not mixed into normal training by default:** it is a poor fit for
fine-grained side-view species classification, so it is excluded from classifier splits unless you
pass `--include-auxiliary`. Use it for detector training, localisation, aerial robustness, and
optional pretraining/auxiliary validation instead.

## Observation schema

```bash
uv run birdidex observations schema
```

Prints the JSON Schema for a cyberdeck field-capture record (timestamp, GPS, weather, device/camera,
predicted class, top-k, user confirmation, notes, …). This is schema-only for now; the live SQLite
writer is in `birdidex.db`.

## Testing

```bash
uv run pytest                # unit tests only — fully offline, no keys or internet
uv run pytest -m live_api    # live eBird/iNaturalist checks (skip cleanly if keys are unset)
```

A plain `pytest` run never touches the network, even on a machine that has provider keys configured
— live tests are gated behind the `live_api` marker.

## Development

```bash
make lint         # ruff check
make format       # ruff format
make typecheck    # pyright
make test         # pytest
make help         # list all targets
```

## What not to commit

Generated dataset content, secrets, and the seed all stay out of version control. Never commit:

- `.env.local` / `.env`, and anything named `*.local` / `*.local.*`
- `configs/scanner/providers.yaml`, `data/seeds/master_seed.txt`
- downloaded images/datasets: `data/images/`, `data/external/`, `data/annotated_dataset/`
- generated outputs: `data/reports/`, `data/profiles/*`, `data/db/`, caches, logs
- model artefacts: `models/`, `*.pt`, `*.pth`, `*.onnx`, `*.ckpt`
- dataset archives (`*.zip`), except the tiny `tests/fixtures/tiny_bigbird.zip`

Commit the `*.example.*` skeletons instead. See `.gitignore` for the full list.

## Docs

- [docs/AGENT_README.md](docs/AGENT_README.md) — agent boundaries and safe commands
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — single-package architecture
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — uv and dependency-group notes
- [docs/WORK_CATEGORIES.md](docs/WORK_CATEGORIES.md) — current work areas
