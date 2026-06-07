from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

from olx_cli.category import (
    _cache_age,
    _cache_path,
    _is_stale,
    ensure_cached,
    get_cached,
    validate,
)

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.olx.pl/motoryzacja/</loc></url>
  <url><loc>https://www.olx.pl/motoryzacja/samochody/</loc></url>
  <url><loc>https://www.olx.pl/motoryzacja/motocykle/</loc></url>
  <url><loc>https://www.olx.pl/nieruchomosci/</loc></url>
  <url><loc>https://www.olx.pl/nieruchomosci/mieszkania/</loc></url>
  <url><loc>https://www.olx.pl/elektronika/</loc></url>
</urlset>"""


class TestCachePaths:
    def test_cache_path_uses_xdg(self, monkeypatch):
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        p = _cache_path()
        assert str(p).endswith("/.cache/olx-cli/categories.json")

    def test_cache_path_respects_xdg_var(self, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", "/custom/cache")
        p = _cache_path()
        assert str(p) == "/custom/cache/olx-cli/categories.json"


class TestCacheAge:
    def test_no_cache_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: tmp_path / "nonexistent.json")
        assert _cache_age() is None

    def test_fresh_cache_not_stale(self, tmp_path, monkeypatch):
        p = tmp_path / "categories.json"
        p.write_text("[]")
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: p)
        assert _cache_age() is not None
        assert not _is_stale()


class TestGetCached:
    def test_no_file_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: tmp_path / "nonexistent.json")
        assert get_cached() == []

    def test_invalid_json_returns_empty_list(self, tmp_path, monkeypatch):
        p = tmp_path / "categories.json"
        p.write_text("not json")
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: p)
        assert get_cached() == []

    def test_valid_json_returns_data(self, tmp_path, monkeypatch):
        p = tmp_path / "categories.json"
        p.write_text('["foo", "foo/bar"]')
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: p)
        assert get_cached() == ["foo", "foo/bar"]


class TestEnsureCached:
    def test_valid_cache_returns_categories(self, tmp_path, monkeypatch):
        p = tmp_path / "categories.json"
        p.write_text('["a", "b"]')
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: p)
        monkeypatch.setattr("olx_cli.category._is_stale", lambda: False)
        assert ensure_cached() == ["a", "b"]

    def test_stale_cache_fetches_new(self, tmp_path, monkeypatch):
        p = tmp_path / "categories.json"
        p.write_text('["a"]')
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: p)
        monkeypatch.setattr("olx_cli.category._is_stale", lambda: True)
        monkeypatch.setattr("olx_cli.category._fetch_categories", lambda: ["motoryzacja", "motoryzacja/samochody", "nieruchomosci", "elektronika"])
        result = ensure_cached()
        assert "motoryzacja" in result
        assert "motoryzacja/samochody" in result
        assert "nieruchomosci" in result
        assert "elektronika" in result

    def test_fetch_failure_falls_back_to_cache(self, tmp_path, monkeypatch):
        p = tmp_path / "categories.json"
        p.write_text('["cached-item"]')
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: p)
        monkeypatch.setattr("olx_cli.category._is_stale", lambda: True)
        monkeypatch.setattr("olx_cli.category._fetch_categories", lambda: (_ for _ in ()).throw(Exception("no network")))
        result = ensure_cached()
        assert result == ["cached-item"]

    def test_fetch_failure_no_cache_returns_empty(self, tmp_path, monkeypatch):
        p = tmp_path / "nonexistent.json"
        monkeypatch.setattr("olx_cli.category._cache_path", lambda: p)
        monkeypatch.setattr("olx_cli.category._is_stale", lambda: True)
        monkeypatch.setattr("olx_cli.category._fetch_categories", lambda: (_ for _ in ()).throw(Exception("no network")))
        assert ensure_cached() == []


class TestValidate:
    def test_valid_category_passes(self, monkeypatch):
        monkeypatch.setattr("olx_cli.category.ensure_cached", lambda: ["motoryzacja", "motoryzacja/samochody"])
        validate("motoryzacja")
        validate("motoryzacja/samochody")

    def test_valid_category_with_slashes(self, monkeypatch):
        monkeypatch.setattr("olx_cli.category.ensure_cached", lambda: ["motoryzacja/samochody"])
        validate("motoryzacja/samochody/")

    def test_invalid_category_raises(self, monkeypatch):
        monkeypatch.setattr("olx_cli.category.ensure_cached", lambda: ["motoryzacja"])
        with pytest.raises(ValueError, match="Invalid category"):
            validate("invalid/cat")

    def test_empty_category_raises(self, monkeypatch):
        monkeypatch.setattr("olx_cli.category.ensure_cached", lambda: ["motoryzacja"])
        with pytest.raises(ValueError, match="category must not be empty"):
            validate("")
