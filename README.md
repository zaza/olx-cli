# olx-cli

[![CI](https://github.com/zaza/olx-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/zaza/olx-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CLI tool for searching and scraping offers from [OLX.pl](https://www.olx.pl), the Polish classifieds marketplace. Built with Python, Click, requests, and BeautifulSoup.

Python port of [olx-rss](https://github.com/zaza/olx-rss/).

## Authentication

Create `credentials.txt` in the project root:

```
username=your@email.com
password=your_password
```

Then login:

```sh
olx-cli login
# outputs your user ID
```

View your profile:

```sh
olx-cli me
olx-cli me --json   # agent-friendly
```

View your offers:

```sh
olx-cli search --user me
olx-cli search --user me --json
```

View any public user's offers (no login required):

```sh
olx-cli search --user USER_ID --json
```

## Search

Search for offers with filters:

```sh
olx-cli search rower \
  --category sport-hobby/rowery \
  --location krakow \
  --radius 10 \
  --photo-only \
  --min-price 100 \
  --max-price 5000 \
  --max-pages 2
```

Search by user ID:

```sh
olx-cli search --user USER_ID
olx-cli search --user USER_ID --json
```

List available categories:

```sh
olx-cli categories
```

---

Created with 🥒 Big Pickle in [OpenCode](https://opencode.ai)
