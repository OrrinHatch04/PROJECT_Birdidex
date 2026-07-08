"""Shared enumerations used across all birdidex packages."""

from enum import StrEnum


class EvidenceSource(StrEnum):
    ala = "ala"
    gbif = "gbif"
    ebird = "ebird"
    inaturalist = "inaturalist"
    web = "web"


class SpeciesStatus(StrEnum):
    accepted = "accepted"
    review = "review"
    rejected = "rejected"


class DatasetSplit(StrEnum):
    train = "train"
    val = "val"
    test = "test"
    review = "review"


class ModelBackend(StrEnum):
    pytorch = "pytorch"
    onnxruntime = "onnxruntime"
