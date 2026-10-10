from __future__ import annotations

import asyncio
import json
import sys
import types

import pytest

import olx_cli.browser_auth as ba


def _payload(**overrides) -> str:
    body = {
        'access_token': 'ACCESS',
        'id_token': 'ID',
        'refresh_token': 'REFRESH',
        'expires_in': 3600,
    }
    body.update(overrides)
    return json.dumps({'body': body})


@pytest.fixture
def tokens_path(monkeypatch, tmp_path):
    p = tmp_path / 'tokens.json'
    monkeypatch.setattr(ba, '_cache_dir', lambda: tmp_path)
    monkeypatch.setattr(ba, '_tokens_path', lambda: p)
    monkeypatch.setattr(ba, '_now', lambda: 1000)
    return p


class TestTokensFromValues:
    def test_parses_valid_payload(self, tokens_path):
        result = ba._tokens_from_values([_payload()])
        assert result == {
            'AccessToken': 'ACCESS',
            'RefreshToken': 'REFRESH',
            'IdToken': 'ID',
            'ExpiresIn': 3600,
            'expires_at': 1000 + 3600,
        }

    def test_skips_invalid_json_then_picks_next(self, tokens_path):
        result = ba._tokens_from_values(['not-json', _payload()])
        assert result['AccessToken'] == 'ACCESS'

    def test_skips_entries_without_access_token(self, tokens_path):
        result = ba._tokens_from_values(
            [json.dumps({'body': {'refresh_token': 'r'}}), _payload()]
        )
        assert result['AccessToken'] == 'ACCESS'

    def test_skips_non_dict_json(self, tokens_path):
        result = ba._tokens_from_values(['[1, 2, 3]', 'null', _payload()])
        assert result['AccessToken'] == 'ACCESS'

    def test_returns_none_when_nothing_usable(self, tokens_path):
        assert ba._tokens_from_values([]) is None
        assert ba._tokens_from_values(None) is None
        assert ba._tokens_from_values(['nope', '{}']) is None

    def test_defaults_for_missing_optional_fields(self, tokens_path):
        result = ba._tokens_from_values(
            [json.dumps({'body': {'access_token': 'A'}})]
        )
        assert result['RefreshToken'] == ''
        assert result['IdToken'] == ''
        assert result['ExpiresIn'] == 3600
        assert result['expires_at'] == 1000 + 3600


class FakePlaywrightError(Exception):
    pass


class FakePage:
    def __init__(self, evaluate_result=None, fail_on=None):
        self.calls: list = []
        self.evaluate_result = evaluate_result
        self.fail_on = fail_on
        self.url = 'https://www.olx.pl/mojolx'

    async def goto(self, *a, **k):
        self.calls.append('goto')
        if self.fail_on == 'goto':
            raise FakePlaywrightError(
                'Target page, context or browser has been closed'
            )

    async def wait_for_selector(self, *a, **k):
        self.calls.append('wait_for_selector')

    async def fill(self, *a, **k):
        self.calls.append(('fill', a[0]))

    async def wait_for_function(self, *a, **k):
        self.calls.append('wait_for_function')

    async def click(self, *a, **k):
        self.calls.append('click')

    async def wait_for_url(self, *a, **k):
        self.calls.append('wait_for_url')

    async def wait_for_timeout(self, *a, **k):
        self.calls.append('wait_for_timeout')

    async def evaluate(self, *a, **k):
        self.calls.append('evaluate')
        return self.evaluate_result


class FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.closed = False

    async def new_context(self, **kw):
        return FakeContext(self.page)

    async def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, page):
        self.page = page

    async def new_page(self):
        return self.page


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser

    async def launch(self, **kw):
        return self.browser


class FakePlaywright:
    def __init__(self, browser):
        self.chromium = FakeChromium(browser)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def fake_playwright(monkeypatch):
    def install(page):
        browser = FakeBrowser(page)
        pkg = types.ModuleType('playwright')
        pkg.__path__ = []
        api = types.ModuleType('playwright.async_api')
        api.Error = FakePlaywrightError
        api.async_playwright = lambda: FakePlaywright(browser)
        monkeypatch.setitem(sys.modules, 'playwright', pkg)
        monkeypatch.setitem(sys.modules, 'playwright.async_api', api)
        return browser

    return install


class TestDoLogin:
    def test_happy_path_waits_for_enabled_button_and_persists(
        self, fake_playwright, tokens_path
    ):
        page = FakePage(evaluate_result=[_payload()])
        browser = fake_playwright(page)

        tokens = asyncio.run(
            ba._do_login(headless=False, email='a@b.pl', password='pw')
        )

        assert tokens['AccessToken'] == 'ACCESS'
        assert json.loads(tokens_path.read_text())['AccessToken'] == 'ACCESS'
        assert browser.closed is True
        # Filled the form, waited for #Login to enable, then clicked.
        assert ('fill', '#username') in page.calls
        assert ('fill', '#password') in page.calls
        assert 'wait_for_function' in page.calls
        assert 'click' in page.calls

    def test_no_credentials_skips_autofill(self, fake_playwright, tokens_path):
        page = FakePage(evaluate_result=[_payload()])
        fake_playwright(page)

        asyncio.run(ba._do_login(headless=False, email=None, password=None))

        assert ('fill', '#username') not in page.calls
        assert 'click' not in page.calls

    def test_playwright_error_is_wrapped_and_browser_closed(
        self, fake_playwright, tokens_path
    ):
        page = FakePage(fail_on='goto')
        browser = fake_playwright(page)

        with pytest.raises(RuntimeError, match='closed'):
            asyncio.run(
                ba._do_login(headless=True, email='a@b.pl', password='pw')
            )

        assert browser.closed is True

    def test_missing_tokens_raises_and_closes_browser(
        self, fake_playwright, tokens_path
    ):
        page = FakePage(evaluate_result=[])
        browser = fake_playwright(page)

        with pytest.raises(RuntimeError, match='Failed to extract'):
            asyncio.run(
                ba._do_login(headless=True, email='a@b.pl', password='pw')
            )

        assert browser.closed is True
