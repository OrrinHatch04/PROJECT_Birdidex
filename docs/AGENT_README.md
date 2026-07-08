# Agent README

BIRDIDEX is a local offline bird-identification research and engineering project. The intended
device is a field-use cyberdeck for South East Queensland birds, with a Raspberry Pi 5 class target,
local camera input, runtime-friendly vision models, and no internet requirement during field
inference.

## Current Status

The repository now carries a runnable **software MVP** that works entirely offline (dry-run):
ROI species candidates → licensed image manifest → dataset splits → training/inference skeletons →
SQLite observation logging → minimal FastAPI UI. Run it with `make dry-run-pipeline`, or see the
"Run the offline MVP pipeline" section of the root README. The current suite has 148 passing
offline tests and 2 skipped training-boundary tests.

Treat every capability as skeleton-level unless a test proves a narrower claim. **No model has been
trained**: the classifier/detector training and ONNX export are runnable skeletons that fail fast
without the `training`/`inference` dependency groups, and the inference demo uses a deterministic
mock — it makes no accuracy claim.

No provider requests or media retrieval run by default. Live provider occurrence requests and media
retrieval exist only as explicit, opt-in commands that currently refuse to act (they document the
required behaviour rather than performing network I/O). Makefile verification targets are local
checks. Future provider access must be triggered by explicit user commands and configuration.

## Provider And Data Boundaries

External provider access is optional and user-configured. Provider tokens and other private local
runtime values belong only in local `.env` files or equivalent local runtime configuration.

Use structured biodiversity sources first:

- Atlas of Living Australia
- GBIF
- iNaturalist
- eBird when configured

Use only documented biodiversity, media, or search-provider APIs. Do not scrape search result pages
directly. Web keyword search is optional weak evidence, not a primary occurrence source.

When media retrieval is implemented, retrieve open-licence media only when explicitly requested.
Preserve licence metadata, attribution, source record IDs, and source URLs in manifests.

Private local configuration, retrieved media, raw/interim/processed data, logs, local databases,
model checkpoints, exports, and generated review artefacts stay out of version control.

## Safe First Commands

```bash
make doctor
make test
make audit-tree
make run-scanner-help
```

These commands are intended as local verification/help commands. They should not retrieve datasets,
make provider requests, train models, or start deployment work.

## Architecture Boundary

Keep the existing uv monorepo architecture unchanged. Apps import shared packages. Shared packages
do not import apps. Shared resources such as `configs/`, `data/`, `models/`, `notebooks/`, `scripts/`,
`tests/`, and `docs/` live at the repo root.

## Implementation Status

Software MVP (offline dry-run) implemented — see `make dry-run-pipeline`:

1. Repo audit — done
2. ROI species candidates — done (`bird_roi_scan`, `scripts/dataset/04`)
3. Licensed manifest — done (`bird_data.manifest_build`, `scripts/dataset/06`)
4. Dataset splits — done (`bird_data.splits`, `scripts/dataset/07`)
5. Baseline training skeleton — done, dependency-gated (`bird_training`)
6. ONNX export + quantisation hook — done, dependency-gated (`bird_training.export_onnx`)
7. Inference skeleton + reranker — done (`bird_inference`)
8. SQLite logging + cyberdeck UI — done (`bird_data.observation_log`, `bird_ui`)

Remaining real-data work (not in this MVP): live provider requests, actual media retrieval,
real model training/evaluation on retrieved data, and on-device deployment.
