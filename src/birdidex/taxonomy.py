"""Taxonomy helpers: name normalisation and cross-API ID resolution.

TODO: Implement a local taxonomy cache backed by a duckdb file or parquet.
      Consider IOC World Bird List or Clements as the canonical backbone.
"""

from __future__ import annotations


def normalise_scientific_name(name: str) -> str:
    """Strip extra whitespace and title-case a scientific name."""
    return " ".join(name.strip().split())


def build_species_key(scientific_name: str) -> str:
    """Return a slug suitable for use as a SpeciesId from a scientific name."""
    return normalise_scientific_name(scientific_name).lower().replace(" ", "_")
