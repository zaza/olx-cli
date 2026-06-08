from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from olx_cli.cache import _cache_dir
from olx_cli.scraper import _USER_AGENT, _DEFAULT_HEADERS

log = logging.getLogger(__name__)

COGNITO_REGION = "eu-west-1"
COGNITO_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
COGNITO_CLIENT_ID = "15gc33db15l8fi8fttfqjtoifn"

log = logging.getLogger(__name__)

_TOKENS_FILENAME = "tokens.json"

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_DEFAULT_HEADERS)
    # Visit front page to prime cookies / WAF
    s.get("https://www.olx.pl/", timeout=15)
    return s


def _cognito_headers() -> dict:
    return {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        "User-Agent": _USER_AGENT,
        "Origin": "https://www.olx.pl",
        "Referer": "https://www.olx.pl/",
        "Accept": "*/*",
        "Accept-Language": _DEFAULT_HEADERS["Accept-Language"],
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Ch-Ua": '"Not/A)Brand";v="99", "Google Chrome";v="135", "Chromium";v="135"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Linux"',
    }


def _tokens_path() -> Path:
    return _cache_dir() / _TOKENS_FILENAME


def _now() -> int:
    return int(time.time())


def decode_jwt(token: str) -> dict:
    """Decode JWT payload (no signature verification)."""
    parts = token.split(".")
    return json.loads(base64.urlsafe_b64decode(parts[1] + "==="))


def _cognito_post(body: dict) -> requests.Response:
    sess = _session()
    return sess.post(COGNITO_URL, json=body, headers=_cognito_headers(), timeout=15)


def _save_tokens(tokens: dict) -> None:
    _cache_dir().mkdir(parents=True, exist_ok=True)
    _tokens_path().write_text(json.dumps(tokens, ensure_ascii=False))


def login(email: str, password: str) -> dict:
    body = {
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": COGNITO_CLIENT_ID,
        "AuthParameters": {
            "USERNAME": email,
            "PASSWORD": password,
        },
    }
    resp = _cognito_post(body)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Login failed (HTTP {resp.status_code}): {resp.text[:200]}"
        )
    result = resp.json()["AuthenticationResult"]
    result["expires_at"] = _now() + result["ExpiresIn"]

    _save_tokens(result)

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
        resp = _cognito_post(body)
        if resp.status_code != 200:
            log.warning("Token refresh failed: %s", resp.text[:200])
            return None
        result = resp.json()["AuthenticationResult"]
        result["expires_at"] = _now() + result["ExpiresIn"]
        result["RefreshToken"] = refresh_token

        _save_tokens(result)

        return result
    except requests.RequestException as e:
        log.warning("Token refresh request failed: %s", e)
        return None


def get_access_token() -> Optional[str]:
    tokens = get_tokens()
    if tokens:
        return tokens["AccessToken"]
    return None


def read_credentials(path: Path) -> tuple[str, str] | None:
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    creds = {k.strip(): v.strip() for line in text.splitlines() if '=' in line and not line.startswith('#') for k, v in [line.split('=', 1)]}
    email = creds.get('username') or creds.get('email')
    password = creds.get('password')
    if email and password:
        return email, password
    return None


def logout() -> None:
    try:
        _tokens_path().unlink()
    except FileNotFoundError:
        pass
