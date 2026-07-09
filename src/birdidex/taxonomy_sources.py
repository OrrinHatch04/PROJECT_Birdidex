"""Authoritative taxonomy sources for expanding ambiguous bird classes.

Two things live here:

1. A **curated candidate knowledge base** (``AMBIGUOUS_GROUPS``) that maps each
   ambiguous group in ``class_index.json`` to concrete Australian / SEQ-relevant
   species. Every candidate carries the authoritative source(s) that support it
   (eBird taxonomy, Atlas of Living Australia, iNaturalist) and a status hint. This
   is the offline, deterministic backbone so ``taxonomy expand-ambiguous`` and the
   test-suite never need the network.

2. Thin, opt-in **provider taxonomy-search** helpers (eBird / iNaturalist / ALA) and
   their response *normalizers*. Live calls happen only when ``live=True``; tests
   drive the normalizers with mocked payloads. These enrich / verify the curated
   candidates but never override the curated ROI judgement.

No image URLs are fetched here — this module is names and ranks only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from birdidex.taxonomy import TaxonClass, normalise_scientific_name, slugify

# Candidate ROI-relevance statuses, most to least confident.
CANDIDATE_STATUSES: tuple[str, ...] = (
    "confirmed_roi",
    "likely_roi",
    "australian_but_not_roi",
    "uncertain",
    "reject",
)

# Source tags used in candidate ``evidence`` lists. ``seq_roi_local_records`` is added
# dynamically by the expander when a candidate appears in the local ROI CSV/summary.
SOURCE_EBIRD = "ebird_taxonomy"
SOURCE_INAT = "inaturalist_taxa"
SOURCE_ALA = "ala_names"
SOURCE_GBIF = "gbif_species"
SOURCE_ROI_LOCAL = "seq_roi_local_records"
SOURCE_CURATED = "curated_override"
SOURCE_NAME_COLLISION = "name_collision"


class HttpClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Curated candidate knowledge base
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroupCandidate:
    """One concrete species proposed as a replacement for an ambiguous group.

    ``always_include`` forces the species into the candidate index as a new class even
    when it is not ROI-relevant (used for "add every Australian species of this family"
    requests); it is ignored when the species already exists as a clean class.
    """

    common_name: str
    scientific_name: str
    status_hint: str
    evidence: tuple[str, ...]
    notes: str = ""
    always_include: bool = False

    def __post_init__(self) -> None:
        if self.status_hint not in CANDIDATE_STATUSES:
            raise ValueError(f"unknown status_hint: {self.status_hint}")


@dataclass(frozen=True)
class AmbiguousGroup:
    """A curated expansion group and the rules that match an ambiguous class to it."""

    group_key: str
    display_name: str
    candidates: tuple[GroupCandidate, ...]
    match_labels: tuple[str, ...] = ()
    match_genera: tuple[str, ...] = ()
    match_families: tuple[str, ...] = ()
    is_split: bool = False
    notes: str = ""


def _c(
    common: str,
    scientific: str,
    status: str,
    evidence: tuple[str, ...],
    notes: str = "",
    *,
    always_include: bool = False,
) -> GroupCandidate:
    return GroupCandidate(common, scientific, status, evidence, notes, always_include)


_ALL_THREE = (SOURCE_EBIRD, SOURCE_ALA, SOURCE_INAT)

# Curated groups. Candidate ROI judgement is hinted here and then reconciled against the
# local ROI files by the expander (a candidate observed locally is upgraded to
# ``confirmed_roi``). Candidates are added only where an authoritative source supports
# Australia / Queensland / SEQ relevance — never "every bird in the family".
AMBIGUOUS_GROUPS: tuple[AmbiguousGroup, ...] = (
    AmbiguousGroup(
        group_key="curlews",
        display_name="Curlews / whimbrels (Numenius)",
        match_labels=("curlew_sp",),
        match_genera=("Numenius",),
        candidates=(
            _c(
                "Far Eastern Curlew",
                "Numenius madagascariensis",
                "likely_roi",
                _ALL_THREE,
                "Migratory shorebird; regular in Moreton Bay / SEQ tidal flats.",
            ),
            _c(
                "Eurasian Whimbrel",
                "Numenius phaeopus",
                "likely_roi",
                _ALL_THREE,
                "eBird common name 'Whimbrel'; common SEQ migratory shorebird.",
            ),
            _c(
                "Little Curlew",
                "Numenius minutus",
                "australian_but_not_roi",
                (SOURCE_EBIRD, SOURCE_ALA),
                "Occurs in Australia; scarce/irregular on the SEQ coast.",
            ),
            _c(
                "Bush Stone-curlew",
                "Burhinus grallarius",
                "reject",
                (SOURCE_NAME_COLLISION,),
                "Name collision only: genus Burhinus, not Numenius; excluded from a "
                "Numenius sp. record. Present as class 'Bush Thick-knee'.",
            ),
        ),
    ),
    AmbiguousGroup(
        group_key="fairywrens",
        display_name="Fairywrens (all Australian Malurus)",
        match_labels=("fairywren_sp",),
        match_genera=("Malurus",),
        notes="Every Australian fairywren (genus Malurus) is included as a class on request.",
        candidates=(
            _c(
                "Superb Fairywren",
                "Malurus cyaneus",
                "likely_roi",
                _ALL_THREE,
                "Widespread in SEQ gardens/parkland; eastern-Australian endemic.",
                always_include=True,
            ),
            _c(
                "Variegated Fairywren",
                "Malurus lamberti",
                "likely_roi",
                _ALL_THREE,
                "Present across SEQ shrubland/heath.",
                always_include=True,
            ),
            _c(
                "Red-backed Fairywren",
                "Malurus melanocephalus",
                "likely_roi",
                _ALL_THREE,
                "Coastal/near-coastal SEQ grasslands and heath.",
                always_include=True,
            ),
            _c(
                "Purple-backed Fairywren",
                "Malurus assimilis",
                "australian_but_not_roi",
                _ALL_THREE,
                "Recent split from Variegated Fairywren; drier inland Australia.",
                always_include=True,
            ),
            _c(
                "Splendid Fairywren",
                "Malurus splendens",
                "australian_but_not_roi",
                _ALL_THREE,
                "Arid/semi-arid inland and western Australia.",
                always_include=True,
            ),
            _c(
                "Lovely Fairywren",
                "Malurus amabilis",
                "australian_but_not_roi",
                _ALL_THREE,
                "Cape York / north-eastern Queensland rainforest edges.",
                always_include=True,
            ),
            _c(
                "White-winged Fairywren",
                "Malurus leucopterus",
                "australian_but_not_roi",
                _ALL_THREE,
                "Arid saltbush/shrub plains across inland Australia.",
                always_include=True,
            ),
            _c(
                "Blue-breasted Fairywren",
                "Malurus pulcherrimus",
                "australian_but_not_roi",
                _ALL_THREE,
                "Mallee/heath of southern WA and SA.",
                always_include=True,
            ),
            _c(
                "Red-winged Fairywren",
                "Malurus elegans",
                "australian_but_not_roi",
                _ALL_THREE,
                "Dense wet understorey of far south-west WA.",
                always_include=True,
            ),
            _c(
                "Purple-crowned Fairywren",
                "Malurus coronatus",
                "australian_but_not_roi",
                _ALL_THREE,
                "Riverine pandanus/cane-grass of the tropical north.",
                always_include=True,
            ),
        ),
    ),
    AmbiguousGroup(
        group_key="kingfishers",
        display_name="Kingfishers & kookaburras (all Australian)",
        match_labels=("kingfisher_sp",),
        match_families=("Alcedinidae", "Halcyonidae"),
        match_genera=("Todiramphus", "Dacelo", "Ceyx", "Alcedo", "Syma", "Tanysiptera"),
        notes="Every Australian kingfisher/kookaburra species is included as a class on request.",
        candidates=(
            _c(
                "Laughing Kookaburra",
                "Dacelo novaeguineae",
                "likely_roi",
                _ALL_THREE,
                "Ubiquitous SEQ kingfisher (kookaburra).",
                always_include=True,
            ),
            _c(
                "Blue-winged Kookaburra",
                "Dacelo leachii",
                "australian_but_not_roi",
                _ALL_THREE,
                "Tropical northern Australia; reaches central-eastern Queensland.",
                always_include=True,
            ),
            _c(
                "Sacred Kingfisher",
                "Todiramphus sanctus",
                "likely_roi",
                _ALL_THREE,
                "Common SEQ breeding migrant.",
                always_include=True,
            ),
            _c(
                "Forest Kingfisher",
                "Todiramphus macleayii",
                "likely_roi",
                _ALL_THREE,
                "Open-forest SEQ kingfisher.",
                always_include=True,
            ),
            _c(
                "Torresian Kingfisher",
                "Todiramphus sordidus",
                "likely_roi",
                _ALL_THREE,
                "Mangrove kingfisher; split from Collared Kingfisher.",
                always_include=True,
            ),
            _c(
                "Red-backed Kingfisher",
                "Todiramphus pyrrhopygius",
                "australian_but_not_roi",
                _ALL_THREE,
                "Arid/semi-arid inland Australia; occasional coastal vagrant.",
                always_include=True,
            ),
            _c(
                "Yellow-billed Kingfisher",
                "Syma torotoro",
                "australian_but_not_roi",
                _ALL_THREE,
                "Cape York Peninsula rainforest.",
                always_include=True,
            ),
            _c(
                "Azure Kingfisher",
                "Ceyx azureus",
                "likely_roi",
                _ALL_THREE,
                "SEQ creeks/rivers; not yet in local ROI records.",
                always_include=True,
            ),
            _c(
                "Little Kingfisher",
                "Ceyx pusillus",
                "australian_but_not_roi",
                _ALL_THREE,
                "Far-north Queensland mangroves and tropical wetlands.",
                always_include=True,
            ),
            _c(
                "Buff-breasted Paradise-Kingfisher",
                "Tanysiptera sylvia",
                "australian_but_not_roi",
                _ALL_THREE,
                "Cape York breeding migrant with a long white tail.",
                always_include=True,
            ),
            _c(
                "Collared Kingfisher",
                "Todiramphus chloris",
                "uncertain",
                (SOURCE_EBIRD, SOURCE_ALA),
                "Australian mangrove birds are now treated as Torresian Kingfisher; "
                "retain only if a source resolves the record to T. chloris sensu stricto.",
            ),
        ),
    ),
    AmbiguousGroup(
        group_key="swallows_martins",
        display_name="Swallows & martins (Hirundinidae)",
        match_labels=("swallow_sp",),
        match_families=("Hirundinidae",),
        match_genera=("Hirundo", "Petrochelidon", "Cheramoeca", "Cecropis"),
        candidates=(
            _c(
                "Welcome Swallow",
                "Hirundo neoxena",
                "likely_roi",
                _ALL_THREE,
                "The default SEQ swallow.",
            ),
            _c(
                "Fairy Martin",
                "Petrochelidon ariel",
                "likely_roi",
                _ALL_THREE,
                "Colonial SEQ martin.",
            ),
            _c(
                "Tree Martin",
                "Petrochelidon nigricans",
                "likely_roi",
                _ALL_THREE,
                "Widespread SEQ martin.",
            ),
            _c(
                "Barn Swallow",
                "Hirundo rustica",
                "likely_roi",
                _ALL_THREE,
                "Uncommon but regular SEQ summer migrant.",
            ),
        ),
    ),
    AmbiguousGroup(
        group_key="teals",
        display_name="Teal (Anas dabbling teal)",
        match_labels=("teal_sp",),
        match_genera=("Anas",),
        notes="Record scientific name is 'Anatidae sp. (teal sp.)' — restrict to teals.",
        candidates=(
            _c(
                "Gray Teal",
                "Anas gracilis",
                "likely_roi",
                _ALL_THREE,
                "Canonical label uses US 'Gray'; 'Grey Teal' is the Australian spelling.",
            ),
            _c(
                "Chestnut Teal",
                "Anas castanea",
                "likely_roi",
                _ALL_THREE,
                "Common SEQ estuarine teal.",
            ),
        ),
    ),
    AmbiguousGroup(
        group_key="terns",
        display_name="Terns (Sterninae)",
        match_labels=("tern_sp",),
        match_families=("Sterninae", "Laridae"),
        match_genera=(
            "Thalasseus",
            "Hydroprogne",
            "Sterna",
            "Sternula",
            "Gelochelidon",
            "Chlidonias",
            "Onychoprion",
        ),
        candidates=(
            _c(
                "Great Crested Tern",
                "Thalasseus bergii",
                "likely_roi",
                _ALL_THREE,
                "eBird 'Great Crested Tern'; often called Crested Tern in Australia.",
            ),
            _c(
                "Lesser Crested Tern",
                "Thalasseus bengalensis",
                "likely_roi",
                _ALL_THREE,
                "Regular SEQ coastal tern.",
            ),
            _c(
                "Caspian Tern",
                "Hydroprogne caspia",
                "likely_roi",
                _ALL_THREE,
                "Largest SEQ tern.",
            ),
            _c(
                "Common Tern",
                "Sterna hirundo",
                "likely_roi",
                _ALL_THREE,
                "SEQ migratory tern.",
            ),
            _c(
                "Little Tern",
                "Sternula albifrons",
                "likely_roi",
                _ALL_THREE,
                "SEQ beach-nesting tern.",
            ),
            _c(
                "Australian Tern",
                "Gelochelidon macrotarsa",
                "likely_roi",
                (SOURCE_EBIRD, SOURCE_ALA),
                "Australian Gull-billed Tern split (Gelochelidon macrotarsa).",
            ),
            _c(
                "Whiskered Tern",
                "Chlidonias hybrida",
                "likely_roi",
                _ALL_THREE,
                "SEQ freshwater wetlands; not yet in local ROI records.",
            ),
        ),
    ),
    AmbiguousGroup(
        group_key="fairy_tree_martin_split",
        display_name="Fairy / Tree Martin (slash split)",
        match_labels=("fairy_tree_martin",),
        is_split=True,
        candidates=(
            _c(
                "Fairy Martin",
                "Petrochelidon ariel",
                "likely_roi",
                _ALL_THREE,
                "Left side of 'Fairy/Tree Martin'.",
            ),
            _c(
                "Tree Martin",
                "Petrochelidon nigricans",
                "likely_roi",
                _ALL_THREE,
                "Right side of 'Fairy/Tree Martin'.",
            ),
        ),
    ),
)


def _scientific_genus(scientific_name: str | None) -> str:
    tokens = normalise_scientific_name(scientific_name).split()
    return tokens[0] if tokens else ""


def _family_tokens(scientific_name: str | None) -> set[str]:
    return {
        token
        for token in normalise_scientific_name(scientific_name).replace("(", " ").split()
        if token.endswith(("idae", "inae"))
    }


def match_group(taxon: TaxonClass) -> AmbiguousGroup | None:
    """Return the curated expansion group for an ambiguous class, if one is known."""
    label = taxon.label.lower()
    genus = _scientific_genus(taxon.scientific_name)
    families = _family_tokens(taxon.scientific_name)
    # Label match is the strongest signal; genus/family are fallbacks.
    for group in AMBIGUOUS_GROUPS:
        if label in {item.lower() for item in group.match_labels}:
            return group
    for group in AMBIGUOUS_GROUPS:
        if genus and genus in group.match_genera:
            return group
        if families & set(group.match_families):
            return group
    return None


# ---------------------------------------------------------------------------
# Provider taxonomy-search normalizers (opt-in live; mocked in tests)
# ---------------------------------------------------------------------------


@dataclass
class TaxonCandidate:
    """A normalized taxonomy-search hit from any provider."""

    common_name: str | None
    scientific_name: str | None
    rank: str | None
    provider: str
    provider_taxon_id: str | None
    is_bird: bool
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_species_level(self) -> bool:
        return (self.rank or "species").strip().lower() in {
            "species",
            "subspecies",
            "issf",
            "form",
            "variety",
        }


def _rows(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def normalize_ebird_taxonomy(payload: Any) -> list[TaxonCandidate]:
    """Normalize eBird taxonomy rows (``comName``/``sciName``/``speciesCode``)."""
    out: list[TaxonCandidate] = []
    for row in _rows(payload, ("results",)):
        category = str(row.get("category") or "species").lower()
        out.append(
            TaxonCandidate(
                common_name=row.get("comName") or row.get("commonName"),
                scientific_name=normalise_scientific_name(row.get("sciName")) or None,
                rank=category,
                provider="ebird",
                provider_taxon_id=row.get("speciesCode"),
                is_bird=True,  # the eBird taxonomy is birds only
                raw=row,
            )
        )
    return out


def normalize_inaturalist_taxa(payload: Any) -> list[TaxonCandidate]:
    """Normalize iNaturalist ``/v1/taxa`` results, keeping birds (Aves) only."""
    out: list[TaxonCandidate] = []
    for row in _rows(payload, ("results",)):
        iconic = str(row.get("iconic_taxon_name") or "").lower()
        is_bird = iconic == "aves" if iconic else True
        out.append(
            TaxonCandidate(
                common_name=row.get("preferred_common_name") or row.get("english_common_name"),
                scientific_name=normalise_scientific_name(row.get("name")) or None,
                rank=row.get("rank"),
                provider="inaturalist",
                provider_taxon_id=str(row.get("id")) if row.get("id") is not None else None,
                is_bird=is_bird,
                raw=row,
            )
        )
    return out


def normalize_ala_names(payload: Any) -> list[TaxonCandidate]:
    """Normalize ALA autocomplete / name-match / search responses."""
    rows = _rows(payload, ("autoCompleteList", "searchResults", "results", "records"))
    if not rows and isinstance(payload, dict) and payload.get("scientificName"):
        rows = [payload]  # single name-match response
    out: list[TaxonCandidate] = []
    for row in rows:
        rank = str(row.get("rankString") or row.get("rank") or "").lower() or None
        common = (
            row.get("commonName")
            or row.get("commonNameSingle")
            or row.get("vernacularName")
            or row.get("name_common")
        )
        scientific = (
            row.get("scientificName") or row.get("name") or row.get("nameComplete")
        )
        kingdom = str(row.get("kingdom") or "").lower()
        class_ = str(row.get("classs") or row.get("class") or "").lower()
        is_bird = class_ == "aves" if class_ else kingdom in ("", "animalia")
        out.append(
            TaxonCandidate(
                common_name=common,
                scientific_name=normalise_scientific_name(scientific) or None,
                rank=rank,
                provider="ala",
                provider_taxon_id=row.get("guid") or row.get("lsid") or row.get("taxonConceptID"),
                is_bird=is_bird,
                raw=row,
            )
        )
    return out


def _json(response: Any) -> Any:
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    return response.json()


def search_ebird_taxonomy(
    query: str, *, api_key: str, client: HttpClient | None = None, live: bool = False
) -> list[TaxonCandidate]:
    """Opt-in eBird taxonomy lookup by common/scientific name (birds only)."""
    if not live:
        return []
    import httpx

    from birdidex.providers import EBIRD_TAXONOMY_URL, ebird_headers

    http = client or httpx.Client(timeout=60)
    response = http.get(
        EBIRD_TAXONOMY_URL,
        params={"fmt": "json", "cat": "species"},
        headers=ebird_headers(api_key),
    )
    hits = normalize_ebird_taxonomy(_json(response))
    needle = query.strip().lower()
    return [
        hit
        for hit in hits
        if needle in (hit.common_name or "").lower()
        or needle in (hit.scientific_name or "").lower()
    ]


def search_inaturalist_taxa(
    query: str, *, client: HttpClient | None = None, live: bool = False, limit: int = 10
) -> list[TaxonCandidate]:
    """Opt-in iNaturalist taxa search restricted to birds (Aves iconic taxon)."""
    if not live:
        return []
    import httpx

    http = client or httpx.Client(timeout=30)
    response = http.get(
        "https://api.inaturalist.org/v1/taxa",
        params={"q": query, "iconic_taxa": "Aves", "per_page": limit, "is_active": "true"},
    )
    return [hit for hit in normalize_inaturalist_taxa(_json(response)) if hit.is_bird]


def search_ala_names(
    query: str, *, client: HttpClient | None = None, live: bool = False, limit: int = 10
) -> list[TaxonCandidate]:
    """Opt-in Atlas of Living Australia autocomplete/name search (birds only)."""
    if not live:
        return []
    import httpx

    http = client or httpx.Client(timeout=30)
    response = http.get(
        "https://bie-ws.ala.org.au/ws/search/auto.json",
        params={"q": query, "limit": limit, "idxType": "TAXON"},
    )
    return [hit for hit in normalize_ala_names(_json(response)) if hit.is_bird]


# A descriptive User-Agent is requested etiquette for the iNaturalist and Wikimedia APIs.
USER_AGENT = "birdidex/0.1 (offline-first bird dataset; https://github.com/local/birdidex)"


def normalize_inaturalist_names(payload: Any, *, english_only: bool = True) -> list[str]:
    """Pull vernacular names from an iNaturalist ``/v1/taxa/{id}?all_names=true`` payload."""
    results = payload.get("results") if isinstance(payload, dict) else None
    detail = results[0] if isinstance(results, list) and results else None
    if detail is None:
        detail = payload if isinstance(payload, dict) else {}
    out: list[str] = []
    seen: set[str] = set()
    for entry in detail.get("names") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        locale = str(entry.get("locale") or "")
        if not name:
            continue
        if english_only and locale and not locale.lower().startswith("en"):
            continue
        key = name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(name.strip())
    return out


def fetch_inaturalist_all_names(
    taxon_id: str | int,
    *,
    client: HttpClient | None = None,
    live: bool = False,
    english_only: bool = True,
) -> list[str]:
    """Opt-in: every (English) common name iNaturalist holds for a taxon."""
    if not live:
        return []
    import httpx

    http = client or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})
    response = http.get(
        f"https://api.inaturalist.org/v1/taxa/{taxon_id}",
        params={"all_names": "true"},
    )
    return normalize_inaturalist_names(_json(response), english_only=english_only)


def normalize_wikipedia_summary(payload: Any) -> dict[str, Any] | None:
    """Normalize a Wikipedia REST summary payload to ``{title, url, extract}``."""
    if not isinstance(payload, dict):
        return None
    if str(payload.get("type", "")).endswith("not_found"):
        return None
    extract = payload.get("extract")
    if not extract:
        return None
    url = (payload.get("content_urls") or {}).get("desktop", {}).get("page")
    return {
        "title": payload.get("title"),
        "url": url or payload.get("canonicalurl"),
        "extract": extract,
    }


def fetch_wikipedia_summary(
    title: str,
    *,
    client: HttpClient | None = None,
    live: bool = False,
) -> dict[str, Any] | None:
    """Opt-in English Wikipedia REST summary for a page title (best-effort)."""
    if not live:
        return None
    from urllib.parse import quote

    import httpx

    http = client or httpx.Client(
        timeout=20, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )
    response = http.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}"
    )
    if getattr(response, "status_code", 200) >= 400:
        return None
    return normalize_wikipedia_summary(response.json())


# ---------------------------------------------------------------------------
# Curated alias overrides for well-known Australian species
#
# Keyed by ``build_species_key(scientific_name)`` so hyphen/spelling variance in
# labels does not matter. Only well-established, source-supported names go here; the
# expander adds programmatic spelling/hyphen/grey-gray variants on top.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AliasOverride:
    aliases: tuple[str, ...] = ()
    scientific_synonyms: tuple[str, ...] = ()
    rejected_names: tuple[str, ...] = ()
    notes: str = ""


ALIAS_OVERRIDES: dict[str, AliasOverride] = {
    "ephippiorhynchus_asiaticus": AliasOverride(
        aliases=("Jabiru", "Australian Jabiru", "Black-necked Stork"),
        notes="Jabiru is the widespread Australian colloquial name; canonical stays "
        "Black-necked Stork.",
    ),
    "alectura_lathami": AliasOverride(
        aliases=(
            "Australian Brush-turkey",
            "Brush Turkey",
            "Brushturkey",
            "Scrub Turkey",
            "Bush Turkey",
        ),
        notes="Common SEQ spelling variants; canonical eBird is Australian Brushturkey.",
    ),
    "dacelo_novaeguineae": AliasOverride(
        aliases=("Kookaburra", "Laughing Jackass", "Giant Kingfisher"),
    ),
    "chenonetta_jubata": AliasOverride(
        aliases=("Australian Wood Duck", "Wood Duck"),
        notes="eBird canonical 'Maned Duck'; ALA/local usage 'Australian Wood Duck'.",
    ),
    "anas_gracilis": AliasOverride(
        aliases=("Grey Teal",),
        notes="Australian 'Grey' spelling of canonical US 'Gray Teal'.",
    ),
    "thalasseus_bergii": AliasOverride(
        aliases=("Crested Tern", "Swift Tern"),
        scientific_synonyms=("Sterna bergii",),
    ),
    "numenius_phaeopus": AliasOverride(
        aliases=("Whimbrel",),
    ),
    "gelochelidon_macrotarsa": AliasOverride(
        aliases=("Australian Gull-billed Tern", "Gull-billed Tern"),
        scientific_synonyms=("Gelochelidon nilotica macrotarsa",),
    ),
    "todiramphus_sordidus": AliasOverride(
        aliases=("Collared Kingfisher", "Mangrove Kingfisher"),
        scientific_synonyms=("Todiramphus chloris sordidus",),
        notes="Australian mangrove population split from Collared Kingfisher.",
    ),
    "threskiornis_molucca": AliasOverride(
        aliases=("Australian Ibis", "Australian White Ibis", "Bin Chicken", "Sacred Ibis"),
        notes="'Bin chicken' is a well-established SEQ colloquialism.",
    ),
    "burhinus_grallarius": AliasOverride(
        aliases=("Bush Stone-curlew", "Bush Thick-knee", "Southern Stone-curlew"),
    ),
    "ardea_coromanda": AliasOverride(
        aliases=("Cattle Egret", "Eastern Cattle Egret"),
        scientific_synonyms=("Bubulcus coromandus", "Bubulcus ibis coromandus"),
    ),
}


def alias_override_for(scientific_name: str | None) -> AliasOverride | None:
    if not scientific_name:
        return None
    return ALIAS_OVERRIDES.get(slugify(normalise_scientific_name(scientific_name)))


# ---------------------------------------------------------------------------
# Curated field notes — the small natural-history / sexing details that make a
# species recognisable in the field. Keyed by build_species_key(scientific_name).
# Live Wikipedia summaries fill in the rest when enrichment runs.
# ---------------------------------------------------------------------------

FIELD_NOTES: dict[str, str] = {
    "ephippiorhynchus_asiaticus": (
        "Australia's only stork, widely called Jabiru. Sexes look alike in plumage but "
        "the eye tells them apart: the female has a bright yellow iris, the male a dark "
        "brown/black iris."
    ),
    "malurus_cyaneus": (
        "Breeding ('nuptial') males are electric blue and black; females and eclipse "
        "males are plain brown with a chestnut-red eye-ring and bill base."
    ),
    "malurus_melanocephalus": (
        "Breeding males are black with a glowing red back/shoulders; females and "
        "non-breeding males are plain warm-brown."
    ),
    "malurus_splendens": (
        "Breeding males are almost entirely brilliant blue; females are brown with a "
        "pale-blue tail and a rusty eye-ring."
    ),
    "malurus_leucopterus": (
        "Breeding males are deep blue with white wings; females are pale grey-brown with "
        "a bluish tail."
    ),
    "dacelo_novaeguineae": (
        "Largest kingfisher in the world, famous for its laughing chorus. Males often "
        "show blue in the wing and rump; females show less blue."
    ),
    "dacelo_leachii": (
        "Blue-winged Kookaburra: males have a blue tail, females a rufous tail with dark "
        "barring; both have a pale, staring eye and a raucous cackle."
    ),
    "todiramphus_sanctus": (
        "Buff-and-turquoise migrant kingfisher; a broad buff collar and a dark eye-stripe "
        "separate it from Forest Kingfisher's white collar and wing-patch."
    ),
    "todiramphus_macleayii": (
        "Forest Kingfisher: deep blue above with a bold white collar; males show a "
        "complete white collar, females a broken one."
    ),
    "ceyx_azureus": (
        "Tiny jewel of creeks and rivers — deep azure-blue above, orange below, perching "
        "low over water before plunge-diving."
    ),
    "menura_alberti": (
        "Albert's Lyrebird: a shy rainforest songbird of the McPherson Range; males give "
        "a rich mimetic song from a display platform rather than a raised tail-mound."
    ),
}


def field_note_for(scientific_name: str | None) -> str:
    if not scientific_name:
        return ""
    return FIELD_NOTES.get(slugify(normalise_scientific_name(scientific_name)), "")
