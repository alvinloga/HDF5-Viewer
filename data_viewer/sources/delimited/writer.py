"""Verified CSV/TSV replacement writer for reviewed table cell patches."""

from __future__ import annotations

import csv
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_viewer.domain import ColumnSpec, DataViewerError, ErrorCode, SourceFingerprint
from data_viewer.editing import CellPatch, ChangeSet, EditPatch, fingerprint_value
from data_viewer.editing.review import SaveStrategy
from data_viewer.persistence.transaction import AtomicReplacementService
from data_viewer.sources.delimited.options import (
    DelimitedTextOptions,
    _convert_value,
)
from data_viewer.tasks import CancellationToken as TaskCancellationToken

TABLE_NODE_PATH = "/table"
type DelimitedPersistenceFailureInjector = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class DelimitedPersistenceResult:
    """Result of applying one CSV/TSV changeset through full replacement."""

    strategy: SaveStrategy
    source_fingerprint: SourceFingerprint
    changed_coordinates: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DelimitedWriteProfile:
    """Text formatting details that must survive a replacement rewrite."""

    lineterminator: str
    has_final_newline: bool


def apply_delimited_change_set(
    *,
    path: Path,
    source_uri: str,
    options: DelimitedTextOptions,
    schema: tuple[ColumnSpec, ...],
    changeset: ChangeSet,
    assert_unchanged: Callable[[SourceFingerprint], None],
    cancellation: object,
    replacement_service: AtomicReplacementService | None = None,
    failure_injector: DelimitedPersistenceFailureInjector | None = None,
) -> DelimitedPersistenceResult:
    """Apply reviewed table cell patches using the atomic replacement service."""

    _raise_if_cancelled(cancellation, operation="source.delimited.apply_change_set")
    _validate_changeset_source(changeset, source_uri=source_uri)
    if changeset.is_clean:
        raise ValueError("changeset must contain at least one patch")
    assert_unchanged(changeset.source_fingerprint)

    patches_by_row = _group_cell_patches(changeset.patches, schema=schema)
    write_profile = _detect_write_profile(path)
    service = replacement_service or AtomicReplacementService()
    token = cancellation if isinstance(cancellation, TaskCancellationToken) else None

    def write_payload(temp_path: Path) -> None:
        _write_patched_table(
            source=path,
            destination=temp_path,
            options=options,
            schema=schema,
            patches_by_row=patches_by_row,
            profile=write_profile,
            cancellation=cancellation,
        )

    def validate_payload(candidate: Path):
        _validate_candidate_table(
            candidate,
            options=options,
            schema=schema,
            patches_by_row=patches_by_row,
            expected_rows=_count_data_rows(path, options),
            expected_columns=len(schema),
        )
        return _fingerprint(candidate)

    result = service.run_replacement(
        path,
        path,
        write_payload=write_payload,
        validate_payload=validate_payload,
        expected_source_fingerprint=changeset.source_fingerprint,
        estimated_output_bytes=path.stat().st_size,
        cancellation=token,
        failure_injector=failure_injector,
    )
    return DelimitedPersistenceResult(
        strategy=SaveStrategy.REPLACEMENT,
        source_fingerprint=result.destination_fingerprint,
        changed_coordinates=sum(len(row_patches) for row_patches in patches_by_row.values()),
    )


def _write_patched_table(
    *,
    source: Path,
    destination: Path,
    options: DelimitedTextOptions,
    schema: tuple[ColumnSpec, ...],
    patches_by_row: dict[int, list[CellPatch]],
    profile: DelimitedWriteProfile,
    cancellation: object,
) -> None:
    touched_rows: set[int] = set()
    with source.open("r", encoding=options.encoding, errors="strict", newline="") as reader_handle:
        with destination.open("w", encoding=options.encoding, errors="strict", newline="") as writer_handle:
            writer = csv.writer(
                writer_handle,
                delimiter=options.delimiter,
                quotechar=options.quotechar,
                escapechar=options.escapechar,
                doublequote=options.doublequote,
                lineterminator=profile.lineterminator,
            )
            reader = csv.reader(
                reader_handle,
                delimiter=options.delimiter,
                quotechar=options.quotechar,
                escapechar=options.escapechar,
                doublequote=options.doublequote,
                strict=True,
            )
            data_index = 0
            last_row_written = False
            for physical_line, raw_row in enumerate(reader):
                _raise_if_cancelled(cancellation, operation="source.delimited.write_payload")
                if not _is_data_row(raw_row, physical_line, options):
                    writer.writerow(raw_row)
                    last_row_written = True
                    continue
                normalized = _normalize_width(tuple(raw_row), len(schema))
                row_patches = patches_by_row.get(data_index, [])
                patched = list(normalized)
                for patch in row_patches:
                    _verify_old_value(normalized, schema, options, patch)
                    patched[patch.coordinate[1]] = _format_patch_value(
                        patch.new_value,
                        schema[patch.coordinate[1]].dtype,
                        options,
                    )
                writer.writerow(patched)
                touched_rows.add(data_index)
                data_index += 1
                last_row_written = True
            missing_rows = sorted(set(patches_by_row) - touched_rows)
            if missing_rows:
                raise DataViewerError(
                    code=ErrorCode.SELECTION_INVALID,
                    message="Delimited patch row coordinate is outside the original table.",
                    operation="source.delimited.write_payload",
                    details={"missing_rows": [int(row) for row in missing_rows]},
                )
            if last_row_written and not profile.has_final_newline:
                writer_handle.seek(writer_handle.tell() - len(profile.lineterminator))
                writer_handle.truncate()


def _validate_candidate_table(
    candidate: Path,
    *,
    options: DelimitedTextOptions,
    schema: tuple[ColumnSpec, ...],
    patches_by_row: dict[int, list[CellPatch]],
    expected_rows: int,
    expected_columns: int,
) -> None:
    rows = tuple(_iter_candidate_rows(candidate, options))
    if len(rows) != expected_rows:
        raise DataViewerError(
            code=ErrorCode.READ_FAILED,
            message="Delimited replacement validation found row-count drift.",
            operation="source.delimited.validate_payload",
            details={
                "expected_rows": expected_rows,
                "candidate_rows": len(rows),
            },
        )
    for data_index, row in enumerate(rows):
        if len(row) != expected_columns:
            raise DataViewerError(
                code=ErrorCode.READ_FAILED,
                message="Delimited replacement validation found column-count drift.",
                operation="source.delimited.validate_payload",
                details={
                    "row": data_index,
                    "expected_columns": expected_columns,
                    "candidate_columns": len(row),
                },
            )
    for row_index, patches in patches_by_row.items():
        row = rows[row_index]
        for patch in patches:
            observed = _convert_value(row[patch.coordinate[1]], schema[patch.coordinate[1]].dtype, options)
            expected = _normalize_for_fingerprint(patch.new_value)
            if _normalize_for_fingerprint(observed) != expected:
                raise DataViewerError(
                    code=ErrorCode.READ_FAILED,
                    message="Delimited replacement validation failed for a patched cell.",
                    operation="source.delimited.validate_payload",
                    resource_id=patch.resource_id,
                    details={"coordinate": [int(item) for item in patch.coordinate]},
                )


def _iter_candidate_rows(
    path: Path,
    options: DelimitedTextOptions,
) -> Iterator[tuple[str, ...]]:
    with path.open("r", encoding=options.encoding, errors="strict", newline="") as handle:
        reader = csv.reader(
            handle,
            delimiter=options.delimiter,
            quotechar=options.quotechar,
            escapechar=options.escapechar,
            doublequote=options.doublequote,
            strict=True,
        )
        for physical_line, row in enumerate(reader):
            if _is_data_row(row, physical_line, options):
                yield tuple(row)


def _group_cell_patches(
    patches: tuple[EditPatch, ...],
    *,
    schema: tuple[ColumnSpec, ...],
) -> dict[int, list[CellPatch]]:
    grouped: dict[int, list[CellPatch]] = {}
    for patch in patches:
        if not isinstance(patch, CellPatch):
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Delimited persistence supports table cell patches only in v1.",
                operation="source.delimited.group_patches",
                resource_id=patch.resource_id,
                details={"patch_type": type(patch).__name__},
            )
        if patch.resource_id.node_path != TABLE_NODE_PATH:
            raise DataViewerError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Delimited changeset targets an unknown table resource.",
                operation="source.delimited.group_patches",
                resource_id=patch.resource_id,
            )
        if len(patch.coordinate) != 2:
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Delimited table patches require row and column coordinates.",
                operation="source.delimited.group_patches",
                resource_id=patch.resource_id,
                details={"coordinate_rank": len(patch.coordinate)},
            )
        row_index, column_index = patch.coordinate
        if column_index >= len(schema):
            raise DataViewerError(
                code=ErrorCode.SELECTION_INVALID,
                message="Delimited patch column coordinate is outside the schema.",
                operation="source.delimited.group_patches",
                resource_id=patch.resource_id,
                details={
                    "column_index": column_index,
                    "column_count": len(schema),
                },
            )
        grouped.setdefault(row_index, []).append(patch)
    return grouped


def _validate_changeset_source(changeset: ChangeSet, *, source_uri: str) -> None:
    for patch in changeset.patches:
        if patch.resource_id.source_uri != source_uri:
            raise DataViewerError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Delimited changeset targets a different source.",
                operation="source.delimited.apply_change_set",
                resource_id=patch.resource_id,
                details={"expected_source_uri": source_uri},
            )


def _verify_old_value(
    row: tuple[str, ...],
    schema: tuple[ColumnSpec, ...],
    options: DelimitedTextOptions,
    patch: CellPatch,
) -> None:
    column_index = patch.coordinate[1]
    observed = _convert_value(row[column_index], schema[column_index].dtype, options)
    observed_fingerprint = fingerprint_value(_normalize_for_fingerprint(observed))
    if observed_fingerprint != patch.old_value_fingerprint:
        raise DataViewerError(
            code=ErrorCode.EDIT_CONFLICT,
            message="Delimited patch old value no longer matches the source.",
            operation="source.delimited.verify_old_values",
            resource_id=patch.resource_id,
            details={
                "coordinate": [int(item) for item in patch.coordinate],
                "expected_fingerprint": patch.old_value_fingerprint,
                "observed_fingerprint": observed_fingerprint,
            },
        )


def _format_patch_value(
    value: object,
    dtype: str,
    options: DelimitedTextOptions,
) -> str:
    if value is None:
        return options.missing_tokens[0] if options.missing_tokens else ""
    if dtype == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
    if dtype == "int64":
        if not isinstance(value, (int, str)):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Delimited int64 patch value must be an integer or integer string.",
                operation="source.delimited.format_patch_value",
            )
        return str(int(value))
    if dtype == "float64":
        if not isinstance(value, (int, float, str)):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Delimited float64 patch value must be numeric or a numeric string.",
                operation="source.delimited.format_patch_value",
            )
        numeric = float(value)
        if math.isnan(numeric):
            return options.missing_tokens[0] if options.missing_tokens else "NaN"
        rendered = format(numeric, "g")
        if options.decimal_separator != ".":
            rendered = rendered.replace(".", options.decimal_separator)
        return rendered
    return str(value)


def _normalize_for_fingerprint(value: object) -> object:
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return value


def _detect_write_profile(path: Path) -> DelimitedWriteProfile:
    data = path.read_bytes()
    lineterminator = "\r\n" if b"\r\n" in data else "\n"
    return DelimitedWriteProfile(
        lineterminator=lineterminator,
        has_final_newline=data.endswith((b"\n", b"\r")),
    )


def _fingerprint(path: Path) -> SourceFingerprint:
    stat = path.stat()
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


def _count_data_rows(path: Path, options: DelimitedTextOptions) -> int:
    return sum(1 for _row in _iter_candidate_rows(path, options))


def _is_data_row(
    row: list[str],
    physical_line: int,
    options: DelimitedTextOptions,
) -> bool:
    if physical_line in set(options.skipped_rows):
        return False
    if options.comment_prefix is not None and row and row[0].startswith(options.comment_prefix):
        return False
    if options.header_row is not None and physical_line == options.header_row:
        return False
    return bool(row)


def _normalize_width(row: tuple[str, ...], width: int) -> tuple[str, ...]:
    if len(row) >= width:
        return row[:width]
    return row + tuple("" for _ in range(width - len(row)))


def _raise_if_cancelled(cancellation: object, *, operation: str) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="Delimited source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = [
    "DelimitedPersistenceFailureInjector",
    "DelimitedPersistenceResult",
    "apply_delimited_change_set",
]
