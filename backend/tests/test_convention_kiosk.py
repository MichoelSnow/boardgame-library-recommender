from backend.app import convention_kiosk


def test_kiosk_cookie_token_roundtrip() -> None:
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


def test_kiosk_cookie_token_rejects_wrong_secret() -> None:
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
