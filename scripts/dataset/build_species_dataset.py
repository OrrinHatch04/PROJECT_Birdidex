#!/usr/bin/env python3
"""build_species_dataset.py — build the BIRDIDEX species/region prototype from eBird CSVs.

Runs the whole prototype end to end:

1. discover + load raw eBird CSVs from ``--raw`` (default ``data/raw/ebird``),
2. build the stable species class index (source of truth for classifier class IDs),
3. build the per-region species presence table (the regional encounter priors),
4. build the prototype rarity scaffold (conservative placeholder — see ``bird_data.rarity``),
5. write JSON/CSV/Markdown outputs into ``--out`` (default ``data/processed/birddex``),
6. print a concise summary.

Usage::

    python scripts/dataset/build_species_dataset.py \
        --raw data/raw/ebird --out data/processed/birddex

This script lives under ``scripts/dataset/`` to match the existing numbered dataset
scripts (01_seed_species.py … 07_build_splits.py). It is intentionally the *only*
entry-point that writes ``class_index.json`` so there is one source of truth.

Next tasks
----------
* TODO(images): after image folders exist, add a step that joins folder->class_id.
* TODO(roi): add a broader-SEQ ROI comparison step feeding ``bird_data.rarity``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pkg in ("bird_core", "bird_data"):
    sys.path.insert(0, str(REPO_ROOT / "packages" / _pkg / "src"))

from bird_data.ebird_ingest import discover_ebird_csvs, load_all_ebird_observations  # noqa: E402
from bird_data.rarity import build_rarity_scaffold  # noqa: E402
from bird_data.region_presence import (  # noqa: E402
    build_region_species_presence,
    build_species_region_summary,
    write_region_presence_csv,
)
from bird_data.species_classes import (  # noqa: E402
    CLASS_ID_POLICY,
    CLASS_INDEX_VERSION,
    build_species_catalog,
    write_class_index,
    write_species_catalog_csv,
)


def _render_ingest_report(
    *,
    raw_dir: Path,
    source_files: list[str],
    n_obs: int,
    n_classes: int,
    n_regions: int,
    n_presence_rows: int,
) -> str:
    """Human-readable markdown explaining how classifier classes were generated."""
    lines = [
        "# BIRDIDEX species dataset — ingest report",
        "",
        "> **Prototype.** Classes and region priors are derived only from the eBird CSVs "
        "currently in `data/raw/ebird/`. Rarity scores are provisional and NOT a "
        "biological abundance model.",
        "",
        f"- Generated: `{datetime.now(UTC).isoformat(timespec='seconds')}`",
        f"- Raw dir: `{raw_dir}`",
        f"- Source CSVs: **{len(source_files)}**",
        f"- Observations loaded: **{n_obs}**",
        f"- Species classes: **{n_classes}**",
        f"- Regions: **{n_regions}**",
        f"- Region×species presence rows: **{n_presence_rows}**",
        "",
        "## How classifier classes are generated",
        "",
        "1. Each CSV row is normalised to canonical fields (`bird_data.ebird_ingest`).",
        "2. A combined `Species Name` is split into common + scientific name.",
        "3. Species are keyed on scientific name (fallback: common name) and de-duplicated.",
        f"4. `class_id` is assigned deterministically: `{CLASS_ID_POLICY}`.",
        "5. The label is a slug of the common name (e.g. `australian_brushturkey`),",
        "   extended to `common__genus_species` only on a collision.",
        "",
        "## Source files",
        "",
        *[f"- `{name}`" for name in source_files],
        "",
        "## Next steps",
        "",
        "- Map image folders onto `class_id` in `class_index.json`.",
        "- Add a broader SEQ ROI comparison to turn rarity into a real anomaly flag.",
        "- Start a supervised classifier baseline from these classes.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=REPO_ROOT / "data/raw/ebird",
                        help="Directory of raw eBird CSVs (default: data/raw/ebird)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data/processed/birddex",
                        help="Output directory (default: data/processed/birddex)")
    args = parser.parse_args()

    raw_dir: Path = args.raw
    out_dir: Path = args.out

    csvs = discover_ebird_csvs(raw_dir)
    if not csvs:
        print(
            "ERROR: no eBird CSV files found.\n"
            f"  Looked in: {raw_dir}\n"
            "  Put your raw eBird CSV exports there (see PLACE_RAW_CSVS_HERE.md) and re-run:\n"
            "    python scripts/dataset/build_species_dataset.py --raw data/raw/ebird "
            "--out data/processed/birddex",
            file=sys.stderr,
        )
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    observations = load_all_ebird_observations(raw_dir)

    species = build_species_catalog(observations)
    presence = build_region_species_presence(observations)
    summary = build_species_region_summary(presence)
    rarity = build_rarity_scaffold(presence)
    source_files = sorted(p.name for p in csvs)
    n_regions = len(summary["region_to_species"])

    # ── Write outputs ────────────────────────────────────────────────────────────────
    write_class_index(species, out_dir / "class_index.json")
    write_species_catalog_csv(species, out_dir / "species_catalog.csv")
    write_region_presence_csv(presence, out_dir / "region_species_presence.csv")
    (out_dir / "species_region_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "rarity_scaffold.json").write_text(
        json.dumps(rarity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    manifest = {
        "version": CLASS_INDEX_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "class_id_policy": CLASS_ID_POLICY,
        "raw_dir": str(raw_dir),
        "source_files": source_files,
        "observation_count": len(observations),
        "n_classes": len(species),
        "n_regions": n_regions,
        "n_presence_rows": len(presence),
        "outputs": [
            "class_index.json",
            "species_catalog.csv",
            "region_species_presence.csv",
            "species_region_summary.json",
            "rarity_scaffold.json",
            "dataset_manifest.json",
            "ingest_report.md",
        ],
        "notes": "Prototype. Rarity is provisional and based only on supplied CSVs.",
    }
    (out_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "ingest_report.md").write_text(
        _render_ingest_report(
            raw_dir=raw_dir,
            source_files=source_files,
            n_obs=len(observations),
            n_classes=len(species),
            n_regions=n_regions,
            n_presence_rows=len(presence),
        ),
        encoding="utf-8",
    )

    # ── Summary ──────────────────────────────────────────────────────────────────────
    print("BIRDIDEX species dataset built.")
    print(f"  CSVs:          {len(csvs)}")
    print(f"  Observations:  {len(observations)}")
    print(f"  Species/classes: {len(species)}")
    print(f"  Regions:       {n_regions}")
    print(f"  Presence rows: {len(presence)}")
    print(f"  Output dir:    {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
