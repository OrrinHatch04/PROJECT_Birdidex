"""Shared enumerations used across all birdidex packages."""

from enum import Enum


class EvidenceSource(str, Enum):
    ala = "ala"
    gbif = "gbif"
    ebird = "ebird"
    inaturalist = "inaturalist"
    web = "web"


class SpeciesStatus(str, Enum):
    accepted = "accepted"
    review = "review"
    rejected = "rejected"


class DatasetSplit(str, Enum):
    train = "train"
    val = "val"
    test = "test"
    review = "review"


class ModelBackend(str, Enum):
    pytorch = "pytorch"
    onnxruntime = "onnxruntime"
