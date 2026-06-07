from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import Tag

_SKIP_PRICES = frozenset({'za darmo', 'zamienię', 'do negocjacji', ''})

BASE_URL = "https://www.olx.pl"


def parse_price(price_str: str) -> int | None:
    s = price_str.strip().lower()
    if not s or s in _SKIP_PRICES:
        return None

    if 'zł' in s:
        s = s[:s.index('zł')].strip()

    s = s.replace(' ', '').replace(',', '.')

    try:
        return round(float(s))
    except ValueError:
        return None


def compute_stats(offers: list, pages_visited: int) -> dict:
    prices = []
    skipped = 0
    for o in offers:
        p = parse_price(o.price)
        if p is not None:
            prices.append(p)
        else:
            skipped += 1

    stats = {
        'total': len(offers),
        'skipped': skipped,
        'pages_visited': pages_visited,
    }

    if prices:
        stats['average'] = round(sum(prices) / len(prices))
        stats['median'] = round(median(prices))
    else:
        stats['average'] = None
        stats['median'] = None

    return stats


@dataclass
class OlxOffer:
    title: str
    price: str
    url: str
    city: str
    photo: Optional[str] = None

    @staticmethod
    def _keywords(query: str) -> List[str]:
        return query.lower().split()

    def matches_keywords(self, query: str) -> bool:
        kw = self._keywords(query)
        if not kw:
            return True
        title_lower = self.title.lower()
        return all(k in title_lower for k in kw)

    @classmethod
    def from_user_listing_offer(cls, data: dict) -> OlxOffer:
        price = data.get('price', {}).get('displayValue', '')
        city = data.get('location', {}).get('cityName', '')
        photos = data.get('photos', [])
        photo = photos[0] if photos else None
        return cls(
            title=data.get('title', ''),
            price=price,
            url=data.get('url', ''),
            city=city,
            photo=photo,
        )

    @classmethod
    def from_api_offer(cls, data: dict) -> OlxOffer:
        price = ''
        for p in data.get('params', []):
            if p.get('key') == 'price':
                price = p.get('value', {}).get('label', '')
                break

        photos = data.get('photos', [])
        photo = photos[0].get('link', '') if photos else None

        city = (
            data.get('location', {})
            .get('city', {})
            .get('name', '')
        )

        return cls(
            title=data.get('title', ''),
            price=price,
            url=data.get('url', ''),
            city=city,
            photo=photo,
        )

    @classmethod
    def from_element(cls, element: Tag) -> OlxOffer:
        title = element.select_one("h4").get_text(strip=True)

        price_el = element.select_one("p[data-testid=ad-price]")
        price = price_el.get_text(strip=True) if price_el else ""

        href = element.select_one("a[href]")["href"]
        url = href if href.startswith("http") else urljoin(BASE_URL, href)

        loc_el = element.select_one("p[data-testid=location-date]")
        city = loc_el.get_text(strip=True).split(" - ")[0] if loc_el else ""

        img = element.select_one("img[src]")
        photo = img["src"] if img else None

        return cls(title=title, price=price, url=url, city=city, photo=photo)
