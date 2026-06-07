from __future__ import annotations

from olx_cli.offer import OlxOffer


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
