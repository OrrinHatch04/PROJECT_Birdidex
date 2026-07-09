# Environment

BIRDIDEX uses Python 3.11 and uv. It is a normal single-package project, not a uv workspace.

## Setup

```bash
uv python install 3.11
uv sync --all-groups
uv run birdidex doctor
uv run pytest
```

The project interpreter is:

```text
${workspaceFolder}/.venv/bin/python
```

Prefer `uv run ...` or Makefile targets so commands use the project environment.

## Docker / VSCodium Notebooks

For a containerized notebook kernel, use:

```bash
make docker-jupyter
```

This builds the full `uv sync --all-groups` environment in Docker and registers a Jupyter kernel
named `BIRDIDEX uv (.venv)`. In VSCodium, use `Select Kernel` and choose that kernel after reopening
the repo in the dev container, or connect to the existing Jupyter server at `http://127.0.0.1:8888`.

See `docs/CONTAINER.md` for details.

## Dependency Groups

| Group | Command | Contains |
| --- | --- | --- |
| base | `uv sync` | CLI, settings, HTTP, YAML, pydantic |
| dev | `uv sync --group dev` | pytest, ruff, pyright, mypy, pre-commit, notebooks |
| scanner | `uv sync --group scanner` | geospatial and provider-support tools |
| vision | `uv sync --group vision` | image inspection and corruption-check tools |
| training | `uv sync --group training` | future training stack |
| inference | `uv sync --group inference` | future local inference runtime |
| ui | `uv sync --group ui` | FastAPI UI scaffold |

Common combinations:

```bash
make sync-dev
make sync-training
make sync-pi
make sync-all
```

## Makefile Commands

| Target | What it does |
| --- | --- |
| `make doctor` | `uv run birdidex doctor` |
| `make verify-stack` | local smoke test script |
| `make test` | `uv run pytest` |
| `make scan-candidates` | offline candidate CSV from class index |
| `make images-scaffold` | create `data/images/` folders from class index |
| `make images-fetch-manifest` | write metadata manifest, no live requests by default |
| `make images-split` | create symlink splits from accepted local records |
| `make images-report` | regenerate image reports |
| `make run-ui-dev` | start the local UI scaffold |

`make clean` removes Python and tool caches only. It does not delete `.venv`, `data/`, `models/`,
notebooks, or generated runtime artifacts.
