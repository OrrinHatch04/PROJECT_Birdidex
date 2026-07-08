"""Metadata-first image provider helpers.

These functions normalize provider metadata into one flat record shape. They do not
download media. Live HTTP calls are opt-in and intentionally thin so tests can pass a
mock client.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from birdidex.taxonomy import (
    TaxonClass,
    normalise_scientific_name,
    scientific_names_match,
)

OPEN_LICENSE_CODES: frozenset[str] = frozenset(
    {
        "cc0",
        "cc-by",
        "cc-by-sa",
        "cc-by-nc",
        "cc-by-nc-sa",
        "pd",
        "publicdomain",
        "public-domain",
    }
)

PROVIDERS: tuple[str, ...] = (
    "inaturalist",
    "ala",
    "gbif",
    "wikimedia_commons",
    "openverse",
)


class HttpClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


@dataclass
class ImageMetadataRecord:
    class_id: int
    label: str
    common_name: str
    scientific_name: str
    provider: str
    provider_record_id: str
    image_url: str | None
    page_url: str | None
    license_code: str | None
    rights_holder: str | None
    attribution: str | None
    width: int | None
    height: int | None
    observed_on: str | None
    latitude: float | None
    longitude: float | None
    raw_metadata: dict[str, Any]
    local_path: str | None = None
    sha256: str | None = None
    phash: str | None = None
    stored_width: int | None = None
    stored_height: int | None = None
    stored_format: str | None = None
    stored_quality: int | None = None
    downloaded_at: str | None = None
    status: str = "review"
    validation_issues: list[str] = field(default_factory=list)

    # ``width``/``height`` are the provider-reported original dimensions. The dataset
    # schema in the docs names these ``original_width``/``original_height`` and the
    # validation state ``validation_status``/``rejection_reason``; ``to_dict`` emits
    # those aliases so on-disk records match the documented contract while the code
    # keeps the shorter internal names.
    @property
    def original_width(self) -> int | None:
        return self.width

    @property
    def original_height(self) -> int | None:
        return self.height

    @property
    def rejection_reason(self) -> str | None:
        return "; ".join(self.validation_issues) or None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["original_width"] = self.width
        data["original_height"] = self.height
        data["validation_status"] = self.status
        data["rejection_reason"] = self.rejection_reason
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageMetadataRecord:
        payload = dict(data)
        # Accept the documented aliases when reading records back.
        if "width" not in payload and "original_width" in payload:
            payload["width"] = payload.get("original_width")
        if "height" not in payload and "original_height" in payload:
            payload["height"] = payload.get("original_height")
        if "status" not in payload and "validation_status" in payload:
            payload["status"] = payload.get("validation_status")
        known = {f.name for f in fields(cls)}
        payload = {key: value for key, value in payload.items() if key in known}
        payload.setdefault("local_path", None)
        payload.setdefault("sha256", None)
        payload.setdefault("status", "review")
        payload.setdefault("validation_issues", [])
        return cls(**payload)


def normalise_license(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.strip().lower().replace("_", "-").replace(" ", "-")
    if normalized.startswith("https://creativecommons.org/licenses/"):
        parts = normalized.rstrip("/").split("/")
        if len(parts) >= 2:
            normalized = f"cc-{parts[-2]}"
    if normalized.startswith("cc-by-4"):
        normalized = "cc-by"
    return normalized


def is_open_license(code: str | None) -> bool:
    return normalise_license(code) in OPEN_LICENSE_CODES


def _json(response: Any) -> Any:
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    return response.json()


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "records", "occurrences", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


# iNaturalist photo URLs default to a 75px ``square`` thumbnail; the size token in the
# path selects the variant. Upgrade to ``large`` (~1024px longest edge) so downloaded
# training images carry real detail instead of being rejected as too small.
_INAT_SIZE_RE = re.compile(r"/(square|small|medium|large|original)\.(?=[A-Za-z0-9]+($|\?))")


def _inat_full_size_url(url: str | None, *, size: str = "large") -> str | None:
    if not url:
        return url
    return _INAT_SIZE_RE.sub(f"/{size}.", url)


def _inat_location(obs: dict[str, Any]) -> tuple[float | None, float | None]:
    location = obs.get("location")
    if isinstance(location, str) and "," in location:
        lat, lon = location.split(",", 1)
        return _float(lat), _float(lon)
    return _float(obs.get("latitude")), _float(obs.get("longitude"))


def _base_record(
    taxon: TaxonClass,
    *,
    provider: str,
    provider_record_id: str,
    image_url: str | None,
    page_url: str | None,
    license_code: str | None,
    rights_holder: str | None,
    attribution: str | None,
    width: Any = None,
    height: Any = None,
    observed_on: str | None = None,
    latitude: Any = None,
    longitude: Any = None,
    scientific_name: str | None = None,
    common_name: str | None = None,
    raw_metadata: dict[str, Any] | None = None,
) -> ImageMetadataRecord:
    return ImageMetadataRecord(
        class_id=taxon.class_id,
        label=taxon.label,
        common_name=common_name or taxon.common_name,
        scientific_name=scientific_name or taxon.scientific_name or "",
        provider=provider,
        provider_record_id=str(provider_record_id),
        image_url=image_url,
        page_url=page_url,
        license_code=normalise_license(license_code),
        rights_holder=rights_holder,
        attribution=attribution,
        width=_int(width),
        height=_int(height),
        observed_on=observed_on,
        latitude=_float(latitude),
        longitude=_float(longitude),
        raw_metadata=raw_metadata or {},
    )


def normalize_inaturalist(payload: Any, taxon: TaxonClass) -> list[ImageMetadataRecord]:
    records: list[ImageMetadataRecord] = []
    for obs in _records(payload):
        obs_id = obs.get("id")
        taxon_data = obs.get("taxon") or {}
        scientific = taxon_data.get("name") or obs.get("scientific_name")
        common = taxon_data.get("preferred_common_name") or obs.get("common_name")
        lat, lon = _inat_location(obs)
        photos = obs.get("photos") or []
        for photo in photos:
            dims = photo.get("original_dimensions") or {}
            photo_id = photo.get("id") or photo.get("uuid") or len(records)
            records.append(
                _base_record(
                    taxon,
                    provider="inaturalist",
                    provider_record_id=f"{obs_id}:{photo_id}",
                    image_url=_inat_full_size_url(photo.get("url") or photo.get("original_url")),
                    page_url=obs.get("uri")
                    or (f"https://www.inaturalist.org/observations/{obs_id}" if obs_id else None),
                    license_code=photo.get("license_code") or obs.get("license_code"),
                    rights_holder=(photo.get("attribution") or {}).get("user")
                    if isinstance(photo.get("attribution"), dict)
                    else None,
                    attribution=(
                        photo.get("attribution")
                        if isinstance(photo.get("attribution"), str)
                        else None
                    ),
                    width=dims.get("width") or photo.get("width"),
                    height=dims.get("height") or photo.get("height"),
                    observed_on=obs.get("observed_on"),
                    latitude=lat,
                    longitude=lon,
                    scientific_name=scientific,
                    common_name=common,
                    raw_metadata={"observation": obs, "photo": photo},
                )
            )
    return records


def normalize_ala(payload: Any, taxon: TaxonClass) -> list[ImageMetadataRecord]:
    out: list[ImageMetadataRecord] = []
    for row in _records(payload):
        media = row.get("multimedia") or row.get("images") or []
        first_media = media[0] if isinstance(media, list) and media else {}
        if not isinstance(first_media, dict):
            first_media = {}
        out.append(
            _base_record(
                taxon,
                provider="ala",
                provider_record_id=(
                    row.get("occurrenceID") or row.get("uuid") or row.get("id") or ""
                ),
                image_url=row.get("image_url")
                or row.get("imageUrl")
                or first_media.get("identifier")
                or first_media.get("url"),
                page_url=row.get("record_url") or row.get("occurrenceDetails"),
                license_code=row.get("license") or row.get("licence") or first_media.get("license"),
                rights_holder=row.get("rightsHolder") or first_media.get("rightsHolder"),
                attribution=row.get("attribution") or first_media.get("creator"),
                width=row.get("width") or first_media.get("width"),
                height=row.get("height") or first_media.get("height"),
                observed_on=row.get("eventDate") or row.get("dateIdentified"),
                latitude=row.get("decimalLatitude"),
                longitude=row.get("decimalLongitude"),
                scientific_name=row.get("scientificName"),
                common_name=row.get("vernacularName"),
                raw_metadata=row,
            )
        )
    return out


def normalize_gbif(payload: Any, taxon: TaxonClass) -> list[ImageMetadataRecord]:
    out: list[ImageMetadataRecord] = []
    for row in _records(payload):
        media = row.get("media") or []
        if not media:
            media = [row]
        for item in media:
            if not isinstance(item, dict):
                continue
            out.append(
                _base_record(
                    taxon,
                    provider="gbif",
                    provider_record_id=(
                        f"{row.get('key') or row.get('gbifID') or row.get('id')}:"
                        f"{item.get('identifier') or item.get('references') or len(out)}"
                    ),
                    image_url=item.get("identifier") or item.get("url"),
                    page_url=item.get("references") or row.get("references"),
                    license_code=item.get("license") or row.get("license"),
                    rights_holder=item.get("rightsHolder") or row.get("rightsHolder"),
                    attribution=item.get("creator") or row.get("recordedBy"),
                    width=item.get("width"),
                    height=item.get("height"),
                    observed_on=row.get("eventDate") or row.get("dateIdentified"),
                    latitude=row.get("decimalLatitude"),
                    longitude=row.get("decimalLongitude"),
                    scientific_name=row.get("scientificName"),
                    common_name=row.get("vernacularName"),
                    raw_metadata={"occurrence": row, "media": item},
                )
            )
    return out


def normalize_wikimedia_commons(payload: Any, taxon: TaxonClass) -> list[ImageMetadataRecord]:
    pages: list[dict[str, Any]]
    if isinstance(payload, dict) and isinstance(payload.get("query"), dict):
        pages = list((payload["query"].get("pages") or {}).values())
    else:
        pages = _records(payload)

    out: list[ImageMetadataRecord] = []
    for page in pages:
        imageinfo = page.get("imageinfo") or []
        info = imageinfo[0] if imageinfo else page
        ext = info.get("extmetadata") or {}
        license_code = (
            (ext.get("LicenseShortName") or {}).get("value")
            or (ext.get("License") or {}).get("value")
            or info.get("license")
        )
        out.append(
            _base_record(
                taxon,
                provider="wikimedia_commons",
                provider_record_id=str(page.get("pageid") or page.get("title") or info.get("url")),
                image_url=info.get("url"),
                page_url=info.get("descriptionurl") or page.get("fullurl"),
                license_code=license_code,
                rights_holder=(ext.get("Artist") or {}).get("value") or info.get("artist"),
                attribution=(ext.get("Credit") or {}).get("value") or info.get("credit"),
                width=info.get("width"),
                height=info.get("height"),
                observed_on=None,
                scientific_name=taxon.scientific_name,
                common_name=taxon.common_name,
                raw_metadata=page,
            )
        )
    return out


def normalize_openverse(payload: Any, taxon: TaxonClass) -> list[ImageMetadataRecord]:
    out: list[ImageMetadataRecord] = []
    for row in _records(payload):
        out.append(
            _base_record(
                taxon,
                provider="openverse",
                provider_record_id=(
                    row.get("id") or row.get("foreign_identifier") or row.get("url") or ""
                ),
                image_url=row.get("url") or row.get("thumbnail"),
                page_url=row.get("foreign_landing_url") or row.get("source"),
                license_code=row.get("license"),
                rights_holder=row.get("creator"),
                attribution=row.get("attribution") or row.get("title"),
                width=row.get("width"),
                height=row.get("height"),
                observed_on=None,
                scientific_name=taxon.scientific_name,
                common_name=taxon.common_name,
                raw_metadata=row,
            )
        )
    return out


def fetch_inaturalist(
    taxon: TaxonClass,
    *,
    client: HttpClient | None = None,
    limit: int = 25,
    live: bool = False,
    access_token: str | None = None,
) -> list[ImageMetadataRecord]:
    if not live:
        return []
    import httpx

    # Public observation search works without auth; a token is used only if supplied.
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
    http = client or httpx.Client(timeout=30, headers=headers)
    kwargs: dict[str, Any] = {
        "params": {
            "taxon_name": taxon.scientific_name or taxon.common_name,
            "photos": "true",
            "quality_grade": "research",
            "per_page": limit,
            "license": "cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nc-sa",
        }
    }
    if client is not None and headers is not None:
        kwargs["headers"] = headers
    response = http.get("https://api.inaturalist.org/v1/observations", **kwargs)
    return normalize_inaturalist(_json(response), taxon)


def fetch_ala(
    taxon: TaxonClass,
    *,
    client: HttpClient | None = None,
    limit: int = 25,
    live: bool = False,
) -> list[ImageMetadataRecord]:
    if not live:
        return []
    import httpx

    http = client or httpx.Client(timeout=30)
    response = http.get(
        "https://biocache-ws.ala.org.au/ws/occurrences/search",
        params={"q": f'lsid:"{taxon.scientific_name or taxon.common_name}"', "pageSize": limit},
    )
    return normalize_ala(_json(response), taxon)


def fetch_gbif(
    taxon: TaxonClass,
    *,
    client: HttpClient | None = None,
    limit: int = 25,
    live: bool = False,
) -> list[ImageMetadataRecord]:
    if not live:
        return []
    import httpx

    http = client or httpx.Client(timeout=30)
    response = http.get(
        "https://api.gbif.org/v1/occurrence/search",
        params={
            "scientificName": taxon.scientific_name or taxon.common_name,
            "mediaType": "StillImage",
            "limit": limit,
        },
    )
    return normalize_gbif(_json(response), taxon)


def fetch_wikimedia_commons(
    taxon: TaxonClass,
    *,
    client: HttpClient | None = None,
    limit: int = 25,
    live: bool = False,
) -> list[ImageMetadataRecord]:
    if not live:
        return []
    import httpx

    http = client or httpx.Client(timeout=30)
    response = http.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": taxon.scientific_name or taxon.common_name,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size",
            "format": "json",
        },
    )
    return normalize_wikimedia_commons(_json(response), taxon)


def fetch_openverse(
    taxon: TaxonClass,
    *,
    client: HttpClient | None = None,
    limit: int = 25,
    live: bool = False,
) -> list[ImageMetadataRecord]:
    if not live:
        return []
    import httpx

    http = client or httpx.Client(timeout=30)
    response = http.get(
        "https://api.openverse.engineering/v1/images/",
        params={"q": taxon.scientific_name or taxon.common_name, "page_size": limit},
    )
    return normalize_openverse(_json(response), taxon)


FETCHERS = {
    "inaturalist": fetch_inaturalist,
    "ala": fetch_ala,
    "gbif": fetch_gbif,
    "wikimedia_commons": fetch_wikimedia_commons,
    "openverse": fetch_openverse,
}


def validate_metadata_records(
    records: list[ImageMetadataRecord],
    *,
    class_lookup: dict[int, TaxonClass] | None = None,
) -> list[ImageMetadataRecord]:
    """Attach validation status and issues to normalized provider records."""
    seen_provider_records: set[tuple[str, str]] = set()
    validated: list[ImageMetadataRecord] = []
    for record in records:
        issues: list[str] = []
        provider_key = (record.provider, record.provider_record_id)
        taxon = class_lookup.get(record.class_id) if class_lookup else None

        if provider_key in seen_provider_records:
            issues.append("duplicate_provider_record")
        seen_provider_records.add(provider_key)

        if not record.image_url:
            issues.append("missing_image_url")
        if not is_open_license(record.license_code):
            issues.append("missing_or_unknown_license")
        if taxon and taxon.is_ambiguous:
            issues.append("ambiguous_taxon")
        if (
            taxon
            and taxon.scientific_name
            and record.scientific_name
            and not scientific_names_match(taxon.scientific_name, record.scientific_name)
        ):
            issues.append("scientific_name_mismatch")

        status = "accepted" if not issues else "quarantine"
        validated.append(replace(record, status=status, validation_issues=issues))
    return validated


# ---------------------------------------------------------------------------
# eBird regional occurrence priors
#
# eBird is used for *context*, not images: given a species and a region it returns
# occurrence, seasonality, and locality signals that later re-rank (but never override)
# visual classifier evidence. Auth uses the documented ``X-eBirdApiToken`` header.
# ---------------------------------------------------------------------------

EBIRD_TAXONOMY_URL = "https://api.ebird.org/v2/ref/taxonomy/ebird"
EBIRD_SPECIES_OBS_URL = "https://api.ebird.org/v2/data/obs/{region}/recent/{species_code}"

# Friendly region aliases mapped to eBird region codes. South East Queensland has no
# single eBird code, so ``seq`` is approximated by the Queensland subnational region.
EBIRD_REGION_ALIASES: dict[str, str] = {
    "seq": "AU-QLD",
    "south_east_queensland": "AU-QLD",
    "south-east-queensland": "AU-QLD",
    "qld": "AU-QLD",
    "queensland": "AU-QLD",
    "au": "AU",
    "australia": "AU",
}

# Process-level cache so one dry-run does not refetch the (large) eBird taxonomy.
_EBIRD_TAXONOMY_CACHE: dict[str, str] | None = None


def resolve_ebird_region(region: str | None) -> str:
    if not region:
        return "AU-QLD"
    token = region.strip()
    return EBIRD_REGION_ALIASES.get(token.lower(), token)


def ebird_headers(api_key: str) -> dict[str, str]:
    return {"X-eBirdApiToken": api_key}


@dataclass
class EbirdPrior:
    class_id: int
    label: str
    common_name: str
    scientific_name: str
    species_code: str | None
    region: str
    region_resolved: str
    total_observations: int
    total_individuals: int
    distinct_localities: int
    top_localities: list[dict[str, Any]]
    month_histogram: dict[str, int]
    first_observed_on: str | None
    last_observed_on: str | None
    sample_observations: list[dict[str, Any]]
    provider: str = "ebird"
    fetched_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ebird_month(obs_dt: str | None) -> str | None:
    if not obs_dt:
        return None
    parts = obs_dt.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return f"{int(parts[1]):02d}"
    return None


def normalize_ebird_observations(
    observations: Any,
    taxon: TaxonClass,
    *,
    region: str,
    region_resolved: str | None = None,
    species_code: str | None = None,
    sample_size: int = 10,
    top_localities: int = 10,
) -> EbirdPrior:
    """Summarize eBird sightings for one species/region into an occurrence prior."""
    rows = _records(observations)
    resolved = region_resolved or resolve_ebird_region(region)

    total_individuals = 0
    locality_counts: Counter[str] = Counter()
    month_counts: Counter[str] = Counter()
    dates: list[str] = []
    samples: list[dict[str, Any]] = []
    derived_code = species_code

    for obs in rows:
        if derived_code is None:
            derived_code = obs.get("speciesCode")
        how_many = _int(obs.get("howMany"))
        total_individuals += how_many or 0
        loc_name = obs.get("locName") or obs.get("locId")
        if loc_name:
            locality_counts[str(loc_name)] += 1
        obs_dt = obs.get("obsDt")
        month = _ebird_month(obs_dt)
        if month:
            month_counts[month] += 1
        if obs_dt:
            dates.append(str(obs_dt))
        if len(samples) < sample_size:
            samples.append(
                {
                    "loc_name": obs.get("locName"),
                    "obs_dt": obs_dt,
                    "how_many": how_many,
                    "latitude": _float(obs.get("lat")),
                    "longitude": _float(obs.get("lng")),
                    "obs_valid": obs.get("obsValid"),
                }
            )

    dates.sort()
    return EbirdPrior(
        class_id=taxon.class_id,
        label=taxon.label,
        common_name=taxon.common_name,
        scientific_name=taxon.scientific_name or "",
        species_code=derived_code,
        region=region,
        region_resolved=resolved,
        total_observations=len(rows),
        total_individuals=total_individuals,
        distinct_localities=len(locality_counts),
        top_localities=[
            {"loc_name": name, "observations": count}
            for name, count in locality_counts.most_common(top_localities)
        ],
        month_histogram={month: month_counts[month] for month in sorted(month_counts)},
        first_observed_on=dates[0] if dates else None,
        last_observed_on=dates[-1] if dates else None,
        sample_observations=samples,
        fetched_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )


def load_ebird_taxonomy(
    *,
    api_key: str,
    client: HttpClient | None = None,
    use_cache: bool = True,
) -> dict[str, str]:
    """Return a ``scientific_name(lower) -> speciesCode`` map from the eBird taxonomy."""
    global _EBIRD_TAXONOMY_CACHE
    if use_cache and _EBIRD_TAXONOMY_CACHE is not None:
        return _EBIRD_TAXONOMY_CACHE
    import httpx

    http = client or httpx.Client(timeout=60)
    response = http.get(EBIRD_TAXONOMY_URL, params={"fmt": "json"}, headers=ebird_headers(api_key))
    rows = _json(response)
    mapping: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        sci = normalise_scientific_name(row.get("sciName")).lower()
        code = row.get("speciesCode")
        if sci and code:
            mapping[sci] = str(code)
    if use_cache:
        _EBIRD_TAXONOMY_CACHE = mapping
    return mapping


def resolve_ebird_species_code(
    taxon: TaxonClass,
    *,
    api_key: str,
    client: HttpClient | None = None,
    taxonomy_map: dict[str, str] | None = None,
) -> str | None:
    if not taxon.scientific_name:
        return None
    mapping = taxonomy_map or load_ebird_taxonomy(api_key=api_key, client=client)
    return mapping.get(normalise_scientific_name(taxon.scientific_name).lower())


def fetch_ebird_priors(
    taxon: TaxonClass,
    *,
    region: str = "seq",
    api_key: str | None = None,
    client: HttpClient | None = None,
    live: bool = False,
    back: int = 30,
    max_results: int = 200,
    taxonomy_map: dict[str, str] | None = None,
) -> EbirdPrior | None:
    """Fetch and normalize regional eBird occurrence priors for one species.

    Returns ``None`` when ``live`` is False (no network). When live, ``api_key`` must be
    provided (resolved from :mod:`birdidex.secrets` by callers). No images are fetched.
    """
    if not live:
        return None
    if not api_key:
        from birdidex.secrets import require_secret

        api_key = require_secret("EBIRD_API_KEY")

    import httpx

    http = client or httpx.Client(timeout=60)
    resolved = resolve_ebird_region(region)
    species_code = resolve_ebird_species_code(
        taxon, api_key=api_key, client=http, taxonomy_map=taxonomy_map
    )
    if species_code is None:
        return normalize_ebird_observations(
            [], taxon, region=region, region_resolved=resolved, species_code=None
        )

    response = http.get(
        EBIRD_SPECIES_OBS_URL.format(region=resolved, species_code=species_code),
        params={"back": back, "maxResults": max_results, "includeProvisional": "true"},
        headers=ebird_headers(api_key),
    )
    payload = _json(response)
    return normalize_ebird_observations(
        payload, taxon, region=region, region_resolved=resolved, species_code=species_code
    )
