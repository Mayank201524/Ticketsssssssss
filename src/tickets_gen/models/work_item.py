from pydantic import BaseModel, ConfigDict, Field


class ChangeAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    change_sha: str
    summary: str
    change_type: str
    components: tuple[str, ...] = ()
    technical_changes: tuple[str, ...] = ()
    impact: str = ""


class WorkItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    summary: str
    change_shas: tuple[str, ...]
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
