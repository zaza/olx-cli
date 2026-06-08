from __future__ import annotations

import logging
import uuid
from pathlib import Path

import requests

from olx_cli.auth import get_access_token
from olx_cli.category_resolver import CategoryResolver
from olx_cli.city_resolver import CityResolver

log = logging.getLogger(__name__)

_POSTING_API_URL = (
    'https://posting-services.prd.01.eu-west-1.eu.olx.org/api/v2/offers'
)

_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Client': 'DESKTOP',
    'X-Platform-Type': 'mobile-html5',
    'X-Platform': 'd',
    'Referer': 'https://www.olx.pl/adding/',
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/133.0.0.0 Safari/537.36'
    ),
}

city_resolver = CityResolver()
category_resolver = CategoryResolver()


def read_offer(path: str) -> dict:
    text = Path(path).read_text(encoding='utf-8')
    parts = text.split('---', 1)
    header_text = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else ''

    data: dict[str, str] = {}
    for line in header_text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, val = line.split('=', 1)
            data[key.strip().lower()] = val.strip()

    data['description'] = description
    return data


def find_offer_files(path: str) -> list[str]:
    p = Path(path)
    if p.is_file():
        return [str(p)]
    return [str(f) for f in p.rglob('offer.txt')]


def validate_offer(data: dict) -> list[str]:
    errors = []

    if not data.get('title'):
        errors.append('title is required')
    elif len(data['title']) < 16:
        errors.append('title must be at least 16 characters')
    elif len(data['title']) > 150:
        errors.append('title must be at most 150 characters')

    if not data.get('description'):
        errors.append('description is required (after --- separator)')
    elif len(data['description']) < 40:
        errors.append('description must be at least 40 characters')
    elif len(data['description']) > 900:
        errors.append('description must be at most 900 characters')

    if not data.get('price'):
        errors.append('price is required')
    else:
        cleaned = data['price'].replace(' ', '').replace(',', '.').replace('zł', '').strip()
        try:
            if float(cleaned) <= 0:
                errors.append('price must be positive')
        except ValueError:
            errors.append(f"invalid price: {data['price']}")

    if not data.get('category'):
        errors.append('category is required')

    if not data.get('city_id') and not data.get('city'):
        errors.append('city or city_id is required')

    if not data.get('email'):
        errors.append('email is required')

    return errors


def _parse_price_value(price_str: str) -> str:
    cleaned = price_str.replace(' ', '').replace(',', '.').replace('zł', '').strip()
    return str(int(float(cleaned)))


def _build_payload(data: dict) -> dict:
    category_id = data.get('category_id')
    if not category_id:
        category_id = category_resolver.resolve(data.get('category', ''))

    city_id = data.get('city_id')
    if not city_id:
        city_id = city_resolver.resolve(data.get('city', ''))

    state_map = {
        'new': 'new',
        'used': 'used',
        'damaged': 'damaged',
        'yes': 'used',
        'tak': 'used',
    }
    state = state_map.get(data.get('state', '').lower(), 'used')

    payload: dict = {
        'brand': 'olxpl',
        'lang': 'pl',
        'category_id': int(category_id) if category_id else 0,
        'city_id': int(city_id) if city_id else 0,
        'description': data['description'],
        'email': data['email'],
        'parameters': {
            'price': {
                'price': _parse_price_value(data['price']),
            },
            'state': state,
            'equipment': {},
        },
        'person': data.get('contact_name', ''),
        'phone': data.get('phone', ''),
        'title': data['title'],
        'images': [],
        'private_business': 'private',
        'components_data': {
            'reposting': {
                'action': 'ad_posted',
                'data': '{"reposting":false}',
            },
        },
    }

    return payload


def submit_offer(data: dict) -> dict:
    token = get_access_token()
    if not token:
        raise RuntimeError('Not logged in. Run olx-cli login first.')

    errors = validate_offer(data)
    if errors:
        raise ValueError('; '.join(errors))

    payload = _build_payload(data)
    headers = {
        **_HEADERS,
        'Authorization': f'Bearer {token}',
        'postingId': str(uuid.uuid4()),
    }

    try:
        resp = requests.post(
            _POSTING_API_URL, json=payload, headers=headers, timeout=30
        )
        if resp.status_code in (200, 201):
            return resp.json()
        if resp.status_code == 401:
            raise RuntimeError('Session expired. Run olx-cli login again.')
        detail = resp.text[:500]
        raise RuntimeError(f'HTTP {resp.status_code}: {detail}')
    except requests.RequestException as e:
        raise RuntimeError(f'Failed to submit offer: {e}')
