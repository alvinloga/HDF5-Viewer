"""Logging configuration and sensitive-field redaction tests."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from data_viewer.infrastructure.config import LoggingConfig
from data_viewer.infrastructure.logging import LogRedactor, configure_logging


def test_redactor_rewrites_path_prefixes() -> None:
    redactor = LogRedactor(
        sensitive_paths=("C:/Users/alvin/data", "/home/alvin/data"),
        sensitive_values=("secret-token",),
    )

    assert redactor.redact("open /home/alvin/data/secret/file.csv") == "open <redacted>/secret/file.csv"
    assert redactor.redact("secret-token=abc") == "<redacted>=abc"


def test_logger_writes_redacted_records_to_stream_and_file(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "app.log"
    logging_config = LoggingConfig(
        level="INFO",
        console_level="INFO",
        file_enabled=True,
        file_max_bytes=1_000,
        sensitive_paths=(str(tmp_path / "private"),),
        sensitive_values=("TOKEN-123",),
    )
    logger = configure_logging(
        logger_name=f"data_viewer.tests.infrastructure.{id(tmp_path)}",
        logging_config=logging_config,
        log_file=log_file,
    )

    stream_handler = next(
        handler for handler in logger.handlers if isinstance(handler, logging.StreamHandler)
    )
    stream_capture = io.StringIO()
    stream_handler.stream = stream_capture

    logger.info("loading %s TOKEN-123", str(tmp_path / "private" / "token.json"))
    stream_handler.flush()

    if log_file.exists():
        file_text = log_file.read_text(encoding="utf-8")
        assert "<redacted>" in file_text
        assert "TOKEN-123" not in file_text
        assert "private" not in file_text

    stream_text = stream_capture.getvalue()
    assert "<redacted>" in stream_text
    assert "TOKEN-123" not in stream_text
    assert "private" not in stream_text
