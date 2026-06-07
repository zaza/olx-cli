import pytest

from olx_cli.query import _deaccent, build_url, describe


class TestDeaccent:
    def test_krakow(self):
        assert _deaccent("Kraków") == "Krakow"

    def test_lodz(self):
        assert _deaccent("Łódź") == "Łodz"

    def test_zdzblo(self):
        assert _deaccent("źdźbło") == "zdzbło"

    def test_ges(self):
        assert _deaccent("gęś") == "ges"

    def test_plain_ascii_unchanged(self):
        assert _deaccent("Warszawa") == "Warszawa"

    def test_empty_string(self):
        assert _deaccent("") == ""


class TestBuildUrlCategory:
    def test_category_in_url(self):
        url = build_url("opel", category="motoryzacja")
        assert "/motoryzacja/" in url

    def test_category_without_location_no_oferty(self):
        url = build_url("opel", category="motoryzacja")
        assert "/motoryzacja/q-opel/" in url
        assert "/oferty/" not in url

    def test_category_no_query_no_location(self):
        url = build_url("", category="elektronika")
        assert "/elektronika/" in url
        assert url.endswith("/elektronika/")

    def test_category_with_location(self):
        url = build_url("opel", category="motoryzacja/samochody", location="Kraków")
        assert "/motoryzacja/samochody/" in url
        assert "Krakow" in url
        assert "/oferty/" not in url

    def test_category_with_slash_stripped(self):
        url = build_url("opel", category="motoryzacja/")
        assert "/motoryzacja/" in url



class TestBuildUrl:
    def test_basic_query(self):
        url = build_url("rower górski")
        assert url.startswith("https://www.olx.pl/")
        assert "q-rower-g%C3%B3rski" in url or "q-rower-gorski" in url

    def test_photo_only(self):
        url = build_url("opel", photo_only=True)
        assert "search%5Bphotos%5D=1" in url or "search[photos]=1" in url

    def test_location(self):
        url = build_url("opel", location="Kraków")
        assert "Krakow" in url
        assert "/oferty/" not in url

    def test_location_with_radius(self):
        url = build_url("opel", location="Kraków", radius=30)
        assert "Krakow" in url
        assert "/oferty/" not in url
        assert "search%5Bdist%5D=30" in url or "search[dist]=30" in url

    def test_no_location_includes_oferty(self):
        url = build_url("opel")
        assert "/oferty/" in url

    def test_min_price(self):
        url = build_url("opel", min_price=500)
        assert "search%5Bfilter_float_price%3Afrom%5D=500" in url

    def test_min_price_zero(self):
        url = build_url("opel", min_price=0)
        assert "free" in url

    def test_max_price(self):
        url = build_url("opel", max_price=2000)
        assert "search%5Bfilter_float_price%3Ato%5D=2000" in url

    def test_max_price_zero_is_omitted(self):
        url = build_url("opel", max_price=0)
        assert "filter_float_price%3Ato" not in url

    def test_full_combo(self):
        url = build_url(
            "giant escape 3",
            photo_only=True,
            location="Kraków",
            radius=30,
            min_price=100,
            max_price=2000,
        )
        assert "Krakow" in url
        assert "q-giant-escape-3" in url
        assert "photos" in url
        assert "dist" in url
        assert "from" in url
        assert "to" in url

    def test_empty_query(self):
        url = build_url("")
        assert url.startswith("https://www.olx.pl/")
        assert "/oferty/" in url

    def test_radius_without_location_raises(self):
        with pytest.raises(ValueError, match="radius requires a location"):
            build_url("opel", radius=30)

    def test_negative_min_price_raises(self):
        with pytest.raises(ValueError, match="min_price must be >= 0"):
            build_url("opel", min_price=-1)

    def test_negative_max_price_raises(self):
        with pytest.raises(ValueError, match="max_price must be >= 0"):
            build_url("opel", max_price=-1)

    def test_min_gte_max_raises(self):
        with pytest.raises(ValueError, match="min_price must be less than max_price"):
            build_url("opel", min_price=2000, max_price=1000)

    def test_min_eq_max_raises(self):
        with pytest.raises(ValueError, match="min_price must be less than max_price"):
            build_url("opel", min_price=500, max_price=500)


class TestDescribe:
    def test_plain(self):
        assert describe("rower", photo_only=False) == "'rower'"

    def test_with_photo(self):
        assert describe("rower", photo_only=True) == "'rower' with photo"

    def test_with_category(self):
        assert describe("auto", photo_only=False, category="motoryzacja") == "'auto' in category 'motoryzacja'"

    def test_with_category_and_photo(self):
        d = describe("auto", photo_only=True, category="motoryzacja")
        assert "'auto' in category 'motoryzacja'" in d
        assert "with photo" in d
