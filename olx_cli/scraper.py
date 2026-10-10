from __future__ import annotations

import json
import logging
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from olx_cli import http
from olx_cli.offer import OlxOffer

_PAGE_TIMEOUT = 30

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)

_DEFAULT_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}

_PRERENDERED_STATE_MARKER = '__PRERENDERED_STATE__'

# Listing pages embed the same SSR blob; the state path differs by page type.
_SSR_LISTING_PATHS = (
    ("listing", "listing"),          # search results
    ("userListing", "userListing"),  # user's offer listing
)

log = logging.getLogger(__name__)


def _api_offers_to_offers(resp_data: dict) -> List[OlxOffer]:
    offers: List[OlxOffer] = []
    for item in resp_data.get("data", []):
        offers.append(OlxOffer.from_api_offer(item))
    return offers


def _has_api_next(resp_data: dict) -> bool:
    return "next" in resp_data.get("links", {})


def fetch_my_offers(
    access_token: str,
    max_pages: Optional[int] = 5,
) -> tuple[list[OlxOffer], int]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    offers: List[OlxOffer] = []
    offset = 0
    page = 1

    while True:
        url = f"https://www.olx.pl/api/v1/users/me/offers/?offset={offset}"
        log.debug("Fetching my offers page %d", page)
        resp = http.get(url, headers=headers, timeout=_PAGE_TIMEOUT)
        if resp.status_code != 200:
            log.warning("My offers API returned HTTP %s", resp.status_code)
            break

        data = resp.json()
        page_offers = _api_offers_to_offers(data)
        if not page_offers:
            break
        offers.extend(page_offers)

        if not _has_api_next(data):
            break

        if max_pages is not None and page >= max_pages:
            log.info("Reached max pages (%d)", max_pages)
            break

        offset += len(page_offers)
        page += 1

    return offers, page


def _extract_ssr_state(html: str) -> dict | None:
    """Decode the window.__PRERENDERED_STATE__ JS string literal.

    The blob is a JS double-quoted literal holding serialized JSON, with
    every inner quote escaped ('\"'). A regex like '"(.*?)";' can truncate
    early on ad content that itself contains '";'. Use a backslash-aware
    scan of the literal instead.
    """
    start = html.find(_PRERENDERED_STATE_MARKER)
    if start == -1:
        return None
    eq = html.find('=', start)
    q = html.find('"', eq) if eq != -1 else -1
    if q == -1:
        return None

    i = q + 1
    chars: list[str] = []
    while i < len(html):
        c = html[i]
        if c == '\\':
            chars.append(c)
            if i + 1 < len(html):
                chars.append(html[i + 1])
                i += 2
                continue
            i += 1
            continue
        if c == '"':  # end of the JS string literal
            raw = ''.join(chars)
            try:
                return json.loads(json.loads('"' + raw + '"'))
            except (json.JSONDecodeError, ValueError):
                log.warning('Failed to decode __PRERENDERED_STATE__')
                return None
        chars.append(c)
        i += 1

    log.warning('__PRERENDERED_STATE__ string terminator not found')
    return None


def _find_listing(state: dict) -> dict | None:
    for path in _SSR_LISTING_PATHS:
        node: object = state
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict):
            return node
    return None


def _parse_ssr_listing(html: str) -> tuple[list[OlxOffer], int, int] | None:
    """Parse a listing from the SSR state blob (search or user pages).

    Returns (offers, total_elements, total_pages) or None if SSR data is missing.
    """
    state = _extract_ssr_state(html)
    if state is None:
        return None
    listing = _find_listing(state)
    if listing is None:
        return None
    ads = listing.get("ads", [])
    offers = [OlxOffer.from_user_listing_offer(ad) for ad in ads]
    return offers, listing.get("totalElements", 0), listing.get("totalPages", 0)


def fetch_user_offers_html(
    user_id: str,
    max_pages: Optional[int] = 5,
) -> tuple[list[OlxOffer], int]:
    offers: List[OlxOffer] = []
    page = 0

    while True:
        page += 1
        if max_pages is not None and page > max_pages:
            break

        url = f'https://www.olx.pl/oferty/uzytkownik/{user_id}/'
        if page > 1:
            url += f'?page={page}'

        resp = http.get(url, headers=_DEFAULT_HEADERS, timeout=_PAGE_TIMEOUT)
        resp.raise_for_status()

        result = _parse_ssr_listing(resp.text)
        if result is None:
            log.warning('__PRERENDERED_STATE__ not found on user page %d', page)
            return offers, page - 1

        page_offers, total_elements, total_pages = result
        if not page_offers:
            return offers, page
        offers.extend(page_offers)

        if total_pages and page >= total_pages:
            return offers, page

    return offers, page


def _page_url(base: str, page: int) -> str:
    """Append ?page=N to a listing URL, preserving existing query params."""
    parts = urlsplit(base)
    params = parse_qsl(parts.query, keep_blank_values=True)
    params = [(k, v) for k, v in params if k != "page"]
    params.append(("page", str(page)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


class OlxScraper:
    def __init__(self, start_url: str, max_pages: Optional[int] = 5) -> None:
        self._start_url = start_url
        self._max_pages = max_pages
        self.pages_visited = 0

    def get_offers(self) -> List[OlxOffer]:
        """Scrape offers from an OLX listing page (SSR state based)."""
        offers: List[OlxOffer] = []
        page = 1

        while True:
            url = self._start_url if page == 1 else _page_url(self._start_url, page)
            log.debug("Fetching page %d: %s", page, url)
            resp = http.get(url, headers=_DEFAULT_HEADERS, timeout=_PAGE_TIMEOUT)
            resp.raise_for_status()

            result = _parse_ssr_listing(resp.text)
            if result is None:
                log.warning("__PRERENDERED_STATE__ not found on page %d", page)
                break
            page_offers, total_elements, total_pages = result
            offers.extend(page_offers)

            if not page_offers or total_pages == 0:
                break
            if page >= total_pages:
                break
            if self._max_pages is not None and page >= self._max_pages:
                log.info("Reached max pages (%d)", self._max_pages)
                break
            page += 1

        self.pages_visited = page
        return offers