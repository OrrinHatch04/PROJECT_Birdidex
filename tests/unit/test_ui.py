"""FastAPI cyberdeck UI: health and basic routes (offline, temp DB)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="ui group not installed")

from bird_data.observation_log import ObservationLog  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    db = tmp_path / "obs.sqlite3"
    monkeypatch.setenv("BIRDIDEX_OBS_DB", str(db))
    log = ObservationLog(db)
    log.upsert_species("dacelo_novaeguineae", "Dacelo novaeguineae", "Laughing Kookaburra")
    log.log_observation(
        predicted_species_id="dacelo_novaeguineae",
        top5=[{"rank": 1, "species_id": "dacelo_novaeguineae", "score": 0.8}],
        confidence=0.8,
        model_version="v0-mock",
    )
    log.close()

    from bird_ui.server import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_health(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_latest(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["observation"]["predicted_species_id"] == "dacelo_novaeguineae"
    assert body["top5"][0]["species_id"] == "dacelo_novaeguineae"


def test_api_observations(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/observations")
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_api_species_found_and_404(client) -> None:  # type: ignore[no-untyped-def]
    ok = client.get("/api/species/dacelo_novaeguineae")
    assert ok.status_code == 200
    assert ok.json()["scientific_name"] == "Dacelo novaeguineae"
    assert client.get("/api/species/does_not_exist").status_code == 404


def test_html_pages_render(client) -> None:  # type: ignore[no-untyped-def]
    for path in ("/", "/observations", "/species/dacelo_novaeguineae"):
        r = client.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
