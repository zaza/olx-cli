from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from olx_cli.auth import _cache_dir, _now, _tokens_path

log = logging.getLogger(__name__)

_AUTH0_CACHE_KEY = (
    '@@auth0spajs@@::6j7elk01p32o648o1io8lvhhab'
    '::default::openid profile email offline_access'
)

_CREDS_PATH = Path.cwd() / 'credentials.txt'


def read_credentials(path: Path | None = None) -> tuple[str, str] | None:
    p = path or _CREDS_PATH
    try:
        text = p.read_text()
    except FileNotFoundError:
        return None
    creds = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            creds[k.strip()] = v.strip()
    email = creds.get('username') or creds.get('email')
    password = creds.get('password')
    if email and password:
        return email, password
    return None


def _tokens_from_values(values) -> dict | None:
    """Pick the first stored value that contains a usable access token."""
    for raw in values or []:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        body = data.get('body') or {}
        access_token = body.get('access_token')
        if not access_token:
            continue
        expires_in = body.get('expires_in', 3600)
        return {
            'AccessToken': access_token,
            'RefreshToken': body.get('refresh_token', ''),
            'IdToken': body.get('id_token', ''),
            'ExpiresIn': expires_in,
            'expires_at': _now() + expires_in,
        }
    return None


async def _extract_tokens(page) -> dict | None:
    # Scan every `@@auth0spajs@@` localStorage entry (preferred key first)
    # so a scope/key-format change does not silently break extraction.
    values = await page.evaluate(
        """
        (preferredKey) => {
            const seen = new Set();
            const out = [];
            const add = (value) => {
                if (value && !seen.has(value)) { seen.add(value); out.push(value); }
            };
            add(window.localStorage.getItem(preferredKey));
            for (const key of Object.keys(window.localStorage)) {
                if (key.startsWith('@@auth0spajs@@')) {
                    add(window.localStorage.getItem(key));
                }
            }
            return out;
        }
        """,
        _AUTH0_CACHE_KEY,
    )
    return _tokens_from_values(values)


async def _do_login(headless: bool, email: str | None, password: str | None) -> dict:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    tokens: dict | None = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                ],
            )
            try:
                ctx = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    locale='pl-PL',
                    timezone_id='Europe/Warsaw',
                )
                page = await ctx.new_page()

                if not headless:
                    print(
                        'A browser window will open. Log in to OLX manually.\n'
                        'The script will wait up to 3 minutes.',
                        flush=True,
                    )

                await page.goto(
                    'https://www.olx.pl/mojolx', wait_until='networkidle'
                )

                if email and password:
                    try:
                        await page.wait_for_selector('#username', timeout=15000)
                        await page.fill('#username', email)
                        await page.fill('#password', password)
                        # The submit button only enables once the form is
                        # valid, so wait for it instead of racing the check
                        # (otherwise the click is silently skipped).
                        await page.wait_for_function(
                            "!document.querySelector('#Login').disabled",
                            timeout=15000,
                        )
                        await page.click('#Login')
                        log.info('Auto-filled credentials and submitted login.')
                    except Exception:
                        log.info(
                            'Auto-fill not possible, waiting for manual login...'
                        )

                def _on_olx(url: str) -> bool:
                    return 'olx.pl' in url and 'login' not in url

                try:
                    await page.wait_for_url(_on_olx, timeout=180000)
                except Exception:
                    log.warning(
                        'Timeout waiting for redirect to olx.pl. '
                        'Current URL: %s', page.url,
                    )

                await page.wait_for_timeout(2000)

                tokens = await _extract_tokens(page)
                if not tokens:
                    raise RuntimeError(
                        'Failed to extract auth tokens. '
                        'Make sure you completed the login in the browser.'
                    )
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    except PlaywrightError as exc:
        raise RuntimeError(
            'Browser login failed: the page or browser was closed '
            f'unexpectedly ({type(exc).__name__}: {exc}).'
        ) from exc

    assert tokens is not None
    _cache_dir().mkdir(parents=True, exist_ok=True)
    _tokens_path().write_text(
        json.dumps(tokens, ensure_ascii=False)
    )
    return tokens


def login_with_browser(
    headless: bool = False,
    email: str | None = None,
    password: str | None = None,
) -> dict:
    return asyncio.run(_do_login(headless, email, password))
