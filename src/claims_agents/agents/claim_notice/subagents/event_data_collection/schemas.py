from pydantic import BaseModel


class EventDraft(BaseModel):
    event_date: str
    location: str
    description: str
    has_injuries: bool = False
    has_third_parties: bool = False
