"""Read and normalise raw eBird-style CSV exports into internal observation rows.

Role in BIRDIDEX
----------------
This is the ingest front-door for the species/region prototype. It discovers raw CSV
files under ``data/raw/ebird/``, reads them with the stdlib ``csv`` module (no pandas
dependency — see the ``bird_data`` package convention), and maps their many possible
column spellings onto a small set of canonical internal field names that the rest of
the prototype (``species_classes``, ``region_presence``, ``rarity``) consumes.

Two CSV shapes are supported today:

* The **simplified export** we currently collect by hand::

      Species Name,Count,Date,Observer,Location

  where ``Species Name`` is a combined "Common Name Genus species" string that is
  split by :func:`split_species_name`.

* The **standard eBird export** (``COMMON NAME``, ``SCIENTIFIC NAME``,
  ``OBSERVATION COUNT``, ``LOCALITY``, ...). When both name columns exist they are used
  directly and no splitting is attempted.

An observation is represented as a plain ``dict[str, str | None]`` keyed by the
canonical field-name constants below. A loaded dataset is just ``list[dict]``.

Next tasks
----------
* TODO(ebird-api): replace/augment CSV ingest with a live eBird API puller
  (``ebird-api`` / eBird 2.0 endpoints) that writes the same canonical rows, so the
  downstream builders need no changes.
* TODO(taxonomy): resolve split common/scientific names against a real taxonomy backbone
  (IOC / Clements) instead of the trailing-binomial heuristic in
  :func:`split_species_name`.
* TODO(effort): carry ``DURATION MINUTES`` / ``ALL SPECIES REPORTED`` through so the
  rarity model can later become effort-aware.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── Canonical internal field names ───────────────────────────────────────────────────
# Downstream code references ONLY these keys, never the raw CSV header text.
F_COMMON_NAME = "common_name"
F_SCIENTIFIC_NAME = "scientific_name"
F_SPECIES_RAW = "species_raw"  # combined "Common Name Genus species", pre-split
F_OBSERVATION_COUNT = "observation_count"
F_OBSERVATION_DATE = "observation_date"
F_LOCALITY = "locality"
F_STATE = "state"
F_COUNTY = "county"
F_LOCALITY_ID = "locality_id"
F_LATITUDE = "latitude"
F_LONGITUDE = "longitude"
F_OBSERVER = "observer"
F_CHECKLIST_ID = "checklist_id"
F_TAXONOMIC_ORDER = "taxonomic_order"
F_SOURCE_FILE = "source_file"  # injected by the loader, not from the CSV

# Map of lower-cased/trimmed raw header -> canonical field name. Add new spellings here
# rather than scattering special-cases through the code.
_COLUMN_ALIASES: dict[str, str] = {
    # simplified in-house export
    "species name": F_SPECIES_RAW,
    "species": F_SPECIES_RAW,
    "count": F_OBSERVATION_COUNT,
    "date": F_OBSERVATION_DATE,
    "observer": F_OBSERVER,
    "location": F_LOCALITY,
    # standard eBird export
    "common name": F_COMMON_NAME,
    "scientific name": F_SCIENTIFIC_NAME,
    "observation count": F_OBSERVATION_COUNT,
    "observation date": F_OBSERVATION_DATE,
    "locality": F_LOCALITY,
    "locality id": F_LOCALITY_ID,
    "state/province": F_STATE,
    "state": F_STATE,
    "county": F_COUNTY,
    "latitude": F_LATITUDE,
    "longitude": F_LONGITUDE,
    "sampling event identifier": F_CHECKLIST_ID,
    "taxonomic order": F_TAXONOMIC_ORDER,
    "observer id": F_OBSERVER,
}


def discover_ebird_csvs(raw_dir: Path) -> list[Path]:
    """Return eBird CSV files from ``raw_dir``, sorted for deterministic ingest order.

    Only top-level ``*.csv`` files are returned. Markdown placeholders such as
    ``PLACE_RAW_CSVS_HERE.md`` are ignored.
    """
    if not raw_dir.exists():
        return []
    return sorted(p for p in raw_dir.glob("*.csv") if p.is_file())


def read_ebird_csv(path: Path) -> list[dict[str, str]]:
    """Read one CSV into a list of raw-keyed row dicts, preserving original columns.

    No normalisation happens here — column names are exactly as written in the file so
    that :func:`normalise_ebird_columns` can log what it did and did not recognise.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def normalise_ebird_columns(
    rows: list[dict[str, str]], *, source: str = "?"
) -> list[dict[str, str | None]]:
    """Map known raw eBird column variants onto canonical internal field names.

    Unknown columns are **not silently dropped**: they are preserved on the row under
    their original (stripped) header and logged once per file so nothing disappears
    without a trace.
    """
    if not rows:
        log.warning("normalise_ebird_columns: no rows for source=%s", source)
        return []

    raw_headers = list(rows[0].keys())
    recognised: dict[str, str] = {}
    unknown: list[str] = []
    for header in raw_headers:
        key = (header or "").strip().lower()
        canonical = _COLUMN_ALIASES.get(key)
        if canonical:
            recognised[header] = canonical
        else:
            unknown.append(header)

    log.info(
        "source=%s recognised columns %s; unmapped (kept as-is) %s",
        source,
        sorted(set(recognised.values())),
        [h for h in unknown if h],
    )

    out: list[dict[str, str | None]] = []
    for row in rows:
        new: dict[str, str | None] = {}
        for header, value in row.items():
            v = value.strip() if isinstance(value, str) else value
            canonical = recognised.get(header)
            if canonical:
                new[canonical] = v or None
            elif header:  # preserve unknown column under its stripped name
                new[header.strip()] = v or None

        # If we only have a combined species string, split it into common/scientific.
        if F_SPECIES_RAW in new and not new.get(F_COMMON_NAME):
            common, scientific = split_species_name(new.get(F_SPECIES_RAW) or "")
            new.setdefault(F_COMMON_NAME, common)
            if scientific and not new.get(F_SCIENTIFIC_NAME):
                new[F_SCIENTIFIC_NAME] = scientific

        new[F_SOURCE_FILE] = source
        out.append(new)
    return out


def split_species_name(raw: str) -> tuple[str, str | None]:
    """Split a combined "Common Name Genus species" string into (common, scientific).

    eBird common names are Title-Cased and the trailing scientific binomial is a
    capitalised *Genus* followed by a lower-case *species* epithet (or ``sp.`` /
    ``genus/genus`` for uncertain "spuh" and slash taxa). We therefore take the
    scientific name to start at the first capitalised token that is immediately followed
    by a lower-case token::

        "Australian Brushturkey Alectura lathami" -> ("Australian Brushturkey", "Alectura lathami")
        "curlew sp. Numenius sp."                 -> ("curlew sp.", "Numenius sp.")
        "Silvereye"                               -> ("Silvereye", None)

    TODO(taxonomy): this heuristic misfires if a common name ever ends in a lower-case
    word other than ``sp.``. Replace with a taxonomy-backed lookup keyed on the raw
    string once a local taxonomy cache exists (see ``bird_data.taxonomy``).
    """
    tokens = (raw or "").split()
    if not tokens:
        return "", None

    for i in range(len(tokens) - 1):
        cur, nxt = tokens[i], tokens[i + 1]
        if cur[:1].isupper() and nxt[:1].islower():
            common = " ".join(tokens[:i]).strip()
            scientific = " ".join(tokens[i:]).strip()
            if not common:  # e.g. genus-only string; treat whole thing as common
                return raw.strip(), None
            return common, scientific or None
    return raw.strip(), None


def load_all_ebird_observations(raw_dir: Path) -> list[dict[str, str | None]]:
    """Discover, read, normalise and concatenate every raw eBird CSV under ``raw_dir``.

    Returns a flat ``list[dict]`` of canonical observation rows, each tagged with its
    ``source_file`` basename. Returns ``[]`` when no CSVs are present — callers (e.g. the
    build script) are responsible for turning that into a helpful "put CSVs here"
    message.
    """
    observations: list[dict[str, str | None]] = []
    for path in discover_ebird_csvs(raw_dir):
        rows = read_ebird_csv(path)
        observations.extend(normalise_ebird_columns(rows, source=path.name))
    return observations
