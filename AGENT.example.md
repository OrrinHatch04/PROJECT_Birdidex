# AGENT.local (skeleton)

Copy this to `AGENT.local.md` (gitignored) and fill in local operating notes. Never move
secrets or seed values into the tracked `docs/AGENT_README.md` or `README.md`.

## Secrets live only in .env.local / the environment

| Env var | Purpose |
| --- | --- |
| `EBIRD_API_KEY` | eBird API token, sent as `X-eBirdApiToken`. |
| `INATURALIST_ACCESS_TOKEN` | Optional iNaturalist OAuth token. |
| `BIRDIDEX_MASTER_SEED` | Deterministic project seed (overrides the seed file). |

- Resolution order: environment → `.env.local` → `.env`.
- All secret rendering goes through `birdidex.secrets.redact` (first 4 chars + `...REDACTED`).
- Never paste full tokens into commits, logs, reports, issues, or screenshots.

## Master seed

- Source of truth: `data/seeds/master_seed.txt` (gitignored), a `SEED: <value>` line.
- Drives species selection, splits, sampling, dedupe tie-breaking, and audit subsets.

## Local run notes

```bash
uv sync --all-groups
uv run birdidex providers doctor
uv run birdidex images pipeline --species-limit 5 --per-class 25 --target-accepted 10
```

Provider calls are opt-in; only `dry-run`, `fetch-metadata`, `download`, and `pipeline`
touch the network, and only when invoked.
