from __future__ import annotations

from pathlib import Path

import pytest

from olx_cli.auth import decode_jwt


@pytest.fixture
def fake_tokens_path(monkeypatch, tmp_path):
    from olx_cli.auth import _tokens_path

    p = tmp_path / 'tokens.json'
    monkeypatch.setattr('olx_cli.auth._tokens_path', lambda: p)
    return p


class TestDecodeJwt:
    def test_valid_token(self):
        token = (
            "eyJhbGciOiJSUzI1NiJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dGVzdF9zaWduYXR1cmU"
        )
        payload = decode_jwt(token)
        assert payload == {"sub": "1234567890"}

    def test_with_extra_fields(self):
        token = (
            "eyJhbGciOiJSUzI1NiJ9."
            "eyJzdWIiOiJhYmMiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJleHAiOjk5OTk5fQ."
            "dGVzdF9zaWduYXR1cmU"
        )
        payload = decode_jwt(token)
        assert payload["sub"] == "abc"
        assert payload["email"] == "test@test.com"
        assert payload["exp"] == 99999

    def test_empty_payload(self):
        token = "e30.eyJzdWIiOiJ4In0.dGVzdA"
        payload = decode_jwt(token)
        assert payload == {"sub": "x"}


class TestGetTokensNoCache:
    def test_returns_none_on_bad_json(self, fake_tokens_path):
        from olx_cli.auth import get_tokens

        fake_tokens_path.parent.mkdir(parents=True, exist_ok=True)
        fake_tokens_path.write_text("not-json")
        result = get_tokens()
        assert result is None


class TestLogout:
    def test_removes_token_file(self, fake_tokens_path):
        from olx_cli.auth import logout

        fake_tokens_path.parent.mkdir(parents=True, exist_ok=True)
        fake_tokens_path.write_text("{}")
        assert fake_tokens_path.exists()
        logout()
        assert not fake_tokens_path.exists()

    def test_no_error_when_no_file(self):
        from olx_cli.auth import logout

        logout()  # should not raise
