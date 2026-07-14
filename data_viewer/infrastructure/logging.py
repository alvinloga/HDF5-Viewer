"""Logging utilities with path and value redaction for safe diagnostics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import LoggingConfig


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/").rstrip("/")
    if normalized.endswith(":"):
        return f"{normalized}/"
    return normalized


def _normalize_message(value: object) -> str:
    return str(value)


def _normalize_for_search(value: str) -> str:
    return str(value).replace("\\", "/")


def _redact_path(message: str, path: str) -> str:
    normalized_message = _normalize_for_search(message)
    normalized_path = _normalize_path(path)
    if not normalized_message or not normalized_path:
        return message

    output = normalized_message
    search_from = 0
    path_len = len(normalized_path)
    while True:
        index = output.find(normalized_path, search_from)
        if index < 0:
            break

        end = index + path_len
        follows = output[end : end + 1]
        if end < len(output) and follows not in ("/", ""):
            search_from = end
            continue

        output = output[:index] + "<redacted>" + output[end:]
        search_from = index + len("<redacted>")

    return output


@dataclass(frozen=True, slots=True)
class LogRedactor:
    """Simple redactor for sensitive paths and values."""

    sensitive_paths: tuple[str, ...] = ()
    sensitive_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sensitive_paths",
            tuple(_normalize_path(path) for path in self.sensitive_paths if path),
        )
        object.__setattr__(
            self,
            "sensitive_values",
            tuple(value for value in self.sensitive_values if value),
        )

    @classmethod
    def from_logging_config(cls, config: LoggingConfig) -> "LogRedactor":
        return cls(
            sensitive_paths=config.sensitive_paths,
            sensitive_values=config.sensitive_values,
        )

    def redact(self, message: str) -> str:
        output = _normalize_message(message)
        normalized_output = _normalize_for_search(output)

        for path in self.sensitive_paths:
            candidate_prefixes = {path, path.replace("\\", "/"), path.replace("/", "\\")}
            for candidate in candidate_prefixes:
                if not candidate:
                    continue
                redacted = _redact_path(normalized_output, candidate)
                if redacted != normalized_output:
                    output = redacted
                    normalized_output = _normalize_for_search(output)
                    break

            if normalized_output == "<redacted>":
                break

        for value in self.sensitive_values:
            output = output.replace(value, "<redacted>")
            normalized_output = _normalize_for_search(output)
        return output

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        return True


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts sensitive payload after final rendering."""

    def __init__(self, redactor: LogRedactor, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return self._redactor.redact(rendered)


@dataclass(frozen=True, slots=True)
class LoggerPrimitives:
    """Configured logger and handlers."""

    logger: logging.Logger


def configure_logging(
    *,
    logger_name: str,
    logging_config: LoggingConfig,
    log_file: Path,
    force: bool = True,
) -> logging.Logger:
    """
    Configure an application logger with redacted stream and optional file output.

    Args:
        logger_name: logger namespace.
        logging_config: redaction and level configuration.
        log_file: target log file for rotating file output.
        force: clear existing handlers and reconfigure.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(_coerce_level(logging_config.level))
    logger.propagate = False

    redactor = LogRedactor.from_logging_config(logging_config)
    formatter = RedactingFormatter(
        redactor,
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    if force:
        for handler in tuple(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(_coerce_level(logging_config.console_level))
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(redactor)
    logger.addHandler(stream_handler)

    if logging_config.file_enabled:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max(logging_config.file_max_bytes, 1),
            backupCount=logging_config.file_backups,
        )
        file_handler.setLevel(_coerce_level(logging_config.level))
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)
        logger.addHandler(file_handler)

    return logger


def _coerce_level(value: str) -> int:
    return getattr(logging, str(value).upper(), logging.INFO)
