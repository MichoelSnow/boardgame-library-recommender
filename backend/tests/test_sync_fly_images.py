from pathlib import Path

from data_pipeline.src.assets.sync_fly_images import (
    build_relative_image_path,
    infer_extension_from_content_type,
    infer_extension_from_url,
    parse_bool_scope,
    qualifies_for_seed,
)


def test_infer_extension_from_content_type_maps_jpeg():
    assert infer_extension_from_content_type("image/jpeg") == "jpg"


def test_infer_extension_from_url_uses_path_suffix():
    assert infer_extension_from_url("https://example.com/image.webp") == "webp"


def test_build_relative_image_path_prefers_content_type():
    relative = build_relative_image_path(
        224517,
        image_url="https://example.com/file.png",
        content_type="image/jpeg",
    )
    assert relative == Path("games/224517.jpg")


def test_parse_bool_scope_all_qualified():
    include_library, include_top_rank = parse_bool_scope("all-qualified")
    assert include_library is True
    assert include_top_rank is True


def test_qualifies_for_seed_top_rank():
    assert qualifies_for_seed(
        game_id=10,
        rank=100,
        library_ids={99},
        max_rank=1000,
        include_library=False,
        include_top_rank=True,
    )


def test_qualifies_for_seed_library_only():
    assert qualifies_for_seed(
        game_id=42,
        rank=50000,
        library_ids={42},
        max_rank=1000,
        include_library=True,
        include_top_rank=False,
    )
    assert not qualifies_for_seed(
        game_id=77,
        rank=50000,
        library_ids={42},
        max_rank=1000,
        include_library=True,
        include_top_rank=False,
    )
