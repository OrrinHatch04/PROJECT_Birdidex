"""End-to-end small-dataset collection pipeline.

One entry point (:func:`run_pipeline`) chains the deterministic steps used by
``birdidex images pipeline``:

1. deterministically select clean, non-ambiguous species using the master seed;
2. fetch eBird regional occurrence/season/locality priors per species (context only);
3. fetch iNaturalist open-license photo metadata and download accepted images only;
4. regenerate dataset reports and rebuild offline species profiles.

Every network dependency is injectable so the whole pipeline runs against tiny in-memory
fixtures in tests. Provider failures are caught per species so one bad response never
aborts the run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from birdidex.download import collect_images
from birdidex.paths import images_dir as default_images_dir
from birdidex.profiles import build_profiles, profiles_dir
from birdidex.providers import EbirdPrior, fetch_ebird_priors
from birdidex.seed import PURPOSE_SPECIES_SELECTION, derive_seed, select_species
from birdidex.taxonomy import TaxonClass, load_class_index

EbirdFetcher = Callable[[TaxonClass, str], "EbirdPrior | None"]

DEFAULT_SPECIES_LIMIT = 5
DEFAULT_PER_CLASS = 25
DEFAULT_TARGET_ACCEPTED = 10


def region_priors_path() -> Path:
    return profiles_dir() / "region_priors.jsonl"


@dataclass
class PipelineSummary:
    dry_run: bool
    species_selected: list[str]
    ebird_priors_written: int
    inat_metadata_records: int
    accepted_images: int
    rejected: int
    duplicates: int
    errors: list[str] = field(default_factory=list)
    records_path: str = ""
    priors_path: str = ""
    profiles_built: int = 0
    master_seed_used: bool = False


def _default_ebird_fetcher(
    *, api_key: str | None, http_client: Any | None, live: bool
) -> EbirdFetcher:
    taxonomy_map: dict[str, str] | None = None

    def fetch(taxon: TaxonClass, region: str) -> EbirdPrior | None:
        nonlocal taxonomy_map
        prior = fetch_ebird_priors(
            taxon,
            region=region,
            api_key=api_key,
            client=http_client,
            live=live,
            taxonomy_map=taxonomy_map,
        )
        return prior

    return fetch


def _write_priors(priors: list[EbirdPrior]) -> Path:
    path = region_priors_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for prior in priors:
            fh.write(json.dumps(prior.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    return path


def run_pipeline(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
    species_limit: int | None = DEFAULT_SPECIES_LIMIT,
    species_list: list[str] | None = None,
    all_species: bool = False,
    per_class: int = DEFAULT_PER_CLASS,
    target_accepted: int = DEFAULT_TARGET_ACCEPTED,
    region: str = "seq",
    max_edge: int = 1024,
    image_format: str = "jpg",
    quality: int = 85,
    keep_originals: bool = False,
    include_ambiguous: bool = False,
    live: bool = True,
    dry_run: bool = False,
    fetch_ebird: bool = True,
    ebird_api_key: str | None = None,
    master: int | None = None,
    http_client: Any | None = None,
    downloader: Callable[[str], bytes] | None = None,
    metadata_fetcher: Callable[[str, TaxonClass, int], list[Any]] | None = None,
    ebird_fetcher: EbirdFetcher | None = None,
) -> PipelineSummary:
    root = images_root or default_images_dir()
    classes = load_class_index(class_index_path)
    limit = None if all_species else species_limit
    selected = select_species(
        classes,
        limit=limit,
        species_list=species_list,
        include_ambiguous=include_ambiguous,
        master=master,
    )

    # Touch the derived seed so a misconfigured seed fails loudly before any network use.
    master_seed_used = False
    if species_list is None:
        derive_seed(PURPOSE_SPECIES_SELECTION, master=master)
        master_seed_used = True

    errors: list[str] = []

    # Step 1: eBird regional priors (context only, never blocks image collection).
    priors: list[EbirdPrior] = []
    if fetch_ebird:
        fetcher = ebird_fetcher or _default_ebird_fetcher(
            api_key=ebird_api_key, http_client=http_client, live=live
        )
        for taxon in selected:
            try:
                prior = fetcher(taxon, region)
            except Exception as exc:  # noqa: BLE001 - one bad species must not abort the run
                errors.append(f"ebird:{taxon.folder_name}: {type(exc).__name__}: {exc}")
                continue
            if prior is not None:
                priors.append(prior)
    priors_path = _write_priors(priors)

    # Step 2: iNaturalist metadata + accepted-image download for the selected species.
    only_classes = tuple(str(taxon.class_id) for taxon in selected)
    try:
        collect = collect_images(
            class_index_path=class_index_path,
            images_root=root,
            provider_names=("inaturalist",),
            per_class=per_class,
            target_accepted=target_accepted,
            include_ambiguous=include_ambiguous,
            only_classes=only_classes,
            max_edge=max_edge,
            image_format=image_format,
            quality=quality,
            keep_originals=keep_originals,
            dry_run=dry_run,
            http_client=http_client,
            downloader=downloader,
            metadata_fetcher=metadata_fetcher,
        )
    except Exception as exc:  # noqa: BLE001 - surface provider failure without a traceback
        errors.append(f"inaturalist: {type(exc).__name__}: {exc}")
        return PipelineSummary(
            dry_run=dry_run,
            species_selected=[taxon.folder_name for taxon in selected],
            ebird_priors_written=len(priors),
            inat_metadata_records=0,
            accepted_images=0,
            rejected=0,
            duplicates=0,
            errors=errors,
            priors_path=str(priors_path),
            master_seed_used=master_seed_used,
        )

    # Step 3: rebuild offline species profiles from the refreshed local data.
    profiles_built = 0
    try:
        profiles = build_profiles(class_index_path=class_index_path, images_root=root)
        profiles_built = len(profiles)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"profiles: {type(exc).__name__}: {exc}")

    inat_records = sum(r.accepted + r.rejected for r in collect.per_class)
    return PipelineSummary(
        dry_run=dry_run,
        species_selected=[taxon.folder_name for taxon in selected],
        ebird_priors_written=len(priors),
        inat_metadata_records=inat_records,
        accepted_images=collect.accepted,
        rejected=collect.rejected,
        duplicates=collect.skipped_duplicate,
        errors=errors,
        records_path=collect.records_path,
        priors_path=str(priors_path),
        profiles_built=profiles_built,
        master_seed_used=master_seed_used,
    )
