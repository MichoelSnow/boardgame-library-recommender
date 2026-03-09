import asyncio
from types import SimpleNamespace

from backend.app import main


def test_cached_image_falls_back_to_proxy_when_r2_not_configured(monkeypatch):
    monkeypatch.setattr(
        main.crud,
        "get_game",
        lambda db, game_id: SimpleNamespace(id=game_id, image="https://example.com/game.jpg"),
    )
    monkeypatch.setattr(main, "r2_config_available", lambda: False)
    monkeypatch.setattr(main, "get_r2_public_base_url", lambda: None)

    response = asyncio.run(main.get_cached_image(224517, db=object()))

    assert response.status_code == 307
    assert response.headers["location"] == "/api/proxy-image/https%3A%2F%2Fexample.com%2Fgame.jpg"


def test_cached_image_redirects_to_cdn_when_sync_succeeds(monkeypatch):
    monkeypatch.setattr(
        main.crud,
        "get_game",
        lambda db, game_id: SimpleNamespace(id=game_id, image="https://example.com/game.jpg"),
    )
    monkeypatch.setattr(main, "r2_config_available", lambda: True)
    monkeypatch.setattr(main, "get_r2_public_base_url", lambda: "https://cdn.example.com")

    class FakeSyncer:
        def sync_image_url(self, *, bgg_id, image_url, overwrite_existing=False, session=None):
            assert bgg_id == 224517
            assert image_url == "https://example.com/game.jpg"
            return "games/224517.jpg", "uploaded"

    monkeypatch.setattr(main.R2ImageSyncer, "from_env", lambda: FakeSyncer())

    response = asyncio.run(main.get_cached_image(224517, db=object()))

    assert response.status_code == 307
    assert response.headers["location"] == "https://cdn.example.com/games/224517.jpg"
