from __future__ import annotations

from unittest.mock import patch

from olx_cli.category_resolver import CategoryResolver


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
