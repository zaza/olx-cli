from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from olx_cli.auth import get_access_token
from olx_cli.scrapper import _USER_AGENT

log = logging.getLogger(__name__)

_API_BASE = "https://www.olx.pl/api/v1"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }


def get(endpoint: str) -> Optional[dict]:
    token = get_access_token()
    if not token:
        return None

    resp = requests.get(
        f"{_API_BASE}{endpoint}", headers=_headers(token), timeout=15
    )
    if resp.status_code == 401:
        log.warning("Token expired, clearing cache. Run 'olx-cli login' again.")
        from olx_cli.auth import logout

        logout()
        return None

    if resp.status_code != 200:
        log.warning("API returned HTTP %s: %s", resp.status_code, resp.text[:200])
        return None

    return resp.json()


def get_profile() -> Optional[dict]:
    data = get("/users/me/")
    if data is None:
        return None
    return data.get("data")


def get_offers() -> Optional[list[dict]]:
    data = get("/users/me/offers/")
    if data is None:
        return None
    return data.get("data", [])
