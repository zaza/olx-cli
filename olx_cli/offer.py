from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import Tag

BASE_URL = "https://www.olx.pl"


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
