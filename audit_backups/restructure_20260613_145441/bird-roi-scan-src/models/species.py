
from pydantic import BaseModel


class Species(BaseModel):
    scientific_name: str
    common_name:     str | None = None
    taxon_id_ala:    str | None = None
    taxon_id_gbif:   int | None = None
    taxon_id_inat:   int | None = None
    ebird_code:      str | None = None
    aliases:         list[str] = []