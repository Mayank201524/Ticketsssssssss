
import json

from tickets_gen.integrations.opencode import OpenCodeClient
from tickets_gen.models.change import Change, ChangeAnalysis


MAX_PATCH_CHARS = 12_000


class ChangeAnalyst:
    """Turns raw source-control evidence into structured semantic analysis."""

    def __init__(self, client: OpenCodeClient) -> None:
        self.client = client

    def analyze(self, change: Change) -> ChangeAnalysis:
        prompt = self._build_prompt(change)

        raw_response = self.client.run(prompt).strip()
        raw_response = self._strip_code_fence(raw_response)

        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Change Analyst returned invalid JSON.\n"
                f"Response:\n{raw_response[:1000]}"
            ) from exc

        analysis = ChangeAnalysis.model_validate(payload)

        if analysis.change_id != change.sha:
            raise RuntimeError(
                "Change Analyst returned a change_id that does not match "
                f"the source commit. Expected {change.sha}, "
                f"got {analysis.change_id}."
            )

        return analysis

    def _build_prompt(self, change: Change) -> str:
        pull_requests = self._render_pull_requests(change)
        files = self._render_files(change)

        return f"""
You are a senior software engineer performing source-code change analysis.

Your job is to analyze ONE source-control change and describe what was
actually changed.

Do not invent requirements.
Do not invent business impact that cannot reasonably be inferred from
the supplied evidence.
Do not write a ticket.
Do not group this change with other commits.

SOURCE CONTROL INFORMATION

Repository:
{change.repository}

Commit SHA:
{change.sha}

Commit message:
{change.message}

Author login:
{change.author_login or "unknown"}

Author name:
{change.author_name or "unknown"}

Author email:
{change.author_email or "unknown"}

Authored at:
{change.authored_at.isoformat()}

Committed at:
{change.committed_at.isoformat()}

Commit URL:
{change.html_url}

ASSOCIATED PULL REQUESTS

{pull_requests}

CHANGED FILES AND DIFFS

{files}

Return ONLY valid JSON.

Do not include markdown.
Do not include a code fence.
Do not include explanation outside the JSON.

The JSON must contain exactly these keys:

{{
  "change_id": "{change.sha}",
  "summary": "Concise explanation of the change",
  "change_type": "feature|bugfix|refactor|test|docs|chore|other",
  "components": [
    "affected logical component"
  ],
  "technical_changes": [
    "specific technical change"
  ],
  "impact": "Concise description of the observable or engineering impact"
}}

Rules:

1. change_id MUST be exactly "{change.sha}".
2. summary must describe what changed, not speculate about future work.
3. technical_changes must be grounded in the provided diff.
4. components should use logical names such as authentication, API,
   database, frontend, tests, configuration, etc.
5. Use "other" when the change type does not clearly fit another category.
6. If impact is primarily internal, say so instead of inventing user impact.
""".strip()

    @staticmethod
    def _render_pull_requests(change: Change) -> str:
        if not change.pull_requests:
            return "None"

        entries: list[str] = []

        for pr in change.pull_requests:
            entries.append(
                "\n".join(
                    [
                        f"PR #{pr.number}",
                        f"Title: {pr.title}",
                        f"State: {pr.state}",
                        f"URL: {pr.url}",
                        (
                            f"Merged at: {pr.merged_at.isoformat()}"
                            if pr.merged_at
                            else "Merged at: not merged"
                        ),
                    ]
                )
            )

        return "\n\n".join(entries)

    @staticmethod
    def _render_files(change: Change) -> str:
        if not change.files:
            return "No changed-file details were available."

        rendered: list[str] = []

        for changed_file in change.files:
            patch = changed_file.patch or "[patch unavailable]"

            if len(patch) > MAX_PATCH_CHARS:
                patch = (
                    patch[:MAX_PATCH_CHARS]
                    + "\n...[patch truncated by Tickets-Gen]"
                )

            rendered.append(
                "\n".join(
                    [
                        f"Path: {changed_file.path}",
                        f"Status: {changed_file.status or 'unknown'}",
                        f"Previous path: {changed_file.previous_path or 'none'}",
                        f"Additions: {changed_file.additions}",
                        f"Deletions: {changed_file.deletions}",
                        f"Total changes: {changed_file.changes}",
                        "Patch:",
                        patch,
                    ]
                )
            )

        return "\n\n---\n\n".join(rendered)

    @staticmethod
    def _strip_code_fence(value: str) -> str:
        if not value.startswith("```"):
            return value

        lines = value.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines).strip()