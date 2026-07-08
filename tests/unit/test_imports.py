from __future__ import annotations

import importlib


def test_birdidex_import_surface() -> None:
    modules = [
        "birdidex",
        "birdidex.cli",
        "birdidex.paths",
        "birdidex.settings",
        "birdidex.taxonomy",
        "birdidex.roi",
        "birdidex.providers",
        "birdidex.secrets",
        "birdidex.seed",
        "birdidex.pipeline",
        "birdidex.images",
        "birdidex.download",
        "birdidex.bigbird",
        "birdidex.profiles",
        "birdidex.observations",
        "birdidex.audit",
        "birdidex.splits",
        "birdidex.train",
        "birdidex.infer",
        "birdidex.db",
        "birdidex.ui",
    ]

    for module in modules:
        importlib.import_module(module)
