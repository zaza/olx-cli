from __future__ import annotations

from unittest.mock import patch

import requests

from olx_cli.category_resolver import (
    CategoryResolver,
    format_category_path,
    suggest_categories,
)


def _mock_suggest(*args, **kwargs):
    query = args[-1] if args else kwargs.get('query', '')
    results = {
        'rowery gorskie': [{'id': '1651', 'name': 'Rowery górskie'}],
        'rowery miejskie': [{'id': '1650', 'name': 'Rowery miejskie'}],
    }
    return results.get(query, [])


class TestCategoryResolver:
    @patch('olx_cli.category_resolver.CategoryResolver._suggest', side_effect=_mock_suggest)
    def test_known_leaf_category(self, mock_suggest):
        r = CategoryResolver()
        assert r.resolve('sport-i-hobby/rowery/rowery-gorskie') == 1651

    @patch('olx_cli.category_resolver.CategoryResolver._suggest', side_effect=_mock_suggest)
    def test_known_leaf_category_miejske(self, mock_suggest):
        r = CategoryResolver()
        assert r.resolve('sport-i-hobby/rowery/rowery-miejskie') == 1650

    @patch('olx_cli.category_resolver.CategoryResolver._suggest', return_value=[])
    def test_unknown_category_returns_none(self, mock_suggest):
        r = CategoryResolver()
        assert r.resolve('nonexistent') is None

    def test_empty_string(self):
        r = CategoryResolver()
        assert r.resolve('') is None


class TestFormatCategoryPath:
    def test_full_path(self):
        item = {
            'id': '2272',
            'name': 'PlayStation',
            'path': [
                {'id': '99', 'name': 'Elektronika'},
                {'id': '93', 'name': 'Gry i Konsole'},
                {'id': '1603', 'name': 'Gry'},
            ],
        }
        assert format_category_path(item) == 'Elektronika / Gry i Konsole / Gry / PlayStation'

    def test_no_path(self):
        item = {'id': '1651', 'name': 'Rowery górskie', 'path': []}
        assert format_category_path(item) == 'Rowery górskie'

    def test_single_parent(self):
        item = {
            'id': '1651',
            'name': 'Rowery górskie',
            'path': [{'id': '1648', 'name': 'Rowery'}],
        }
        assert format_category_path(item) == 'Rowery / Rowery górskie'


class TestSuggestCategories:
    @patch('olx_cli.category_resolver.get_access_token', return_value='fake-token')
    @patch('olx_cli.category_resolver.requests.get')
    def test_returns_data(self, mock_get, mock_token):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'data': [{'id': '2272', 'name': 'PlayStation', 'path': []}],
        }
        result = suggest_categories('playstation')
        assert result == [{'id': '2272', 'name': 'PlayStation', 'path': []}]

    @patch('olx_cli.category_resolver.get_access_token', return_value='fake-token')
    @patch('olx_cli.category_resolver.requests.get')
    def test_empty_on_non_200(self, mock_get, mock_token):
        mock_get.return_value.status_code = 500
        result = suggest_categories('playstation')
        assert result == []

    @patch('olx_cli.category_resolver.get_access_token', return_value='fake-token')
    @patch('olx_cli.category_resolver.requests.get', side_effect=requests.RequestException)
    def test_empty_on_exception(self, mock_get, mock_token):
        result = suggest_categories('playstation')
        assert result == []

    @patch('olx_cli.category_resolver.get_access_token', return_value=None)
    def test_none_when_not_authenticated(self, mock_token):
        result = suggest_categories('playstation')
        assert result is None
