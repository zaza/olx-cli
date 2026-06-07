from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

from olx_cli.scrapper import _USER_AGENT

log = logging.getLogger(__name__)

COGNITO_REGION = "eu-west-1"
COGNITO_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
COGNITO_CLIENT_ID = "15gc33db15l8fi8fttfqjtoifn"

_TOKENS_FILENAME = "tokens.json"
_HEADERS = {
    "Content-Type": "application/x-amz-json-1.1",
    "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    "User-Agent": _USER_AGENT,
    "Origin": "https://www.olx.pl",
    "Referer": "https://www.olx.pl/",
}


def _cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "olx-cli"


def _tokens_path() -> Path:
    return _cache_dir() / _TOKENS_FILENAME


def _now() -> int:
    return int(time.time())


def decode_jwt(token: str) -> dict:
    """Decode JWT payload (no signature verification)."""
    import base64

    parts = token.split(".")
    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def login(email: str, password: str) -> dict:
    body = {
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": COGNITO_CLIENT_ID,
        "AuthParameters": {
            "USERNAME": email,
            "PASSWORD": password,
        },
    }
    resp = requests.post(
        COGNITO_URL, json=body, headers=_HEADERS, timeout=15
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Login failed (HTTP {resp.status_code}): {resp.text[:200]}"
        )
    result = resp.json()["AuthenticationResult"]
    result["expires_at"] = _now() + result["ExpiresIn"]

    _cache_dir().mkdir(parents=True, exist_ok=True)
    _tokens_path().write_text(json.dumps(result, ensure_ascii=False))

    return result


def get_tokens() -> Optional[dict]:
    try:
        data = json.loads(_tokens_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    if _now() >= data.get("expires_at", 0):
        return _refresh(data.get("RefreshToken"))

    return data


def _refresh(refresh_token: Optional[str]) -> Optional[dict]:
    if not refresh_token:
        return None

    body = {
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "ClientId": COGNITO_CLIENT_ID,
        "AuthParameters": {"REFRESH_TOKEN": refresh_token},
    }
    try:
        resp = requests.post(
            COGNITO_URL, json=body, headers=_HEADERS, timeout=15
        )
        if resp.status_code != 200:
            log.warning("Token refresh failed: %s", resp.text[:200])
            return None
        result = resp.json()["AuthenticationResult"]
        result["expires_at"] = _now() + result["ExpiresIn"]
        result["RefreshToken"] = refresh_token

        _cache_dir().mkdir(parents=True, exist_ok=True)
        _tokens_path().write_text(json.dumps(result, ensure_ascii=False))

        return result
    except requests.RequestException as e:
        log.warning("Token refresh request failed: %s", e)
        return None


def get_access_token() -> Optional[str]:
    tokens = get_tokens()
    if tokens:
        return tokens["AccessToken"]
    return None


def logout() -> None:
    try:
        _tokens_path().unlink()
    except FileNotFoundError:
        pass
