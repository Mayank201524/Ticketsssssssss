from pydantic import BaseModel, ConfigDict, Field


class GeneratedTicket(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=255)
    description: str
    acceptance_criteria: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
