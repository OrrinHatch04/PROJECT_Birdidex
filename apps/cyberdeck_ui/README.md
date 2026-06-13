# Cyberdeck UI

Minimal FastAPI web UI for the Bird Pokedex cyberdeck. Displays species name, photo, ID, facts, and type/climate/habitat for the current detected bird.

## Status

Stub only — health endpoint and placeholder route only.

## Run (once wired up)

```bash
make sync-ui
uvicorn bird_ui.server:app --host 0.0.0.0 --port 8080
```
