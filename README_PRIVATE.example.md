# BIRDIDEX Private Runbook (skeleton)

Copy this to `README_PRIVATE.local.md` (gitignored) and fill in local details. Keep secrets
in `.env.local`; never duplicate them here or in the public `README.md`.

## First-time setup

```bash
uv python install 3.11
uv sync --all-groups
cp .env.example .env.local     # then fill in the real values
```

`.env.local` should contain:

```dotenv
EBIRD_API_KEY=<real eBird token>
INATURALIST_ACCESS_TOKEN=<real iNaturalist token, optional>
BIRDIDEX_MASTER_SEED=<project seed>   # or rely on data/seeds/master_seed.txt
```

## Verify (offline)

```bash
uv run birdidex doctor
uv run birdidex providers doctor
uv run birdidex images scaffold
uv run birdidex images report
uv run pytest
```

## Live checks / collection (needs .env.local)

```bash
uv run birdidex providers dry-run --provider ebird --species "Rainbow Lorikeet"
uv run birdidex providers dry-run --provider inaturalist --species "Rainbow Lorikeet" --limit 5
uv run birdidex images pipeline --species-limit 5 --per-class 25 --target-accepted 10
uv run birdidex images pipeline --all --per-class 250 --target-accepted 200
```

## Never commit

`.env.local`, `.env`, `data/seeds/master_seed.txt`, `AGENT.local.md`,
`README_PRIVATE.local.md`, `configs/scanner/providers.yaml`, `configs/*.local.toml`,
downloaded images/datasets, caches, reports, profiles, model weights.
