"""Ambiguous-class expansion, alias lexicon, and safe class-index regeneration.

Pipeline (all offline/deterministic unless ``live=True`` is explicitly passed):

* ``audit``            -> detect ambiguous classes, write reports
* ``expand-ambiguous`` -> map each ambiguous group to concrete Australian species
* ``build-aliases``    -> build a robust alias/search-term lexicon for clean species
* ``validate-candidate`` -> check ``class_index_candidate.json`` consistency + folder safety
* ``apply-candidate``  -> replace ``class_index.json`` only after validation passes

Nothing here downloads media, and provider calls are opt-in. The curated candidate
knowledge base in :mod:`birdidex.taxonomy_sources` is the offline source of truth;
live provider searches only enrich it.
"""

from __future__ import annotations

import csv
import json
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from birdidex.paths import data_dir, default_class_index_path, images_dir
from birdidex.taxonomy import (
    TaxonClass,
    build_species_key,
    load_class_index,
    normalise_scientific_name,
    slugify,
)
from birdidex.taxonomy_sources import (
    SOURCE_CURATED,
    SOURCE_ROI_LOCAL,
    AmbiguousGroup,
    GroupCandidate,
    alias_override_for,
    field_note_for,
    match_group,
)

# Statuses whose candidates may be auto-added to the candidate index as new classes.
_ADDABLE_STATUSES: frozenset[str] = frozenset({"confirmed_roi", "likely_roi"})

_LIST_SEP = "|"


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------


def taxonomy_dir() -> Path:
    return data_dir() / "taxonomy"


def ambiguous_classes_csv_path() -> Path:
    return taxonomy_dir() / "ambiguous_classes.csv"


def ambiguous_expansion_candidates_csv_path() -> Path:
    return taxonomy_dir() / "ambiguous_expansion_candidates.csv"


def alias_lexicon_json_path() -> Path:
    return taxonomy_dir() / "alias_lexicon.json"


def alias_lexicon_csv_path() -> Path:
    return taxonomy_dir() / "alias_lexicon.csv"


def taxonomy_audit_json_path() -> Path:
    return taxonomy_dir() / "taxonomy_audit.json"


def taxonomy_audit_md_path() -> Path:
    return taxonomy_dir() / "taxonomy_audit.md"


def class_index_candidate_path() -> Path:
    return taxonomy_dir() / "class_index_candidate.json"


def class_replacement_map_csv_path() -> Path:
    return taxonomy_dir() / "class_replacement_map.csv"


def manual_overrides_example_path() -> Path:
    return taxonomy_dir() / "manual_overrides.example.toml"


def manual_overrides_local_path() -> Path:
    return taxonomy_dir() / "manual_overrides.local.toml"


def _local_roi_presence_csv() -> Path:
    return default_class_index_path().parent / "region_species_presence.csv"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Manual overrides
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManualOverrides:
    """Local Australian naming decisions loaded from a TOML override file."""

    status_by_scientific: dict[str, str] = field(default_factory=dict)
    extra_candidates: dict[str, tuple[GroupCandidate, ...]] = field(default_factory=dict)
    alias_add: dict[str, tuple[str, ...]] = field(default_factory=dict)
    alias_reject: dict[str, tuple[str, ...]] = field(default_factory=dict)
    source_path: str | None = None

    def status_for(self, scientific_name: str | None) -> str | None:
        if not scientific_name:
            return None
        return self.status_by_scientific.get(build_species_key(scientific_name))


def load_manual_overrides(path: Path | None = None) -> ManualOverrides:
    """Load manual overrides from TOML, tolerating a missing file."""
    target = path or manual_overrides_local_path()
    if not target.exists():
        return ManualOverrides()
    data = tomllib.loads(target.read_text(encoding="utf-8"))

    status_by_scientific: dict[str, str] = {}
    for name, status in (data.get("status_overrides") or {}).items():
        status_by_scientific[build_species_key(name)] = str(status)

    extra_candidates: dict[str, tuple[GroupCandidate, ...]] = {}
    for group_key, group_data in (data.get("groups") or {}).items():
        rows = group_data.get("candidates") if isinstance(group_data, dict) else None
        candidates: list[GroupCandidate] = []
        for row in rows or []:
            candidates.append(
                GroupCandidate(
                    common_name=str(row["common_name"]),
                    scientific_name=normalise_scientific_name(row["scientific_name"]),
                    status_hint=str(row.get("status", "uncertain")),
                    evidence=(SOURCE_CURATED,),
                    notes=str(row.get("notes", "")),
                )
            )
        if candidates:
            extra_candidates[group_key] = tuple(candidates)

    alias_add: dict[str, tuple[str, ...]] = {}
    alias_reject: dict[str, tuple[str, ...]] = {}
    for name, spec in (data.get("aliases") or {}).items():
        key = build_species_key(name)
        if isinstance(spec, dict):
            if spec.get("add"):
                alias_add[key] = tuple(str(item) for item in spec["add"])
            if spec.get("reject"):
                alias_reject[key] = tuple(str(item) for item in spec["reject"])
        elif isinstance(spec, list):
            alias_add[key] = tuple(str(item) for item in spec)

    return ManualOverrides(
        status_by_scientific=status_by_scientific,
        extra_candidates=extra_candidates,
        alias_add=alias_add,
        alias_reject=alias_reject,
        source_path=str(target),
    )


# ---------------------------------------------------------------------------
# Local ROI evidence
# ---------------------------------------------------------------------------


def load_local_roi_presence(path: Path | None = None) -> dict[str, list[str]]:
    """Return ``scientific_name(lower) -> sorted regions`` from local ROI records."""
    target = path or _local_roi_presence_csv()
    presence: dict[str, set[str]] = {}
    if not target.exists():
        return {}
    with target.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sci = normalise_scientific_name(row.get("scientific_name")).lower()
            region = (row.get("region") or "").strip()
            if sci and region:
                presence.setdefault(sci, set()).add(region)
    return {sci: sorted(regions) for sci, regions in presence.items()}


# ---------------------------------------------------------------------------
# Ambiguous-class audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AmbiguousRecord:
    taxon: TaxonClass
    reasons: tuple[str, ...]
    group: AmbiguousGroup | None

    @property
    def group_key(self) -> str:
        return self.group.group_key if self.group else ""


def detect_ambiguous(classes: list[TaxonClass]) -> list[AmbiguousRecord]:
    """Return every ambiguous class with its reasons and matched curated group."""
    records: list[AmbiguousRecord] = []
    for taxon in classes:
        reasons = taxon.ambiguity_reasons
        if reasons:
            records.append(AmbiguousRecord(taxon, reasons, match_group(taxon)))
    return records


# ---------------------------------------------------------------------------
# Expansion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpansionCandidate:
    old_class_id: int
    old_label: str
    old_common_name: str
    old_scientific_name: str
    group_key: str
    candidate_common_name: str
    candidate_scientific_name: str
    status: str
    existing_class_id: int | None
    existing_label: str | None
    roi_regions: tuple[str, ...]
    evidence: tuple[str, ...]
    add_to_candidate_index: bool
    notes: str

    @property
    def replacement_label(self) -> str:
        return self.existing_label or slugify(self.candidate_common_name)


def _reconcile_status(
    candidate: GroupCandidate,
    *,
    existing: TaxonClass | None,
    roi_regions: list[str],
    overrides: ManualOverrides,
) -> str:
    forced = overrides.status_for(candidate.scientific_name)
    if forced:
        return forced
    if candidate.status_hint == "reject":
        return "reject"
    if roi_regions:
        return "confirmed_roi"
    if existing is not None and candidate.status_hint in _ADDABLE_STATUSES:
        # An existing clean class is at least a likely ROI species.
        if candidate.status_hint == "australian_but_not_roi":
            return "likely_roi"
        return candidate.status_hint
    return candidate.status_hint


def expand_ambiguous(
    classes: list[TaxonClass],
    *,
    overrides: ManualOverrides | None = None,
    roi_presence: dict[str, list[str]] | None = None,
) -> list[ExpansionCandidate]:
    """Expand every ambiguous class into concrete candidate species."""
    overrides = overrides or ManualOverrides()
    roi_presence = roi_presence if roi_presence is not None else load_local_roi_presence()
    clean_by_sci = {
        build_species_key(taxon.scientific_name): taxon
        for taxon in classes
        if taxon.scientific_name and not taxon.is_ambiguous
    }

    out: list[ExpansionCandidate] = []
    for record in detect_ambiguous(classes):
        group = record.group
        taxon = record.taxon
        candidates: list[GroupCandidate] = list(group.candidates) if group else []
        if group and group.group_key in overrides.extra_candidates:
            candidates.extend(overrides.extra_candidates[group.group_key])

        for candidate in candidates:
            sci_key = build_species_key(candidate.scientific_name)
            existing = clean_by_sci.get(sci_key)
            roi_regions = roi_presence.get(candidate.scientific_name.lower(), [])
            status = _reconcile_status(
                candidate, existing=existing, roi_regions=roi_regions, overrides=overrides
            )
            evidence = list(candidate.evidence)
            if roi_regions and SOURCE_ROI_LOCAL not in evidence:
                evidence.append(SOURCE_ROI_LOCAL)
            add = (
                existing is None
                and status != "reject"
                and (candidate.always_include or status in _ADDABLE_STATUSES)
            )
            out.append(
                ExpansionCandidate(
                    old_class_id=taxon.class_id,
                    old_label=taxon.label,
                    old_common_name=taxon.common_name,
                    old_scientific_name=taxon.scientific_name or "",
                    group_key=record.group_key,
                    candidate_common_name=candidate.common_name,
                    candidate_scientific_name=candidate.scientific_name,
                    status=status,
                    existing_class_id=existing.class_id if existing else None,
                    existing_label=existing.label if existing else None,
                    roi_regions=tuple(roi_regions),
                    evidence=tuple(evidence),
                    add_to_candidate_index=add,
                    notes=candidate.notes,
                )
            )
    return out


# ---------------------------------------------------------------------------
# Alias lexicon
# ---------------------------------------------------------------------------


@dataclass
class AliasRecord:
    class_id: int
    label: str
    canonical_common_name: str
    canonical_scientific_name: str | None
    ebird_species_code: str | None = None
    inaturalist_taxon_id: str | None = None
    ala_guid_or_lsid: str | None = None
    gbif_taxon_key: str | None = None
    aliases: list[str] = field(default_factory=list)
    scientific_synonyms: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    rejected_names: list[str] = field(default_factory=list)
    source_records: list[str] = field(default_factory=list)
    confidence: str = "medium"
    notes: str = ""
    field_notes: str = ""
    wikipedia_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_id": self.class_id,
            "label": self.label,
            "canonical_common_name": self.canonical_common_name,
            "canonical_scientific_name": self.canonical_scientific_name,
            "eBird_species_code": self.ebird_species_code,
            "iNaturalist_taxon_id": self.inaturalist_taxon_id,
            "ALA_guid_or_lsid": self.ala_guid_or_lsid,
            "GBIF_taxon_key": self.gbif_taxon_key,
            "aliases": self.aliases,
            "scientific_synonyms": self.scientific_synonyms,
            "search_terms": self.search_terms,
            "rejected_names": self.rejected_names,
            "source_records": self.source_records,
            "confidence": self.confidence,
            "notes": self.notes,
            "field_notes": self.field_notes,
            "wikipedia_url": self.wikipedia_url,
        }


def _swap_grey_gray(text: str) -> list[str]:
    """Return Grey<->Gray spelling variants of ``text`` (case-preserving)."""
    out: list[str] = []
    lowered = text.lower()
    if "grey" in lowered:
        out.append(_ci_replace(text, "grey", "gray"))
    if "gray" in lowered:
        out.append(_ci_replace(text, "gray", "grey"))
    return out


def _ci_replace(text: str, old: str, new: str) -> str:
    """Case-insensitively replace ``old`` with ``new``, matching leading capitalization."""
    result: list[str] = []
    idx = 0
    lowered = text.lower()
    target = old.lower()
    while idx < len(text):
        if lowered.startswith(target, idx):
            chunk = text[idx : idx + len(old)]
            replacement = new.capitalize() if chunk[:1].isupper() else new
            result.append(replacement)
            idx += len(old)
        else:
            result.append(text[idx])
            idx += 1
    return "".join(result)


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        cleaned = item.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def generate_common_name_variants(common: str) -> list[str]:
    """Programmatic hyphen / apostrophe / grey-gray variants of a common name."""
    variants = [common]
    if "-" in common:
        variants.append(common.replace("-", " "))
    if " " in common and "-" not in common:
        # A conservative hyphenation is not attempted; only the de-hyphen direction is safe.
        pass
    if "'" in common or "’" in common:
        variants.append(common.replace("'", "").replace("’", ""))
        variants.append(common.replace("'", "").replace("’", "").replace("s ", "s "))
    for variant in list(variants):
        variants.extend(_swap_grey_gray(variant))
    # Compact spacing after substitutions.
    return _dedup_keep_order([" ".join(v.split()) for v in variants])


def build_alias_record(
    taxon: TaxonClass,
    *,
    overrides: ManualOverrides | None = None,
) -> AliasRecord:
    """Build the alias/search-term record for one clean species class."""
    overrides = overrides or ManualOverrides()
    common = taxon.common_name
    scientific = taxon.scientific_name
    override = alias_override_for(scientific)
    sci_key = build_species_key(scientific) if scientific else ""

    source_records = ["class_index.json"]
    confidence = "medium"

    aliases: list[str] = generate_common_name_variants(common)
    aliases.extend(taxon.aliases)
    scientific_synonyms: list[str] = []
    rejected_names: list[str] = []
    notes = ""

    if override is not None:
        confidence = "high"
        source_records.append(SOURCE_CURATED)
        for name in override.aliases:
            aliases.append(name)
            aliases.extend(generate_common_name_variants(name))
        scientific_synonyms.extend(override.scientific_synonyms)
        rejected_names.extend(override.rejected_names)
        notes = override.notes

    aliases.extend(overrides.alias_add.get(sci_key, ()))
    reject = {name.lower() for name in overrides.alias_reject.get(sci_key, ())}

    aliases = [name for name in _dedup_keep_order(aliases) if name.lower() not in reject]

    # Search terms lead with the most precise identifier (scientific), then canonical
    # common name and its spelling variants. The bare species epithet is included last
    # as a low-confidence keyword only.
    search_terms: list[str] = []
    if scientific:
        search_terms.append(scientific)
    search_terms.append(common)
    search_terms.extend(generate_common_name_variants(common))
    search_terms.extend(a for a in aliases if a.lower() != common.lower())
    if scientific and len(scientific.split()) >= 2:
        search_terms.append(scientific.split()[1])  # species epithet, low confidence
    search_terms = [t for t in _dedup_keep_order(search_terms) if t.lower() not in reject]

    return AliasRecord(
        class_id=taxon.class_id,
        label=taxon.label,
        canonical_common_name=common,
        canonical_scientific_name=scientific,
        aliases=aliases,
        scientific_synonyms=_dedup_keep_order(scientific_synonyms),
        search_terms=search_terms,
        rejected_names=_dedup_keep_order(rejected_names),
        source_records=source_records,
        confidence=confidence,
        notes=notes,
        field_notes=field_note_for(scientific),
    )


def build_alias_lexicon(
    classes: list[TaxonClass],
    *,
    overrides: ManualOverrides | None = None,
) -> list[AliasRecord]:
    """Build alias records for every clean (non-ambiguous) species class."""
    return [
        build_alias_record(taxon, overrides=overrides)
        for taxon in classes
        if not taxon.is_ambiguous
    ]


def write_alias_lexicon(records: list[AliasRecord]) -> tuple[Path, Path]:
    json_path = alias_lexicon_json_path()
    _write_json(
        json_path,
        {
            "generated_at": _utc_now(),
            "n_species": len(records),
            "schema": [
                "class_id",
                "label",
                "canonical_common_name",
                "canonical_scientific_name",
                "eBird_species_code",
                "iNaturalist_taxon_id",
                "ALA_guid_or_lsid",
                "GBIF_taxon_key",
                "aliases",
                "scientific_synonyms",
                "search_terms",
                "rejected_names",
                "source_records",
                "confidence",
                "notes",
                "field_notes",
                "wikipedia_url",
            ],
            "records": [record.to_dict() for record in records],
        },
    )
    csv_path = alias_lexicon_csv_path()
    _write_csv(
        csv_path,
        [
            "class_id",
            "label",
            "canonical_common_name",
            "canonical_scientific_name",
            "aliases",
            "scientific_synonyms",
            "search_terms",
            "rejected_names",
            "confidence",
            "notes",
            "field_notes",
            "wikipedia_url",
        ],
        [
            {
                "class_id": record.class_id,
                "label": record.label,
                "canonical_common_name": record.canonical_common_name,
                "canonical_scientific_name": record.canonical_scientific_name or "",
                "aliases": _LIST_SEP.join(record.aliases),
                "scientific_synonyms": _LIST_SEP.join(record.scientific_synonyms),
                "search_terms": _LIST_SEP.join(record.search_terms),
                "rejected_names": _LIST_SEP.join(record.rejected_names),
                "confidence": record.confidence,
                "notes": record.notes,
                "field_notes": record.field_notes,
                "wikipedia_url": record.wikipedia_url or "",
            }
            for record in records
        ],
    )
    return json_path, csv_path


# ---------------------------------------------------------------------------
# Candidate class index + replacement map
# ---------------------------------------------------------------------------


def _embed_alias_fields(base: dict[str, Any], rec: AliasRecord) -> None:
    """Copy alias/search/enrichment fields from an AliasRecord onto a class record."""
    base["aliases"] = rec.aliases
    if rec.search_terms:
        base["search_terms"] = rec.search_terms
    if rec.field_notes:
        base["field_notes"] = rec.field_notes
    if rec.wikipedia_url:
        base["wikipedia_url"] = rec.wikipedia_url
    if rec.ebird_species_code:
        base["ebird_species_code"] = rec.ebird_species_code
    if rec.inaturalist_taxon_id:
        base["inaturalist_taxon_id"] = rec.inaturalist_taxon_id


def build_candidate_index(
    classes: list[TaxonClass],
    expansion: list[ExpansionCandidate],
    *,
    alias_records: list[AliasRecord] | None = None,
) -> dict[str, Any]:
    """Build the candidate class index without overwriting the canonical one.

    Existing clean classes keep their ``class_id``; ambiguous classes are marked
    ``deprecated`` (never deleted) and annotated with their replacement class ids; new
    concrete species (addable status, not already present) get fresh appended ids.
    """
    records_by_id = {rec.class_id: rec for rec in (alias_records or [])}
    ambiguous_records = {rec.taxon.class_id: rec for rec in detect_ambiguous(classes)}

    # New species to append: addable, no existing clean class, de-duplicated by sci name.
    existing_sci = {
        build_species_key(taxon.scientific_name)
        for taxon in classes
        if taxon.scientific_name
    }
    new_species: dict[str, ExpansionCandidate] = {}
    for cand in expansion:
        key = build_species_key(cand.candidate_scientific_name)
        if cand.add_to_candidate_index and key not in existing_sci and key not in new_species:
            new_species[key] = cand

    next_id = (max((taxon.class_id for taxon in classes), default=-1)) + 1
    new_id_by_sci: dict[str, int] = {}
    for key in sorted(new_species):
        new_id_by_sci[key] = next_id
        next_id += 1

    # Map each ambiguous class -> the concrete class ids it now expands into. Rejected
    # candidates (e.g. name collisions) are never listed as replacements.
    replacements_by_old: dict[int, list[int]] = {}
    for cand in expansion:
        if cand.status == "reject":
            continue
        key = build_species_key(cand.candidate_scientific_name)
        target_id = cand.existing_class_id
        if target_id is None:
            target_id = new_id_by_sci.get(key)
        if target_id is not None:
            replacements_by_old.setdefault(cand.old_class_id, [])
            if target_id not in replacements_by_old[cand.old_class_id]:
                replacements_by_old[cand.old_class_id].append(target_id)

    records: list[dict[str, Any]] = []
    for taxon in classes:
        base = dict(taxon.raw)
        base["class_id"] = taxon.class_id
        base["label"] = taxon.label
        base["common_name"] = taxon.common_name
        base["scientific_name"] = taxon.scientific_name
        if taxon.class_id in records_by_id:
            _embed_alias_fields(base, records_by_id[taxon.class_id])
        if taxon.class_id in ambiguous_records:
            rec = ambiguous_records[taxon.class_id]
            base["deprecated"] = True
            base["status"] = "deprecated_ambiguous"
            base["ambiguity_reasons"] = list(rec.reasons)
            base["replacement_class_ids"] = sorted(replacements_by_old.get(taxon.class_id, []))
        else:
            base.setdefault("status", "active")
        records.append(base)

    # Append new concrete species.
    new_by_id = {new_id: new_species[key] for key, new_id in new_id_by_sci.items()}
    for new_id in sorted(new_by_id):
        cand = new_by_id[new_id]
        temp = TaxonClass(
            class_id=new_id,
            label=slugify(cand.candidate_common_name),
            common_name=cand.candidate_common_name,
            scientific_name=cand.candidate_scientific_name,
        )
        alias_rec = records_by_id.get(new_id) or build_alias_record(temp)
        record = {
            "class_id": new_id,
            "label": temp.label,
            "common_name": cand.candidate_common_name,
            "scientific_name": cand.candidate_scientific_name,
            "known_regions": list(cand.roi_regions),
            "source_files": [],
            "observation_count": 0,
            "status": "proposed_new",
            "expansion_status": cand.status,
            "expanded_from_class_id": cand.old_class_id,
            "expanded_from_label": cand.old_label,
            "evidence": list(cand.evidence),
        }
        _embed_alias_fields(record, alias_rec)
        records.append(record)

    return {
        "version": 2,
        "class_id_policy": "existing_ids_retained__new_species_appended",
        "generated_at": _utc_now(),
        "source": "birdidex taxonomy expand-ambiguous",
        "n_classes": len(records),
        "n_deprecated": sum(1 for r in records if r.get("deprecated")),
        "n_proposed_new": len(new_by_id),
        "classes": records,
    }


def write_candidate_index(payload: dict[str, Any], path: Path | None = None) -> Path:
    """Write the candidate class index JSON (never the canonical class_index.json)."""
    target = path or class_index_candidate_path()
    _write_json(target, payload)
    return target


def build_enriched_candidate(
    classes: list[TaxonClass],
    expansion: list[ExpansionCandidate],
    *,
    overrides: ManualOverrides | None = None,
    live: bool = False,
    ebird_api_key: str | None = None,
    use_wikipedia: bool = False,
    throttle: float = 0.25,
    progress: Any = None,
) -> tuple[dict[str, Any], list[AliasRecord], list[str]]:
    """Build the candidate index and its alias lexicon together.

    Aliases are built over the *candidate* classes (existing clean species **plus** the
    newly proposed ones) so new species also receive curated + scoured aliases. When
    ``live`` is set, the alias records are enriched from iNaturalist/eBird/Wikipedia and
    embedded back into the candidate index (matched by stable class id).
    """
    overrides = overrides or ManualOverrides()
    # First pass (offline) assigns stable ids to the new species.
    offline = build_candidate_index(classes, expansion)
    candidate_classes = _classes_from_payload(offline)
    alias_records = build_alias_lexicon(candidate_classes, overrides=overrides)

    errors: list[str] = []
    if live:
        errors = enrich_aliases_live(
            alias_records,
            ebird_api_key=ebird_api_key,
            use_wikipedia=use_wikipedia,
            throttle=throttle,
            progress=progress,
        )
    candidate = build_candidate_index(classes, expansion, alias_records=alias_records)
    return candidate, alias_records, errors


def _classes_from_payload(payload: dict[str, Any]) -> list[TaxonClass]:
    """Load a class list from an in-memory candidate index payload (validates it)."""
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as handle:
        json.dump(payload, handle)
        temp_path = Path(handle.name)
    try:
        return load_class_index(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def build_replacement_rows(expansion: list[ExpansionCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "old_class_id": cand.old_class_id,
            "old_label": cand.old_label,
            "old_common_name": cand.old_common_name,
            "old_scientific_name": cand.old_scientific_name,
            "replacement_label": cand.replacement_label,
            "replacement_common_name": cand.candidate_common_name,
            "replacement_scientific_name": cand.candidate_scientific_name,
            "replacement_status": cand.status,
            "evidence_sources": _LIST_SEP.join(cand.evidence),
            "notes": cand.notes,
        }
        for cand in expansion
    ]


REPLACEMENT_MAP_FIELDS = [
    "old_class_id",
    "old_label",
    "old_common_name",
    "old_scientific_name",
    "replacement_label",
    "replacement_common_name",
    "replacement_scientific_name",
    "replacement_status",
    "evidence_sources",
    "notes",
]


# ---------------------------------------------------------------------------
# Report writers (audit + expansion CSVs)
# ---------------------------------------------------------------------------


def write_ambiguous_reports(
    classes: list[TaxonClass],
    expansion: list[ExpansionCandidate],
) -> dict[str, Any]:
    """Write the ambiguous-class + expansion + audit reports; return the audit summary."""
    ambiguous = detect_ambiguous(classes)
    candidates_by_old: dict[int, list[ExpansionCandidate]] = {}
    for cand in expansion:
        candidates_by_old.setdefault(cand.old_class_id, []).append(cand)

    _write_csv(
        ambiguous_classes_csv_path(),
        [
            "class_id",
            "label",
            "common_name",
            "scientific_name",
            "ambiguity_reasons",
            "group_key",
            "n_candidates",
            "n_addable_candidates",
            "resolved",
            "action",
        ],
        [
            {
                "class_id": rec.taxon.class_id,
                "label": rec.taxon.label,
                "common_name": rec.taxon.common_name,
                "scientific_name": rec.taxon.scientific_name or "",
                "ambiguity_reasons": _LIST_SEP.join(rec.reasons),
                "group_key": rec.group_key,
                "n_candidates": len(candidates_by_old.get(rec.taxon.class_id, [])),
                "n_addable_candidates": sum(
                    1
                    for c in candidates_by_old.get(rec.taxon.class_id, [])
                    if c.add_to_candidate_index
                ),
                "resolved": str(bool(candidates_by_old.get(rec.taxon.class_id))).lower(),
                "action": "deprecate_and_expand"
                if candidates_by_old.get(rec.taxon.class_id)
                else "deprecate_needs_manual_review",
            }
            for rec in ambiguous
        ],
    )

    _write_csv(
        ambiguous_expansion_candidates_csv_path(),
        [
            "old_class_id",
            "old_label",
            "group_key",
            "candidate_common_name",
            "candidate_scientific_name",
            "status",
            "existing_class_id",
            "existing_label",
            "in_local_roi",
            "roi_regions",
            "evidence",
            "add_to_candidate_index",
            "notes",
        ],
        [
            {
                "old_class_id": cand.old_class_id,
                "old_label": cand.old_label,
                "group_key": cand.group_key,
                "candidate_common_name": cand.candidate_common_name,
                "candidate_scientific_name": cand.candidate_scientific_name,
                "status": cand.status,
                "existing_class_id": cand.existing_class_id
                if cand.existing_class_id is not None
                else "",
                "existing_label": cand.existing_label or "",
                "in_local_roi": str(bool(cand.roi_regions)).lower(),
                "roi_regions": _LIST_SEP.join(cand.roi_regions),
                "evidence": _LIST_SEP.join(cand.evidence),
                "add_to_candidate_index": str(cand.add_to_candidate_index).lower(),
                "notes": cand.notes,
            }
            for cand in expansion
        ],
    )

    _write_csv(
        class_replacement_map_csv_path(),
        REPLACEMENT_MAP_FIELDS,
        build_replacement_rows(expansion),
    )

    summary = _audit_summary(classes, ambiguous, expansion, candidates_by_old)
    _write_json(taxonomy_audit_json_path(), summary)
    _write_audit_markdown(summary)
    return summary


def _audit_summary(
    classes: list[TaxonClass],
    ambiguous: list[AmbiguousRecord],
    expansion: list[ExpansionCandidate],
    candidates_by_old: dict[int, list[ExpansionCandidate]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for cand in expansion:
        status_counts[cand.status] = status_counts.get(cand.status, 0) + 1
    return {
        "generated_at": _utc_now(),
        "class_index": str(default_class_index_path()),
        "provider_mode": "offline_curated (live provider searches are opt-in)",
        "n_classes": len(classes),
        "n_clean_classifier_classes": sum(1 for t in classes if t.clean_classifier_class),
        "n_ambiguous_classes": len(ambiguous),
        "n_expansion_candidates": len(expansion),
        "n_addable_new_species": len({
            build_species_key(c.candidate_scientific_name)
            for c in expansion
            if c.add_to_candidate_index and c.existing_class_id is None
        }),
        "candidate_status_counts": status_counts,
        "ambiguous_classes": [
            {
                "class_id": rec.taxon.class_id,
                "label": rec.taxon.label,
                "common_name": rec.taxon.common_name,
                "scientific_name": rec.taxon.scientific_name,
                "ambiguity_reasons": list(rec.reasons),
                "group_key": rec.group_key,
                "candidates": [
                    {
                        "common_name": c.candidate_common_name,
                        "scientific_name": c.candidate_scientific_name,
                        "status": c.status,
                        "existing_class_id": c.existing_class_id,
                        "roi_regions": list(c.roi_regions),
                        "evidence": list(c.evidence),
                        "add_to_candidate_index": c.add_to_candidate_index,
                        "notes": c.notes,
                    }
                    for c in candidates_by_old.get(rec.taxon.class_id, [])
                ],
            }
            for rec in ambiguous
        ],
    }


def _audit_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# BIRDIDEX taxonomy audit",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"- Classes: **{summary['n_classes']}**",
        f"- Clean classifier classes: **{summary['n_clean_classifier_classes']}**",
        f"- Ambiguous classes: **{summary['n_ambiguous_classes']}**",
        f"- Expansion candidates: **{summary['n_expansion_candidates']}**",
        f"- Proposed new species: **{summary['n_addable_new_species']}**",
        f"- Provider mode: {summary['provider_mode']}",
        "",
        "Ambiguous classes are **deprecated, never deleted**, and excluded from automatic "
        "image download/training. Concrete replacements are proposed below; review "
        "`class_index_candidate.json` before running `taxonomy apply-candidate --confirm`.",
        "",
        "## Ambiguous classes and proposed replacements",
        "",
    ]
    for entry in summary["ambiguous_classes"]:
        lines.append(
            f"### {entry['class_id']:03d} · {entry['common_name']} "
            f"(`{entry['scientific_name']}`)"
        )
        lines.append("")
        lines.append(f"- Reasons: {', '.join(entry['ambiguity_reasons'])}")
        lines.append(f"- Group: `{entry['group_key'] or '(unmatched — manual review)'}`")
        lines.append("")
        if entry["candidates"]:
            lines.append("| Candidate | Scientific | Status | Existing id | ROI | Add? |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for cand in entry["candidates"]:
                existing = cand["existing_class_id"]
                roi = ", ".join(cand["roi_regions"]) or "—"
                lines.append(
                    f"| {cand['common_name']} | *{cand['scientific_name']}* | "
                    f"{cand['status']} | {existing if existing is not None else '—'} | "
                    f"{roi} | {'yes' if cand['add_to_candidate_index'] else 'no'} |"
                )
        else:
            lines.append("_No curated candidates — needs manual review._")
        lines.append("")
    return "\n".join(lines) + "\n"


def _write_audit_markdown(summary: dict[str, Any]) -> None:
    path = taxonomy_audit_md_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_audit_markdown(summary), encoding="utf-8")


# ---------------------------------------------------------------------------
# Validation + apply
# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def validate_candidate_index(
    candidate_path: Path | None = None,
    *,
    images_root: Path | None = None,
) -> ValidationReport:
    """Validate the candidate class index and check image-folder safety."""
    path = candidate_path or class_index_candidate_path()
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return ValidationReport(False, [f"candidate index not found: {path}"])

    try:
        # load_class_index enforces required fields and rejects duplicate ids/labels/folders.
        classes = load_class_index(path)
    except ValueError as exc:
        return ValidationReport(False, [f"class index invalid: {exc}"])

    # No duplicate scientific names among active (non-deprecated) classes.
    seen_sci: dict[str, int] = {}
    for taxon in classes:
        if taxon.is_deprecated or not taxon.scientific_name:
            continue
        key = build_species_key(taxon.scientific_name)
        if key in seen_sci:
            errors.append(
                f"duplicate scientific name among active classes: "
                f"{taxon.scientific_name} (ids {seen_sci[key]} and {taxon.class_id})"
            )
        seen_sci[key] = taxon.class_id

    # Every ambiguous class must be marked deprecated (excluded from clean/download).
    for taxon in classes:
        if taxon.is_ambiguous and not taxon.is_deprecated:
            errors.append(
                f"ambiguous class not marked deprecated: {taxon.class_id} {taxon.label}"
            )
        if taxon.is_deprecated and taxon.clean_classifier_class:
            errors.append(f"deprecated class still counted as clean: {taxon.class_id}")

    # Folder safety: existing image folders that are not in the candidate index, and
    # deprecated folders that still hold images (manual review required — nothing moved).
    root = images_root or images_dir()
    folder_report = scan_deprecated_folders(classes, images_root=root)
    for extra in folder_report["extra_folders"]:
        warnings.append(f"image folder not in candidate index: {extra}")
    for entry in folder_report["deprecated_with_images"]:
        warnings.append(
            f"deprecated folder holds {entry['image_count']} image(s), quarantine/review "
            f"before removal: {entry['folder']}"
        )

    summary = {
        "candidate_path": str(path),
        "n_classes": len(classes),
        "n_clean": sum(1 for t in classes if t.clean_classifier_class),
        "n_deprecated": sum(1 for t in classes if t.is_deprecated),
        "n_proposed_new": sum(1 for t in classes if t.raw.get("status") == "proposed_new"),
        "extra_image_folders": len(folder_report["extra_folders"]),
        "deprecated_folders_with_images": len(folder_report["deprecated_with_images"]),
    }
    return ValidationReport(not errors, errors, warnings, summary)


def scan_deprecated_folders(
    classes: list[TaxonClass],
    *,
    images_root: Path | None = None,
) -> dict[str, Any]:
    """Report image folders vs the class index without moving any files."""
    from birdidex.images import scan_class_folders

    return scan_class_folders(classes, images_root=images_root or images_dir())


# ---------------------------------------------------------------------------
# Opt-in live provider enrichment (best-effort; never required, never tested live
# in a plain pytest run). Uses the taxonomy-search helpers, all guarded.
# ---------------------------------------------------------------------------


def _taxonomy_cache_dir() -> Path:
    return data_dir() / "cache" / "taxonomy"


def _trim_extract(text: str, limit: int = 400) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(".,;") + "…"


def _scour_one(
    common: str,
    scientific: str | None,
    *,
    inat_client: Any,
    wiki_client: Any,
    use_inaturalist: bool,
    use_wikipedia: bool,
) -> dict[str, Any]:
    """Fetch iNaturalist all-names (+ optional Wikipedia summary) for one species."""
    from birdidex import taxonomy_sources as ts

    blob: dict[str, Any] = {
        "inat_taxon_id": None,
        "inat_names": [],
        "wikipedia": None,
        "errors": [],
    }
    sci_lower = (scientific or "").lower()
    if use_inaturalist and inat_client is not None:
        try:
            hits = ts.search_inaturalist_taxa(scientific or common, client=inat_client, live=True)
            match = next(
                (h for h in hits if (h.scientific_name or "").lower() == sci_lower),
                hits[0] if hits else None,
            )
            if match is not None:
                blob["inat_taxon_id"] = match.provider_taxon_id
                names = [match.common_name] if match.common_name else []
                if match.provider_taxon_id:
                    names += ts.fetch_inaturalist_all_names(
                        match.provider_taxon_id, client=inat_client, live=True
                    )
                blob["inat_names"] = _dedup_keep_order(names)
        except Exception as exc:  # noqa: BLE001 - network failures are non-fatal
            blob["errors"].append(f"inaturalist[{common}]: {type(exc).__name__}: {exc}")
    if use_wikipedia and wiki_client is not None:
        for title in [t for t in (common, scientific) if t]:
            try:
                summary = ts.fetch_wikipedia_summary(title, client=wiki_client, live=True)
            except Exception as exc:  # noqa: BLE001
                blob["errors"].append(f"wikipedia[{title}]: {type(exc).__name__}: {exc}")
                continue
            if summary:
                blob["wikipedia"] = summary
                break
    return blob


def _scour_species_cached(
    common: str,
    scientific: str | None,
    *,
    inat_client: Any,
    wiki_client: Any,
    use_inaturalist: bool,
    use_wikipedia: bool,
    cache: bool,
) -> tuple[dict[str, Any], bool]:
    key = scientific or common
    path = _taxonomy_cache_dir() / "species" / f"{slugify(key)}.json"
    if cache and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")), True
        except json.JSONDecodeError:
            pass
    blob = _scour_one(
        common,
        scientific,
        inat_client=inat_client,
        wiki_client=wiki_client,
        use_inaturalist=use_inaturalist,
        use_wikipedia=use_wikipedia,
    )
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    return blob, False


def enrich_aliases_live(
    records: list[AliasRecord],
    *,
    ebird_api_key: str | None = None,
    use_inaturalist: bool = True,
    use_wikipedia: bool = False,
    throttle: float = 0.25,
    cache: bool = True,
    progress: Any = None,
) -> list[str]:
    """Scour iNaturalist (all names) + eBird codes (+ optional Wikipedia) into records.

    Mutates ``records`` in place; returns non-fatal provider error strings. Responses are
    cached under ``data/cache/taxonomy`` so reruns are cheap and interruptible; the
    network is only touched on a cache miss (throttled between species).
    """
    import time

    import httpx

    from birdidex import taxonomy_sources as ts

    errors: list[str] = []
    ebird_map: dict[str, str] = {}
    if ebird_api_key:
        try:
            from birdidex.providers import load_ebird_taxonomy

            ebird_map = load_ebird_taxonomy(api_key=ebird_api_key)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ebird_taxonomy: {type(exc).__name__}: {exc}")

    headers = {"User-Agent": ts.USER_AGENT}
    inat_client = httpx.Client(timeout=30, headers=headers) if use_inaturalist else None
    wiki_client = (
        httpx.Client(timeout=20, headers=headers, follow_redirects=True) if use_wikipedia else None
    )
    try:
        for index, record in enumerate(records):
            sci = record.canonical_scientific_name
            common = record.canonical_common_name
            if ebird_map and sci:
                code = ebird_map.get(normalise_scientific_name(sci).lower())
                if code:
                    record.ebird_species_code = code
                    _add_source(record, "ebird_taxonomy")

            if not (use_inaturalist or use_wikipedia):
                if progress is not None:
                    progress(index + 1, len(records), common)
                continue

            blob, from_cache = _scour_species_cached(
                common,
                sci,
                inat_client=inat_client,
                wiki_client=wiki_client,
                use_inaturalist=use_inaturalist,
                use_wikipedia=use_wikipedia,
                cache=cache,
            )
            errors.extend(blob.get("errors", []))

            if blob.get("inat_taxon_id"):
                record.inaturalist_taxon_id = str(blob["inat_taxon_id"])
                _add_source(record, "inaturalist_taxa")
            inat_names = blob.get("inat_names") or []
            for name in inat_names:
                record.aliases.extend(generate_common_name_variants(name))
            record.aliases = _dedup_keep_order(record.aliases)
            if inat_names:
                record.search_terms = _dedup_keep_order(record.search_terms + inat_names)

            wiki = blob.get("wikipedia")
            if wiki:
                record.wikipedia_url = wiki.get("url") or record.wikipedia_url
                _add_source(record, "wikipedia")
                if not record.field_notes and wiki.get("extract"):
                    record.field_notes = _trim_extract(wiki["extract"])

            if progress is not None:
                progress(index + 1, len(records), common)
            if throttle and not from_cache:
                time.sleep(throttle)
    finally:
        if inat_client is not None:
            inat_client.close()
        if wiki_client is not None:
            wiki_client.close()
    return errors


def _add_source(record: AliasRecord, tag: str) -> None:
    if tag not in record.source_records:
        record.source_records.append(tag)


def apply_candidate_index(
    *,
    candidate_path: Path | None = None,
    target_path: Path | None = None,
    images_root: Path | None = None,
    confirm: bool = False,
) -> ValidationReport:
    """Replace ``class_index.json`` with the candidate index after validation.

    Refuses to write unless ``confirm`` is True and validation passes. Never touches
    image files.
    """
    src = candidate_path or class_index_candidate_path()
    dst = target_path or default_class_index_path()
    report = validate_candidate_index(src, images_root=images_root)
    if not report.ok:
        return report
    if not confirm:
        report.warnings.append("dry-run: pass confirm=True to write class_index.json")
        return report

    payload = json.loads(src.read_text(encoding="utf-8"))
    payload["applied_at"] = _utc_now()
    payload["applied_from"] = str(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report.summary["written"] = str(dst)
    return report
