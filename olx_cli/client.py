from __future__ import annotations

import logging
import re
from typing import Optional

from curl_cffi import requests

from olx_cli.auth import get_access_token, logout
from olx_cli.scraper import _PAGE_TIMEOUT, _USER_AGENT

log = logging.getLogger(__name__)

_API_BASE = "https://www.olx.pl/api/v1"


def get_user_id_from_profile(profile: dict) -> Optional[str]:
    """Extract user ID from the user_ads_url in the profile data."""
    url = profile.get('user_ads_url', '')
    m = re.search(r'/user/([^/]+)/', url)
    return m.group(1) if m else None


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Version": "1.0.0"
    }


def get(endpoint: str) -> Optional[dict]:
    token = get_access_token()
    if not token:
        return None

    resp = requests.get(
        f"{_API_BASE}{endpoint}", 
        headers=_headers(token), 
        timeout=_PAGE_TIMEOUT, 
        impersonate="chrome120"
    )
    
    if resp.status_code == 401:
        log.warning("Token expired, clearing cache. Run 'olx-cli login' again.")
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
