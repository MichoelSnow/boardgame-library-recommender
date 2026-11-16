import logging

from data_pipeline.src.common import logging_utils


def test_build_log_handlers_uses_file_and_stream_handlers(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PIPELINE_LOG_DIR", str(tmp_path))

    handlers = logging_utils.build_log_handlers("test.log")

    try:
        assert len(handlers) == 2
        assert type(handlers[0]) is logging.FileHandler
        assert type(handlers[1]) is logging.StreamHandler
        assert (tmp_path / "test.log").exists()
    finally:
        for handler in handlers:
            handler.close()


def test_configure_stage_logging_attaches_handlers_to_stage_logger(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATA_PIPELINE_LOG_DIR", str(tmp_path))
    logger = logging.getLogger("test.stage.logger")

    logging_utils.configure_stage_logging(logger, "stage.log")

    try:
        assert logger.propagate is False
        assert [type(handler) for handler in logger.handlers] == [
            logging.FileHandler,
            logging.StreamHandler,
        ]
        logger.info("stage message")
        assert "stage message" in (tmp_path / "stage.log").read_text()
    finally:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
