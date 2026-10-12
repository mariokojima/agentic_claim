from pydantic import BaseModel


class CoverageAssessment(BaseModel):
    covered: bool
    reason: str
