import time

import pytest

from olx_cli.query import build_url
from olx_cli.scrapper import OlxScrapper


@pytest.fixture(autouse=True)
def throttle():
    time.sleep(2)


class TestOlxScrapper:
    def test_has_offers(self):
        url = build_url("kierowce przyjme")
        scrapper = OlxScrapper(url, max_pages=1)
        offers = scrapper.get_offers()
        assert len(offers) > 0

    def test_pagination_limits(self):
        import requests as req_lib
        url = build_url("rower", photo_only=True)
        try:
            one_page = OlxScrapper(url, max_pages=1).get_offers()
            two_pages = OlxScrapper(url, max_pages=2).get_offers()
            assert len(two_pages) >= len(one_page)
        except req_lib.ReadTimeout:
            pytest.skip("OLX read timeout during pagination test")

    def test_all_fields_populated(self):
        url = build_url("rower", photo_only=True)
        scrapper = OlxScrapper(url, max_pages=1)
        offers = scrapper.get_offers()
        assert len(offers) > 0
        for o in offers:
            assert o.title, "title must be non-empty"
            assert o.price, "price must be non-empty"
            assert o.url, "url must be non-empty"
            assert o.city, "city must be non-empty"

    def test_photo_only_differs(self):
        url_all = build_url("rower")
        all_offers = OlxScrapper(url_all, max_pages=1).get_offers()

        url_photo = build_url("rower", photo_only=True)
        photo_offers = OlxScrapper(url_photo, max_pages=1).get_offers()

        # with photo should return fewer or equal results
        assert len(photo_offers) <= len(all_offers)
