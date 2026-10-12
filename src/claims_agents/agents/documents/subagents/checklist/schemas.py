from pydantic import BaseModel


class Requirement(BaseModel):
    doc_type: str
    label: str
    min_count: int
