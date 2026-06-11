from __future__ import annotations

import json

from olx_cli.city_resolver import (
    CityResolver,
    _deaccent,
    _fetch_sitemap,
    _sitemap_cache_path,
)


class TestDeaccent:
    def test_krakow(self):
        assert _deaccent('Kraków') == 'Krakow'

    def test_lodz(self):
        assert _deaccent('Łódź') == 'Lodz'

    def test_gdansk(self):
        assert _deaccent('Gdańsk') == 'Gdansk'

    def test_zielona_gora(self):
        assert _deaccent('Zielona Góra') == 'Zielona Gora'

    def test_gorzow_wielkopolski(self):
        assert _deaccent('Gorzów Wielkopolski') == 'Gorzow Wielkopolski'

    def test_boguszow_gorce(self):
        assert _deaccent('Boguszów-Gorce') == 'Boguszow-Gorce'

    def test_jelenia_gora(self):
        assert _deaccent('Jelenia Góra') == 'Jelenia Gora'

    def test_brzeg_dolny(self):
        assert _deaccent('Brzeg Dolny') == 'Brzeg Dolny'

    def test_plain_ascii_unchanged(self):
        assert _deaccent('Warszawa') == 'Warszawa'

    def test_empty_string(self):
        assert _deaccent('') == ''


class TestSitemapParser:
    @classmethod
    def setup_class(cls):
        cls._sitemap = _fetch_sitemap()

    def test_parse_real_sitemap(self):
        assert len(self._sitemap) > 500

    def test_regular_city_slug(self):
        assert self._sitemap['Kraków'] == 'krakow'
        assert self._sitemap['Warszawa'] == 'warszawa'
        assert self._sitemap['Gdańsk'] == 'gdansk'
        assert self._sitemap['Łódź'] == 'lodz'
        assert self._sitemap['Wrocław'] == 'wroclaw'
        assert self._sitemap['Poznań'] == 'poznan'

    def test_multi_word_city_concatenated(self):
        assert self._sitemap['Zielona Góra'] == 'zielonagora'

    def test_multi_word_city_hyphenated(self):
        assert self._sitemap['Jelenia Góra'] == 'jelenia-gora'
        assert self._sitemap['Boguszów-Gorce'] == 'boguszow-gorce'
        assert self._sitemap['Brzeg Dolny'] == 'brzeg-dolny'

    def test_sitemap_shortened_name(self):
        assert self._sitemap['Gorzów Wielkopolski'] == 'gorzow'

    def test_no_empty_slugs(self):
        for name, slug in self._sitemap.items():
            assert slug, f'Empty slug for {name}'
            assert ' ' not in slug, f'Slug contains spaces for {name}: {slug}'


class TestSitemapSlugsMatchApi:
    CONFIRMED: dict[str, int] = {
        'Kraków': 8959,
        'Warszawa': 17871,
        'Gdańsk': 5659,
        'Łódź': 10609,
        'Wrocław': 19701,
        'Poznań': 13983,
        'Zielona Góra': 20787,
        'Jelenia Góra': 7257,
        'Boguszów-Gorce': 42471,
        'Brzeg Dolny': 24811,
        'Gorzów Wielkopolski': 6331,
        'Bydgoszcz': 4019,
        'Rzeszów': 15241,
        'Białystok': 1079,
        'Katowice': 7691,
        'Lublin': 10119,
        'Olsztyn': 12673,
        'Szczecin': 16705,
        'Toruń': 38395,
        'Opole': 12885,
        'Kielce': 7971,
        'Gdynia': 5849,
        'Częstochowa': 4765,
    }

    def test_confirmed_cities_resolve_correctly(self):
        r = CityResolver()
        for city, expected_id in self.CONFIRMED.items():
            assert r.resolve(city) == expected_id, f'{city} should resolve to {expected_id}'

    def test_unknown_city(self):
        r = CityResolver()
        assert r.resolve('Nowe Miasto Nienazwane') is None

    def test_empty_string(self):
        r = CityResolver()
        assert r.resolve('') is None


class TestCityResolverIntegration:
    def test_cache(self):
        r = CityResolver()
        cid1 = r.resolve('Kraków')
        cid2 = r.resolve('Kraków')
        assert cid1 == cid2 == 8959
        assert 'Kraków' in r._id_cache

    def test_different_instances_have_separate_caches(self):
        r1 = CityResolver()
        r2 = CityResolver()
        r1.resolve('Kraków')
        assert 'Kraków' in r1._id_cache
        assert 'Kraków' not in r2._id_cache

    def test_whitespace_stripped(self):
        r = CityResolver()
        assert r.resolve(' Kraków ') == 8959

    def test_sitemap_loaded_lazily(self):
        r = CityResolver()
        assert r._slug_map is None
        r.resolve('Kraków')
        assert r._slug_map is not None
        assert len(r._slug_map) > 500

    def test_disk_cache_created(self):
        cache_path = _sitemap_cache_path()
        if cache_path.exists():
            cache_path.unlink()
        assert not cache_path.exists()
        r = CityResolver()
        r.resolve('Kraków')
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert isinstance(data, dict)
        assert len(data) > 500
        assert data['Kraków'] == 'krakow'
