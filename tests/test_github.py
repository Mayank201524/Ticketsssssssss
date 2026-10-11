from datetime import datetime, timezone

import httpx
import pytest

from tickets_gen.integrations.github import GitHubClient


@pytest.fixture
def api_payloads():
    return {
        "/user": {"login": "alice"},
        "/repos/acme/api/commits": [
            {"sha": "abcdef1234567890"},
        ],
        "/repos/acme/api/commits/abcdef1234567890": {
            "sha": "abcdef1234567890",
            "html_url": "https://github.com/acme/api/commit/abcdef1234567890",
            "author": {"login": "alice"},
            "commit": {
                "message": "feat: add refresh tokens\n\nAdds token rotation.",
                "author": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": "2026-10-01T09:00:00Z",
                },
                "committer": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": "2026-10-01T09:05:00Z",
                },
            },
            "files": [
                {
                    "filename": "src/auth/token.py",
                    "status": "modified",
                    "additions": 20,
                    "deletions": 3,
                    "changes": 23,
                    "patch": "@@ -1 +1 @@",
                }
            ],
        },
        "/repos/acme/api/commits/abcdef1234567890/pulls": [
            {
                "number": 42,
                "title": "Add refresh-token flow",
                "html_url": "https://github.com/acme/api/pull/42",
                "state": "closed",
                "merged_at": "2026-10-01T10:00:00Z",
            }
        ],
    }


def test_fetch_changes_normalizes_commit(api_payloads):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = api_payloads[path]
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with GitHubClient("token", transport=transport) as client:
        changes = client.fetch_changes(
            "acme/api",
            since=datetime(2026, 10, 1, tzinfo=timezone.utc),
            until=datetime(2026, 10, 2, tzinfo=timezone.utc),
        )

    assert len(changes) == 1
    change = changes[0]
    assert change.author_login == "alice"
    assert change.sha == "abcdef1234567890"
    assert change.files[0].path == "src/auth/token.py"
    assert change.files[0].additions == 20
    assert change.pull_requests[0].number == 42


def test_fetch_changes_uses_authenticated_login(api_payloads):
    captured_author = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_author
        if request.url.path == "/repos/acme/api/commits":
            captured_author = request.url.params.get("author")
        return httpx.Response(200, json=api_payloads[request.url.path])

    transport = httpx.MockTransport(handler)
    with GitHubClient("token", transport=transport) as client:
        client.fetch_changes(
            "acme/api",
            since=datetime(2026, 10, 1, tzinfo=timezone.utc),
            until=datetime(2026, 10, 2, tzinfo=timezone.utc),
            include_pull_requests=False,
        )

    assert captured_author == "alice"


def test_rejects_invalid_time_window():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    with GitHubClient("token", transport=transport) as client:
        with pytest.raises(ValueError, match="since must be earlier"):
            client.fetch_changes(
                "acme/api",
                since=datetime(2026, 10, 2, tzinfo=timezone.utc),
                until=datetime(2026, 10, 1, tzinfo=timezone.utc),
            )
