import httpx
import pytest

from backend.app import main


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def api_client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_request_context_headers_present(api_client):
    response = await api_client.get(
        "/api/version",
        headers={"X-Request-ID": "req-123"},
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-123"
    assert "x-response-time-ms" in response.headers
    float(response.headers["x-response-time-ms"])


@pytest.mark.anyio
async def test_health_live_returns_live(api_client):
    response = await api_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.anyio
async def test_health_ready_returns_ready(monkeypatch, api_client):
    monkeypatch.setattr(main, "check_db_readiness", lambda: (True, None))
    monkeypatch.setattr(
        main,
        "get_model_readiness",
        lambda: {"available": True, "state": "ready"},
    )
    response = await api_client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["database"]["ready"] is True
    assert payload["checks"]["model"]["ready"] is True


@pytest.mark.anyio
async def test_health_ready_returns_not_ready_on_db_failure(monkeypatch, api_client):
    monkeypatch.setattr(main, "check_db_readiness", lambda: (False, "db down"))
    monkeypatch.setattr(
        main,
        "get_model_readiness",
        lambda: {"available": True, "state": "ready"},
    )
    response = await api_client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["database"]["ready"] is False
    assert payload["checks"]["database"]["error"] == "db down"
