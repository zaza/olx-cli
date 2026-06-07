from __future__ import annotations

from olx_cli.offer import OlxOffer, compute_stats, parse_price


class TestKeywords:
    def test_splits_query(self):
        assert OlxOffer._keywords("fiat freemont") == ["fiat", "freemont"]

    def test_case_normalized(self):
        assert OlxOffer._keywords("Fiat Freemont") == ["fiat", "freemont"]

    def test_empty_query(self):
        assert OlxOffer._keywords("") == []

    def test_single_word(self):
        assert OlxOffer._keywords("rower") == ["rower"]


class TestMatchesKeywords:
    def make_offer(self, title: str) -> OlxOffer:
        return OlxOffer(title=title, price="", url="", city="")

    def test_single_keyword_match(self):
        o = self.make_offer("Rower górski Kross")
        assert o.matches_keywords("rower")

    def test_single_keyword_no_match(self):
        o = self.make_offer("Samochód osobowy")
        assert not o.matches_keywords("rower")

    def test_all_keywords_required(self):
        o = self.make_offer("Fiat Freemont 2013 2.0 JTD")
        assert o.matches_keywords("fiat freemont")

    def test_all_keywords_missing_one(self):
        o = self.make_offer("Fiat Punto 1.2")
        assert not o.matches_keywords("fiat freemont")

    def test_case_insensitive(self):
        o = self.make_offer("FIAT FREEMONT LOUNGE")
        assert o.matches_keywords("fiat freemont")

    def test_partial_word_match(self):
        o = self.make_offer("Komputer stacjonarny")
        assert o.matches_keywords("komp")

    def test_polish_chars(self):
        o = self.make_offer("Gęś domowa")
        assert o.matches_keywords("gęś")

    def test_empty_query_returns_true(self):
        o = self.make_offer("anything")
        assert o.matches_keywords("")

    def test_no_title_match(self):
        o = self.make_offer("Rowerek dziecięcy")
        assert not o.matches_keywords("fiat")

    def test_otomoto_title(self):
        o = self.make_offer("Fiat Freemont Urban Manual Czarny Metalik Skóry 7 Osób")
        assert o.matches_keywords("fiat freemont")


def _offer(price: str, title: str = '') -> OlxOffer:
    return OlxOffer(title=title or price, price=price, url='', city='')


class TestParsePrice:
    def test_za_darmo_returns_none(self):
        assert parse_price('Za darmo') is None

    def test_zamienie_returns_none(self):
        assert parse_price('Zamienię') is None

    def test_do_negocjacji_returns_none(self):
        assert parse_price('Do negocjacji') is None

    def test_empty_string_returns_none(self):
        assert parse_price('') is None

    def test_whitespace_only_returns_none(self):
        assert parse_price('   ') is None

    def test_simple_zl(self):
        assert parse_price('100 zł') == 100

    def test_price_with_comma(self):
        assert parse_price('1 299,99 zł') == 1300

    def test_price_without_zl_suffix(self):
        assert parse_price('500') == 500

    def test_price_with_spaces(self):
        assert parse_price('12 500 zł') == 12500

    def test_invalid_string_returns_none(self):
        assert parse_price('nie podano') is None

    def test_zero_price(self):
        assert parse_price('0 zł') == 0


class TestComputeStats:
    def test_empty_offers(self):
        stats = compute_stats([], pages_visited=0)
        assert stats == {
            'total': 0, 'skipped': 0, 'pages_visited': 0,
            'average': None, 'median': None,
        }

    def test_all_skip_prices(self):
        stats = compute_stats([_offer('Za darmo'), _offer('Zamienię')], pages_visited=1)
        assert stats['total'] == 2
        assert stats['skipped'] == 2
        assert stats['average'] is None
        assert stats['median'] is None

    def test_single_offer(self):
        stats = compute_stats([_offer('100 zł')], pages_visited=1)
        assert stats == {
            'total': 1, 'skipped': 0, 'pages_visited': 1,
            'average': 100, 'median': 100,
        }

    def test_multiple_offers_average_and_median(self):
        offers = [_offer(str(p)) for p in [100, 200, 300]]
        stats = compute_stats(offers, pages_visited=2)
        assert stats['average'] == 200
        assert stats['median'] == 200
        assert stats['pages_visited'] == 2

    def test_median_with_even_count(self):
        offers = [_offer(str(p)) for p in [100, 200, 300, 400]]
        stats = compute_stats(offers, pages_visited=1)
        assert stats['median'] == 250

    def test_mixed_skip_and_valid(self):
        offers = [_offer('100 zł'), _offer('Za darmo'), _offer('200 zł')]
        stats = compute_stats(offers, pages_visited=3)
        assert stats['total'] == 3
        assert stats['skipped'] == 1
        assert stats['average'] == 150
        assert stats['median'] == 150

class TestNegotiablePrice:
    def test_pure_negotiable(self):
        o = _offer('do negocjacji')
        assert o.is_negotiable is True
        assert o.clean_price == ''

    def test_price_with_negotiable(self):
        o = _offer('320 złdo negocjacji')
        assert o.is_negotiable is True
        assert o.clean_price == '320 zł'

    def test_not_negotiable(self):
        o = _offer('320 zł')
        assert o.is_negotiable is False
        assert o.clean_price == '320 zł'

    def test_case_insensitivity(self):
        o = _offer('320 złDO NEGOCJACJI')
        assert o.is_negotiable is True
        assert o.clean_price == '320 zł'
