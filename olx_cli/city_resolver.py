from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from html.parser import HTMLParser

import requests

from olx_cli.cache import _cache_dir

log = logging.getLogger(__name__)

_OLX_URL = 'https://www.olx.pl'

_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/133.0.0.0 Safari/537.36'
    ),
}

_TRANSLIT_MAP = str.maketrans({
    'Ł': 'L', 'ł': 'l',
    'ß': 'ss', 'ẞ': 'SS',
})

_SITEMAP_CACHE_TTL = 604800  # 7 days


def _deaccent(text: str) -> str:
    text = text.translate(_TRANSLIT_MAP)
    text = unicodedata.normalize('NFKD', text)
    text = re.sub(r'[^a-zA-Z0-9 -]+', '', text)
    return text.strip()


def _sitemap_cache_path():
    return _cache_dir() / 'sitemap.json'


def _sitemap_cache_age() -> float | None:
    try:
        return time.time() - _sitemap_cache_path().stat().st_mtime
    except FileNotFoundError:
        return None


def _is_sitemap_cache_stale() -> bool:
    age = _sitemap_cache_age()
    return age is None or age > _SITEMAP_CACHE_TTL


def _load_cached_sitemap() -> dict[str, str] | None:
    try:
        data = json.loads(_sitemap_cache_path().read_text())
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def _save_sitemap_cache(slug_map: dict[str, str]) -> None:
    _cache_dir().mkdir(parents=True, exist_ok=True)
    _sitemap_cache_path().write_text(json.dumps(slug_map, ensure_ascii=False))


def _fetch_sitemap() -> dict[str, str]:
    resp = requests.get(
        f'{_OLX_URL}/sitemap/regions/',
        headers=_HEADERS,
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'Sitemap returned HTTP {resp.status_code}')
    parser = _SitemapParser()
    parser.feed(resp.text)
    return parser.map


class _SitemapParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.map: dict[str, str] = {}
        self._tag_stack: list[str] = []
        self._href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        if tag == 'a':
            self._href = dict(attrs).get('href', '')

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == 'a' and self._href:
            name = data.strip()
            if name and len(name) > 2 and self._href:
                href = self._href.rstrip('/')
                slug = href.split('/')[-1].split('_')[0]
                if not slug.startswith('http') and '/' not in slug:
                    self.map[name] = slug


class CityResolver:
    def __init__(self) -> None:
        self._id_cache: dict[str, int] = {}
        self._slug_map: dict[str, str] | None = None

    def resolve(self, city: str) -> int | None:
        key = city.strip()
        cached = self._id_cache.get(key)
        if cached is not None:
            return cached
        cid = self._fetch(key)
        if cid is not None:
            self._id_cache[key] = cid
        return cid

    def _load_sitemap(self) -> dict[str, str]:
        if self._slug_map is not None:
            return self._slug_map

        if not _is_sitemap_cache_stale():
            cached = _load_cached_sitemap()
            if cached is not None:
                self._slug_map = cached
                return cached

        try:
            slug_map = _fetch_sitemap()
            _save_sitemap_cache(slug_map)
            self._slug_map = slug_map
            log.info('Loaded %d city slugs from sitemap', len(slug_map))
            return slug_map
        except Exception:
            log.warning('Sitemap fetch failed', exc_info=True)
            cached = _load_cached_sitemap()
            if cached is not None:
                log.info('Falling back to stale sitemap cache (%d entries)', len(cached))
                self._slug_map = cached
                return cached

        self._slug_map = {}
        return self._slug_map

    def _fetch(self, city: str) -> int | None:
        slug = self._load_sitemap().get(city)
        if not slug:
            slug = _deaccent(city).lower().replace(' ', '-')
            log.debug('City %s not in sitemap, using deaccented slug: %s', city, slug)

        try:
            seen: set[str] = set()
            for offset in range(0, 1050, 50):
                resp = requests.get(
                    f'{_OLX_URL}/api/v1/offers/',
                    params={'query': '', 'city': slug, 'offset': offset, 'limit': 50},
                    headers=_HEADERS,
                    timeout=10,
                )
                if resp.status_code != 200:
                    break
                offers = resp.json().get('data', [])
                if not offers:
                    break
                for o in offers:
                    loc = o.get('location', {})
                    c = loc.get('city', {})
                    norm = c.get('normalized_name', '')
                    if not norm or norm in seen:
                        continue
                    seen.add(norm)
                    if norm == slug or norm == slug.replace('-', '') or norm == slug.replace('-', ' '):
                        return c['id']
        except Exception:
            log.warning('City pagination lookup failed for %s', city, exc_info=True)

        try:
            resp = requests.get(
                f'{_OLX_URL}/api/v1/offers/',
                params={'query': slug, 'limit': 10},
                headers=_HEADERS,
                timeout=10,
            )
            if resp.status_code == 200:
                for o in resp.json().get('data', []):
                    loc = o.get('location', {})
                    c = loc.get('city', {})
                    norm = c.get('normalized_name', '')
                    if norm and (norm == slug or norm == slug.replace('-', '') or norm == slug.replace('-', ' ')):
                        return c['id']
        except Exception:
            log.warning('City keyword fallback failed for %s', city, exc_info=True)

        return None
