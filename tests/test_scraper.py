import pytest
import requests as req
from bs4 import BeautifulSoup

from olx_cli.query import build_url
from olx_cli.scraper import OlxScraper, _DEFAULT_HEADERS, _PAGE_TIMEOUT


_PAGINATION_FORWARD_LINK = """\
<html><body>
<a data-testid="pagination-forward" href="/oferty/q-rower/?page=2"></a>
</body></html>"""

_PAGINATION_WRAPPER = """\
<html><body>
<div data-testid="pagination-wrapper">
<a href="/oferty/q-rower/?page=2">2</a>
<a href="/oferty/q-rower/?page=3">3</a>
<a href="/oferty/q-rower/?page=4">4</a>
<a href="/oferty/q-rower/?page=5">5</a>
</div>
</body></html>"""

_PAGINATION_WRAPPER_LAST_PAGE = """\
<html><body>
<div data-testid="pagination-wrapper">
<a href="/oferty/q-rower/?page=1">1</a>
<a href="/oferty/q-rower/?page=2">2</a>
<a href="/oferty/q-rower/?page=3">3</a>
<a href="/oferty/q-rower/?page=4">4</a>
</div>
</body></html>"""

_NO_PAGINATION = """\
<html><body>
<p>single page of results</p>
</body></html>"""


class TestOlxScraper:
    def test_has_offers(self):
        url = build_url("kierowce przyjme")
        scrapper = OlxScraper(url, max_pages=1)
        offers = scrapper.get_offers()
        assert len(offers) > 0

    def test_pagination(self):
        url = build_url("rower", photo_only=True)
        one_page = OlxScraper(url, max_pages=1).get_offers()
        two_pages = OlxScraper(url, max_pages=2).get_offers()
        assert len(two_pages) > len(one_page), (
            f"2 pages ({len(two_pages)}) should return more than 1 page ({len(one_page)})"
        )

    def test_next_page_url(self):
        url = build_url("rower")
        resp = req.get(url, headers=_DEFAULT_HEADERS, timeout=_PAGE_TIMEOUT)
        soup = BeautifulSoup(resp.text, "lxml")
        next_url = OlxScraper._next_page_url(soup)
        assert next_url is not None, "pagination-forward link should exist for high-volume query"
        assert "page=2" in next_url or "?page=2" in next_url, f"expected page=2 in next_url, got {next_url}"

    def test_all_fields_populated(self):
        url = build_url("rower", photo_only=True)
        scrapper = OlxScraper(url, max_pages=1)
        offers = scrapper.get_offers()
        assert len(offers) > 0
        for o in offers:
            assert o.title, "title must be non-empty"
            assert o.price, "price must be non-empty"
            assert o.url, "url must be non-empty"
            assert o.city, "city must be non-empty"

    def test_photo_only_differs(self):
        url_all = build_url("rower")
        all_offers = OlxScraper(url_all, max_pages=1).get_offers()

        url_photo = build_url("rower", photo_only=True)
        photo_offers = OlxScraper(url_photo, max_pages=1).get_offers()

        titles_all = {o.title for o in all_offers}
        titles_photo = {o.title for o in photo_offers}
        assert titles_all != titles_photo, "photo filter should change results"


class TestPaginationDetection:
    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, 'lxml')

    def test_forward_link_has_next(self):
        soup = self._soup(_PAGINATION_FORWARD_LINK)
        assert OlxScraper._has_next_page(soup) is True

    def test_forward_link_next_url(self):
        soup = self._soup(_PAGINATION_FORWARD_LINK)
        assert OlxScraper._next_page_url(soup) == '/oferty/q-rower/?page=2'

    def test_wrapper_has_next_on_page_1(self):
        soup = self._soup(_PAGINATION_WRAPPER)
        assert OlxScraper._has_next_page(soup, page=1) is True

    def test_wrapper_has_next_on_page_3(self):
        soup = self._soup(_PAGINATION_WRAPPER)
        assert OlxScraper._has_next_page(soup, page=3) is True

    def test_wrapper_next_url_page_1(self):
        soup = self._soup(_PAGINATION_WRAPPER)
        assert OlxScraper._next_page_url(soup, page=1) == '/oferty/q-rower/?page=2'

    def test_wrapper_next_url_page_3(self):
        soup = self._soup(_PAGINATION_WRAPPER)
        assert OlxScraper._next_page_url(soup, page=3) == '/oferty/q-rower/?page=4'

    def test_wrapper_last_page_no_next(self):
        soup = self._soup(_PAGINATION_WRAPPER_LAST_PAGE)
        assert OlxScraper._has_next_page(soup, page=4) is False

    def test_wrapper_last_page_no_next_url(self):
        soup = self._soup(_PAGINATION_WRAPPER_LAST_PAGE)
        assert OlxScraper._next_page_url(soup, page=4) is None

    def test_no_pagination_has_no_next(self):
        soup = self._soup(_NO_PAGINATION)
        assert OlxScraper._has_next_page(soup) is False

    def test_no_pagination_no_next_url(self):
        soup = self._soup(_NO_PAGINATION)
        assert OlxScraper._next_page_url(soup) is None

    def test_max_page_num_wrapper(self):
        soup = self._soup(_PAGINATION_WRAPPER)
        assert OlxScraper._max_page_num(soup) == 5

    def test_max_page_num_wrapper_last(self):
        soup = self._soup(_PAGINATION_WRAPPER_LAST_PAGE)
        assert OlxScraper._max_page_num(soup) == 4

    def test_max_page_num_no_pagination(self):
        soup = self._soup(_NO_PAGINATION)
        assert OlxScraper._max_page_num(soup) == 1
