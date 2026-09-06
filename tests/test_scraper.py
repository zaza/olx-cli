import os
import requests as req
from bs4 import BeautifulSoup
from unittest.mock import patch, MagicMock

from olx_cli.query import build_url
from olx_cli.scraper import OlxScraper, _DEFAULT_HEADERS, _PAGE_TIMEOUT

OLX_CLI_USE_REAL_SITE = os.environ.get("OLX_CLI_USE_REAL_SITE", "false").lower() == "true"

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
        if OLX_CLI_USE_REAL_SITE:
            url = build_url("kierowce przyjme")
            scrapper = OlxScraper(url, max_pages=1)
            offers = scrapper.get_offers()
            assert len(offers) > 0
            return

        with patch('requests.get') as mock_get:
            # Mock a response with at least one offer
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '<html><div data-testid="listing-grid"><div data-testid="l-card"><h4 data-testid="ad-title">Test Title</h4><p data-testid="ad-price">100 zł</p><a href="/offer/1">Link</a><p data-testid="location-date">Kraków - Today</p></div></div><span data-testid="total-count">Znaleźliśmy 1 ogłoszenie</span></html>'
            mock_get.return_value = mock_resp

            url = build_url("kierowce przyjme")
            scrapper = OlxScraper(url, max_pages=1)
            offers = scrapper.get_offers()
            assert len(offers) > 0

    def test_pagination(self):
        if OLX_CLI_USE_REAL_SITE:
            url = build_url("rower", photo_only=True)
            one_page = OlxScraper(url, max_pages=1).get_offers()
            two_pages = OlxScraper(url, max_pages=2).get_offers()
            assert len(two_pages) > len(one_page), (
                f"2 pages ({len(two_pages)}) should return more than 1 page ({len(one_page)})"
            )
            return

        with patch('requests.get') as mock_get:
            # Mock page 1 and page 2
            mock_resp1 = MagicMock()
            mock_resp1.status_code = 200
            mock_resp1.text = '<html><div data-testid="listing-grid"><div data-testid="l-card"><div><h6 data-testid="ad-title">T1</h6></div><div data-testid="ad-price">10 zł</div><a href="/o1">L1</a><div data-testid="ad-city">C1</div></div></div><a data-testid="pagination-forward" href="/page=2">Next</a><span data-testid="total-count">Znaleźliśmy 2 ogłoszenia</span></html>'
            
            mock_resp2 = MagicMock()
            mock_resp2.status_code = 200
            mock_resp2.text = '<html><div data-testid="listing-grid"><div data-testid="l-card"><div><h6 data-testid="ad-title">T2</h6></div><div data-testid="ad-price">20 zł</div><a href="/o2">L2</a><div data-testid="ad-city">C2</div></div></div></html>'
            
            mock_get.side_effect = [mock_resp1, mock_resp2]

            url = build_url("rower", photo_only=True)
            one_page = OlxScraper(url, max_pages=1).get_offers()
            
            mock_get.side_effect = [mock_resp1, mock_resp2]
            two_pages = OlxScraper(url, max_pages=2).get_offers()
            assert len(two_pages) > len(one_page), (
                f"2 pages ({len(two_pages)}) should return more than 1 page ({len(one_page)})"
            )

    def test_next_page_url(self):
        if OLX_CLI_USE_REAL_SITE:
            url = build_url("rower")
            resp = req.get(url, headers=_DEFAULT_HEADERS, timeout=_PAGE_TIMEOUT)
            soup = BeautifulSoup(resp.text, "lxml")
            next_url = OlxScraper._next_page_url(soup)
            assert next_url is not None, "pagination-forward link should exist for high-volume query"
            assert "page=2" in next_url or "?page=2" in next_url, f"expected page=2 in next_url, got {next_url}"
            return

        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '<html><a data-testid="pagination-forward" href="/oferty/q-rower/?page=2">Next</a></html>'
            mock_get.return_value = mock_resp

            soup = BeautifulSoup(mock_resp.text, "lxml")
            next_url = OlxScraper._next_page_url(soup)
            assert next_url is not None, "pagination-forward link should exist for high-volume query"
            assert "page=2" in next_url or "?page=2" in next_url, f"expected page=2 in next_url, got {next_url}"

    def test_all_fields_populated(self):
        if OLX_CLI_USE_REAL_SITE:
            url = build_url("rower", photo_only=True)
            scrapper = OlxScraper(url, max_pages=1)
            offers = scrapper.get_offers()
            assert len(offers) > 0
            for o in offers:
                assert o.title, "title must be non-empty"
                assert o.price, "price must be non-empty"
                assert o.url, "url must be non-empty"
                assert o.city, "city must be non-empty"
            return

        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '<html><div data-testid="listing-grid"><div data-testid="l-card"><h4>Title</h4><p data-testid="ad-price">100 zł</p><a href="/offer/1">URL</a><p data-testid="location-date">City - Today</p></div></div><span data-testid="total-count">Znaleźliśmy 1 ogłoszenie</span></html>'
            mock_get.return_value = mock_resp

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
        if OLX_CLI_USE_REAL_SITE:
            url_all = build_url("rower")
            all_offers = OlxScraper(url_all, max_pages=1).get_offers()

            url_photo = build_url("rower", photo_only=True)
            photo_offers = OlxScraper(url_photo, max_pages=1).get_offers()

            titles_all = {o.title for o in all_offers}
            titles_photo = {o.title for o in photo_offers}
            assert titles_all != titles_photo, "photo filter should change results"
            return

        with patch('requests.get') as mock_get:
            # Mock for all offers
            mock_resp_all = MagicMock()
            mock_resp_all.status_code = 200
            mock_resp_all.text = '<html><div data-testid="listing-grid"><div data-testid="l-card"><h4>Title 1</h4><p data-testid="ad-price">10 zł</p><a href="/o1">L1</a><p data-testid="location-date">C1 - T</p></div></div></html>'
        
            # Mock for photo offers
            mock_resp_photo = MagicMock()
            mock_resp_photo.status_code = 200
            mock_resp_photo.text = '<html><div data-testid="listing-grid"><div data-testid="l-card"><h4>Title 2</h4><p data-testid="ad-price">20 zł</p><a href="/o2">L2</a><p data-testid="location-date">C2 - T</p></div></div></html>'
        
            mock_get.side_effect = [mock_resp_all, mock_resp_photo]

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
