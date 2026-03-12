import io

import pytest

from backend.app import main


def test_resolve_cli_password_prefers_password_arg():
    assert (
        main.resolve_cli_password(password_arg="secret-pass", use_stdin=False)
        == "secret-pass"
    )


def test_resolve_cli_password_reads_stdin(monkeypatch):
    monkeypatch.setattr(main.sys, "stdin", io.StringIO("stdin-pass\n"))
    assert (
        main.resolve_cli_password(password_arg=None, use_stdin=True) == "stdin-pass"
    )


def test_resolve_cli_password_prompt_mismatch_raises(monkeypatch):
    prompts = iter(["first-pass", "second-pass"])
    monkeypatch.setattr(main, "getpass", lambda _label: next(prompts))
    with pytest.raises(ValueError, match="do not match"):
        main.resolve_cli_password(password_arg=None, use_stdin=False)

