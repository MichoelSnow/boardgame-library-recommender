from backend.app.versioning import DEFAULT_APP_VERSION, get_app_version


def test_get_app_version_matches_pyproject():
    get_app_version.cache_clear()

    version = get_app_version()

    assert version == "0.1.0"
    assert version != DEFAULT_APP_VERSION
