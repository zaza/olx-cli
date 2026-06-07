# olx-cli

[![CI](https://github.com/zaza/olx-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/zaza/olx-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CLI tool for searching and scraping offers from [OLX.pl](https://www.olx.pl), the Polish classifieds marketplace. Built with Python, Click, requests, and BeautifulSoup.

```sh
./olx-cli search rower \
  --category sport-hobby/rowery \
  --location krakow \
  --radius 10 \
  --photo-only \
  --min-price 100 \
  --max-price 5000 \
  --max-pages 2
```

Python port of [olx-rss](https://github.com/zaza/olx-rss/).

List available categories:
```sh
./olx-cli categories
```