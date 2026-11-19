from types import SimpleNamespace

import httpx
import pytest

from backend.app import main, security


def _override_current_user():
    return SimpleNamespace(id=1, username="tester", is_active=True, is_admin=False)


@pytest.fixture(autouse=True)
def override_main_db_dependency():
    def _override_db():
        yield object()

    main.app.dependency_overrides[main.get_db] = _override_db
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
async def api_client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.anyio
async def test_games_endpoint_preserves_core_query_contract(monkeypatch, api_client):
    captured = {}

    def mock_get_games(**kwargs):
        captured.update(kwargs)
        return ([{"id": 1, "name": "Alpha", "mechanics": [], "categories": [], "suggested_players": []}], 1)

    monkeypatch.setattr(main.crud, "get_games", mock_get_games)
    response = await api_client.get(
        "/api/games/",
        params={"skip": 5, "limit": 10, "sort_by": "rank", "search": "alph", "library_only": "true"},
    )

    assert response.status_code == 200
    assert response.json()["games"][0]["id"] == 1
    assert response.json()["total"] == 1
    assert captured["skip"] == 5
    assert captured["limit"] == 10
    assert captured["search"] == "alph"
    assert captured["library_only"] is True


@pytest.mark.anyio
async def test_recommendations_endpoint_returns_recommendations(monkeypatch, api_client):
    monkeypatch.setattr(
        main.crud,
        "get_recommendations",
        lambda **kwargs: [{"id": 2, "name": "Rec", "recommendation_score": 0.9}],
    )

    response = await api_client.get("/api/recommendations/1", params={"limit": 5})

    assert response.status_code == 200
    assert response.json()[0]["id"] == 2


@pytest.mark.anyio
async def test_authentication_accepts_valid_credentials_and_rejects_invalid(
    monkeypatch, api_client
):
    monkeypatch.setattr(main.crud, "authenticate_user", lambda db, u, p: None)
    invalid = await api_client.post("/api/token", data={"username": "u", "password": "bad"})
    assert invalid.status_code == 401

    monkeypatch.setattr(
        main.crud,
        "authenticate_user",
        lambda db, u, p: SimpleNamespace(username="u"),
    )
    monkeypatch.setattr(security, "create_access_token", lambda data, expires_delta=None: "token123")
    valid = await api_client.post("/api/token", data={"username": "u", "password": "ok"})
    assert valid.status_code == 200
    assert valid.json()["access_token"] == "token123"


@pytest.mark.anyio
async def test_authenticated_and_admin_routes_reject_unauthorized_users(api_client):
    me = await api_client.get("/api/users/me/")
    assert me.status_code == 401

    admin_users = await api_client.get("/api/admin/users")
    assert admin_users.status_code == 401

    main.app.dependency_overrides[security.get_current_active_user] = _override_current_user
    forbidden = await api_client.get("/api/admin/users")
    assert forbidden.status_code == 403
