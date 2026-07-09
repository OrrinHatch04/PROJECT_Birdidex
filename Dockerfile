# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/birdidex/.venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/birdidex/.venv/bin:/home/vscode/.local/bin:/usr/local/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        libglib2.0-0 \
        libgomp1 \
        libgl1 \
        procps \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip uv

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m "${USERNAME}" \
    && mkdir -p /workspace/birdidex /opt/birdidex \
    && chown -R "${USERNAME}:${USERNAME}" /workspace /opt/birdidex

USER "${USERNAME}"
WORKDIR /workspace/birdidex

# Install dependencies before copying the full repo so Docker can cache the uv layer.
COPY --chown=${USERNAME}:${USERNAME} pyproject.toml uv.lock README.md ./
COPY --chown=${USERNAME}:${USERNAME} src ./src
RUN uv sync --all-groups --frozen

COPY --chown=${USERNAME}:${USERNAME} . .
RUN uv sync --all-groups --frozen \
    && uv run python -m ipykernel install \
        --user \
        --name birdidex-uv \
        --display-name "BIRDIDEX uv (.venv)"

EXPOSE 8888 8000

CMD ["bash", "-lc", "uv sync --all-groups --frozen && uv run python -m ipykernel install --user --name birdidex-uv --display-name 'BIRDIDEX uv (.venv)' && uv run jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.token='' --ServerApp.password=''"]
