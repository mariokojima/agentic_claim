from pydantic import BaseModel


class AnswerOutcome(BaseModel):
    topic: str | None
    source: str  # regras | base_de_conhecimento | llm | sem_resposta
