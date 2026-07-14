"""Delimited-text options, bounded preview, and schema inference."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from data_viewer.domain import ColumnSpec, DataViewerError, ErrorCode, JsonValue

MAX_PREVIEW_BYTES = 64 * 1024
MAX_PREVIEW_ROWS = 50
MAX_COUNT_BYTES = 2 * 1024 * 1024
DEFAULT_MISSING_TOKENS = ("", "NA", "N/A", "NaN", "nan", "null", "None")
SUPPORTED_DTYPES = frozenset({"string", "int64", "float64", "bool"})
_INT_PATTERN = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True, slots=True)
class DelimitedTextOptions:
    """Confirmed parsing options for one CSV/TSV table source."""

    encoding: str = "utf-8"
    delimiter: str = ","
    quotechar: str = '"'
    escapechar: str | None = None
    doublequote: bool = True
    header_row: int | None = 0
    skipped_rows: tuple[int, ...] = ()
    comment_prefix: str | None = None
    decimal_separator: str = "."
    thousands_separator: str = ""
    missing_tokens: tuple[str, ...] = DEFAULT_MISSING_TOKENS
    dtype_overrides: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.encoding:
            raise ValueError("encoding must not be empty")
        if len(self.delimiter) != 1:
            raise ValueError("delimiter must be one character")
        if len(self.quotechar) != 1:
            raise ValueError("quotechar must be one character")
        if self.escapechar is not None and len(self.escapechar) != 1:
            raise ValueError("escapechar must be one character or None")
        if self.header_row is not None and (
            isinstance(self.header_row, bool) or self.header_row < 0
        ):
            raise ValueError("header_row must be a non-negative integer or None")
        skipped_rows = tuple(int(row) for row in self.skipped_rows)
        if any(row < 0 for row in skipped_rows):
            raise ValueError("skipped_rows must be non-negative")
        if self.comment_prefix is not None and not self.comment_prefix:
            raise ValueError("comment_prefix must be non-empty or None")
        if len(self.decimal_separator) != 1:
            raise ValueError("decimal_separator must be one character")
        if self.thousands_separator and len(self.thousands_separator) != 1:
            raise ValueError("thousands_separator must be one character or empty")
        overrides = {str(name): str(dtype) for name, dtype in self.dtype_overrides.items()}
        unsupported = sorted(set(overrides.values()) - SUPPORTED_DTYPES)
        if unsupported:
            raise ValueError(f"unsupported dtype overrides: {unsupported!r}")
        object.__setattr__(self, "skipped_rows", skipped_rows)
        object.__setattr__(self, "missing_tokens", tuple(self.missing_tokens))
        object.__setattr__(self, "dtype_overrides", overrides)

    @classmethod
    def for_path(cls, path: Path) -> "DelimitedTextOptions":
        """Return explicit v1 defaults for a CSV/TSV path."""

        suffix = path.suffix.lower()
        delimiter = "\t" if suffix == ".tsv" else ","
        return cls(delimiter=delimiter)

    def with_detected_encoding(self, encoding: str) -> "DelimitedTextOptions":
        """Return options with the same dialect and a detected encoding."""

        return DelimitedTextOptions(
            encoding=encoding,
            delimiter=self.delimiter,
            quotechar=self.quotechar,
            escapechar=self.escapechar,
            doublequote=self.doublequote,
            header_row=self.header_row,
            skipped_rows=self.skipped_rows,
            comment_prefix=self.comment_prefix,
            decimal_separator=self.decimal_separator,
            thousands_separator=self.thousands_separator,
            missing_tokens=self.missing_tokens,
            dtype_overrides=self.dtype_overrides,
        )

    def with_dtype_overrides(
        self,
        overrides: Mapping[str, str],
    ) -> "DelimitedTextOptions":
        """Return options whose per-column dtype overrides are explicit."""

        return DelimitedTextOptions(
            encoding=self.encoding,
            delimiter=self.delimiter,
            quotechar=self.quotechar,
            escapechar=self.escapechar,
            doublequote=self.doublequote,
            header_row=self.header_row,
            skipped_rows=self.skipped_rows,
            comment_prefix=self.comment_prefix,
            decimal_separator=self.decimal_separator,
            thousands_separator=self.thousands_separator,
            missing_tokens=self.missing_tokens,
            dtype_overrides=dict(overrides),
        )

    def to_json(self) -> dict[str, JsonValue]:
        """Return JSON-compatible provenance for metadata/workspace state."""

        return {
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "quotechar": self.quotechar,
            "escapechar": self.escapechar,
            "doublequote": self.doublequote,
            "header_row": self.header_row,
            "skipped_rows": [int(row) for row in self.skipped_rows],
            "comment_prefix": self.comment_prefix,
            "decimal_separator": self.decimal_separator,
            "thousands_separator": self.thousands_separator,
            "missing_tokens": list(self.missing_tokens),
            "dtype_overrides": dict(self.dtype_overrides),
        }


@dataclass(frozen=True, slots=True)
class DelimitedPreview:
    """Bounded preview and confirmed schema for a delimited source."""

    options: DelimitedTextOptions
    schema: tuple[ColumnSpec, ...]
    preview_rows: tuple[tuple[str, ...], ...]
    data_row_count: int | None
    total_rows_known: bool
    source_data_start_line: int
    bytes_scanned: int


def preview_delimited_source(
    path: Path,
    *,
    options: DelimitedTextOptions | None = None,
) -> DelimitedPreview:
    """Read a bounded preview, infer a provisional schema, and record options."""

    path = Path(path)
    base_options = options or DelimitedTextOptions.for_path(path)
    preview_bytes = _read_preview_bytes(path)
    encoding = _detect_encoding(path, base_options, header=preview_bytes)
    confirmed_options = base_options.with_detected_encoding(encoding)
    preview_rows = tuple(
        _preview_rows_from_prefix(
            path,
            preview_bytes,
            confirmed_options,
            file_size=path.stat().st_size,
        )
    )
    header_row = _read_header(path, confirmed_options)
    column_names = _column_names(header_row, preview_rows)
    normalized_rows = tuple(_normalize_width(row, len(column_names)) for row in preview_rows)
    schema = _infer_schema(column_names, normalized_rows, confirmed_options)
    data_row_count = _count_data_rows(path, confirmed_options)
    return DelimitedPreview(
        options=confirmed_options,
        schema=schema,
        preview_rows=normalized_rows,
        data_row_count=data_row_count,
        total_rows_known=data_row_count is not None,
        source_data_start_line=_source_data_start_line(confirmed_options),
        bytes_scanned=min(path.stat().st_size, MAX_PREVIEW_BYTES),
    )


def iter_converted_rows(
    path: Path,
    options: DelimitedTextOptions,
    schema: tuple[ColumnSpec, ...],
    *,
    row_offset: int,
    row_limit: int | None,
) -> Iterator[tuple[int, tuple[object, ...]]]:
    """Yield converted rows by stable data-row offset."""

    if row_offset < 0:
        raise ValueError("row_offset must be non-negative")
    stop = None if row_limit is None else row_offset + row_limit
    for _physical_line, data_index, raw_row in _iter_data_rows(path, options):
        if data_index < row_offset:
            continue
        if stop is not None and data_index >= stop:
            break
        normalized = _normalize_width(raw_row, len(schema))
        yield data_index, tuple(
            _convert_value(value, schema[column_index].dtype, options)
            for column_index, value in enumerate(normalized)
        )


def _read_preview_bytes(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            return handle.read(MAX_PREVIEW_BYTES + 1)
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to read delimited source preview.",
            operation="source.delimited.preview",
            details={"path": str(path)},
            cause=exc,
        ) from exc


def _detect_encoding(
    path: Path,
    options: DelimitedTextOptions,
    *,
    header: bytes,
) -> str:
    encoding = "utf-8-sig" if header.startswith(b"\xef\xbb\xbf") else options.encoding
    try:
        header[:MAX_PREVIEW_BYTES].decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Delimited source cannot be decoded with the confirmed encoding.",
            operation="source.delimited.preview",
            details={
                "path": str(path),
                "encoding": encoding,
                "replacement_characters": False,
            },
            cause=exc,
        ) from exc
    return encoding


def _preview_rows_from_prefix(
    path: Path,
    header: bytes,
    options: DelimitedTextOptions,
    *,
    file_size: int,
) -> Iterator[tuple[str, ...]]:
    decoded = header[:MAX_PREVIEW_BYTES].decode(options.encoding, errors="strict")
    if file_size > MAX_PREVIEW_BYTES and not decoded.endswith(("\n", "\r")):
        decoded = decoded.rsplit("\n", 1)[0]
    skipped_rows = set(options.skipped_rows)
    data_rows = 0
    reader = csv.reader(
        io.StringIO(decoded),
        delimiter=options.delimiter,
        quotechar=options.quotechar,
        escapechar=options.escapechar,
        doublequote=options.doublequote,
        strict=True,
    )
    try:
        for physical_line, row in enumerate(reader):
            if physical_line in skipped_rows:
                continue
            if options.comment_prefix is not None and row and row[0].startswith(
                options.comment_prefix
            ):
                continue
            if options.header_row is not None and physical_line == options.header_row:
                continue
            if not row:
                continue
            yield tuple(row)
            data_rows += 1
            if data_rows >= MAX_PREVIEW_ROWS:
                return
    except csv.Error as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Delimited preview contains malformed CSV/TSV structure.",
            operation="source.delimited.preview",
            details={"path": str(path), "delimiter": options.delimiter},
            cause=exc,
        ) from exc


def _open_text(path: Path, options: DelimitedTextOptions):
    try:
        return path.open(
            "r",
            encoding=options.encoding,
            errors="strict",
            newline="",
        )
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to open delimited source.",
            operation="source.delimited.open_text",
            details={"path": str(path)},
            cause=exc,
        ) from exc


def _iter_data_rows(
    path: Path,
    options: DelimitedTextOptions,
    *,
    max_rows: int | None = None,
) -> Iterator[tuple[int, int, tuple[str, ...]]]:
    skipped_rows = set(options.skipped_rows)
    data_index = 0
    yielded = 0
    with _open_text(path, options) as handle:
        reader = csv.reader(
            handle,
            delimiter=options.delimiter,
            quotechar=options.quotechar,
            escapechar=options.escapechar,
            doublequote=options.doublequote,
            strict=True,
        )
        try:
            for physical_line, row in enumerate(reader):
                if physical_line in skipped_rows:
                    continue
                if options.comment_prefix is not None and row and row[0].startswith(
                    options.comment_prefix
                ):
                    continue
                if options.header_row is not None and physical_line == options.header_row:
                    continue
                if not row:
                    continue
                yield physical_line, data_index, tuple(row)
                data_index += 1
                yielded += 1
                if max_rows is not None and yielded >= max_rows:
                    return
        except csv.Error as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Delimited source contains malformed CSV/TSV structure.",
                operation="source.delimited.parse",
                details={"path": str(path), "delimiter": options.delimiter},
                cause=exc,
            ) from exc
        except UnicodeDecodeError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Delimited source cannot be decoded with the confirmed encoding.",
                operation="source.delimited.parse",
                details={
                    "path": str(path),
                    "encoding": options.encoding,
                    "replacement_characters": False,
                },
                cause=exc,
            ) from exc


def _read_header(path: Path, options: DelimitedTextOptions) -> tuple[str, ...] | None:
    if options.header_row is None:
        return None
    skipped_rows = set(options.skipped_rows)
    with _open_text(path, options) as handle:
        reader = csv.reader(
            handle,
            delimiter=options.delimiter,
            quotechar=options.quotechar,
            escapechar=options.escapechar,
            doublequote=options.doublequote,
            strict=True,
        )
        try:
            for physical_line, row in enumerate(reader):
                if physical_line in skipped_rows:
                    continue
                if physical_line == options.header_row:
                    return tuple(row)
        except csv.Error as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Delimited header is malformed.",
                operation="source.delimited.header",
                details={"path": str(path), "delimiter": options.delimiter},
                cause=exc,
            ) from exc
    return None


def _column_names(
    header: tuple[str, ...] | None,
    preview_rows: tuple[tuple[str, ...], ...],
) -> tuple[str, ...]:
    width = len(header) if header is not None else 0
    for row in preview_rows:
        width = max(width, len(row))
    if width == 0:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="Delimited source contains no table columns.",
            operation="source.delimited.schema",
        )
    raw = header if header is not None else tuple(f"column_{idx + 1}" for idx in range(width))
    padded = tuple(raw) + tuple(f"column_{idx + 1}" for idx in range(len(raw), width))
    return _deduplicate_names(padded[:width])


def _deduplicate_names(names: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for index, name in enumerate(names):
        base = name.strip() or f"column_{index + 1}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return tuple(result)


def _normalize_width(row: tuple[str, ...], width: int) -> tuple[str, ...]:
    if len(row) >= width:
        return row[:width]
    return row + tuple("" for _ in range(width - len(row)))


def _infer_schema(
    column_names: tuple[str, ...],
    preview_rows: tuple[tuple[str, ...], ...],
    options: DelimitedTextOptions,
) -> tuple[ColumnSpec, ...]:
    columns: list[ColumnSpec] = []
    for column_index, name in enumerate(column_names):
        values = tuple(row[column_index] for row in preview_rows)
        dtype = options.dtype_overrides.get(name) or _infer_dtype(values, options)
        nullable = any(_is_missing(value, options) for value in values)
        columns.append(
            ColumnSpec(
                name=name,
                dtype=dtype,
                nullable=nullable,
                metadata={
                    "source_column_index": column_index,
                    "dtype_confirmed": name in options.dtype_overrides,
                },
            )
        )
    return tuple(columns)


def _infer_dtype(values: tuple[str, ...], options: DelimitedTextOptions) -> str:
    non_missing = tuple(value for value in values if not _is_missing(value, options))
    if not non_missing:
        return "string"
    if all(_parse_bool(value) is not None for value in non_missing):
        return "bool"
    if all(_is_int(value, options) for value in non_missing):
        return "float64" if len(non_missing) != len(values) else "int64"
    if all(_is_float(value, options) for value in non_missing):
        return "float64"
    return "string"


def _is_missing(value: str, options: DelimitedTextOptions) -> bool:
    return value in set(options.missing_tokens)


def _is_int(value: str, options: DelimitedTextOptions) -> bool:
    normalized = _normalize_number(value, options)
    return bool(_INT_PATTERN.match(normalized))


def _is_float(value: str, options: DelimitedTextOptions) -> bool:
    normalized = _normalize_number(value, options)
    try:
        float(normalized)
    except ValueError:
        return False
    return True


def _normalize_number(value: str, options: DelimitedTextOptions) -> str:
    normalized = value
    if options.thousands_separator:
        normalized = normalized.replace(options.thousands_separator, "")
    if options.decimal_separator != ".":
        normalized = normalized.replace(options.decimal_separator, ".")
    return normalized


def _parse_bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in {"true", "t", "yes", "y"}:
        return True
    if lowered in {"false", "f", "no", "n"}:
        return False
    return None


def _convert_value(
    value: str,
    dtype: str,
    options: DelimitedTextOptions,
) -> object:
    missing = _is_missing(value, options)
    if dtype == "string":
        return "" if missing else value
    if dtype == "float64":
        return np.nan if missing else float(_normalize_number(value, options))
    if dtype == "int64":
        if missing:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Missing value cannot be represented as int64.",
                operation="source.delimited.convert",
                details={"dtype": dtype},
            )
        return int(_normalize_number(value, options))
    if dtype == "bool":
        parsed = _parse_bool(value)
        if parsed is None:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Value cannot be represented as bool.",
                operation="source.delimited.convert",
                details={"dtype": dtype},
            )
        return parsed
    raise DataViewerError(
        code=ErrorCode.SOURCE_MALFORMED,
        message="Unsupported confirmed delimited dtype.",
        operation="source.delimited.convert",
        details={"dtype": dtype},
    )


def _count_data_rows(path: Path, options: DelimitedTextOptions) -> int | None:
    if path.stat().st_size > MAX_COUNT_BYTES:
        return None
    count = 0
    for _physical_line, _data_index, _row in _iter_data_rows(path, options):
        count += 1
    return count


def _source_data_start_line(options: DelimitedTextOptions) -> int:
    if options.header_row is None:
        return 0
    return options.header_row + 1


__all__ = [
    "DelimitedPreview",
    "DelimitedTextOptions",
    "iter_converted_rows",
    "preview_delimited_source",
]
