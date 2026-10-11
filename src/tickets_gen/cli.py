from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tickets_gen.config import get_settings
from tickets_gen.errors import GitHubAPIError
from tickets_gen.integrations import GitHubClient
from tickets_gen.services import ChangeIngestionService

app = typer.Typer(no_args_is_help=True, help="Generate sprint tickets from source-control evidence.")
github_app = typer.Typer(no_args_is_help=True, help="GitHub ingestion commands.")
app.add_typer(github_app, name="github")
console = Console()


def _parse_date(value: str, option_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(
            "expected YYYY-MM-DD", param_hint=option_name
        ) from exc


def _window_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _window_end(value: date) -> datetime:
    # User-facing --to is inclusive. GitHub receives the end of that UTC day.
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


@github_app.command("whoami")
def github_whoami() -> None:
    """Verify GitHub authentication and print the authenticated login."""
    settings = get_settings()
    if settings.github_token is None:
        console.print("[red]Missing TICKETSGEN_GITHUB_TOKEN.[/red]")
        raise typer.Exit(2)

    try:
        with GitHubClient(
            settings.github_token.get_secret_value(), api_url=settings.github_api_url
        ) as github:
            login = github.get_authenticated_login()
    except GitHubAPIError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    console.print(f"Authenticated as [bold]{login}[/bold]")


@github_app.command("fetch")
def github_fetch(
    repository: Annotated[str, typer.Option("--repo", help="Repository as owner/name.")],
    since: Annotated[str, typer.Option("--from", help="Inclusive start date (YYYY-MM-DD).")],
    until: Annotated[str, typer.Option("--to", help="Inclusive end date (YYYY-MM-DD).")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="JSON output path.")
    ] = Path("data/changes.json"),
    include_prs: Annotated[
        bool, typer.Option("--include-prs/--no-prs", help="Resolve PRs linked to each commit.")
    ] = True,
) -> None:
    """Fetch the authenticated developer's commits and diffs for a date window."""
    since_date = _parse_date(since, "--from")
    until_date = _parse_date(until, "--to")
    if since_date > until_date:
        console.print("[red]--from cannot be after --to.[/red]")
        raise typer.Exit(2)

    settings = get_settings()
    if settings.github_token is None:
        console.print(
            "[red]Missing TICKETSGEN_GITHUB_TOKEN.[/red] "
            "Create .env from .env.example or export the variable."
        )
        raise typer.Exit(2)

    try:
        with GitHubClient(
            settings.github_token.get_secret_value(), api_url=settings.github_api_url
        ) as github:
            login = github.get_authenticated_login()
            console.print(f"Fetching [bold]{login}[/bold]'s changes from [bold]{repository}[/bold]…")
            service = ChangeIngestionService(github)
            changes = service.fetch_github(
                repository,
                since=_window_start(since_date),
                until=_window_end(until_date),
                include_pull_requests=include_prs,
            )
            service.write_json(changes, output)
    except (GitHubAPIError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    table = Table(title="Fetched changes")
    table.add_column("SHA")
    table.add_column("Date")
    table.add_column("Files", justify="right")
    table.add_column("PRs", justify="right")
    table.add_column("Message")
    for change in changes:
        first_line = change.message.splitlines()[0] if change.message else ""
        table.add_row(
            change.sha[:8],
            change.committed_at.date().isoformat(),
            str(len(change.files)),
            str(len(change.pull_requests)),
            first_line[:70],
        )
    console.print(table)
    console.print(f"\nSaved [bold]{len(changes)}[/bold] normalized changes to [green]{output}[/green]")


if __name__ == "__main__":
    app()
