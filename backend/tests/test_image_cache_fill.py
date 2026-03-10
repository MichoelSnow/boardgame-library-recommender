import asyncio
from types import SimpleNamespace

from backend.app import main


def test_cached_image_falls_back_to_proxy_when_r2_not_configured(monkeypatch):
    monkeypatch.setattr(main, "get_image_backend", lambda: "bgg_proxy")

    response = asyncio.run(
        main.get_cached_image(224517, image_url="https://example.com/game.jpg")
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/api/proxy-image/https%3A%2F%2Fexample.com%2Fgame.jpg"


def test_cached_image_redirects_to_cdn_when_sync_succeeds(monkeypatch):
    monkeypatch.setattr(main, "get_image_backend", lambda: "r2_cdn")
    monkeypatch.setattr(main, "get_r2_public_base_url", lambda: "https://cdn.example.com")

    response = asyncio.run(
        main.get_cached_image(224517, image_url="https://example.com/game.jpg")
    )

    assert response.status_code == 307
    assert response.headers["location"] == "https://cdn.example.com/games/224517.jpg"


def test_cached_image_fly_local_downloads_and_redirects(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "get_image_backend", lambda: "fly_local")
    monkeypatch.setattr(main, "IMAGE_STORAGE_DIR", tmp_path)

    async def mock_download_origin_image_content(image_url):
        return (b"image-bytes", "image/jpeg")

    monkeypatch.setattr(main, "download_origin_image_content", mock_download_origin_image_content)
    async def mock_run_image_io_task(task):
        task()
    monkeypatch.setattr(main, "run_image_io_task", mock_run_image_io_task)

    response = asyncio.run(
        main.get_cached_image(224517, image_url="https://example.com/game.jpg")
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/images/games/224517.jpg"
    assert (tmp_path / "games" / "224517.jpg").exists()


def test_cached_image_falls_back_to_db_lookup_when_image_url_missing(monkeypatch):
    monkeypatch.setattr(main, "get_image_backend", lambda: "bgg_proxy")
    monkeypatch.setattr(
        main.crud,
        "get_game",
        lambda db, game_id: SimpleNamespace(id=game_id, image="https://example.com/db-game.jpg"),
    )

    response = asyncio.run(main.get_cached_image(224517, image_url=None))

    assert response.status_code == 307
    assert response.headers["location"] == "/api/proxy-image/https%3A%2F%2Fexample.com%2Fdb-game.jpg"
