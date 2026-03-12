import httpx
import pytest

from backend.app import main, security


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    main.RATE_LIMITER._bucket.clear()
    yield
    main.RATE_LIMITER._bucket.clear()


@pytest.fixture
async def api_client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_security_headers_present_for_api_response(api_client):
    response = await api_client.get("/api/version")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in response.headers
    assert "strict-transport-security" not in response.headers


@pytest.mark.anyio
async def test_hsts_only_in_production(monkeypatch, api_client):
    monkeypatch.setenv("NODE_ENV", "production")
    response = await api_client.get("/api/version")
    assert response.status_code == 200
    assert response.headers["strict-transport-security"].startswith("max-age=")


@pytest.mark.anyio
async def test_csp_policy_is_path_specific_in_production(monkeypatch, api_client):
    monkeypatch.setenv("NODE_ENV", "production")

    api_response = await api_client.get("/api/version")
    assert api_response.status_code == 200
    assert api_response.headers["content-security-policy"] == (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )

    docs_response = await api_client.get("/docs")
    assert docs_response.status_code == 200
    assert docs_response.headers["content-security-policy"] == (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


@pytest.mark.anyio
async def test_auth_rate_limit_enforced(monkeypatch, api_client):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MIN", "2")

    def _override_db():
        yield object()

    main.app.dependency_overrides[main.get_db] = _override_db
    monkeypatch.setattr(main.crud, "authenticate_user", lambda *_args, **_kwargs: None)
    try:
        for _ in range(2):
            response = await api_client.post(
                "/api/token", data={"username": "u", "password": "bad"}
            )
            assert response.status_code == 401

        limited = await api_client.post(
            "/api/token", data={"username": "u", "password": "bad"}
        )
        assert limited.status_code == 429
        assert "Rate limit exceeded" in limited.json()["detail"]
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_expired_token_returns_consistent_unauthorized(monkeypatch, api_client):
    monkeypatch.setattr(
        main.crud, "get_user_by_username", lambda *_args, **_kwargs: None
    )
    expired = security.create_access_token(
        data={"sub": "ghost-user"},
        expires_delta=main.timedelta(seconds=-5),
    )
    response = await api_client.get(
        "/api/users/me/",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"
    assert response.headers["www-authenticate"] == "Bearer"
