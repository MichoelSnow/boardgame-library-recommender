from backend.app import convention_kiosk


def test_convention_mode_enabled_parsing() -> None:
    assert convention_kiosk.is_convention_mode_enabled({"CONVENTION_MODE": "true"})
    assert convention_kiosk.is_convention_mode_enabled({"CONVENTION_MODE": "1"})
    assert not convention_kiosk.is_convention_mode_enabled({"CONVENTION_MODE": "false"})


def test_guest_mode_enabled_parsing() -> None:
    assert convention_kiosk.is_convention_guest_enabled({"CONVENTION_GUEST_ENABLED": "yes"})
    assert not convention_kiosk.is_convention_guest_enabled({"CONVENTION_GUEST_ENABLED": "0"})


def test_kiosk_cookie_token_issue_and_validate_roundtrip() -> None:
    token = convention_kiosk.issue_kiosk_cookie_token(
        secret_key="x" * 32,
        algorithm="HS256",
        ttl_seconds=60,
    )

    assert convention_kiosk.is_valid_kiosk_cookie_token(
        token=token,
        secret_key="x" * 32,
        algorithm="HS256",
    )


def test_kiosk_cookie_token_invalid_secret_rejected() -> None:
    token = convention_kiosk.issue_kiosk_cookie_token(
        secret_key="x" * 32,
        algorithm="HS256",
        ttl_seconds=60,
    )

    assert not convention_kiosk.is_valid_kiosk_cookie_token(
        token=token,
        secret_key="y" * 32,
        algorithm="HS256",
    )
