#!/usr/bin/env python3
"""run_demo_inference.py — Offline mock inference demo that populates the observation log.

No camera, no model, no network. For each species in the image manifest it synthesises a
deterministic frame, runs the mock detector + classifier (+ geotemporal reranker seeded
from the ROI candidates), and logs the result to the SQLite observation log so the UI has
data to display.

Usage:
    uv run python scripts/inference/run_demo_inference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pkg in ("bird_core", "bird_data", "bird_ml"):
    sys.path.insert(0, str(REPO_ROOT / "packages" / _pkg / "src"))
for _app in ("inference",):
    sys.path.insert(0, str(REPO_ROOT / "apps" / _app / "src"))

import numpy as np  # noqa: E402
from bird_data.csvio import load_manifest_csv  # noqa: E402
from bird_data.observation_log import ObservationLog  # noqa: E402
from bird_inference.classifier import MockClassifier  # noqa: E402
from bird_inference.detector import BoundingBox, MockDetector  # noqa: E402
from bird_inference.logging_sink import log_result  # noqa: E402
from bird_inference.pipeline import run_image_inference  # noqa: E402
from bird_inference.reranker import GeoTemporalReranker, priors_from_candidates_csv  # noqa: E402
from bird_ml.labels import LabelMap  # noqa: E402

MODEL_VERSION = "v0.0.0-mock"


def main() -> None:
    manifest = REPO_ROOT / "data/manifests/images_manifest.csv"
    if not manifest.exists():
        print("ERROR: run scripts/dataset/06_build_image_manifest.py first.")
        sys.exit(1)

    records = load_manifest_csv(manifest)
    names = sorted({r.scientific_name for r in records})
    from bird_data.taxonomy import build_species_key

    label_map = LabelMap.from_species([build_species_key(n) for n in names])
    common = {build_species_key(r.scientific_name): (r.common_name or "") for r in records}

    candidates = REPO_ROOT / "data/manifests/roi_species_candidates.csv"
    reranker = None
    if candidates.exists():
        reranker = GeoTemporalReranker(priors_from_candidates_csv(str(candidates)))

    db = REPO_ROOT / "data/db/observations.sqlite3"
    log = ObservationLog(db)
    log.log_model_version(
        MODEL_VERSION, backbone="mock", notes="demo inference, not a trained model"
    )
    for sid in label_map.species_ids:
        log.upsert_species(str(sid), str(sid).replace("_", " ").title(), common.get(str(sid)))
    session_id = log.start_session("demo-session", location="SEQ (synthetic)")

    classifier = MockClassifier(label_map)
    total = 0
    for i, rec in enumerate(records[:8]):
        rng = np.random.default_rng(abs(hash(rec.image_id)) % (2**32))
        frame = (rng.random((240, 240, 3)) * 255).astype(np.uint8)
        detector = MockDetector([BoundingBox(10, 10, 200, 200, 0.9)])
        result = run_image_inference(
            frame, image_id=str(rec.image_id), detector=detector, classifier=classifier,
            reranker=reranker, model_version=MODEL_VERSION, month=(i % 12) + 1,
        )
        ids = log_result(log, result, image_path=str(rec.photo_url or ""), session_id=session_id)
        total += len(ids)

    log.end_session(session_id)
    print(f"Logged {total} demo observation(s) -> {db}")
    print(f"Latest predicted: {log.latest_observation()['predicted_species_id']}")
    log.close()
    print("Start the UI with:  make run-ui-dev   (then visit http://127.0.0.1:8000/)")


if __name__ == "__main__":
    main()
