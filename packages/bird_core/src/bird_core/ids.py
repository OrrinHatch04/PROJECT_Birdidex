"""Domain NewType identifiers for type-safe ID handling."""

from typing import NewType

SpeciesId = NewType("SpeciesId", str)
ImageId = NewType("ImageId", str)
ObservationId = NewType("ObservationId", str)
SourceRecordId = NewType("SourceRecordId", str)
ModelClassId = NewType("ModelClassId", int)
