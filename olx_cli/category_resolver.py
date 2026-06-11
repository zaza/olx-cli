from __future__ import annotations

import logging
import unicodedata

import requests

from olx_cli.auth import get_access_token

log = logging.getLogger(__name__)

_API_URL = 'https://www.olx.pl/api/v1/categories/suggestion/'


def suggest_categories(query: str) -> list[dict] | None:
    token = get_access_token()
    if not token:
        return None
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'X-Client': 'DESKTOP',
            'X-Platform-Type': 'mobile-html5',
        }
        resp = requests.get(_API_URL, params={'q': query}, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('data', [])
    except Exception:
        log.warning('Category suggestion lookup failed for %s', query, exc_info=True)
    return []


def format_category_path(item: dict) -> str:
    parts = [p['name'] for p in item.get('path', [])]
    parts.append(item['name'])
    return ' / '.join(parts)


class CategoryResolver:
    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize('NFKD', text)
        return ''.join(c for c in text if not unicodedata.category(c).startswith('M')).lower()

    def resolve(self, category_slug: str) -> int | None:
        slug = category_slug.strip().strip('/')
        leaf = slug.rsplit('/', 1)[-1]
        query = leaf.replace('-', ' ')
        normalized_query = self._normalize(query)
        results = self._suggest(query)
        for r in results:
            name = self._normalize(r.get('name', ''))
            if normalized_query in name:
                return int(r['id'])
        if results:
            return int(results[0]['id'])
        return None

    def _suggest(self, query: str) -> list[dict]:
        results = suggest_categories(query)
        if results is None:
            return []
        return results
