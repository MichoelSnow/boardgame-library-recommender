import asyncio

import pytest

from backend.app import main


class _DummyResponse:
    def __init__(self, status_code=200, headers=None, body=b"img"):
        self.status_code = status_code
        self.headers = headers or {"content-type": "image/jpeg"}
        self._body = body

    def iter_bytes(self):
        yield self._body


class _DummyAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *_args, **_kwargs):
        return self._response


def test_proxy_image_rejects_non_http_scheme():
    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.proxy_image("ftp://example.com/image.jpg"))
    assert exc.value.status_code == 400


def test_proxy_image_rejects_private_dns_resolution(monkeypatch):
    monkeypatch.setattr(
        main.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (None, None, None, None, ("10.0.0.8", 80)),
        ],
    )

    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.proxy_image("https://example.com/image.jpg"))
    assert exc.value.status_code == 400


def test_proxy_image_rejects_large_content_length(monkeypatch):
    monkeypatch.setattr(
        main.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (None, None, None, None, ("93.184.216.34", 443)),
        ],
    )
    response = _DummyResponse(
        headers={
            "content-type": "image/jpeg",
            "content-length": str(main.MAX_PROXY_IMAGE_BYTES + 1),
        }
    )
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda: _DummyAsyncClient(response))

    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.proxy_image("https://example.com/image.jpg"))
    assert exc.value.status_code == 413

