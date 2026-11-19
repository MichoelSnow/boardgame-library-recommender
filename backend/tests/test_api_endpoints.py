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
        params={
            "skip": 5,
            "limit": 10,
            "sort_by": "rank",
            "search": "alph",
            "players": "9plus",
            "max_playtime": 60,
            "min_age": 8,
            "game_style": "party",
            "cooperative": "true",
            "game_types": "game-type:deduction,game-type:dice-games",
            "themes": "theme:fantasy",
            "library_only": "true",
        },
    )

    assert response.status_code == 200
    assert response.json()["games"][0]["id"] == 1
    assert response.json()["total"] == 1
    assert captured["skip"] == 5
    assert captured["limit"] == 10
    assert captured["search"] == "alph"
    assert captured["players"] == "9plus"
    assert captured["max_playtime"] == 60
    assert captured["min_age"] == 8
    assert captured["game_style"] == "party"
    assert captured["cooperative"] is True
    assert captured["game_types"] == "game-type:deduction,game-type:dice-games"
    assert captured["themes"] == "theme:fantasy"
    assert captured["library_only"] is True


@pytest.mark.anyio
async def test_filter_taxonomy_endpoint_returns_stable_option_contract(monkeypatch, api_client):
    monkeypatch.setattr(
        main.taxonomy,
        "get_taxonomy_options",
        lambda db: [
            {
                "option_id": "game-type:dice-games",
                "label": "Dice Games",
                "group": "game_type",
                "featured": False,
                "sources": [
                    {"type": "category", "id": 1017, "name": "Dice"},
                    {"type": "mechanic", "id": 2072, "name": "Dice Rolling"},
                ],
                "explanation": None,
            }
        ],
    )

    response = await api_client.get("/api/filter-taxonomy/")

    assert response.status_code == 200
    assert response.json()[0]["option_id"] == "game-type:dice-games"
    assert response.json()[0]["sources"][1]["id"] == 2072


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
