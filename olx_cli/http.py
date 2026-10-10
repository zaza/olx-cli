from __future__ import annotations

"""HTTP layer with browser TLS impersonation.

OLX.pl blocks the plain-``requests`` TLS/HTTP2 fingerprint (CloudFront
returns HTTP 403 before any HTML is served). ``curl_cffi`` impersonates
Chrome's TLS/HTTP2 fingerprint at the socket level — no browser or JS
required. All network calls in the project go through this module so the
impersonation profile (and any future fallback) is configured in one place.
"""

from curl_cffi import requests as _requests
from curl_cffi.requests.exceptions import (
    RequestException as RequestException,
)

IMPERSONATE = "chrome"

Session = _requests.Session
Response = _requests.Response


def new_session(**kwargs) -> Session:
    kwargs.setdefault("impersonate", IMPERSONATE)
    return Session(**kwargs)


def get(url: str, **kwargs) -> Response:
    kwargs.setdefault("impersonate", IMPERSONATE)
    return _requests.get(url, **kwargs)


def post(url: str, **kwargs) -> Response:
    kwargs.setdefault("impersonate", IMPERSONATE)
    return _requests.post(url, **kwargs)