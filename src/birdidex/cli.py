"""Single BIRDIDEX CLI."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import typer
from rich.console import Console

from birdidex import __version__, infer, train
from birdidex.images import (
    class_folder_index_path,
    fetch_image_manifest,
    report_image_dataset,
    scaffold_image_dataset,
)
from birdidex.paths import default_class_index_path, images_dir, manifests_dir, repo_root
from birdidex.splits import create_splits
from birdidex.taxonomy import load_class_index

console = Console()
app = typer.Typer(help="BIRDIDEX local dataset and model scaffold.", no_args_is_help=True)
images_app = typer.Typer(help="Image dataset metadata scaffold.", no_args_is_help=True)
ui_app = typer.Typer(help="Local UI scaffold.", no_args_is_help=True)

app.add_typer(images_app, name="images")
app.add_typer(train.app, name="train")
app.add_typer(infer.app, name="infer")
app.add_typer(ui_app, name="ui")


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Print the BIRDIDEX version."),
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit(0)


@app.command()
def doctor() -> None:
    """Print local package and dataset diagnostics."""
    root = repo_root()
    class_index = default_class_index_path()
    console.print(f"repo: {root}")
    console.print(f"python: {sys.version.split()[0]}")
    console.print(f"class_index: {class_index}")
    if not class_index.exists():
        console.print("[red]class_index.json is missing[/]")
        raise typer.Exit(1)
    classes = load_class_index(class_index)
    ambiguous = sum(1 for taxon in classes if taxon.is_ambiguous)
    console.print(f"classes: {len(classes)}")
    console.print(f"ambiguous_taxa: {ambiguous}")
    console.print("provider/media default: metadata-only, no media retrieval")


@app.command("scan-candidates")
def scan_candidates(
    class_index: Path = typer.Option(
        default_class_index_path(), help="Canonical classifier class index JSON."
    ),
    output: Path = typer.Option(
        manifests_dir() / "roi_species_candidates.csv",
        help="Candidate CSV output path.",
    ),
) -> None:
    """Create a deterministic offline candidate table from the class index."""
    classes = load_class_index(class_index)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "class_id",
                "label",
                "common_name",
                "scientific_name",
                "observation_count",
                "clean_classifier_class",
                "status",
            ],
        )
        writer.writeheader()
        for taxon in classes:
            writer.writerow(
                {
                    "class_id": taxon.class_id,
                    "label": taxon.label,
                    "common_name": taxon.common_name,
                    "scientific_name": taxon.scientific_name or "",
                    "observation_count": taxon.observation_count,
                    "clean_classifier_class": str(taxon.clean_classifier_class).lower(),
                    "status": "review" if taxon.is_ambiguous else "candidate",
                }
            )
    console.print(f"wrote {len(classes)} candidates: {output}")


@images_app.command("scaffold")
def images_scaffold(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
) -> None:
    """Create class folders and class_folder_index.csv."""
    created = scaffold_image_dataset(class_index_path=class_index, images_root=root)
    console.print(f"scaffolded {len(created)} directories")
    console.print(f"class folder index: {class_folder_index_path(root)}")


@images_app.command("fetch-manifest")
def images_fetch_manifest(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
    live: bool = typer.Option(False, "--live", help="Make metadata-only provider requests."),
    include_ambiguous: bool = typer.Option(
        False,
        "--include-ambiguous",
        help="Include ambiguous taxa in provider metadata fetching.",
    ),
    limit_per_class: int = typer.Option(10, min=1, help="Maximum provider records per class."),
    providers: str = typer.Option(
        "inaturalist,ala,gbif,wikimedia_commons,openverse",
        help="Comma-separated provider names.",
    ),
) -> None:
    """Write metadata records without downloading images."""
    provider_names = tuple(item.strip() for item in providers.split(",") if item.strip())
    records = fetch_image_manifest(
        class_index_path=class_index,
        images_root=root,
        provider_names=provider_names,
        live=live,
        include_ambiguous=include_ambiguous,
        limit_per_class=limit_per_class,
    )
    mode = "live metadata" if live else "dry-run metadata"
    console.print(f"{mode}: wrote {len(records)} records under {root}")


@images_app.command("split")
def images_split(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
    train_ratio: float = typer.Option(0.75, "--train", help="Training split ratio."),
    val_ratio: float = typer.Option(0.15, "--val", help="Validation split ratio."),
    test_ratio: float = typer.Option(0.10, "--test", help="Test split ratio."),
    seed: int = typer.Option(42, help="Deterministic split seed."),
    copy: bool = typer.Option(False, "--copy", help="Copy files instead of symlinking."),
) -> None:
    """Create train/val/test folders from accepted local image records."""
    summary = create_splits(
        class_index_path=class_index,
        images_root=root,
        train=train_ratio,
        val=val_ratio,
        test=test_ratio,
        seed=seed,
        copy=copy,
    )
    console.print(
        f"split records: train={summary.train} val={summary.val} "
        f"test={summary.test} files={summary.linked_or_copied}"
    )


@images_app.command("report")
def images_report(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
) -> None:
    """Regenerate metadata reports."""
    summary = report_image_dataset(class_index_path=class_index, images_root=root)
    console.print(
        f"classes={summary['classes']} records={summary['records']} "
        f"accepted={summary['accepted_records']} extra_folders={summary['extra_class_folders']}"
    )


@ui_app.command("serve")
def ui_serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    """Start the local FastAPI UI."""
    import uvicorn

    uvicorn.run("birdidex.ui.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
