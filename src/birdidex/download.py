"""Opt-in real image collection engine.

This is the only place BIRDIDEX downloads media. Nothing here runs during tests or
normal setup: the ``birdidex images fetch`` command is the single entry point and it
makes network requests only when invoked. Everything is metadata-first — a candidate is
downloaded only after its provider metadata passes open-license and taxonomy checks.

The engine is deliberately injectable. ``metadata_fetcher`` supplies candidate records
and ``downloader`` supplies image bytes, so tests exercise the full pipeline with tiny
in-memory fixtures and never touch the network.
"""

from __future__ import annotations

import hashlib
import io
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from birdidex.images import (
    image_records_path,
    read_metadata_jsonl,
    write_dataset_manifest,
    write_metadata_jsonl,
    write_reports,
)
from birdidex.paths import images_dir as default_images_dir
from birdidex.paths import repo_root
from birdidex.providers import (
    PROVIDERS,
    ImageMetadataRecord,
    validate_metadata_records,
)
from birdidex.taxonomy import (
    TaxonClass,
    classes_by_id,
    clean_classifier_classes,
    load_class_index,
)

# Fallback providers are queried only if the higher-quality providers have not reached
# the per-class accepted target.
FALLBACK_PROVIDERS: tuple[str, ...] = ("openverse",)
PRIMARY_PROVIDERS: tuple[str, ...] = tuple(p for p in PROVIDERS if p not in FALLBACK_PROVIDERS)

PHOTO_FORMATS: frozenset[str] = frozenset({"JPEG", "JPG", "PNG", "WEBP", "TIFF", "MPO"})
MIN_STORED_EDGE = 128
DEFAULT_MAX_EDGE = 1024
DEFAULT_FORMAT = "jpg"
DEFAULT_QUALITY = 85
DEFAULT_PER_CLASS = 250
DEFAULT_TARGET_ACCEPTED = 200
PHASH_MAX_DISTANCE = 4

Downloader = Callable[[str], bytes]
MetadataFetcher = Callable[[str, TaxonClass, int], list[ImageMetadataRecord]]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ImageRejected(Exception):
    """Raised when downloaded bytes fail a validation gate.

    ``reason`` is one of the documented rejection codes and is stored on the record.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    sha256: str
    phash: str | None
    original_width: int
    original_height: int
    stored_width: int
    stored_height: int
    stored_format: str
    stored_quality: int


def process_image_bytes(
    data: bytes,
    *,
    max_edge: int = DEFAULT_MAX_EDGE,
    image_format: str = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY,
) -> ProcessedImage:
    """Validate and normalize raw image bytes.

    Rejects corrupt, animated, non-photo, or very small media. Resizes so the longest
    edge is at most ``max_edge`` (never upscales) and re-encodes to ``image_format`` at
    ``quality``. Model input sizing is intentionally *not* applied here.
    """
    from PIL import Image

    try:
        import imagehash
    except ImportError:  # pragma: no cover - optional at collection time
        imagehash = None  # type: ignore[assignment]

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # noqa: BLE001 - any decode failure is a corrupt image
        raise ImageRejected("corrupt_image") from exc

    if getattr(img, "is_animated", False) or getattr(img, "n_frames", 1) > 1:
        raise ImageRejected("animated_file")

    source_format = (img.format or "").upper()
    if source_format and source_format not in PHOTO_FORMATS:
        raise ImageRejected("non_photo_media")

    original_width, original_height = img.size
    if min(original_width, original_height) < MIN_STORED_EDGE:
        raise ImageRejected("image_too_small")

    rgb = img.convert("RGB")
    phash = str(imagehash.phash(rgb)) if imagehash is not None else None

    longest = max(original_width, original_height)
    if longest > max_edge:
        scale = max_edge / longest
        rgb = rgb.resize(
            (max(1, round(original_width * scale)), max(1, round(original_height * scale))),
            Image.Resampling.LANCZOS,
        )

    save_format = "JPEG" if image_format.lower() in {"jpg", "jpeg"} else image_format.upper()
    buffer = io.BytesIO()
    save_kwargs: dict[str, Any] = {}
    if save_format == "JPEG":
        save_kwargs = {"quality": quality, "optimize": True}
    rgb.save(buffer, format=save_format, **save_kwargs)
    stored = buffer.getvalue()

    return ProcessedImage(
        data=stored,
        sha256=hashlib.sha256(stored).hexdigest(),
        phash=phash,
        original_width=original_width,
        original_height=original_height,
        stored_width=rgb.width,
        stored_height=rgb.height,
        stored_format=image_format.lower(),
        stored_quality=quality if save_format == "JPEG" else 0,
    )


def _phash_distance(left: str | None, right: str | None) -> int | None:
    if not left or not right or len(left) != len(right):
        return None
    try:
        return bin(int(left, 16) ^ int(right, 16)).count("1")
    except ValueError:
        return None


def _default_metadata_fetcher(
    http_client: Any | None,
) -> MetadataFetcher:
    from birdidex.providers import FETCHERS

    def fetch(provider_name: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        fetcher = FETCHERS[provider_name]
        return fetcher(taxon, client=http_client, live=True, limit=limit)

    return fetch


def _default_downloader() -> Downloader:
    import httpx

    client = httpx.Client(timeout=60, follow_redirects=True)

    def download(url: str) -> bytes:
        response = client.get(url)
        response.raise_for_status()
        return response.content

    return download


def _stored_filename(record: ImageMetadataRecord, image_format: str) -> str:
    stem = f"{record.provider}_{record.provider_record_id}"
    stem = stem.replace("/", "_").replace(":", "_").replace(" ", "_")
    ext = "jpg" if image_format.lower() in {"jpg", "jpeg"} else image_format.lower()
    return f"{stem}.{ext}"


@dataclass
class ClassCollectResult:
    class_id: int
    label: str
    accepted: int = 0
    rejected: int = 0
    skipped_duplicate: int = 0
    per_provider: Counter[str] = field(default_factory=Counter)


@dataclass
class CollectSummary:
    dry_run: bool
    classes_processed: int
    accepted: int
    rejected: int
    skipped_duplicate: int
    per_class: list[ClassCollectResult]
    records_path: str


def _select_classes(
    classes: list[TaxonClass],
    *,
    include_ambiguous: bool,
    only: tuple[str, ...] | None,
) -> list[TaxonClass]:
    selected = classes if include_ambiguous else clean_classifier_classes(classes)
    if not only:
        return selected
    wanted = {value.strip().lower() for value in only if value.strip()}
    filtered: list[TaxonClass] = []
    for taxon in selected:
        keys = {taxon.label.lower(), taxon.folder_name.lower(), str(taxon.class_id)}
        if keys & wanted:
            filtered.append(taxon)
    return filtered


def _provider_order(provider_names: tuple[str, ...]) -> tuple[list[str], list[str]]:
    primary = [name for name in provider_names if name not in FALLBACK_PROVIDERS]
    fallback = [name for name in provider_names if name in FALLBACK_PROVIDERS]
    return primary, fallback


def collect_images(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
    provider_names: tuple[str, ...] = PROVIDERS,
    per_class: int = DEFAULT_PER_CLASS,
    target_accepted: int = DEFAULT_TARGET_ACCEPTED,
    include_ambiguous: bool = False,
    only_classes: tuple[str, ...] | None = None,
    max_edge: int = DEFAULT_MAX_EDGE,
    image_format: str = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY,
    keep_originals: bool = False,
    dry_run: bool = False,
    http_client: Any | None = None,
    downloader: Downloader | None = None,
    metadata_fetcher: MetadataFetcher | None = None,
) -> CollectSummary:
    """Collect open-license images for clean classifier classes.

    Ambiguous taxa are skipped unless ``include_ambiguous`` is set. For each class the
    primary providers are queried first, and fallback providers (Openverse) are used
    only if the accepted target has not been reached. Downloaded bytes are validated and
    normalized; sha256 and perceptual-hash duplicates are quarantined rather than stored.

    With ``dry_run`` no bytes are downloaded: metadata candidates are validated and
    written so a review pass can happen before spending bandwidth.
    """
    root = images_root or default_images_dir()
    classes = load_class_index(class_index_path)
    lookup = classes_by_id(classes)
    selected = _select_classes(classes, include_ambiguous=include_ambiguous, only=only_classes)
    primary, fallback = _provider_order(provider_names)

    fetch_metadata = metadata_fetcher or _default_metadata_fetcher(http_client)
    fetch_bytes: Downloader | None = None if dry_run else downloader or _default_downloader()

    existing = {
        (record.provider, record.provider_record_id): record
        for record in read_metadata_jsonl(image_records_path(root))
    }

    new_records: list[ImageMetadataRecord] = []
    per_class_results: list[ClassCollectResult] = []

    for taxon in selected:
        result = ClassCollectResult(class_id=taxon.class_id, label=taxon.label)
        seen_provider_keys: set[tuple[str, str]] = set()
        seen_sha: set[str] = set()
        seen_phash: list[str] = []

        for provider_name in [*primary, *fallback]:
            if provider_name in fallback and result.accepted >= target_accepted:
                break
            if result.accepted >= target_accepted:
                break

            candidates = fetch_metadata(provider_name, taxon, per_class)
            validated = validate_metadata_records(candidates, class_lookup=lookup)

            for record in validated:
                key = (record.provider, record.provider_record_id)
                if key in seen_provider_keys:
                    continue
                seen_provider_keys.add(key)

                if record.status != "accepted":
                    result.rejected += 1
                    new_records.append(record)
                    continue

                if result.accepted >= target_accepted:
                    # Enough accepted; keep the metadata as a reviewable candidate.
                    new_records.append(replace(record, status="review"))
                    continue

                if dry_run or fetch_bytes is None:
                    new_records.append(replace(record, status="candidate"))
                    result.per_provider[provider_name] += 1
                    result.accepted += 1
                    continue

                stored = _store_candidate(
                    record,
                    taxon=taxon,
                    root=root,
                    fetch_bytes=fetch_bytes,
                    max_edge=max_edge,
                    image_format=image_format,
                    quality=quality,
                    keep_originals=keep_originals,
                    seen_sha=seen_sha,
                    seen_phash=seen_phash,
                    result=result,
                )
                new_records.append(stored)

        per_class_results.append(result)

    merged = _merge_records(existing, new_records)
    write_metadata_jsonl(merged, image_records_path(root))
    write_dataset_manifest(
        merged,
        classes,
        (root / "image_dataset_manifest.json"),
        live=not dry_run,
    )
    write_reports(merged, classes, images_root=root)

    return CollectSummary(
        dry_run=dry_run,
        classes_processed=len(selected),
        accepted=sum(r.accepted for r in per_class_results),
        rejected=sum(r.rejected for r in per_class_results),
        skipped_duplicate=sum(r.skipped_duplicate for r in per_class_results),
        per_class=per_class_results,
        records_path=str(image_records_path(root)),
    )


def _store_candidate(
    record: ImageMetadataRecord,
    *,
    taxon: TaxonClass,
    root: Path,
    fetch_bytes: Downloader,
    max_edge: int,
    image_format: str,
    quality: int,
    keep_originals: bool,
    seen_sha: set[str],
    seen_phash: list[str],
    result: ClassCollectResult,
) -> ImageMetadataRecord:
    assert record.image_url is not None
    try:
        raw = fetch_bytes(record.image_url)
    except Exception:  # noqa: BLE001 - network/transport failures quarantine
        result.rejected += 1
        return replace(
            record,
            status="quarantine",
            validation_issues=[*record.validation_issues, "download_failed"],
        )

    try:
        processed = process_image_bytes(
            raw, max_edge=max_edge, image_format=image_format, quality=quality
        )
    except ImageRejected as exc:
        result.rejected += 1
        return replace(
            record,
            status="quarantine",
            validation_issues=[*record.validation_issues, exc.reason],
        )

    if processed.sha256 in seen_sha:
        result.skipped_duplicate += 1
        return replace(
            record,
            sha256=processed.sha256,
            phash=processed.phash,
            status="quarantine",
            validation_issues=[*record.validation_issues, "sha256_duplicate"],
        )
    for other in seen_phash:
        distance = _phash_distance(processed.phash, other)
        if distance is not None and distance <= PHASH_MAX_DISTANCE:
            result.skipped_duplicate += 1
            return replace(
                record,
                sha256=processed.sha256,
                phash=processed.phash,
                status="quarantine",
                validation_issues=[*record.validation_issues, "perceptual_duplicate"],
            )

    raw_dir = root / "raw" / taxon.folder_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = _stored_filename(record, image_format)
    dest = raw_dir / filename
    dest.write_bytes(processed.data)

    if keep_originals:
        originals_dir = root / "originals" / taxon.folder_name
        originals_dir.mkdir(parents=True, exist_ok=True)
        (originals_dir / filename).write_bytes(raw)

    seen_sha.add(processed.sha256)
    if processed.phash:
        seen_phash.append(processed.phash)
    result.accepted += 1
    result.per_provider[record.provider] += 1

    return replace(
        record,
        local_path=str(dest.relative_to(repo_root())) if _within_repo(dest) else str(dest),
        sha256=processed.sha256,
        phash=processed.phash,
        stored_width=processed.stored_width,
        stored_height=processed.stored_height,
        stored_format=processed.stored_format,
        stored_quality=processed.stored_quality,
        downloaded_at=_utc_now(),
        status="accepted",
    )


def _within_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root())
        return True
    except ValueError:
        return False


def _merge_records(
    existing: dict[tuple[str, str], ImageMetadataRecord],
    new_records: list[ImageMetadataRecord],
) -> list[ImageMetadataRecord]:
    merged = dict(existing)
    for record in new_records:
        merged[(record.provider, record.provider_record_id)] = record
    return sorted(merged.values(), key=lambda r: (r.class_id, r.provider, r.provider_record_id))
