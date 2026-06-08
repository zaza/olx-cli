from __future__ import annotations

from olx_cli.offer_submit import (
    _parse_price_value,
    find_offer_files,
    read_offer,
    validate_offer,
)


class TestReadOffer:
    def test_simple_offer(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text(
            'title=Sprzedam rower\n'
            'price=1299\n'
            'category=rowery\n'
            'city=Kraków\n'
            '---\n'
            'Sprzedam rower w dobrym stanie.'
        )
        data = read_offer(str(f))
        assert data['title'] == 'Sprzedam rower'
        assert data['price'] == '1299'
        assert data['category'] == 'rowery'
        assert data['city'] == 'Kraków'
        assert data['description'] == 'Sprzedam rower w dobrym stanie.'

    def test_multiline_description(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text(
            'title=Sprzedam rower\n'
            'price=1299\n'
            'category=rowery\n'
            '---\n'
            'Sprzedam rower w dobrym stanie.\n'
            '\n'
            'Rower jest w pełni sprawny.\n'
            'Cena do negocjacji.'
        )
        data = read_offer(str(f))
        assert data['description'] == 'Sprzedam rower w dobrym stanie.\n\nRower jest w pełni sprawny.\nCena do negocjacji.'

    def test_no_separator(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text('title=Bez opisu\nprice=100\n')
        data = read_offer(str(f))
        assert data['title'] == 'Bez opisu'
        assert data['price'] == '100'
        assert data['description'] == ''

    def test_extra_whitespace_in_headers(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text(
            '  title  =  Rower  \n'
            'price=1299\n'
            '---\n'
            'Opis.'
        )
        data = read_offer(str(f))
        assert data['title'] == 'Rower'
        assert data['description'] == 'Opis.'

    def test_comments_ignored(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text(
            '# this is a comment\n'
            'title=Rower\n'
            'price=1299\n'
            '# another comment\n'
            '---\n'
            'Opis.'
        )
        data = read_offer(str(f))
        assert data['title'] == 'Rower'
        assert 'description' in data

    def test_keys_are_lowercased(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text(
            'Title=Rower\nPrice=1299\n---\nOpis.'
        )
        data = read_offer(str(f))
        assert data['title'] == 'Rower'
        assert data['price'] == '1299'

    def test_empty_lines_in_headers(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text(
            'title=Rower\n'
            '\n'
            'price=1299\n'
            '\n'
            '---\n'
            'Opis.'
        )
        data = read_offer(str(f))
        assert data['title'] == 'Rower'
        assert data['price'] == '1299'


class TestFindOfferFiles:
    def test_single_file(self, tmp_path):
        f = tmp_path / 'offer.txt'
        f.write_text('title=x')
        files = find_offer_files(str(f))
        assert files == [str(f)]

    def test_folder_with_subfolders(self, tmp_path):
        (tmp_path / 'offer1' / 'offer.txt').parent.mkdir()
        (tmp_path / 'offer1' / 'offer.txt').write_text('title=1')
        (tmp_path / 'offer2' / 'offer.txt').parent.mkdir()
        (tmp_path / 'offer2' / 'offer.txt').write_text('title=2')
        files = find_offer_files(str(tmp_path))
        assert len(files) == 2
        assert all(f.endswith('offer.txt') for f in files)

    def test_no_offer_txt(self, tmp_path):
        files = find_offer_files(str(tmp_path))
        assert files == []

    def test_nested_subdirs(self, tmp_path):
        p = tmp_path / 'a' / 'b' / 'c'
        p.mkdir(parents=True)
        (p / 'offer.txt').write_text('title=x')
        files = find_offer_files(str(tmp_path))
        assert len(files) == 1


_LONG_DESC = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.'  # > 40 chars


class TestValidateOffer:
    def test_valid_offer(self):
        data = {
            'title': 'Sprzedam rower górski',
            'description': _LONG_DESC,
            'price': '1299',
            'category': 'rowery',
            'city': 'Kraków',
            'email': 'test@example.com',
        }
        assert validate_offer(data) == []

    def test_missing_title(self):
        data = {'description': _LONG_DESC, 'price': '100', 'category': 'x', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert 'title is required' in errors

    def test_title_too_short(self):
        data = {'title': 'Krótki tytuł', 'description': _LONG_DESC, 'price': '100', 'category': 'x', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert any('title' in e and '16' in e for e in errors)

    def test_missing_description(self):
        data = {'title': 'Sprzedam rower', 'price': '100', 'category': 'x', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert any('description' in e for e in errors)

    def test_missing_price(self):
        data = {'title': 'Sprzedam rower', 'description': _LONG_DESC, 'category': 'x', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert 'price is required' in errors

    def test_invalid_price(self):
        data = {'title': 'Sprzedam rower', 'description': _LONG_DESC, 'price': 'abc', 'category': 'x', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert any('price' in e for e in errors)

    def test_negative_price(self):
        data = {'title': 'Sprzedam rower', 'description': _LONG_DESC, 'price': '-100', 'category': 'x', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert any('positive' in e for e in errors)

    def test_missing_category(self):
        data = {'title': 'Sprzedam rower', 'description': _LONG_DESC, 'price': '100', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert 'category is required' in errors

    def test_missing_city_and_city_id(self):
        data = {'title': 'Sprzedam rower', 'description': _LONG_DESC, 'price': '100', 'category': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert any('city' in e for e in errors)

    def test_city_id_instead_of_city(self):
        data = {'title': 'Sprzedam rower górski', 'description': _LONG_DESC, 'price': '100', 'category': 'x', 'city_id': '89363', 'email': 'a@b.com'}
        assert validate_offer(data) == []

    def test_missing_email(self):
        data = {'title': 'Sprzedam rower', 'description': _LONG_DESC, 'price': '100', 'category': 'x', 'city': 'x'}
        errors = validate_offer(data)
        assert 'email is required' in errors

    def test_price_with_zl_suffix(self):
        data = {
            'title': 'Sprzedam rower górski',
            'description': _LONG_DESC,
            'price': '1 299,99 zł',
            'category': 'rowery',
            'city': 'Kraków',
            'email': 'test@example.com',
        }
        assert validate_offer(data) == []

    def test_description_too_short(self):
        data = {'title': 'Sprzedam rower górski', 'description': 'Krótki opis', 'price': '100', 'category': 'x', 'city': 'x', 'email': 'a@b.com'}
        errors = validate_offer(data)
        assert any('40' in e for e in errors)

    def test_multiple_errors(self):
        data = {}
        errors = validate_offer(data)
        assert len(errors) >= 5


class TestParsePriceValue:
    def test_simple_integer(self):
        assert _parse_price_value('1299') == '1299'

    def test_with_zl_suffix(self):
        assert _parse_price_value('1299 zł') == '1299'

    def test_with_spaces(self):
        assert _parse_price_value('1 299') == '1299'

    def test_with_commas(self):
        assert _parse_price_value('1,5') == '1'

    def test_with_zl_spaces_commas(self):
        assert _parse_price_value('1 299,99 zł') == '1299'

    def test_zero(self):
        assert _parse_price_value('0') == '0'
