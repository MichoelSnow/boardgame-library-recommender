import httpx
import pytest

from backend.app import main


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    main.RATE_LIMITER._bucket.clear()
    yield
    main.RATE_LIMITER._bucket.clear()


@pytest.fixture
async def api_client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.anyio
async def test_security_headers_are_present(api_client):
    response = await api_client.get("/api/version")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in response.headers


@pytest.mark.anyio
async def test_auth_rate_limit_is_enforced(monkeypatch, api_client):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MIN", "2")
    monkeypatch.setattr(main.crud, "authenticate_user", lambda *_args, **_kwargs: None)

    for _ in range(2):
        response = await api_client.post("/api/token", data={"username": "u", "password": "bad"})
        assert response.status_code == 401

    limited = await api_client.post("/api/token", data={"username": "u", "password": "bad"})
    assert limited.status_code == 429
