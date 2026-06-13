# Bird Scanner

Collects structured occurrence records (ALA, GBIF, eBird, iNaturalist) and weak keyword evidence (web search) to determine which bird species are present in the SEQ / Bundaberg-to-Goondiwindi ROI.

## Legacy code

The original `bird-roi-scan/` sub-project at the repo root is preserved. The new `apps/scanner/` integrates its best ideas with the typed package structure.

## Usage (not yet functional)

```bash
make sync-scanner
uv run bird-scanner score
uv run bird-scanner report
```
