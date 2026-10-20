from pydantic import BaseModel


class QueryClassification(BaseModel):
    topic: str | None
    faq_id: str | None = None
    coverage_asked: str | None = None
