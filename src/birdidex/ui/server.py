"""FastAPI server for the Bird Pokedex cyberdeck UI.

Minimal, offline-only. Serves a health check, the latest prediction, the observation log,
and species-card lookups — as both JSON APIs and basic HTML pages. Styling is deliberately
plain; the point is field usability, not polish.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bird_ui.data_access import open_log, species_card

_HERE = Path(__file__).parent

app = FastAPI(title="Bird Pokedex", version="0.1.0")
templates = Jinja2Templates(directory=str(_HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


def _parse_top5(obs: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not obs or not obs.get("top5_json"):
        return []
    try:
        return json.loads(obs["top5_json"])
    except (ValueError, TypeError):
        return []


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check — returns OK when the server is running."""
    return {"status": "ok"}


# ── JSON APIs ───────────────────────────────────────────────────────────────────
@app.get("/api/latest")
async def api_latest() -> JSONResponse:
    with open_log() as log:
        obs = log.latest_observation()
    return JSONResponse({"observation": obs, "top5": _parse_top5(obs)})


@app.get("/api/observations")
async def api_observations(limit: int = 50) -> JSONResponse:
    with open_log() as log:
        rows = log.list_observations(limit=limit)
    return JSONResponse({"count": len(rows), "observations": rows})


@app.get("/api/species/{species_id}")
async def api_species(species_id: str) -> JSONResponse:
    card = species_card(species_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"species not found: {species_id}")
    return JSONResponse(card)


# ── HTML pages ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    with open_log() as log:
        obs = log.latest_observation()
    return templates.TemplateResponse(
        request, "index.html", {"observation": obs, "top5": _parse_top5(obs)}
    )


@app.get("/observations", response_class=HTMLResponse)
async def observations_page(request: Request) -> HTMLResponse:
    with open_log() as log:
        rows = log.list_observations(limit=100)
    return templates.TemplateResponse(request, "observations.html", {"observations": rows})


@app.get("/species/{species_id}", response_class=HTMLResponse)
async def species_page(request: Request, species_id: str) -> HTMLResponse:
    card = species_card(species_id)
    return templates.TemplateResponse(
        request, "species.html", {"species_id": species_id, "card": card}
    )
