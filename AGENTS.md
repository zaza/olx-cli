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
```

List available categories:
```sh
python3 -m olx_cli categories
```

## Run tests

```sh
python3 -m pytest tests/ -v
```

## Code style

- Python 3.14+, uses `from __future__ import annotations`
- Single quotes for strings
- No semicolons
- Dataclasses for data models
- Static methods on scrapper class
- Descriptive test classes (TestCliHelp, TestBuildUrl, etc.)
