from __future__ import annotations

from pathlib import Path

import pytest

from olx_cli.auth import read_credentials
from olx_cli.scraper import fetch_my_offers, fetch_user_offers_html


@pytest.fixture(scope='module')
def authenticated_user(tmp_path_factory):
    """Login and return (access_token, user_id). Skips if no credentials.txt."""
    import json
    import re

    from olx_cli.auth import (
        _tokens_path as _real_tokens_path,
        get_tokens,
        login as auth_login,
        logout,
    )
    from olx_cli.client import get_profile

    import olx_cli.auth as auth_module

    creds_path = Path.cwd() / 'credentials.txt'
    creds = read_credentials(creds_path)
    if creds is None:
        pytest.skip('credentials.txt not found')

    fake_tokens = tmp_path_factory.mktemp('olx-auth') / 'tokens.json'
    auth_module._tokens_path = lambda: fake_tokens

    email, password = creds
    try:
        auth_login(email, password)
    except RuntimeError:
        pytest.skip('login failed (WAF / network issue)')

    tokens = get_tokens()
    assert tokens is not None, 'token cache should be populated after login'
    access_token = tokens.get('AccessToken') or tokens.get('access_token')
    assert access_token, 'AccessToken missing from tokens'

    profile = get_profile()
    assert profile is not None, 'profile should be fetchable'

    m = re.search(r'/user/([^/]+)/', profile.get('user_ads_url', ''))
    assert m, f'user_ads_url not found in profile: {profile}'
    user_id = m.group(1)
    tokens['user_id'] = user_id
    auth_module._tokens_path = lambda: fake_tokens
    fake_tokens.write_text(json.dumps(tokens, ensure_ascii=False))

    yield access_token, user_id

    logout()
    auth_module._tokens_path = _real_tokens_path


def _offer_key(o):
    """Return a hashable key for comparing offers across APIs."""
    return (o.title, o.price, o.url)


class TestMojolxVsUserSearch:
    """mojolx (API) and search --user (HTML) should return the same offers."""

    def test_same_offers(self, authenticated_user):
        access_token, user_id = authenticated_user

        api_offers, _ = fetch_my_offers(access_token, max_pages=5)
        html_offers, _ = fetch_user_offers_html(user_id)

        assert type(api_offers) == type(html_offers)
        assert len(api_offers) == len(html_offers), (
            f'API returned {len(api_offers)} offers, HTML returned {len(html_offers)}'
        )

        api_set = frozenset(_offer_key(o) for o in api_offers)
        html_set = frozenset(_offer_key(o) for o in html_offers)

        missing_in_html = api_set - html_set
        extra_in_html = html_set - api_set

        assert not missing_in_html, (
            f'{len(missing_in_html)} offers from API missing in HTML: '
            f'{dict(missing_in_html)}'
        )
        assert not extra_in_html, (
            f'{len(extra_in_html)} offers from HTML not in API: '
            f'{dict(extra_in_html)}'
        )
