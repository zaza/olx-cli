# AGENTS.md

## Project overview

A CLI tool that scrapes OLX.pl (Polish classifieds) for offers matching a search query. Uses Click for CLI, requests + BeautifulSoup for scraping.

## Setup commands

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run CLI

```sh
./olx-cli search <query> [options]
# or
python3 -m olx_cli search <query> [options]
```

When running via agent, prefer `--json` for structured output:

```sh
python3 -m olx_cli search rower -l krakow --json
# With category:
python3 -m olx_cli search fiat -c motoryzacja/samochody -l krakow --json
# By user ID (any user, scraped from SSR HTML):
python3 -m olx_cli search --user USER_ID --json
```

List available categories:
```sh
python3 -m olx_cli categories
```

## Authentication

```sh
# Login (reads credentials.txt from CWD, outputs user ID for chaining)
python3 -m olx_cli login

# Show profile (prefer --json for agent usage):
python3 -m olx_cli me --json

# Show my offers:
python3 -m olx_cli search --user me --json
# or via search with user ID from login:
python3 -m olx_cli search --user $(python3 -m olx_cli login) --json --max-pages 2

# Logout
python3 -m olx_cli logout
```

## Run tests

```sh
# Sequential:
python3 -m pytest tests/ -v -n 0
# Parallel (default, auto-detect cores):
python3 -m pytest tests/ -v
```

## Test CI workflow locally (act)

Requires Docker and valid `gh` auth:

```sh
# Test the full CI pipeline locally
act -j test
```

If `act` fails with "authentication required" when cloning actions, first run `gh auth status` to verify your token is valid. If needed, re-authenticate: `gh auth login`.

## Code style

- Python 3.14+, uses `from __future__ import annotations`
- Single quotes for strings
- No semicolons
- Dataclasses for data models
- Static methods on scrapper class
- Descriptive test classes (TestCliHelp, TestBuildUrl, etc.)
