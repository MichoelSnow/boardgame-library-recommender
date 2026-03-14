from __future__ import annotations

from backend.app import security


def test_verify_password_handles_value_error(monkeypatch):
    def _raise_value_error(*_args, **_kwargs):
        raise ValueError("password cannot be longer than 72 bytes")

    monkeypatch.setattr(security.pwd_context, "verify", _raise_value_error)

    assert security.verify_password("x" * 200, "$2b$12$examplehashvalue") is False
