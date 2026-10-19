from pydantic import BaseModel


class PartiesExtraction(BaseModel):
    """Envolvidos no sinistro de colisão (None = não informado)."""

    has_third_parties: bool | None = None
    has_injuries: bool | None = None
