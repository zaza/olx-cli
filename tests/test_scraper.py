import pytest
import requests as req
from bs4 import BeautifulSoup

from olx_cli.query import build_url
from olx_cli.scraper import OlxScraper, _DEFAULT_HEADERS, _PAGE_TIMEOUT


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
