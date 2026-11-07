import logging

from data_pipeline.src.common import logging_utils


def test_build_log_handlers_uses_file_handler_only(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PIPELINE_LOG_DIR", str(tmp_path))

    handlers = logging_utils.build_log_handlers("test.log")

    try:
        assert len(handlers) == 1
        assert type(handlers[0]) is logging.FileHandler
        assert (tmp_path / "test.log").exists()
    finally:
        for handler in handlers:
            handler.close()
