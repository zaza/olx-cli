from __future__ import annotations

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from olx_cli.offer import BASE_URL, OlxOffer

_OFFER_COUNT_RE = re.compile(r"Znaleźliśmy\s+(ponad\s+)?(\d+)\s+ogłosze(ń|nia)")
_PAGE_TIMEOUT = 30
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _USER_AGENT,
}

_PRERENDERED_STATE_RE = re.compile(
    r'window\.__PRERENDERED_STATE__\s*=\s*"(.+?)"\s*;'
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
        resp = requests.get(url, headers=headers, timeout=_PAGE_TIMEOUT)
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


def _parse_ssr_user_offers(html: str) -> tuple[list[OlxOffer], int, int] | None:
    """Parse __PRERENDERED_STATE__ from a user listing page.

    Returns (offers, total_elements, total_pages) or None if SSR data is missing.
    """
    import json

    m = _PRERENDERED_STATE_RE.search(html)
    if not m:
        return None

    raw = m.group(1)
    js_value = json.loads('"' + raw + '"')
    state = json.loads(js_value)
    listing = state.get('userListing', {}).get('userListing', {})
    ads = listing.get('ads', [])
    offers = [OlxOffer.from_user_listing_offer(ad) for ad in ads]
    return offers, listing.get('totalElements', 0), listing.get('totalPages', 0)


def fetch_user_offers_html(
    user_id: str,
    max_pages: Optional[int] = 5,
) -> tuple[list[OlxOffer], int]:
    offers: List[OlxOffer] = []
    total_pages = 0

    for page in range(1, max_pages + 1):
        url = f'https://www.olx.pl/oferty/uzytkownik/{user_id}/'
        if page > 1:
            url += f'?page={page}'

        resp = requests.get(url, headers=_HEADERS, timeout=_PAGE_TIMEOUT)
        resp.raise_for_status()

        result = _parse_ssr_user_offers(resp.text)
        if result is None:
            log.warning('__PRERENDERED_STATE__ not found on user page %d', page)
            return offers, page - 1

        page_offers, total_elements, total_pages = result
        if not page_offers:
            return offers, page
        offers.extend(page_offers)

        if page >= total_pages:
            return offers, page

    return offers, page


class OlxScrapper:
    def __init__(self, start_url: str, max_pages: Optional[int] = 5) -> None:
        self._start_url = start_url
        self._max_pages = max_pages
        self.pages_visited = 0

    def get_offers(self) -> List[OlxOffer]:
        url = self._start_url
        page = 1
        offers: List[OlxOffer] = []

        while True:
            log.debug("Fetching page %d: %s", page, url)
            resp = requests.get(url, headers=_HEADERS, timeout=_PAGE_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            page_offers = soup.select(
                "div[data-testid=listing-grid] > div[data-testid=l-card]"
            )

            if page == 1:
                total = self._parse_offer_count(soup)
                log.info("Found %d total offers", total)
                if total == 0:
                    return []
                if not self._has_next_page(soup) and page_offers:
                    count = min(total, len(page_offers))
                    page_offers = page_offers[:count]

            for el in page_offers:
                offers.append(OlxOffer.from_element(el))

            if not self._has_next_page(soup):
                break

            if self._max_pages is not None and page >= self._max_pages:
                log.info("Reached max pages (%d)", self._max_pages)
                break

            next_url = self._next_page_url(soup)
            if not next_url:
                break
            url = urljoin(BASE_URL, next_url)
            page += 1
        self.pages_visited = page

        return offers

    @staticmethod
    def _parse_offer_count(soup: BeautifulSoup) -> int:
        el = soup.select_one("span[data-testid=total-count]")
        if el is None:
            return 0
        text = el.get_text(separator=" ", strip=True)
        m = _OFFER_COUNT_RE.match(text)
        if m:
            return int(m.group(2))
        return 0

    @staticmethod
    def _has_next_page(soup: BeautifulSoup) -> bool:
        link = soup.select_one("a[data-testid=pagination-forward]")
        if not link:
            return False
        href = link.get("href")
        return bool(href) and href != "#"

    @staticmethod
    def _next_page_url(soup: BeautifulSoup) -> Optional[str]:
        link = soup.select_one("a[data-testid=pagination-forward]")
        if not link:
            return None
        href = link.get("href")
        if href and href != "#":
            return href
        return None
