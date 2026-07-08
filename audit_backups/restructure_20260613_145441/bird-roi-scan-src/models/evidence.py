from pydantic import BaseModel


class EvidenceRecord(BaseModel):
    species:        str
    source:         str
    evidence_type:  str
    strength:       str
    title:          str  | None = None
    url:            str  | None = None
    snippet:        str  | None = None
    matched_places: list[str] = []
    inside_roi:     bool | None = None
    notes:          str  | None = None