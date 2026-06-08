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


async def _extract_tokens(page) -> dict | None:
    raw = await page.evaluate(
        f"window.localStorage.getItem('{_AUTH0_CACHE_KEY}')"
    )
    if not raw:
        return None
    data = json.loads(raw)
    body = data.get('body', {})
    if not body.get('access_token'):
        return None
    expires_in = body.get('expires_in', 3600)
    return {
        'AccessToken': body['access_token'],
        'RefreshToken': body.get('refresh_token', ''),
        'IdToken': body.get('id_token', ''),
        'ExpiresIn': expires_in,
        'expires_at': _now() + expires_in,
    }


async def _do_login(headless: bool, email: str | None, password: str | None) -> dict:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
        )
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
                login_btn = await page.wait_for_selector(
                    '#Login', timeout=15000
                )
                if login_btn and not await login_btn.is_disabled():
                    log.info('Auto-filling credentials...')
                    await page.fill('#username', email)
                    await page.fill('#password', password)
                    await page.click('#Login')
            except Exception:
                log.info('Auto-fill not possible, waiting for manual login...')

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

        _cache_dir().mkdir(parents=True, exist_ok=True)
        _tokens_path().write_text(
            json.dumps(tokens, ensure_ascii=False)
        )

        await browser.close()
        return tokens


def login_with_browser(
    headless: bool = False,
    email: str | None = None,
    password: str | None = None,
) -> dict:
    return asyncio.run(_do_login(headless, email, password))
