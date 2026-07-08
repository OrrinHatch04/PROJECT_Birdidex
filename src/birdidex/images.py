"""Build image manifests from iNaturalist-style observation records.

This module parses *already-fetched* observation dicts (from fixtures in dry-run mode,
or from a live iNaturalist request performed by an explicit command) into flat
:class:`ImageManifestRecord` rows. It performs no network I/O itself.

The parser targets the iNaturalist observation shape but only touches a small,
documented subset of fields so it degrades gracefully on partial records.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from bird_core.ids import ImageId, SourceRecordId
from bird_core.schemas import EvidenceSource

from bird_data.licensing import normalise_license
from bird_data.manifests import ImageManifestRecord


def _parse_location(obs: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract (lat, lon) from an iNat ``location`` string or geojson-ish fields."""
    loc = obs.get("location")
    if isinstance(loc, str) and "," in loc:
        try:
            lat_s, lon_s = loc.split(",", 1)
            return float(lat_s), float(lon_s)
        except ValueError:
            return None, None
    lat = obs.get("latitude")
    lon = obs.get("longitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return None, None


def _parse_event_date(obs: dict[str, Any]) -> date | None:
    raw = obs.get("observed_on") or obs.get("event_date")
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            return None
    return None


def parse_inat_observations(
    observations: list[dict[str, Any]],
    *,
    inside_roi_fn: Any = None,
) -> list[ImageManifestRecord]:
    """Parse iNaturalist observation dicts into one record per photo.

    ``inside_roi_fn`` is an optional callable ``(lat, lon) -> bool`` (e.g. wrapping a
    shapely ROI predicate). When omitted, ``inside_roi`` is left unset.
    """
    records: list[ImageManifestRecord] = []
    for obs in observations:
        obs_id = obs.get("id")
        taxon = obs.get("taxon") or {}
        sci_name = taxon.get("name") or obs.get("scientific_name")
        if not sci_name:
            # Cannot label an image without a species name — skip.
            continue
        common = taxon.get("preferred_common_name") or obs.get("common_name")
        taxon_id = taxon.get("id") or obs.get("taxon_id")
        user = (obs.get("user") or {}).get("login") or obs.get("observer")
        lat, lon = _parse_location(obs)
        event_date = _parse_event_date(obs)
        quality = obs.get("quality_grade")
        captive = obs.get("captive")
        inside_roi: bool | None = None
        if inside_roi_fn is not None and lat is not None and lon is not None:
            inside_roi = bool(inside_roi_fn(lat, lon))

        photos = obs.get("photos") or []
        for photo in photos:
            photo_id = photo.get("id")
            dims = photo.get("original_dimensions") or {}
            image_id = f"inat-{obs_id}-{photo_id}"
            records.append(
                ImageManifestRecord(
                    image_id=ImageId(image_id),
                    source=EvidenceSource.inaturalist,
                    license=normalise_license(photo.get("license_code")),
                    photo_url=photo.get("url"),
                    scientific_name=str(sci_name),
                    common_name=str(common) if common else None,
                    taxon_id=str(taxon_id) if taxon_id is not None else None,
                    latitude=lat,
                    longitude=lon,
                    event_date=event_date,
                    inside_roi=inside_roi,
                    quality_grade=str(quality) if quality else None,
                    captive_or_cultivated=bool(captive) if captive is not None else None,
                    source_record_id=SourceRecordId(str(obs_id)) if obs_id is not None else None,
                    width_px=dims.get("width"),
                    height_px=dims.get("height"),
                    extra={
                        k: v
                        for k, v in (
                            ("observer", str(user) if user else ""),
                            ("observation_id", str(obs_id) if obs_id is not None else ""),
                            ("photo_id", str(photo_id) if photo_id is not None else ""),
                        )
                        if v
                    },
                )
            )
    return records


def class_counts(records: list[ImageManifestRecord]) -> dict[str, int]:
    """Return {scientific_name: image_count}, sorted by name."""
    counts: dict[str, int] = {}
    for record in records:
        counts[record.scientific_name] = counts.get(record.scientific_name, 0) + 1
    return dict(sorted(counts.items()))


def find_duplicates(records: list[ImageManifestRecord]) -> dict[str, list[str]]:
    """Find exact duplicates keyed by image_id and by photo_url.

    Returns a mapping ``duplicate_key -> [image_id, ...]`` for keys that appear more
    than once. Near-duplicate (perceptual-hash) detection is a documented TODO — it
    needs the optional ``imagehash``/``pillow`` vision dependencies and the media files
    themselves, so it is out of scope for the metadata-only manifest stage.
    """
    by_id: dict[str, list[str]] = {}
    by_url: dict[str, list[str]] = {}
    for record in records:
        by_id.setdefault(str(record.image_id), []).append(str(record.image_id))
        if record.photo_url:
            by_url.setdefault(record.photo_url, []).append(str(record.image_id))

    dups: dict[str, list[str]] = {}
    for image_id, group in by_id.items():
        if len(group) > 1:
            dups[f"image_id:{image_id}"] = group
    for url, group in by_url.items():
        if len(group) > 1:
            dups[f"photo_url:{url}"] = group
    return dups
