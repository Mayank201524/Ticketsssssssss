from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import httpx

from tickets_gen.errors import GitHubAPIError
from tickets_gen.models import Change, ChangedFile, ChangeSource, PullRequestRef


class GitHubClient:
    """Small GitHub REST client focused on developer change ingestion."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not token.strip():
            raise ValueError("GitHub token must not be empty")

        self._client = httpx.Client(
            base_url=api_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "tickets-gen/0.1.0",
            },
        )

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_authenticated_login(self) -> str:
        payload = self._get_json("/user")
        login = payload.get("login")
        if not isinstance(login, str) or not login:
            raise GitHubAPIError("GitHub /user response did not contain a login")
        return login

    def fetch_changes(
        self,
        repository: str,
        *,
        since: datetime,
        until: datetime,
        author: str | None = None,
        include_pull_requests: bool = True,
    ) -> list[Change]:
        self._validate_window(since, until)
        owner, repo = self._parse_repository(repository)
        author = author or self.get_authenticated_login()

        summaries = list(
            self._paginate(
                f"/repos/{owner}/{repo}/commits",
                params={
                    "author": author,
                    "since": self._to_github_datetime(since),
                    "until": self._to_github_datetime(until),
                    "per_page": 100,
                },
            )
        )

        changes: list[Change] = []
        seen: set[str] = set()
        for summary in summaries:
            sha = summary.get("sha")
            if not isinstance(sha, str) or not sha or sha in seen:
                continue
            seen.add(sha)

            detail = self._get_json(f"/repos/{owner}/{repo}/commits/{sha}")
            prs = (
                self._fetch_pull_requests_for_commit(owner, repo, sha)
                if include_pull_requests
                else ()
            )
            changes.append(self._normalize_commit(repository, detail, prs))

        changes.sort(key=lambda item: item.committed_at)
        return changes

    def _fetch_pull_requests_for_commit(
        self, owner: str, repo: str, sha: str
    ) -> tuple[PullRequestRef, ...]:
        payload = self._get_json(f"/repos/{owner}/{repo}/commits/{sha}/pulls")
        if not isinstance(payload, list):
            raise GitHubAPIError("Expected a list when resolving pull requests for a commit")

        refs: list[PullRequestRef] = []
        for item in payload:
            number = item.get("number")
            title = item.get("title")
            html_url = item.get("html_url")
            state = item.get("state")
            if not all(
                [isinstance(number, int), isinstance(title, str), isinstance(html_url, str)]
            ) or not isinstance(state, str):
                continue
            refs.append(
                PullRequestRef(
                    number=number,
                    title=title,
                    url=html_url,
                    state=state,
                    merged_at=self._parse_datetime(item.get("merged_at")),
                )
            )
        return tuple(refs)

    def _normalize_commit(
        self,
        repository: str,
        payload: dict[str, Any],
        prs: tuple[PullRequestRef, ...],
    ) -> Change:
        commit = payload.get("commit") or {}
        author = commit.get("author") or {}
        committer = commit.get("committer") or {}
        github_author = payload.get("author") or {}

        authored_at = self._require_datetime(author.get("date"), "author date")
        committed_at = self._require_datetime(committer.get("date"), "committer date")

        files: list[ChangedFile] = []
        for item in payload.get("files") or []:
            filename = item.get("filename")
            if not isinstance(filename, str) or not filename:
                continue
            files.append(
                ChangedFile(
                    path=filename,
                    status=item.get("status"),
                    additions=int(item.get("additions") or 0),
                    deletions=int(item.get("deletions") or 0),
                    changes=int(item.get("changes") or 0),
                    patch=item.get("patch") if isinstance(item.get("patch"), str) else None,
                    previous_path=(
                        item.get("previous_filename")
                        if isinstance(item.get("previous_filename"), str)
                        else None
                    ),
                )
            )

        sha = payload.get("sha")
        html_url = payload.get("html_url")
        if not isinstance(sha, str) or not isinstance(html_url, str):
            raise GitHubAPIError("Commit response is missing sha or html_url")

        return Change(
            source=ChangeSource.GITHUB,
            repository=repository,
            sha=sha,
            message=str(commit.get("message") or ""),
            author_login=(
                github_author.get("login") if isinstance(github_author.get("login"), str) else None
            ),
            author_name=author.get("name") if isinstance(author.get("name"), str) else None,
            author_email=author.get("email") if isinstance(author.get("email"), str) else None,
            authored_at=authored_at,
            committed_at=committed_at,
            html_url=html_url,
            files=tuple(files),
            pull_requests=prs,
        )

    def _paginate(self, path: str, *, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            page_params = {**params, "page": page}
            payload = self._get_json(path, params=page_params)
            if not isinstance(payload, list):
                raise GitHubAPIError(f"Expected list response from {path}")
            if not payload:
                return
            for item in payload:
                if isinstance(item, dict):
                    yield item
            if len(payload) < int(params.get("per_page", 30)):
                return
            page += 1

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"GitHub request failed: {exc}") from exc

        if response.is_success:
            return response.json()

        try:
            detail = response.json().get("message", response.text)
        except (ValueError, AttributeError):
            detail = response.text
        rate_remaining = response.headers.get("x-ratelimit-remaining")
        rate_reset = response.headers.get("x-ratelimit-reset")
        rate_context = ""
        if rate_remaining == "0":
            rate_context = f"; rate limit resets at unix timestamp {rate_reset}"
        raise GitHubAPIError(
            f"GitHub API returned {response.status_code} for {path}: {detail}{rate_context}"
        )

    @staticmethod
    def _parse_repository(repository: str) -> tuple[str, str]:
        parts = repository.strip().split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("repository must be in 'owner/name' format")
        return parts[0], parts[1]

    @staticmethod
    def _validate_window(since: datetime, until: datetime) -> None:
        for name, value in (("since", since), ("until", until)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if since >= until:
            raise ValueError("since must be earlier than until")

    @staticmethod
    def _to_github_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @classmethod
    def _require_datetime(cls, value: object, field_name: str) -> datetime:
        parsed = cls._parse_datetime(value)
        if parsed is None:
            raise GitHubAPIError(f"Commit response is missing valid {field_name}")
        return parsed

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed
