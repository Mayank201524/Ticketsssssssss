# Tickets-Gen

Tickets-Gen reconstructs a developer's completed work from source-control evidence and turns it into reviewable sprint tickets.

## v0.1 scope

The first vertical slice deliberately does one thing well:

1. authenticate to GitHub as the local developer;
2. fetch that developer's commits for a repository and time window;
3. fetch the full commit details, changed files, patches, and linked pull requests;
4. normalize the evidence into stable Pydantic models;
5. write the result to JSON for the future Change Analyst agent.

No ticket is created remotely in v0.1.

## Requirements

- Python 3.12+
- a GitHub personal access token with access to the repository you want to inspect

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Put your token in `.env`:

```dotenv
TICKETSGEN_GITHUB_TOKEN=github_pat_xxx
```

Never commit `.env`.

## Verify authentication

```bash
tickets-gen github whoami
```

## Fetch a sprint window

```bash
tickets-gen github fetch \
  --repo owner/repository \
  --from 2026-09-28 \
  --to 2026-10-09 \
  --output data/changes.json
```

`--from` and `--to` are inclusive calendar dates. The current CLI interprets them as UTC boundaries to keep ingestion deterministic. A configured sprint timezone will be added when sprint configuration lands.

The output contains normalized commit metadata, file stats, available diff patches, and pull requests associated with each commit.

## Architecture boundary

```text
GitHub REST API
      │
      ▼
GitHubClient
      │
      ▼
Change[]
      │
      ▼
data/changes.json
      │
      ▼
Change Analyst   (next milestone)
      │
      ▼
Work Item Grouper
      │
      ▼
Ticket Writer
      │
      ▼
Human Review
      │
      ▼
OpenProject
```

The LLM will consume normalized `Change` objects. It will never be responsible for making GitHub or OpenProject API calls directly.

## Test

```bash
pytest -q
ruff check .
```
