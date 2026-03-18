from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from backend.app import main, security


def _override_current_user():
    return SimpleNamespace(id=1, username="tester", is_active=True, is_admin=False)


def _override_admin_user():
    return SimpleNamespace(id=2, username="admin", is_active=True, is_admin=True)


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
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


@pytest.mark.anyio
async def test_library_game_ids_endpoint_sets_no_store_headers(monkeypatch, api_client):
    monkeypatch.setattr(main.crud, "get_library_ids_for_runtime", lambda db: [1, 2, 3])

    response = await api_client.get("/api/library_game_ids/")

    assert response.status_code == 200
    assert response.json() == [1, 2, 3]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


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
async def test_theme_settings_get_uses_default_when_unset(monkeypatch, api_client):
    monkeypatch.setattr(main.crud, "get_app_setting", lambda db, key: None)
    response = await api_client.get("/api/theme")
    assert response.status_code == 200
    assert response.json()["primary_color"] == "#D9272D"
    assert response.json()["library_name"] is None


@pytest.mark.anyio
async def test_theme_settings_update_requires_auth(api_client):
    response = await api_client.put(
        "/api/admin/theme", json={"primary_color": "#007DBB"}
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_theme_settings_update_requires_admin(api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_current_user
    )

    response = await api_client.put(
        "/api/admin/theme", json={"primary_color": "#007DBB"}
    )
    assert response.status_code == 403
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_theme_settings_update_allows_admin(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    captured = {}

    def _mock_upsert(db, key, value):
        captured["key"] = key
        captured["value"] = value
        return SimpleNamespace(key=key, value=value)

    monkeypatch.setattr(main.crud, "get_app_setting", lambda db, key: None)
    monkeypatch.setattr(main.crud, "upsert_app_setting", _mock_upsert)

    response = await api_client.put(
        "/api/admin/theme", json={"primary_color": "#007dbb"}
    )
    assert response.status_code == 200
    assert response.json()["primary_color"] == "#007DBB"
    assert response.json()["library_name"] is None
    assert captured["key"] == "theme_primary_color"
    assert captured["value"] == "#007DBB"
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_theme_settings_update_library_name_set_and_clear(
    monkeypatch, api_client
):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    store = {}

    def _mock_get(db, key):
        value = store.get(key)
        if value is None:
            return None
        return SimpleNamespace(key=key, value=value)

    def _mock_upsert(db, key, value):
        store[key] = value
        return SimpleNamespace(key=key, value=value)

    def _mock_delete(db, key):
        store.pop(key, None)
        return True

    monkeypatch.setattr(main.crud, "get_app_setting", _mock_get)
    monkeypatch.setattr(main.crud, "upsert_app_setting", _mock_upsert)
    monkeypatch.setattr(main.crud, "delete_app_setting", _mock_delete)

    set_response = await api_client.put(
        "/api/admin/theme",
        json={"primary_color": "#D9272D", "library_name": "PAX Unplugged"},
    )
    assert set_response.status_code == 200
    assert set_response.json()["library_name"] == "PAX Unplugged"

    clear_response = await api_client.put(
        "/api/admin/theme",
        json={"library_name": ""},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["library_name"] is None
    assert clear_response.json()["primary_color"] == "#D9272D"
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_user_management_endpoints_require_admin(api_client):
    response = await api_client.get("/api/admin/users")
    assert response.status_code == 401

    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_current_user
    )
    forbidden = await api_client.get("/api/admin/users")
    assert forbidden.status_code == 403
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_user_management_list_update_and_reset_password(
    monkeypatch, api_client
):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )

    monkeypatch.setattr(
        main.crud,
        "get_users",
        lambda db: [
            SimpleNamespace(id=1, username="admin", is_admin=True, is_active=True)
        ],
    )
    listed = await api_client.get("/api/admin/users")
    assert listed.status_code == 200
    assert listed.json()[0]["username"] == "admin"

    monkeypatch.setattr(
        main.crud,
        "get_user",
        lambda db, user_id: SimpleNamespace(
            id=user_id,
            username="user1",
            is_admin=False,
            is_active=True,
        ),
    )
    monkeypatch.setattr(
        main.crud,
        "update_user_admin_flags",
        lambda db, user_id, is_admin=None, is_active=None: SimpleNamespace(
            id=user_id,
            username="user1",
            is_admin=is_admin if is_admin is not None else False,
            is_active=is_active if is_active is not None else True,
        ),
    )
    updated = await api_client.put(
        "/api/admin/users/5",
        json={"is_admin": True, "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_admin"] is True
    assert updated.json()["is_active"] is False

    monkeypatch.setattr(
        main.crud, "admin_reset_password_by_user_id", lambda **kwargs: True
    )
    reset_response = await api_client.put(
        "/api/admin/users/5/password",
        json={"new_password": "newpass123"},
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["message"] == "Password reset successfully"
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_library_game_ids_uses_runtime_source(monkeypatch, api_client):
    monkeypatch.setattr(main.crud, "get_library_ids_for_runtime", lambda db: [101, 202])
    response = await api_client.get("/api/library_game_ids")
    assert response.status_code == 200
    assert response.json() == [101, 202]


@pytest.mark.anyio
async def test_admin_library_import_endpoints_require_admin(api_client):
    listing = await api_client.get("/api/admin/library-imports")
    assert listing.status_code == 401

    validate = await api_client.post(
        "/api/admin/library-imports/csv/validate",
        files={"file": ("ids.csv", "1\n2\n", "text/csv")},
    )
    assert validate.status_code == 401

    upload = await api_client.post(
        "/api/admin/library-imports/csv",
        data={"label": "test-import"},
        files={"file": ("ids.csv", "1\n2\n", "text/csv")},
    )
    assert upload.status_code == 401

    activate = await api_client.post("/api/admin/library-imports/1/activate")
    assert activate.status_code == 401

    delete_response = await api_client.delete("/api/admin/library-imports/1")
    assert delete_response.status_code == 401


@pytest.mark.anyio
async def test_admin_library_import_upload_and_activate(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    captured = {}

    monkeypatch.setattr(
        main,
        "_analyze_library_csv",
        lambda raw: {
            "total_rows": 4,
            "parsed_rows": [(1, 10), (2, 20), (3, 20), (4, 30)],
            "deduped_rows": [(1, 10), (2, 20), (4, 30)],
            "duplicate_rows": 1,
            "invalid_warnings": [],
        },
    )
    monkeypatch.setattr(main.crud, "find_missing_games_for_ids", lambda db, bgg_ids: [])

    def _mock_create_library_import(
        db,
        *,
        label,
        import_method,
        imported_by_user_id,
        bgg_ids,
        activate,
    ):
        captured["label"] = label
        captured["import_method"] = import_method
        captured["imported_by_user_id"] = imported_by_user_id
        captured["bgg_ids"] = bgg_ids
        captured["activate"] = activate
        return SimpleNamespace(id=99)

    monkeypatch.setattr(main.crud, "create_library_import", _mock_create_library_import)
    monkeypatch.setattr(
        main.crud,
        "list_library_import_summaries",
        lambda db: [
            {
                "id": 99,
                "label": "Spring CSV",
                "import_method": "csv_upload",
                "is_active": True,
                "total_items": 3,
                "created_at": "2026-03-16T10:00:00",
                "activated_at": "2026-03-16T10:00:00",
                "imported_by_user_id": 2,
                "activated_by_user_id": 2,
                "imported_by_username": "admin",
                "activated_by_username": "admin",
            }
        ],
    )

    upload = await api_client.post(
        "/api/admin/library-imports/csv",
        data={
            "label": " Spring CSV ",
            "activate": "true",
            "ignore_invalid_rows": "true",
            "allow_unknown_ids": "false",
        },
        files={"file": ("ids.csv", "10\n20\n20\n30\n", "text/csv")},
    )
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["skipped_duplicates"] == 1
    assert payload["skipped_invalid_rows"] == 0
    assert payload["skipped_unknown_ids"] == 0
    assert payload["kept_unknown_ids"] == 0
    assert payload["import_record"]["id"] == 99
    assert captured["label"] == "Spring CSV"
    assert captured["bgg_ids"] == [10, 20, 30]
    assert captured["import_method"] == "csv_upload"
    assert captured["imported_by_user_id"] == 2
    assert captured["activate"] is True

    monkeypatch.setattr(
        main.crud,
        "activate_library_import",
        lambda db, import_id, activated_by_user_id: SimpleNamespace(id=99),
    )
    activated = await api_client.post("/api/admin/library-imports/99/activate")
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_library_import_upload_rejects_bad_csv(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    monkeypatch.setattr(
        main,
        "_analyze_library_csv",
        lambda raw: (_ for _ in ()).throw(ValueError("CSV file is empty.")),
    )

    response = await api_client.post(
        "/api/admin/library-imports/csv",
        data={"label": "bad"},
        files={"file": ("ids.csv", "", "text/csv")},
    )
    assert response.status_code == 400
    assert "CSV file is empty" in response.json()["detail"]
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_library_import_validate_and_allow_unknown(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    monkeypatch.setattr(
        main,
        "_analyze_library_csv",
        lambda raw: {
            "total_rows": 3,
            "parsed_rows": [(1, 10), (2, 10), (3, 999999)],
            "deduped_rows": [(1, 10), (3, 999999)],
            "duplicate_rows": 1,
            "invalid_warnings": [
                {"row_number": 4, "value": "abc", "reason": "not_positive_integer"}
            ],
        },
    )
    monkeypatch.setattr(
        main.crud,
        "find_missing_games_for_ids",
        lambda db, bgg_ids: [999999],
    )
    monkeypatch.setattr(
        main.crud,
        "create_library_import",
        lambda *args, **kwargs: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(
        main.crud,
        "list_library_import_summaries",
        lambda db: [
            {
                "id": 1,
                "label": "allow-unknown",
                "import_method": "csv_upload",
                "is_active": True,
                "total_items": 2,
                "created_at": "2026-03-16T10:00:00",
                "activated_at": "2026-03-16T10:00:00",
                "imported_by_user_id": 2,
                "activated_by_user_id": 2,
                "imported_by_username": "admin",
                "activated_by_username": "admin",
            }
        ],
    )

    validate_response = await api_client.post(
        "/api/admin/library-imports/csv/validate",
        files={"file": ("ids.csv", "10\n999999\n", "text/csv")},
    )
    assert validate_response.status_code == 200
    validate_payload = validate_response.json()
    assert validate_payload["invalid_rows"] == 1
    assert validate_payload["unknown_id_rows"] == 1

    upload_response = await api_client.post(
        "/api/admin/library-imports/csv",
        data={
            "label": "allow-unknown",
            "activate": "true",
            "ignore_invalid_rows": "true",
            "allow_unknown_ids": "true",
        },
        files={"file": ("ids.csv", "10\n999999\n", "text/csv")},
    )
    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["skipped_duplicates"] == 1
    assert upload_payload["skipped_invalid_rows"] == 1
    assert upload_payload["kept_unknown_ids"] == 1
    assert upload_payload["skipped_unknown_ids"] == 0
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_library_import_delete(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )

    monkeypatch.setattr(main.crud, "delete_library_import", lambda db, import_id: True)
    deleted = await api_client.delete("/api/admin/library-imports/5")
    assert deleted.status_code == 204

    monkeypatch.setattr(main.crud, "delete_library_import", lambda db, import_id: False)
    not_found = await api_client.delete("/api/admin/library-imports/99")
    assert not_found.status_code == 404
    assert "not found" in not_found.json()["detail"].lower()

    def _raise_active_import_error(db, import_id):
        raise ValueError("Active library import cannot be deleted.")

    monkeypatch.setattr(main.crud, "delete_library_import", _raise_active_import_error)
    active_import = await api_client.delete("/api/admin/library-imports/1")
    assert active_import.status_code == 400
    assert "active" in active_import.json()["detail"].lower()
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_library_import_validate_rejects_oversized_csv(
    monkeypatch, api_client
):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    monkeypatch.setattr(main, "MAX_LIBRARY_IMPORT_CSV_BYTES", 8)

    response = await api_client.post(
        "/api/admin/library-imports/csv/validate",
        files={"file": ("ids.csv", "1\n2\n3\n4\n5\n", "text/csv")},
    )

    assert response.status_code == 400
    assert "CSV is too large" in response.json()["detail"]
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_library_import_upload_rejects_oversized_csv(
    monkeypatch, api_client
):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    monkeypatch.setattr(main, "MAX_LIBRARY_IMPORT_CSV_BYTES", 8)

    response = await api_client.post(
        "/api/admin/library-imports/csv",
        data={"label": "too-large"},
        files={"file": ("ids.csv", "1\n2\n3\n4\n5\n", "text/csv")},
    )

    assert response.status_code == 400
    assert "CSV is too large" in response.json()["detail"]
    main.app.dependency_overrides.clear()


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
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_convention_kiosk_admin_endpoints_require_auth(api_client):
    legacy_unenroll_response = await api_client.post("/api/convention/kiosk/unenroll")
    enroll_response = await api_client.post("/api/convention/kiosk/admin/enroll")
    unenroll_response = await api_client.post("/api/convention/kiosk/admin/unenroll")

    assert legacy_unenroll_response.status_code in {404, 405}
    assert enroll_response.status_code == 401
    assert unenroll_response.status_code == 401


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_convention_kiosk_admin_endpoints_require_admin(api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_current_user
    )

    enroll_response = await api_client.post("/api/convention/kiosk/admin/enroll")
    unenroll_response = await api_client.post("/api/convention/kiosk/admin/unenroll")

    assert enroll_response.status_code == 403
    assert unenroll_response.status_code == 403
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_convention_kiosk_admin_endpoints_allow_admin_when_enabled(
    monkeypatch, api_client
):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    monkeypatch.setenv("CONVENTION_MODE", "true")
    monkeypatch.setenv("CONVENTION_GUEST_ENABLED", "true")

    enroll_response = await api_client.post("/api/convention/kiosk/admin/enroll")
    assert enroll_response.status_code == 200
    assert enroll_response.json()["kiosk_mode"] is True

    status_response = await api_client.get("/api/convention/kiosk/status")
    assert status_response.status_code == 200
    assert status_response.json()["convention_mode"] is True
    assert status_response.json()["kiosk_mode"] is True

    unenroll_response = await api_client.post("/api/convention/kiosk/admin/unenroll")
    assert unenroll_response.status_code == 200
    assert unenroll_response.json()["kiosk_mode"] is False
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_convention_guest_token_requires_kiosk_enrollment(
    monkeypatch, api_client
):
    monkeypatch.setenv("CONVENTION_MODE", "true")
    monkeypatch.setenv("CONVENTION_GUEST_ENABLED", "true")

    response = await api_client.post("/api/convention/guest-token")
    assert response.status_code == 401


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_convention_guest_token_works_after_admin_enroll(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    monkeypatch.setenv("CONVENTION_MODE", "true")
    monkeypatch.setenv("CONVENTION_GUEST_ENABLED", "true")

    enroll_response = await api_client.post("/api/convention/kiosk/admin/enroll")
    assert enroll_response.status_code == 200

    guest_response = await api_client.post("/api/convention/guest-token")
    assert guest_response.status_code == 200
    payload = guest_response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    main.app.dependency_overrides.clear()


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_guest_session_cannot_use_write_endpoints(monkeypatch, api_client):
    main.app.dependency_overrides[security.get_current_active_user] = (
        _override_admin_user
    )
    monkeypatch.setenv("CONVENTION_MODE", "true")
    monkeypatch.setenv("CONVENTION_GUEST_ENABLED", "true")
    enroll_response = await api_client.post("/api/convention/kiosk/admin/enroll")
    assert enroll_response.status_code == 200
    main.app.dependency_overrides.clear()

    token_response = await api_client.post("/api/convention/guest-token")
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    password_response = await api_client.put(
        "/api/users/me/password",
        json={"current_password": "x", "new_password": "abcdef"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert password_response.status_code == 403

    monkeypatch.setattr(
        main.crud,
        "get_or_create_guest_user",
        lambda db: SimpleNamespace(id=99, username=security.CONVENTION_GUEST_USERNAME),
    )
    monkeypatch.setattr(
        main.crud,
        "create_user_suggestion",
        lambda db, user_id, suggestion: SimpleNamespace(
            id=22,
            comment=suggestion.comment,
            timestamp=SimpleNamespace(isoformat=lambda: "2026-03-15T00:00:00Z"),
        ),
    )
    suggestion_response = await api_client.post(
        "/api/suggestions/",
        json={"comment": "guest suggestion"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert suggestion_response.status_code == 200
    assert suggestion_response.json()["username"] == security.CONVENTION_GUEST_USERNAME


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
