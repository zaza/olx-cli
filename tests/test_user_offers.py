from __future__ import annotations
import os

from pathlib import Path

OLX_CLI_USE_REAL_SITE = os.environ.get("OLX_CLI_USE_REAL_SITE", "false").lower() == "true"

import pytest
from unittest.mock import patch, MagicMock

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
    return o.title, o.price, o.url


class TestMojolxVsUserSearch:
    """mojolx (API) and search --user (HTML) should return the same offers."""

    def test_same_offers(self, authenticated_user):
        if OLX_CLI_USE_REAL_SITE:
            access_token, user_id = authenticated_user
            api_offers, _ = fetch_my_offers(access_token, max_pages=5)
            html_offers, _ = fetch_user_offers_html(user_id)

            assert type(api_offers) == type(html_offers)
            assert len(api_offers) == len(html_offers), (
                f'API returned {len(api_offers)} offers, HTML returned {len(html_offers)}'
            )

            api_set: frozenset = frozenset(_offer_key(o) for o in api_offers)
            html_set: frozenset = frozenset(_offer_key(o) for o in html_offers)

            assert api_set == html_set
            return

        with patch('olx_cli.client.requests.get'), patch('olx_cli.auth.requests.get'):
            access_token, user_id = authenticated_user
            # Mock API response for fetch_my_offers
            mock_api_resp = MagicMock()
            mock_api_resp.status_code = 200
            mock_api_resp.json.return_value = {
                "data": [{
                    "title": "Test Offer",
                    "price": {"value": 100},
                    "url": "https://www.olx.pl/d/test-offer-123/",
                    "city": "Kraków"
                }],
                "links": {}
            }
            
            # Since fetch_my_offers is in scraper.py, we need to mock requests.get in scraper
            with patch('olx_cli.scraper.requests.get') as mock_scraper_get:
                mock_scraper_get.return_value = mock_api_resp
                
                # Mock HTML response for fetch_user_offers_html
                mock_html_resp = MagicMock()
                mock_html_resp.status_code = 200
                # Simplified __PRERENDERED_STATE__ for mock
                state = {
                    "userListing": {
                        "userListing": {
                            "ads": [{
                                "title": "Test Offer",
                                "price": {"value": 100},
                                "url": "https://www.olx.pl/d/test-offer-123/",
                                "city": "Kraków"
                            }],
                            "totalElements": 1,
                            "totalPages": 1
                        }
                    }
                }
                import json
                json_state = json.dumps(state)
                # Escape for JS string
                escaped_state = json_state.replace('"', '\\"')
                mock_html_resp.text = f'window.__PRENDERED_STATE__="{escaped_state}";'
                mock_scraper_get.side_effect = [mock_api_resp, mock_html_resp]

                api_offers, _ = fetch_my_offers(access_token, max_pages=5)
                html_offers, _ = fetch_user_offers_html(user_id)

                assert type(api_offers) == type(html_offers)
                assert len(api_offers) == len(html_offers), (
                    f'API returned {len(api_offers)} offers, HTML returned {len(html_offers)}'
                )

                api_set: frozenset = frozenset(_offer_key(o) for o in api_offers)
                html_set: frozenset = frozenset(_offer_key(o) for o in html_offers)

                assert api_set == html_set
