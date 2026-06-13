from pydantic import BaseModel
from datetime import date

class Occurrence(BaseModel):
    source:                   str
    source_record_id:         str
    scientific_name:          str
    common_name:              str   | None = None
    latitude:                 float | None = None
    longitude:                float | None = None
    event_date:               date  | None = None
    locality:                 str   | None = None
    inside_roi:               bool  | None = None
    coordinate_uncertainty_m: float | None = None
    basis_of_record:          str   | None = None
    occurrence_status:        str   | None = None
    captive_or_cultivated:    bool  | None = None
    raw_url:                  str   | None = None