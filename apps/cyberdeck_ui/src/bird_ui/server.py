"""FastAPI server for the Bird Pokedex cyberdeck UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_HERE = Path(__file__).parent

app = FastAPI(title="Bird Pokedex", version="0.1.0")
templates = Jinja2Templates(directory=str(_HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check — returns OK when the server is running."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Main display page — shows current detected species.

    TODO: Accept species_id query param and look up from SpeciesDB.
    TODO: Render real species name, photo, facts, type/climate/habitat.
    """
    return templates.TemplateResponse("index.html", {"request": request, "species": None})
