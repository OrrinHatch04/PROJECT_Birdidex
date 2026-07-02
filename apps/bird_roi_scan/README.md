# Bird ROI Scanner (`bird_roi_scan`)

Collects structured occurrence records (ALA, GBIF, eBird, iNaturalist) and weak keyword
evidence (web search) to determine which bird species are present in the
SEQ / Bundaberg-to-Goondiwindi ROI.

This app owns only its CLI, pipeline orchestration, and provider adapters. Shared concerns
live in the workspace packages:

- `bird_core` — IDs, settings, logging, enums
- `bird_geo` — ROI loading + WKT export
- `bird_data` — `SpeciesRecord`, manifests, taxonomy

> **Status: skeleton only.** Providers raise `NotImplementedError`. No API calls are made yet.

## Usage (not yet functional)

```bash
make sync-scanner
uv run bird-roi-scan score
uv run bird-roi-scan report
```

> Note: a console entry point named `bird-roi-scan` is not yet declared in `pyproject.toml`.
> For now invoke the CLI module directly:
>
> ```bash
> python -m bird_roi_scan.cli score
> ```

## History

The earlier root-level `bird-roi-scan/` prototype was folded into this app during the
2026-06-13 restructure. Its broken-skeleton source (space-prefixed ` __init__.py` files,
typo'd method names) was archived under `audit_backups/restructure_<timestamp>/`; its useful
ideas (Pydantic species model, web-search query templates, provider ABC) are represented here
and in the shared packages. See [docs/RESTRUCTURE_AUDIT.md](../../docs/RESTRUCTURE_AUDIT.md).
