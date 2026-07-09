# Container and VSCodium Notebook Kernel

This repo includes a Docker setup that builds the full `uv sync --all-groups` environment and
registers it as a Jupyter kernel named `BIRDIDEX uv (.venv)`.

The container keeps the uv environment at `/opt/birdidex/.venv` instead of inside the repository.
That matters because the repo is bind-mounted into the container while you work, and a bind mount
would otherwise hide an image-built `.venv`.

The full image is large because `--all-groups` includes the ROCm PyTorch training stack. On this
machine the built image is about 47 GB.

## Start Jupyter

```bash
docker compose up --build birdidex-jupyter
```

Jupyter is bound to localhost:

```text
http://127.0.0.1:8888
```

The FastAPI UI scaffold port is also exposed on localhost:

```text
http://127.0.0.1:8000
```

## Use From VSCodium

Option 1, Dev Containers:

1. Install a Dev Containers-compatible extension plus Python and Jupyter notebook extensions.
2. Run `Dev Containers: Reopen in Container`.
3. Open a notebook.
4. Use `Select Kernel` and choose `BIRDIDEX uv (.venv)`.

Option 2, existing Jupyter server:

1. Run `docker compose up --build birdidex-jupyter`.
2. In VSCodium, use `Select Kernel`.
3. Choose an existing Jupyter server and enter `http://127.0.0.1:8888`.
4. Select the `BIRDIDEX uv (.venv)` kernel.

## Shell Access

```bash
docker compose exec birdidex-jupyter bash
uv run birdidex doctor
uv run pytest
```

## Local Config

The repository is mounted at `/workspace/birdidex`, so a local `.env.local` remains available inside
the container but is still gitignored. Provider commands remain opt-in; starting the container does
not make provider requests or download images.
