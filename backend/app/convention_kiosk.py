import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

KIOSK_COOKIE_NAME = "convention_kiosk"
KIOSK_TOKEN_TYPE = "convention_kiosk_device"
KIOSK_COOKIE_TTL_SECONDS = 8 * 60 * 60


def _is_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_convention_mode_enabled(env: dict[str, str] | None = None) -> bool:
    environment = env or os.environ
    return _is_enabled(environment.get("CONVENTION_MODE"))


def is_convention_guest_enabled(env: dict[str, str] | None = None) -> bool:
    environment = env or os.environ
    return _is_enabled(environment.get("CONVENTION_GUEST_ENABLED"))


def get_expected_kiosk_key(env: dict[str, str] | None = None) -> str:
    environment = env or os.environ
    return (environment.get("CONVENTION_KIOSK_KEY") or "").strip()


def issue_kiosk_cookie_token(
    *,
    secret_key: str,
    algorithm: str,
    ttl_seconds: int = KIOSK_COOKIE_TTL_SECONDS,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": "kiosk_device",
        "type": KIOSK_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def is_valid_kiosk_cookie_token(
    *,
    token: str | None,
    secret_key: str,
    algorithm: str,
) -> bool:
    if not token:
        return False

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError:
        return False

    return payload.get("type") == KIOSK_TOKEN_TYPE
