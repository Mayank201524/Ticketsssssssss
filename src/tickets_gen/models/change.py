from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChangeSource(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"


class ChangedFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1)
    status: str | None = None
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    changes: int = Field(default=0, ge=0)
    patch: str | None = None
    previous_path: str | None = None


class PullRequestRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int = Field(gt=0)
    title: str = Field(min_length=1)
    url: str
    state: str
    merged_at: datetime | None = None


class Change(BaseModel):
    """Normalized source-control change consumed by downstream agents."""

    model_config = ConfigDict(frozen=True)

    source: ChangeSource
    repository: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    sha: str = Field(min_length=7)
    message: str
    author_login: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    authored_at: datetime
    committed_at: datetime
    html_url: str
    files: tuple[ChangedFile, ...] = ()
    pull_requests: tuple[PullRequestRef, ...] = ()

    @field_validator("authored_at", "committed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class ChangeAnalysis(BaseModel):
    """Semantic analysis of a normalized source-control change."""

    model_config = ConfigDict(frozen=True)

    change_id: str = Field(min_length=7)
    summary: str = Field(min_length=1)
    change_type: str = Field(min_length=1)
    components: tuple[str, ...] = ()
    technical_changes: tuple[str, ...] = ()
    impact: str = Field(min_length=1)