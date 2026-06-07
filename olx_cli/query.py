from __future__ import annotations

import unicodedata
from typing import Optional
from urllib.parse import quote, urlencode, urlunparse

from olx_cli.radius import validate_radius

BASE_URL = "https://www.olx.pl"


def _deaccent(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))


def build_url(
    query: str,
    *,
    photo_only: bool = False,
    location: Optional[str] = None,
    radius: Optional[int] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
) -> str:
    if radius is not None:
        if location is None:
            raise ValueError("radius requires a location")
        validate_radius(radius)

    if min_price is not None and min_price < 0:
        raise ValueError("min_price must be >= 0")

    if max_price is not None and max_price < 0:
        raise ValueError("max_price must be >= 0")

    if min_price is not None and max_price is not None and min_price >= max_price:
        raise ValueError("min_price must be less than max_price")

    path_parts = []

    if location:
        path_parts.append(_deaccent(location))
    else:
        path_parts.append("oferty")

    if query:
        path_parts.append(f"q-{query.replace(' ', '-')}")

    path = "/" + "/".join(path_parts) + "/"
    path = quote(path, safe="/")

    params = {}
    if photo_only:
        params["search[photos]"] = "1"
    if radius is not None:
        params["search[dist]"] = str(radius)
    if min_price is not None:
        params["search[filter_float_price:from]"] = (
            "free" if min_price == 0 else str(min_price)
        )
    if max_price is not None and max_price > 0:
        params["search[filter_float_price:to]"] = str(max_price)

    query_string = urlencode(params) if params else ""
    return urlunparse(("https", "www.olx.pl", path, "", query_string, ""))


def describe(query: str, *, photo_only: bool) -> str:
    desc = f"'{query}'"
    if photo_only:
        desc += " with photo"
    return desc
