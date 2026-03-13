import pandas as pd

from data_pipeline.src.assets.r2_sync import R2ImageSyncer, build_r2_image_key
import data_pipeline.src.assets.r2_sync as r2_module
from data_pipeline.src.assets.sync_r2_images import (
    iter_sync_candidates,
    parse_id_list,
    qualifies_for_sync,
)


def test_build_r2_image_key_uses_bgg_id_and_url_extension():
    key = build_r2_image_key(224517, image_url="https://example.com/images/test.png")
    assert key == "games/224517.png"


def test_build_r2_image_key_prefers_content_type():
    key = build_r2_image_key(
        224517,
        image_url="https://example.com/images/test.jpg",
        content_type="image/webp",
    )
    assert key == "games/224517.webp"


def test_build_r2_image_key_defaults_to_jpg():
    key = build_r2_image_key(224517, image_url="https://example.com/images/noext")
    assert key == "games/224517.jpg"


def test_parse_id_list_handles_empty_and_whitespace():
    assert parse_id_list("") == set()
    assert parse_id_list("  ") == set()
    assert parse_id_list("1, 2,3") == {1, 2, 3}


def test_qualifies_for_sync_scopes():
    library_ids = {10}
    assert qualifies_for_sync(
        game_id=10, game_rank=None, library_ids=library_ids, max_rank=100, scope="library-only"
    )
    assert not qualifies_for_sync(
        game_id=11, game_rank=200, library_ids=library_ids, max_rank=100, scope="library-only"
    )
    assert qualifies_for_sync(
        game_id=11, game_rank=99, library_ids=library_ids, max_rank=100, scope="top-rank-only"
    )
    assert not qualifies_for_sync(
        game_id=11, game_rank=101, library_ids=library_ids, max_rank=100, scope="top-rank-only"
    )
    assert qualifies_for_sync(
        game_id=10, game_rank=500, library_ids=library_ids, max_rank=100, scope="all-qualified"
    )
    assert qualifies_for_sync(
        game_id=11, game_rank=50, library_ids=library_ids, max_rank=100, scope="all-qualified"
    )
    assert not qualifies_for_sync(
        game_id=12, game_rank=500, library_ids=library_ids, max_rank=100, scope="all-qualified"
    )


def test_iter_sync_candidates_filters_and_qualifies():
    df = pd.DataFrame(
        [
            {"id": 1, "rank": 50, "image": "https://example.com/1.jpg"},
            {"id": 2, "rank": 50000, "image": "https://example.com/2.jpg"},
            {"id": 3, "rank": 50000, "image": "https://example.com/3.jpg"},
            {"id": 4, "rank": 5, "image": None},
        ]
    )
    library_ids = {3}
    candidates = list(
        iter_sync_candidates(
            df,
            library_ids=library_ids,
            max_rank=100,
            scope="all-qualified",
            include_game_ids=set(),
        )
    )
    assert candidates == [
        (1, "https://example.com/1.jpg"),
        (3, "https://example.com/3.jpg"),
    ]


def test_iter_sync_candidates_applies_include_filter_before_qualification():
    df = pd.DataFrame(
        [
            {"id": 1, "rank": 50, "image": "https://example.com/1.jpg"},
            {"id": 3, "rank": 50000, "image": "https://example.com/3.jpg"},
        ]
    )
    library_ids = {3}
    candidates = list(
        iter_sync_candidates(
            df,
            library_ids=library_ids,
            max_rank=100,
            scope="all-qualified",
            include_game_ids={1},
        )
    )
    assert candidates == [(1, "https://example.com/1.jpg")]


def test_existing_key_for_bgg_id_checks_all_supported_extensions():
    syncer = object.__new__(R2ImageSyncer)
    existing = {"games/224517.webp"}
    syncer.object_exists = lambda key: key in existing

    key = syncer.existing_key_for_bgg_id(224517)
    assert key == "games/224517.webp"


def test_sync_image_url_skips_download_when_object_exists(monkeypatch):
    syncer = object.__new__(R2ImageSyncer)
    syncer.existing_key_for_bgg_id = lambda bgg_id: "games/224517.jpg"
    syncer.upload_bytes = lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("upload_bytes should not be called for existing objects")
    )

    def fail_download(*args, **kwargs):
        raise AssertionError(
            "download_image_content should not be called for existing objects"
        )

    monkeypatch.setattr(r2_module, "download_image_content", fail_download)

    key, status = syncer.sync_image_url(
        bgg_id=224517,
        image_url="https://example.com/224517.jpg",
        overwrite_existing=False,
    )
    assert key == "games/224517.jpg"
    assert status == "skipped_existing"


def test_build_existing_bgg_id_map_parses_canonical_keys():
    keys = {
        "games/224517.jpg",
        "games/167791.webp",
        "games/not-an-id.png",
        "other/123.jpg",
    }
    result = R2ImageSyncer.build_existing_bgg_id_map(keys)
    assert result == {
        224517: "games/224517.jpg",
        167791: "games/167791.webp",
    }
