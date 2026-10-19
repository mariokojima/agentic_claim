from pydantic import BaseModel


class CoverageAssessment(BaseModel):
    """Avaliação preliminar (não é aprovação): o evento está entre as coberturas da apólice?"""

    covered: bool
    reason: str
    third_party_coverage: bool | None = None  # só avaliado quando há terceiros
