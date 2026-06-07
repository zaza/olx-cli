from __future__ import annotations

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from olx_cli.offer import BASE_URL, OlxOffer

_OFFER_COUNT_RE = re.compile(r"Znaleźliśmy\s+(ponad\s+)?(\d+)\s+ogłosze(ń|nia)")
_PAGE_TIMEOUT = 15

log = logging.getLogger(__name__)


class OlxScrapper:
    def __init__(self, start_url: str, max_pages: Optional[int] = 5) -> None:
        self._start_url = start_url
        self._max_pages = max_pages

    def get_offers(self) -> List[OlxOffer]:
        url = self._start_url
        page = 1
        offers: List[OlxOffer] = []

        while True:
            log.debug("Fetching page %d: %s", page, url)
            resp = requests.get(url, timeout=_PAGE_TIMEOUT)
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
