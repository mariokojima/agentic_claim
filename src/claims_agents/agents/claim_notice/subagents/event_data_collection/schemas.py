from pydantic import BaseModel


class EventDraft(BaseModel):
    event_date: str
    event_time: str | None = None
    location: str
    description: str
    damages: str = ""
    has_injuries: bool = False
    has_third_parties: bool = False
