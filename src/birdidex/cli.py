"""Single BIRDIDEX CLI."""

from __future__ import annotations

import csv
import hashlib
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
providers_app = typer.Typer(
    help="Provider auth diagnostics and dry-runs (eBird priors, iNaturalist photos).",
    no_args_is_help=True,
)
bigbird_app = typer.Typer(
    help="Big Bird UAV dataset audit and auxiliary import.", no_args_is_help=True
)
profiles_app = typer.Typer(help="Offline species profiles.", no_args_is_help=True)
observations_app = typer.Typer(help="Cyberdeck observation schema.", no_args_is_help=True)
audit_app = typer.Typer(help="Dataset coverage audit.", no_args_is_help=True)
ui_app = typer.Typer(help="Local UI scaffold.", no_args_is_help=True)

app.add_typer(images_app, name="images")
app.add_typer(providers_app, name="providers")
app.add_typer(bigbird_app, name="bigbird")
app.add_typer(profiles_app, name="profiles")
app.add_typer(observations_app, name="observations")
app.add_typer(audit_app, name="audit")
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


@images_app.command("fetch")
def images_fetch(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
    all_providers: bool = typer.Option(
        False, "--all", help="Use every configured provider (default when no --provider given)."
    ),
    provider: list[str] = typer.Option(
        [], "--provider", help="Restrict to a provider (repeatable)."
    ),
    per_class: int = typer.Option(250, "--per-class", min=1, help="Candidates fetched per class."),
    target_accepted: int = typer.Option(
        200, "--target-accepted", min=1, help="Accepted images to keep per class."
    ),
    max_edge: int = typer.Option(1024, "--max-edge", min=64, help="Stored image longest edge."),
    image_format: str = typer.Option("jpg", "--format", help="Stored image format."),
    quality: int = typer.Option(85, "--quality", min=1, max=100, help="Stored JPEG quality."),
    keep_originals: bool = typer.Option(
        False, "--keep-originals", help="Also store full-resolution originals."
    ),
    include_ambiguous: bool = typer.Option(
        False, "--include-ambiguous", help="Include ambiguous taxa (off by default)."
    ),
    only: list[str] = typer.Option(
        [], "--class", help="Limit to class id/label/folder (repeatable)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Fetch and validate metadata only; download nothing."
    ),
) -> None:
    """Download open-license images for clean classifier classes (opt-in network use)."""
    from birdidex.download import collect_images

    if provider:
        provider_names = tuple(provider)
    else:
        from birdidex.providers import PROVIDERS

        provider_names = PROVIDERS
    summary = collect_images(
        class_index_path=class_index,
        images_root=root,
        provider_names=provider_names,
        per_class=per_class,
        target_accepted=target_accepted,
        include_ambiguous=include_ambiguous,
        only_classes=tuple(only) or None,
        max_edge=max_edge,
        image_format=image_format,
        quality=quality,
        keep_originals=keep_originals,
        dry_run=dry_run,
    )
    mode = "dry-run" if summary.dry_run else "download"
    console.print(
        f"{mode}: classes={summary.classes_processed} accepted={summary.accepted} "
        f"rejected={summary.rejected} duplicates={summary.skipped_duplicate}"
    )
    console.print(f"records: {summary.records_path}")


@images_app.command("split")
def images_split(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
    train_ratio: float = typer.Option(0.75, "--train", help="Training split ratio."),
    val_ratio: float = typer.Option(0.15, "--val", help="Validation split ratio."),
    test_ratio: float = typer.Option(0.10, "--test", help="Test split ratio."),
    seed: int = typer.Option(42, help="Deterministic split seed."),
    seed_env: str | None = typer.Option(
        None,
        "--seed-env",
        help="Read the split seed from an environment/local-runtime variable.",
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy files instead of symlinking."),
) -> None:
    """Create train/val/test folders from accepted local image records."""
    resolved_seed = _resolve_cli_seed(seed, seed_env)
    summary = create_splits(
        class_index_path=class_index,
        images_root=root,
        train=train_ratio,
        val=val_ratio,
        test=test_ratio,
        seed=resolved_seed,
        copy=copy,
    )
    console.print(
        f"split records: train={summary.train} val={summary.val} "
        f"test={summary.test} files={summary.linked_or_copied}"
    )


def _resolve_cli_seed(default_seed: int, seed_env: str | None) -> int:
    if not seed_env:
        return default_seed
    from birdidex.secrets import get_secret

    value = get_secret(seed_env)
    if not value:
        console.print(f"[red]{seed_env} is not set in the environment or local runtime config[/]")
        raise typer.Exit(1)
    try:
        return int(value.strip())
    except ValueError:
        digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()
        return int(digest, 16) % (2**31)


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


@providers_app.command("doctor")
def providers_doctor(
    provider: str = typer.Option(
        None, "--provider", help="Limit to 'ebird' or 'inaturalist' (default: both)."
    ),
) -> None:
    """Report provider auth configuration without printing secrets or making live calls."""
    from birdidex.secrets import (
        get_ebird_api_key,
        get_inaturalist_access_token,
        master_seed_configured,
        redact,
    )

    provider = (provider or "").strip().lower()
    if provider and provider not in {"ebird", "inaturalist"}:
        console.print(f"[red]unknown provider: {provider}[/]")
        raise typer.Exit(2)

    if provider in ("", "ebird"):
        key = get_ebird_api_key()
        status = "configured" if key else "not configured (dry-run unavailable)"
        console.print("provider: ebird")
        console.print("  auth: X-eBirdApiToken header")
        console.print(f"  EBIRD_API_KEY: {redact(key)} ({status})")
        console.print("  role: regional occurrence / season / locality priors")

    if provider in ("", "inaturalist"):
        token = get_inaturalist_access_token()
        status = "configured" if token else "using public endpoints (no token)"
        console.print("provider: inaturalist")
        console.print("  auth: optional Bearer token; public endpoints need none")
        console.print(f"  INATURALIST_ACCESS_TOKEN: {redact(token)} ({status})")
        console.print("  role: open-license photo metadata and image downloads")

    seed_status = "configured" if master_seed_configured() else "MISSING"
    console.print(f"master seed (BIRDIDEX_MASTER_SEED / seed file): {seed_status}")


@providers_app.command("dry-run")
def providers_dry_run(
    provider: str = typer.Option(..., "--provider", help="'ebird' or 'inaturalist'."),
    species: str = typer.Option(..., "--species", help="Common/scientific name from class_index."),
    limit: int = typer.Option(5, "--limit", min=1, help="Max iNaturalist photo records."),
    region: str = typer.Option("seq", "--region", help="eBird region code or alias (e.g. seq)."),
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
) -> None:
    """Validate provider auth and return one species' normalized metadata (no downloads)."""
    from birdidex.taxonomy import find_taxon

    provider_name = provider.strip().lower()
    classes = load_class_index(class_index)
    taxon = find_taxon(classes, species)
    if taxon is None:
        console.print(f"[red]species not found in class_index: {species}[/]")
        raise typer.Exit(1)

    if provider_name == "ebird":
        _dry_run_ebird(taxon, region=region)
    elif provider_name == "inaturalist":
        _dry_run_inaturalist(taxon, limit=limit)
    else:
        console.print(f"[red]unknown provider: {provider}[/]")
        raise typer.Exit(2)


def _dry_run_ebird(taxon: object, *, region: str) -> None:
    from birdidex.providers import fetch_ebird_priors
    from birdidex.secrets import MissingSecretError, get_ebird_api_key

    key = get_ebird_api_key()
    if not key:
        console.print("[red]EBIRD_API_KEY is not set. Add it to .env.local.[/]")
        raise typer.Exit(1)
    try:
        prior = fetch_ebird_priors(taxon, region=region, api_key=key, live=True)  # type: ignore[arg-type]
    except MissingSecretError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001 - report provider/network failure cleanly
        console.print(f"[red]eBird request failed: {type(exc).__name__}: {exc}[/]")
        raise typer.Exit(1) from exc
    assert prior is not None
    console.print(f"eBird prior for {prior.common_name} ({prior.scientific_name})")
    console.print(f"  species_code: {prior.species_code}")
    console.print(f"  region: {prior.region} -> {prior.region_resolved}")
    console.print(
        f"  observations: {prior.total_observations} (individuals {prior.total_individuals})"
    )
    console.print(f"  distinct_localities: {prior.distinct_localities}")
    console.print(f"  month_histogram: {prior.month_histogram}")
    for loc in prior.top_localities[:5]:
        console.print(f"    - {loc['loc_name']}: {loc['observations']}")


def _dry_run_inaturalist(taxon: object, *, limit: int) -> None:
    from birdidex.providers import fetch_inaturalist, validate_metadata_records
    from birdidex.secrets import get_inaturalist_access_token

    token = get_inaturalist_access_token()
    try:
        records = fetch_inaturalist(taxon, live=True, limit=limit, access_token=token)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]iNaturalist request failed: {type(exc).__name__}: {exc}[/]")
        raise typer.Exit(1) from exc
    validated = validate_metadata_records(records, class_lookup={taxon.class_id: taxon})  # type: ignore[attr-defined]
    accepted = [r for r in validated if r.status == "accepted"][:limit]
    console.print(f"iNaturalist open-license photos for {species_label(taxon)}: {len(accepted)}")
    for record in accepted:
        console.print(
            f"  - {record.license_code} | {record.image_url} | {record.attribution or ''}"
        )
    if not accepted:
        console.print("  (no open-license photos returned)")


def species_label(taxon: object) -> str:
    return f"{getattr(taxon, 'common_name', '')} ({getattr(taxon, 'scientific_name', '') or ''})"


@images_app.command("fetch-metadata")
def images_fetch_metadata(
    provider: str = typer.Option(..., "--provider", help="'inaturalist' or 'ebird'."),
    species: str = typer.Option(
        None, "--species", help="Single species; omit to use deterministic clean-species set."
    ),
    region: str = typer.Option("seq", "--region", help="eBird region code/alias."),
    limit: int = typer.Option(25, "--limit", min=1, help="Records per species."),
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
) -> None:
    """Fetch provider metadata only — no image files are downloaded."""
    from birdidex.taxonomy import find_taxon

    provider_name = provider.strip().lower()
    if provider_name == "ebird":
        _fetch_metadata_ebird(species, region=region, limit=limit, class_index=class_index)
        return
    if provider_name != "inaturalist":
        console.print(f"[red]unknown provider: {provider}[/]")
        raise typer.Exit(2)

    from birdidex.download import collect_images

    only: tuple[str, ...] | None = None
    if species:
        taxon = find_taxon(load_class_index(class_index), species)
        if taxon is None:
            console.print(f"[red]species not found in class_index: {species}[/]")
            raise typer.Exit(1)
        only = (str(taxon.class_id),)

    summary = collect_images(
        class_index_path=class_index,
        images_root=root,
        provider_names=("inaturalist",),
        per_class=limit,
        target_accepted=limit,
        only_classes=only,
        dry_run=True,
    )
    console.print(
        f"iNaturalist metadata: classes={summary.classes_processed} "
        f"candidates={summary.accepted} rejected={summary.rejected}"
    )
    console.print(f"records: {summary.records_path}")


def _fetch_metadata_ebird(
    species: str | None, *, region: str, limit: int, class_index: Path
) -> None:
    import json as _json

    from birdidex.pipeline import region_priors_path
    from birdidex.providers import fetch_ebird_priors
    from birdidex.secrets import get_ebird_api_key
    from birdidex.seed import select_species
    from birdidex.taxonomy import find_taxon

    key = get_ebird_api_key()
    if not key:
        console.print("[red]EBIRD_API_KEY is not set. Add it to .env.local.[/]")
        raise typer.Exit(1)

    classes = load_class_index(class_index)
    if species:
        taxon = find_taxon(classes, species)
        if taxon is None:
            console.print(f"[red]species not found in class_index: {species}[/]")
            raise typer.Exit(1)
        targets = [taxon]
    else:
        targets = select_species(classes, limit=limit)

    priors = []
    taxonomy_map: dict[str, str] | None = None
    for taxon in targets:
        try:
            prior = fetch_ebird_priors(
                taxon, region=region, api_key=key, live=True, taxonomy_map=taxonomy_map
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]skip {taxon.folder_name}: {type(exc).__name__}: {exc}[/]")
            continue
        if prior is not None:
            priors.append(prior)

    path = region_priors_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for prior in priors:
            fh.write(_json.dumps(prior.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    console.print(f"eBird priors: species={len(priors)} region={region}")
    console.print(f"priors: {path}")


@images_app.command("download")
def images_download(
    species: str = typer.Option(..., "--species", help="Species to download (iNaturalist)."),
    target_accepted: int = typer.Option(
        150, "--target-accepted", min=1, help="Accepted images to keep."
    ),
    per_class: int = typer.Option(
        250, "--per-class", min=1, help="Candidate metadata records to consider."
    ),
    max_edge: int = typer.Option(1024, "--max-edge", min=64, help="Stored longest edge."),
    image_format: str = typer.Option("jpg", "--format", help="Stored image format."),
    quality: int = typer.Option(85, "--quality", min=1, max=100, help="Stored JPEG quality."),
    keep_originals: bool = typer.Option(
        False, "--keep-originals", help="Also store full-resolution originals."
    ),
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
) -> None:
    """Download accepted open-license iNaturalist images for one species."""
    from birdidex.download import collect_images
    from birdidex.taxonomy import find_taxon

    taxon = find_taxon(load_class_index(class_index), species)
    if taxon is None:
        console.print(f"[red]species not found in class_index: {species}[/]")
        raise typer.Exit(1)
    if taxon.is_ambiguous:
        console.print(f"[red]{species} is an ambiguous taxon and is excluded from download.[/]")
        raise typer.Exit(1)

    summary = collect_images(
        class_index_path=class_index,
        images_root=root,
        provider_names=("inaturalist",),
        per_class=per_class,
        target_accepted=target_accepted,
        only_classes=(str(taxon.class_id),),
        max_edge=max_edge,
        image_format=image_format,
        quality=quality,
        keep_originals=keep_originals,
    )
    console.print(
        f"download: accepted={summary.accepted} rejected={summary.rejected} "
        f"duplicates={summary.skipped_duplicate}"
    )
    console.print(f"records: {summary.records_path}")


@images_app.command("pipeline")
def images_pipeline(
    species_limit: int = typer.Option(
        5, "--species-limit", min=1, help="Deterministic clean-species count."
    ),
    all_species: bool = typer.Option(False, "--all", help="Process every clean species."),
    species_list: str = typer.Option(
        None, "--species-list", help="Comma-separated species names (overrides selection)."
    ),
    per_class: int = typer.Option(25, "--per-class", min=1, help="Candidates per class."),
    target_accepted: int = typer.Option(
        10, "--target-accepted", min=1, help="Accepted images per class."
    ),
    region: str = typer.Option("seq", "--region", help="eBird region code/alias."),
    max_edge: int = typer.Option(1024, "--max-edge", min=64, help="Stored longest edge."),
    image_format: str = typer.Option("jpg", "--format", help="Stored image format."),
    quality: int = typer.Option(85, "--quality", min=1, max=100, help="Stored JPEG quality."),
    keep_originals: bool = typer.Option(False, "--keep-originals", help="Keep originals."),
    no_ebird: bool = typer.Option(False, "--no-ebird", help="Skip eBird priors."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate metadata; download nothing."),
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
) -> None:
    """Run the deterministic small-dataset pipeline (eBird priors + iNaturalist images)."""
    from birdidex.pipeline import run_pipeline
    from birdidex.secrets import MissingSecretError, get_ebird_api_key

    names = (
        [item.strip() for item in species_list.split(",") if item.strip()] if species_list else None
    )
    try:
        summary = run_pipeline(
            class_index_path=class_index,
            images_root=root,
            species_limit=species_limit,
            species_list=names,
            all_species=all_species,
            per_class=per_class,
            target_accepted=target_accepted,
            region=region,
            max_edge=max_edge,
            image_format=image_format,
            quality=quality,
            keep_originals=keep_originals,
            dry_run=dry_run,
            fetch_ebird=not no_ebird,
            ebird_api_key=get_ebird_api_key(),
        )
    except MissingSecretError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    mode = "dry-run" if summary.dry_run else "pipeline"
    console.print(
        f"{mode}: species={len(summary.species_selected)} "
        f"ebird_priors={summary.ebird_priors_written} "
        f"inat_records={summary.inat_metadata_records} "
        f"accepted={summary.accepted_images} rejected={summary.rejected} "
        f"duplicates={summary.duplicates} profiles={summary.profiles_built}"
    )
    console.print(f"records: {summary.records_path}")
    console.print(f"priors: {summary.priors_path}")
    for err in summary.errors:
        console.print(f"[yellow]  provider issue: {err}[/]")


@bigbird_app.command("audit")
def bigbird_audit(
    zip: Path = typer.Option(..., "--zip", help="Path to the Big Bird zip archive."),
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
) -> None:
    """Inspect the Big Bird zip and report overlap without extracting it."""
    from birdidex.bigbird import audit_zip, write_audit_reports

    if not zip.exists():
        console.print(f"[red]zip not found: {zip}[/]")
        raise typer.Exit(1)
    audit = audit_zip(zip, class_index_path=class_index)
    json_path, csv_path = write_audit_reports(audit)
    console.print(
        f"zip_size={audit.zip_size_bytes} files={audit.file_count} images={audit.image_count} "
        f"species={len(audit.species_names)} overlap={len(audit.overlap)}"
    )
    console.print(f"audit: {json_path}")
    console.print(f"overlap: {csv_path}")
    for step in audit.recommended_import_plan:
        console.print(f"  - {step}")


@bigbird_app.command("import")
def bigbird_import(
    zip: Path = typer.Option(..., "--zip", help="Path to the Big Bird zip archive."),
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    mode: str = typer.Option("auxiliary", "--mode", help="Import mode (auxiliary only)."),
    include_auxiliary: bool = typer.Option(
        False, "--include-auxiliary", help="Mark auxiliary frames for classifier splits."
    ),
    limit_per_class: int = typer.Option(
        0, "--limit-per-class", min=0, help="Cap frames per class (0 = no cap)."
    ),
) -> None:
    """Extract overlapping species-level frames into the auxiliary dataset area."""
    from birdidex.bigbird import import_zip

    if not zip.exists():
        console.print(f"[red]zip not found: {zip}[/]")
        raise typer.Exit(1)
    if mode != "auxiliary":
        console.print("[red]only --mode auxiliary is supported[/]")
        raise typer.Exit(1)
    summary = import_zip(
        zip,
        class_index_path=class_index,
        mode=mode,
        include_auxiliary=include_auxiliary,
        limit_per_class=limit_per_class or None,
    )
    console.print(
        f"imported images={summary.extracted_images} classes={summary.classes_touched} "
        f"in_splits={summary.included_in_splits}"
    )
    console.print(f"records: {summary.records_path}")


@profiles_app.command("build")
def profiles_build(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
) -> None:
    """Build offline species profiles from local structured data."""
    from birdidex.profiles import build_profiles, species_profiles_path

    profiles = build_profiles(class_index_path=class_index, images_root=root)
    console.print(f"built {len(profiles)} profiles")
    console.print(f"combined: {species_profiles_path()}")


@observations_app.command("schema")
def observations_schema(
    output: Path = typer.Option(
        None, "--output", help="Write the JSON schema to a file instead of stdout."
    ),
) -> None:
    """Print (or write) the cyberdeck observation JSON schema."""
    from birdidex.observations import observation_schema_json

    payload = observation_schema_json()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        console.print(f"wrote observation schema: {output}")
    else:
        console.print(payload)


@audit_app.command("dataset")
def audit_dataset(
    class_index: Path = typer.Option(default_class_index_path(), help="Class index JSON."),
    root: Path = typer.Option(images_dir(), help="Image dataset root."),
) -> None:
    """Audit dataset coverage and write HTML/JSON/CSV reports."""
    from birdidex.audit import (
        dataset_audit_html_path,
        dataset_audit_json_path,
        run_dataset_audit,
        species_coverage_csv_path,
    )

    result = run_dataset_audit(class_index_path=class_index, images_root=root)
    console.print(
        f"classes={result['n_classes']} accepted={result['n_accepted']} "
        f"weak={len(result['weak_coverage_classes'])} "
        f"no_rep={len(result['classes_without_representative_image'])}"
    )
    console.print(f"json: {dataset_audit_json_path()}")
    console.print(f"html: {dataset_audit_html_path()}")
    console.print(f"csv: {species_coverage_csv_path()}")


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
