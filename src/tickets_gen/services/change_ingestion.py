import json
from datetime import datetime
from pathlib import Path

from tickets_gen.integrations import GitHubClient
from tickets_gen.models import Change


class ChangeIngestionService:
    def __init__(self, github: GitHubClient) -> None:
        self._github = github

    def fetch_github(
        self,
        repository: str,
        *,
        since: datetime,
        until: datetime,
        include_pull_requests: bool = True,
    ) -> list[Change]:
        return self._github.fetch_changes(
            repository,
            since=since,
            until=until,
            include_pull_requests=include_pull_requests,
        )

    @staticmethod
    def write_json(changes: list[Change], destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = [change.model_dump(mode="json") for change in changes]
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return destination
