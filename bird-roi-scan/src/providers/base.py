from abc import ABC, abstractmethod
from bird_roi_scan.models.species import Species
from bird_roi_scan.models.occurrence import Occurrence
from bird_roi_scan.models.evidence import EvidenceRecord

class Provider(ABC):
    name: str

    @abstractmethod
    def search_occurences(
        self,
        species: Species,
        roi_wkt: str,
    ) -> list[Occurrence]:
        pass

    def search_web_evidence(
        self,
        species: Species,
        roi_places: list[str],
    ) -> list[EvidenceRecord]:
        pass