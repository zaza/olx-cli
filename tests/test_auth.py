from __future__ import annotations

from unittest.mock import patch

from olx_cli.auth import decode_jwt


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
    def test_returns_none_on_bad_json(self):
        from pathlib import Path
        from olx_cli.auth import get_tokens

        p = Path.home() / ".cache" / "olx-cli" / "tokens.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("not-json")
        result = get_tokens()
        p.unlink(missing_ok=True)
        assert result is None


class TestLogout:
    def test_removes_token_file(self, tmp_path):
        from olx_cli.auth import logout, _tokens_path

        p = _tokens_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}")
        assert p.exists()
        logout()
        assert not p.exists()

    def test_no_error_when_no_file(self):
        from olx_cli.auth import logout

        logout()  # should not raise
