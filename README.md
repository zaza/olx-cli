# olx-cli

[![CI](https://github.com/zaza/olx-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/zaza/olx-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CLI tool for searching and scraping offers from [OLX.pl](https://www.olx.pl), the Polish classifieds marketplace. Built with 🐍

## Features

### Search offers

Search with optional filters:

```sh
olx-cli search rower --category sport-hobby/rowery --location krakow --radius 10
olx-cli search fiat --photo-only --min-price 1000 --max-price 5000 --max-pages 2
```

### Browse by user

Any public user's offers visible via their user ID:

```sh
olx-cli search --user USER_ID
```

### List categories

```sh
olx-cli categories
```

### 🔒 Suggest categories by title

```sh
olx-cli suggest-category "rayman legends ps4"
```

### 🔒 Add offers

Create offers from a text file:

```sh
olx-cli add offer.txt
olx-cli add offers/   # batch from folder
```

File format:

```
title=Tytuł ogłoszenia
price=1299
category=sport-i-hobby/rowery
city=Kraków
contact_name=Jan Kowalski   # optional
phone=123456789             # optional
negotiable=yes              # optional

---
Multiline description here.
```

### 🔒 View your own stuff

```sh
olx-cli me                  # your profile
olx-cli search --user me    # your active offers
```

## Authentication

Some features (add offers, view profile, my offers) require logging in.

1. Create `credentials.txt` in the project root:

```
username=your@email.com
password=your_password
```

2. Login:

```sh
olx-cli login
```

If automated login fails (WAF/DataDome blocking), it falls back to opening a browser for manual login. If both fail, wait a minute and try again.

Logout:

```sh
olx-cli logout
```

---

Created with 🥒 Big Pickle in [OpenCode](https://opencode.ai)
