from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from backend.app import main, security


def _override_current_user():
    return SimpleNamespace(id=1, username="tester", is_active=True, is_admin=False)


@pytest.fixture(autouse=True)
def override_main_db_dependency():
    def _override_db():
        yield object()

    main.app.dependency_overrides[main.get_db] = _override_db
    yield
    main.app.dependency_overrides.pop(main.get_db, None)


@pytest.fixture
async def api_client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_games_endpoint_passes_filter_and_pagination_params(
    monkeypatch, api_client
):
    captured = {}

    def mock_get_games(**kwargs):
        captured.update(kwargs)
        return (
            [
                {
                    "id": 1,
                    "name": "Alpha",
                    "mechanics": [],
                    "categories": [],
                    "suggested_players": [],
                }
            ],
            1,
        )

    monkeypatch.setattr(main.crud, "get_games", mock_get_games)

    response = await api_client.get(
        "/api/games/",
        params={
            "skip": 5,
            "limit": 10,
            "sort_by": "rank",
            "search": "alph",
            "library_only": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["games"][0]["id"] == 1
    assert captured["skip"] == 5
    assert captured["limit"] == 10
    assert captured["search"] == "alph"
    assert captured["library_only"] is True


@pytest.mark.anyio
async def test_games_endpoint_rejects_invalid_limit():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as api_client:
        response = await api_client.get("/api/games/", params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_recommendations_by_id_rejects_bad_disliked_games(api_client):
    response = await api_client.get(
        "/api/recommendations/123",
        params={"disliked_games": "abc,2"},
    )
    assert response.status_code == 400
    assert "Invalid disliked_games format" in response.json()["detail"]


@pytest.mark.anyio
async def test_recommendations_by_id_returns_list(monkeypatch, api_client):
    monkeypatch.setattr(
        main.crud,
        "get_recommendations",
        lambda **kwargs: [{"id": 2, "name": "Rec", "recommendation_score": 0.9}],
    )

    response = await api_client.get("/api/recommendations/1", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == 2


@pytest.mark.anyio
async def test_multi_recommendations_empty_result(monkeypatch, api_client):
    monkeypatch.setattr(main.crud, "get_recommendations", lambda **kwargs: [])

    response = await api_client.post(
        "/api/recommendations",
        json={
            "liked_games": [1],
            "disliked_games": [],
            "limit": 5,
            "library_only": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_auth_token_success_and_failure(monkeypatch, api_client):
    monkeypatch.setattr(main.crud, "authenticate_user", lambda db, u, p: None)
    bad = await api_client.post("/api/token", data={"username": "u", "password": "bad"})
    assert bad.status_code == 401

    monkeypatch.setattr(
        main.crud,
        "authenticate_user",
        lambda db, u, p: SimpleNamespace(username="u"),
    )
    monkeypatch.setattr(
        security, "create_access_token", lambda data, expires_delta=None: "token123"
    )
    good = await api_client.post("/api/token", data={"username": "u", "password": "ok"})
    assert good.status_code == 200
    assert good.json()["access_token"] == "token123"


@pytest.mark.anyio
async def test_users_me_requires_auth(api_client):
    response = await api_client.get("/api/users/me/")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_users_me_and_password_change_authenticated(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_current_user
    )
    monkeypatch.setattr(main.crud, "change_user_password", lambda **kwargs: True)

    me = await api_client.get("/api/users/me/")
    assert me.status_code == 200
    assert me.json()["username"] == "tester"

    changed = await api_client.put(
        "/api/users/me/password",
        json={"current_password": "oldpass", "new_password": "newpass123"},
    )
    assert changed.status_code == 200
    assert changed.json()["message"] == "Password changed successfully"

    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_suggestions_requires_auth(api_client):
    response = await api_client.post("/api/suggestions/", json={"comment": "test"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_suggestions_authenticated(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_current_user
    )
    monkeypatch.setattr(
        main.crud,
        "create_user_suggestion",
        lambda db, user_id, suggestion: SimpleNamespace(
            id=10,
            comment=suggestion.comment,
            timestamp=SimpleNamespace(isoformat=lambda: "2026-03-11T00:00:00Z"),
        ),
    )

    response = await api_client.post("/api/suggestions/", json={"comment": "Great app"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 10
    assert payload["username"] == "tester"

    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_openapi_contract_contains_core_paths(api_client):
    response = await api_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/games/" in schema["paths"]
    assert "/api/recommendations" in schema["paths"]
    assert "/api/token" in schema["paths"]


@pytest.mark.anyio
async def test_spa_login_route_refresh_serves_index_html(tmp_path):
    static_dir = tmp_path / "frontend_build"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<!doctype html><html><body><div id='root'></div></body></html>",
        encoding="utf-8",
    )

    app = FastAPI()
    app.mount("/", main.SPAStaticFiles(directory=str(static_dir), html=True))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/login")

    assert response.status_code == 200
    assert "<!doctype html>" in response.text.lower()
