# AGENTS.md

## Project overview

A CLI tool that scrapes OLX.pl (Polish classifieds) for offers matching a search query. Uses Click for CLI, requests + BeautifulSoup for scraping.

## Setup commands

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run CLI

```sh
./olx-cli search <query> [options]
# or
python -m olx_cli search <query> [options]
```

When running via agent, prefer `--json` for structured output:

```sh
python -m olx_cli search rower -l krakow --json
```

## Run tests

```sh
python -m pytest tests/ -v
```

## Code style

- Python 3.14+, uses `from __future__ import annotations`
- Single quotes for strings
- No semicolons
- Dataclasses for data models
- Static methods on scrapper class
- Descriptive test classes (TestCliHelp, TestBuildUrl, etc.)
