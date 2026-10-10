import json
import os

from unittest.mock import patch, MagicMock

from olx_cli.query import build_url
from olx_cli.scraper import (
    OlxScraper,
    _parse_ssr_listing,
    _page_url,
)

OLX_CLI_USE_REAL_SITE = os.environ.get("OLX_CLI_USE_REAL_SITE", "false").lower() == "true"


def _ad(title, price, url, city):
    return {
        'title': title,
        'price': {'displayValue': price},
        'url': url,
        'location': {'cityName': city},
        'photos': [],
    }


def _listing_state(listing, path=("listing", "listing")):
    """Nest a listing dict under an SSR state path."""
    state = {}
    node = state
    for key in path:
        node[key] = {}
        node = node[key]
    node.update(listing)
    return state


def _ssr_html(listing, path=("listing", "listing")):
    state = _listing_state(listing, path)
    escaped = json.dumps(state).replace('"', '\\"')
    return f'window.__PRERENDERED_STATE__="{escaped}";'


def _mock_resp(listing, path=("listing", "listing")):
    mock = MagicMock()
    mock.status_code = 200
    mock.text = _ssr_html(listing, path)
    return mock


class TestOlxScraper:
    def test_has_offers(self):
        if OLX_CLI_USE_REAL_SITE:
            url = build_url("kierowce przyjme")
            scrapper = OlxScraper(url, max_pages=1)
            offers = scrapper.get_offers()
            assert len(offers) > 0
            return

        with patch('olx_cli.http.get') as mock_get:
            mock_get.return_value = _mock_resp({
                'ads': [_ad('Test Title', '100 zł', '/offer/1', 'Kraków')],
                'totalElements': 1,
                'totalPages': 1,
            })
            offers = OlxScraper(build_url("kierowce przyjme"), max_pages=1).get_offers()
            assert len(offers) == 1
            assert offers[0].title == 'Test Title'
            assert offers[0].clean_price == '100 zł'
            assert offers[0].city == 'Kraków'

    def test_pagination(self):
        if OLX_CLI_USE_REAL_SITE:
            url = build_url("rower", photo_only=True)
            one_page = OlxScraper(url, max_pages=1).get_offers()
            two_pages = OlxScraper(url, max_pages=2).get_offers()
            assert len(two_pages) > len(one_page), (
                f"2 pages ({len(two_pages)}) should return more than 1 page ({len(one_page)})"
            )
            return

        page1 = {
            'ads': [_ad('T1', '10 zł', '/o1', 'C1')],
            'totalElements': 2,
            'totalPages': 2,
        }
        page2 = {
            'ads': [_ad('T2', '20 zł', '/o2', 'C2')],
            'totalElements': 2,
            'totalPages': 2,
        }

        with patch('olx_cli.http.get') as mock_get:
            mock_get.side_effect = [_mock_resp(page1), _mock_resp(page2)]
            one_page = OlxScraper(build_url("rower", photo_only=True), max_pages=1).get_offers()

            mock_get.side_effect = [_mock_resp(page1), _mock_resp(page2)]
            two_pages = OlxScraper(build_url("rower", photo_only=True), max_pages=2).get_offers()

            assert len(one_page) == 1
            assert len(two_pages) == 2

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

        with patch('olx_cli.http.get') as mock_get:
            mock_get.return_value = _mock_resp({
                'ads': [_ad('Rower górski', '3 500 zł', '/offer/1', 'Kraków')],
                'totalElements': 1,
                'totalPages': 1,
            })
            offers = OlxScraper(build_url("rower", photo_only=True), max_pages=1).get_offers()
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

        with patch('olx_cli.http.get') as mock_get:
            mock_get.side_effect = [
                _mock_resp({
                    'ads': [_ad('Title 1', '10 zł', '/o1', 'C1')],
                    'totalElements': 1,
                    'totalPages': 1,
                }),
                _mock_resp({
                    'ads': [_ad('Title 2', '20 zł', '/o2', 'C2')],
                    'totalElements': 1,
                    'totalPages': 1,
                }),
            ]

            all_offers = OlxScraper(build_url("rower"), max_pages=1).get_offers()
            photo_offers = OlxScraper(build_url("rower", photo_only=True), max_pages=1).get_offers()

            assert {o.title for o in all_offers} != {o.title for o in photo_offers}


class TestSsrListing:
    def test_parse_search_listing(self):
        ads = [_ad('Rower', '100 zł', '/d/oferta/1/', 'Warszawa')]
        html = _ssr_html({'ads': ads, 'totalElements': 7, 'totalPages': 3})
        offers, total_elements, total_pages = _parse_ssr_listing(html)
        assert len(offers) == 1
        assert total_elements == 7
        assert total_pages == 3

    def test_parse_user_listing(self):
        ads = [_ad('Rower', '100 zł', '/d/oferta/2/', 'Kraków')]
        html = _ssr_html(
            {'ads': ads, 'totalElements': 42, 'totalPages': 1},
            path=("userListing", "userListing"),
        )
        offers, total_elements, total_pages = _parse_ssr_listing(html)
        assert len(offers) == 1
        assert total_elements == 42
        assert total_pages == 1

    def test_no_ssr_returns_none(self):
        assert _parse_ssr_listing('<html><body>plain</body></html>') is None

    def test_missing_listing_returns_none(self):
        state = {'listing': {'filters': {'data': {}}}}
        escaped = json.dumps(state).replace('"', '\\"')
        html = f'window.__PRERENDERED_STATE__="{escaped}";'
        assert _parse_ssr_listing(html) is None


class TestPageUrl:
    def test_plain_url(self):
        assert _page_url('https://www.olx.pl/oferty/q-rower/', 2) == \
            'https://www.olx.pl/oferty/q-rower/?page=2'

    def test_preserves_existing_query_params(self):
        url = build_url('rower', photo_only=True, min_price=100)
        assert _page_url(url, 2) == url + '&page=2'

    def test_replaces_existing_page_param(self):
        assert _page_url('https://www.olx.pl/oferty/q-rower/?page=3', 2) == \
            'https://www.olx.pl/oferty/q-rower/?page=2'