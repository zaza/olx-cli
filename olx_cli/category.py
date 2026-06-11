from __future__ import annotations

import json
import logging
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import List, Optional
from urllib.request import urlopen

from olx_cli.cache import _cache_dir

log = logging.getLogger(__name__)

SITEMAP_URL = "https://www.olx.pl/sitemap-categories.xml"
CACHE_TTL = 86400  # 24 hours


def _cache_path() -> Path:
    return _cache_dir() / "categories.json"


def _cache_age() -> Optional[float]:
    try:
        return time.time() - _cache_path().stat().st_mtime
    except FileNotFoundError:
        return None


def _is_stale() -> bool:
    age = _cache_age()
    return age is None or age > CACHE_TTL


def _fetch_categories() -> List[str]:
    resp = urlopen(SITEMAP_URL, timeout=15)
    tree = ElementTree.parse(resp)
    root = tree.getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    categories: set[str] = set()
    for loc in root.findall(".//s:loc", ns):
        path = (loc.text or '').replace("https://www.olx.pl/", "").rstrip("/")
        if not path:
            continue
        parts = path.split("/")
        categories.add(parts[0])
        for i in range(1, len(parts)):
            categories.add("/".join(parts[: i + 1]))
    return sorted(categories)


def get_cached() -> List[str]:
    try:
        return json.loads(_cache_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def ensure_cached() -> List[str]:
    if _is_stale():
        try:
            categories = _fetch_categories()
            _cache_dir().mkdir(parents=True, exist_ok=True)
            _cache_path().write_text(json.dumps(categories, ensure_ascii=False))
            return categories
        except Exception as e:
            log.warning("Failed to fetch categories: %s", e)
            cached = get_cached()
            if cached:
                return cached
            return []
    return get_cached()


def validate(category: str) -> None:
    if not category:
        raise ValueError("category must not be empty")
    normalized = category.strip().strip("/")
    if normalized not in ensure_cached():
        raise ValueError(
            f"Invalid category '{category}'. "
            f"Use 'olx-cli categories' to list available categories."
        )
