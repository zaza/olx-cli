# AGENTS.md

## Project overview

A CLI tool that scrapes OLX.pl (Polish classifieds) for offers matching a search query. Uses Click for CLI, `curl_cffi` (Chrome TLS impersonation; plain `requests` gets HTTP 403) + `__PRERENDERED_STATE__` SSR JSON parsing for scraping.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the CLI (agent mode)

Always use `--json` for structured, parseable output:

```sh
# Search
python3 -m olx_cli search rower -l krakow --json

# With category
python3 -m olx_cli search fiat -c motoryzacja/samochody -l krakow --json

# By user ID (short slug copied from any offer's seller link, e.g. `Qsl`)
# Numeric user IDs no longer resolve (404) — grab the short `uzytkownik/<slug>/` slug.
python3 -m olx_cli search --user USER_SLUG --json

# List categories
python3 -m olx_cli categories

# Suggest categories by title/keywords
python3 -m olx_cli suggest-category 'rayman legends ps4'
python3 -m olx_cli suggest-category 'rower górski' --json
```

### Auth-protected commands

```sh
# Login (reads credentials.txt from CWD)
python3 -m olx_cli login

# Profile
python3 -m olx_cli me --json

# My offers
python3 -m olx_cli search --user me --json

# Add offers
python3 -m olx_cli add offer.txt
python3 -m olx_cli add offers/

# Logout
python3 -m olx_cli logout
```

## Authentication flow

Credentials file format (in CWD):

```
username=your@email.com
password=your_password
```

The `login` command tries two methods automatically:

1. **Cognito SRP API** — direct Cognito pool login (`eu-west-1_dUjFuvTf4`, web client `6j7elk01p32o648o1io8lvhhab`). Works unless blocked by AWS WAF.
2. **Browser fallback** — if Cognito fails, opens Chromium via Playwright (headed) at `https://www.olx.pl/mojolx` which redirects to the Cognito hosted UI. User logs in manually — natural interaction bypasses WAF + DataDome.

If both fail, tell the user to wait a few minutes and retry.

**Force browser mode** (recommended for scripts, avoids WAF entirely):

```sh
python3 -m olx_cli login --browser
```

**Chain with search** (using jq to get user ID from profile):

```sh
olx-cli login --browser && olx-cli search --user $(olx-cli me --json | jq -r '.user_id') --json --max-pages 2
```

After login, tokens are saved to `~/.cache/olx-cli/tokens.json` (keys: AccessToken, RefreshToken, IdToken).

Requires Playwright + Chromium for browser fallback: `pip install playwright && python3 -m playwright install chromium`

### Auth findings (observed 2026-10, IP flagged)

Both login paths can be blocked simultaneously. Diagnostics performed:

- **Cognito primary** returns `HTTP 403 {"__type":"ForbiddenException","message":"Request not allowed due to WAF block."}`. This is AWS WAF rejecting the request *before* credentials are checked — not a bad-password error. `_refresh` hits the same endpoint, so **token refresh is blocked too**.
- **Browser fallback**: Playwright reaches `login.olx.pl`, fills the form, and `#Login` becomes enabled — but submitting leaves the page on the login URL indefinitely (**no redirect, no error, no token**). DataDome intercepts the login POST. A DataDome block page appears intermittently ("Dlaczego zostałeś zablokowany?") naming the client IP and saying a bot operates from that network.
- **Scraping (GET) is unaffected**: `curl_cffi` listing fetches still return 200 while login is blocked. Only the login endpoints (Cognito + Auth0/DataDome) enforce the bot rules.
- **Likely cause**: the scraping traffic flags the IP; DataDome/WAF then block login from that IP. Block is usually temporary (cooldown), but may persist for a while.

Remaining robustness gaps in `olx_cli/browser_auth.py` (browser fallback login):

1. No popup/new-page handling — OAuth flows that open a new tab are not tracked.
2. No DataDome block detection — a block still hangs for the full 180s timeout, then reports a generic "failed to extract tokens" instead of "blocked".
3. Headless mode still waits the full timeout when auto-fill fails, though a human cannot appear.
4. Auto-fill + auto-click is more bot-like than the intended manual login and more likely to be challenged.
5. `wait_until='networkidle'` + the loose `_on_olx` success predicate can return before tokens are persisted (2s fixed wait).

Mitigations: cool down / use a different IP for login; use a persistent browser context or a real Chrome profile; prefer manual login so a human clears any challenge; keep the scraping IP separate from the login IP and throttle scraping.

## Scraping — fetch layer (`olx_cli/http.py`, `olx_cli/scraper.py`)

- **`requests` is blocked.** OLX's CloudFront layer 403s the plain Python TLS fingerprint (JA3/JA4). All HTTP goes through `olx_cli/http.py`, a thin `curl_cffi` wrapper with `impersonate="chrome"` — socket-level TLS/HTTP2 impersonation, no browser needed.
- **Page structure changed.** Search AND user-listing pages no longer render `div[data-testid=listing-grid]` cards. They embed a `window.__PRERENDERED_STATE__` JS string literal holding serialized JSON; ads live under `listing.listing.ads` (search) or `userListing.userListing.ads` (user pages).
- `OlxScraper.get_offers()` parses SSR state directly (`_parse_ssr_listing`, `_extract_ssr_state`) — no BeautifulSoup. Pagination: append `?page=N` (via `_page_url`, preserves filters), stop at SSR `totalPages` or `max_pages`.
- `_extract_ssr_state` uses a backslash-aware scanner instead of a regex: ad content can contain `";`, which truncates naive `"(.*?)";` patterns.
- **Job listings** (`Praca` category) have `price: null` — `OlxOffer.from_user_listing_offer` tolerates this (empty price).
- Playwright remains for auth login only (browser fallback).
- User listing URL: `https://www.olx.pl/oferty/uzytkownik/<SLUG>/` where `<SLUG>` is the short ID from an ad page's seller link. Numeric `user.id`/`uuid` from SSR do NOT resolve (404).

## Add offers — technical details

### Offer file parser (`olx_cli/offer_submit.py`)

The `add` command reads offer files in a simple header-body format. Headers are `key=value` lines above a `---` separator; everything after is the multiline description.

Supported headers: `title`, `price`, `category`, `city`, `city_id` (alternative to city), `email`, `contact_name`, `phone`, `negotiable`

Validation rules:
- `title`: 16–150 chars
- `description` (body): 40–900 chars
- `price`: numeric, ≥ 0 (via `_parse_price_value` — strips `zł`, spaces, commas)
- `category`: required (slug)
- `city` or `city_id`: required (one or the other)
- `email`: required

### Category resolution (`olx_cli/category_resolver.py`)

Category slugs → numeric IDs via `GET /api/v1/categories/suggestion/?q=<query>`. Requires auth token.

The resolver:
1. Strips the leaf of the slug path (e.g. `sport-i-hobby/rowery/rowery-gorskie` → `rowery-gorskie`)
2. Replaces hyphens with spaces
3. Queries the suggestion API
4. Matches using NFKD-normalized name comparison (handles Polish diacritics: `gorskie` matches `górskie`)
5. Falls back to the first result if no name match

### City resolution (`olx_cli/city_resolver.py`)

City names → OLX numeric city IDs. Multi-step resolution:

1. **Sitemap scrape** — fetches `https://www.olx.pl/sitemap/regions/`, parses `<li>` elements with `_SitemapParser` (HTMLParser subclass) to extract city name → URL slug mappings
2. **Pagination search** — iterates `GET /api/v1/cities/?offset=0..1050&limit=50` looking for a name match
3. **Keyword fallback** — if pagination fails, `GET /api/v1/cities/?query=<slug>`
4. **Deaccent fallback** — if sitemap + API fail, strips diacritics via NFKD normalization (`_deaccent`) and retries

Caching:
- Sitemap cached to `~/.cache/olx-cli/sitemap.json` (7-day TTL)
- Pagination results not cached (re-fetched each `resolve()` call, but sitemap avoids most pagination)
- Delete `~/.cache/olx-cli/sitemap.json` to force sitemap refresh

City ID notes:
- IDs are assigned roughly alphabetically (auto-increment PK)
- Outliers: Toruń (38395), Piła (52515) — likely added to the database later

### Payload building (`olx_cli/offer_submit.py`)

`_build_payload` constructs the POST body for `POST https://posting-services.prd.01.eu-west-1.eu.olx.org/api/v2/offers`.

Key payload structure:

```python
{
    'brand': 'OLX',
    'lang': 'pl',
    'category_id': <int>,
    'city_id': <int>,
    'email': str,
    'parameters': {
        'price': {'price': str},   # stringified PLN value
        'state': 'used',
    },
    'components_data': {'reposting': ...},
}
```

Headers required (from `_get_submit_headers`):
- `Authorization: Bearer <token>`
- `postingId: <uuid4>` (one per offer)
- `X-Client: DESKTOP`
- `X-Platform-Type: mobile-html5`

`submit_offer` accepts HTTP 200 **or** 201 from the API.

### Directory batch mode

```python
_find_offer_files(path):
    if path is a file → [path]
    if path is a directory → glob for `*/offer.txt` in subdirectories
```

## Running tests

```sh
# Sequential (avoids locking issues):
python3 -m pytest tests/ -v -n 0

# Parallel (auto-detect cores):
python3 -m pytest tests/ -v
```

Network-dependent tests (`TestOlxScraper`) make real HTTP requests to OLX. Each has a 30s per-request timeout (`_PAGE_TIMEOUT`). They pass when run individually (~3–8s each), but can slow down the full suite.

## CI workflow (act)

Requires Docker and valid `gh` auth:

```sh
act -j test
```

If `act` fails with "authentication required", verify token: `gh auth status`. Re-authenticate if needed: `gh auth login`.

## Code conventions

- Python 3.14+, `from __future__ import annotations`
- Single quotes, no semicolons
- Dataclasses for data models
- Static methods on Scraper class
- Descriptive test class names (TestCliHelp, TestBuildUrl, TestCategoryResolver, etc.)
- Use `_deaccent()` (NFKD normalization) for Polish diacritic handling in both `query.py` and `city_resolver.py`
