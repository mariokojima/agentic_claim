from pydantic import BaseModel


class CpfExtraction(BaseModel):
    cpf: str | None
    valid: bool
