"""Session implementation for CSV/TSV table resources in Data Viewer v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from data_viewer.domain import (
    ColumnSpec,
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    JsonValue,
    NodeKind,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.domain.payload import TablePayload
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest

from .options import (
    DelimitedPreview,
    DelimitedTextOptions,
    iter_converted_rows,
    preview_delimited_source,
)

TABLE_NODE_PATH = "/table"
DEFAULT_PAGE_ROWS = 1_000


class DelimitedSourceSession:
    """One owned CSV/TSV table session with explicit parse options."""

    def __init__(
        self,
        path: Path,
        *,
        options: DelimitedTextOptions | None = None,
    ) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._fingerprint = _fingerprint(path)
        self._preview: DelimitedPreview = preview_delimited_source(
            path,
            options=options,
        )

    @property
    def source_uri(self) -> str:
        return self._source_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        return (
            SourceCapability.HIERARCHY
            | SourceCapability.PAGED_ROWS
            | SourceCapability.SEARCH
            | SourceCapability.COLUMN_SCHEMA
            | SourceCapability.SAVE_AS
        )

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.delimited.root")
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, "/"),
            name=self._path.name,
            node_kind=NodeKind.ROOT,
            domain=DataDomain.TABLE,
            has_children=True,
            summary=f"Delimited table source {self._path.name}",
        )

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.delimited.list_children")
        _raise_if_cancelled(cancellation, operation="source.delimited.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        if parent != ResourceId(self._source_uri, "/"):
            raise _resource_not_found(parent, operation="source.delimited.list_children")
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        if start < 0:
            raise ValueError("cursor must be a non-negative integer")
        children = (self._table_node(),)
        stop = min(start + page_size, len(children))
        return NodePage(
            items=children[start:stop],
            next_cursor=str(stop) if stop < len(children) else None,
            total_count=len(children),
        )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: object,
    ) -> DataMetadata:
        self._ensure_open(operation="source.delimited.get_metadata")
        _raise_if_cancelled(cancellation, operation="source.delimited.get_metadata")
        if resource.source_uri != self._source_uri:
            raise _resource_not_found(resource, operation="source.delimited.get_metadata")
        if resource.node_path == "/":
            return DataMetadata(
                resource_id=resource,
                name=self._path.name,
                domain=DataDomain.TABLE,
                node_kind=NodeKind.ROOT,
                shape=self._metadata_shape(),
                dtype="table",
                storage_size_bytes=self._path.stat().st_size,
                capabilities=self.capabilities,
                attributes=self._metadata_attributes(root=True),
                columns=self._preview.schema,
            )
        if resource.node_path != TABLE_NODE_PATH:
            raise _resource_not_found(resource, operation="source.delimited.get_metadata")
        return DataMetadata(
            resource_id=resource,
            name="table",
            domain=DataDomain.TABLE,
            node_kind=NodeKind.RESOURCE,
            shape=self._metadata_shape(),
            dtype="table",
            logical_size_bytes=_estimated_preview_logical_size(self._preview),
            storage_size_bytes=self._path.stat().st_size,
            capabilities=(
                SourceCapability.PAGED_ROWS
                | SourceCapability.SEARCH
                | SourceCapability.COLUMN_SCHEMA
                | SourceCapability.SAVE_AS
            ),
            attributes=self._metadata_attributes(root=False),
            columns=self._preview.schema,
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.delimited.read")
        _raise_if_cancelled(cancellation, operation="source.delimited.read")
        if request.resource_id != ResourceId(self._source_uri, TABLE_NODE_PATH):
            raise _resource_not_found(request.resource_id, operation="source.delimited.read")
        if request.selection.axes:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="SelectionSpec slicing is not supported for delimited table reads.",
                operation="source.delimited.read",
                resource_id=request.resource_id,
            )
        if request.scope not in {OperationScope.PAGE, OperationScope.FULL}:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="Delimited reads support PAGE or FULL scope only.",
                operation="source.delimited.read",
                resource_id=request.resource_id,
                details={"scope": request.scope.value},
            )

        row_offset = request.row_offset or 0
        row_limit = request.row_limit
        if request.scope is OperationScope.PAGE and row_limit is None:
            row_limit = DEFAULT_PAGE_ROWS
        if request.scope is OperationScope.FULL and row_limit is None:
            if self._preview.data_row_count is None:
                raise DataViewerError(
                    code=ErrorCode.BUDGET_EXCEEDED,
                    message="Full delimited read requires a known bounded row count.",
                    operation="source.delimited.read",
                    resource_id=request.resource_id,
                )
            row_limit = self._preview.data_row_count
        selected_schema = _select_columns(self._preview.schema, request.selected_columns)
        selected_indices = tuple(
            _schema_index(self._preview.schema, column.name) for column in selected_schema
        )

        progress(0, 1, "start")
        row_values: list[tuple[object, ...]] = []
        for _data_index, values in iter_converted_rows(
            self._path,
            self._preview.options,
            self._preview.schema,
            row_offset=row_offset,
            row_limit=row_limit,
        ):
            _raise_if_cancelled(cancellation, operation="source.delimited.read")
            row_values.append(tuple(values[index] for index in selected_indices))
        columns = _column_arrays(selected_schema, row_values)
        payload = TablePayload(
            columns=selected_schema,
            column_values=columns,
            row_offset=row_offset,
            total_rows=self._preview.data_row_count,
        )
        bytes_read = _table_payload_bytes(payload)
        if bytes_read > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Delimited table page exceeds the requested read budget.",
                operation="source.delimited.read",
                resource_id=request.resource_id,
                details={"bytes_read": bytes_read, "max_bytes": request.max_bytes},
            )
        progress(1, 1, "done")
        return ReadResult(
            payload=payload,
            scope=request.scope,
            bytes_read=bytes_read,
            is_sampled=False,
            sample=request.sample,
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.delimited.search")
        _raise_if_cancelled(cancellation, operation="source.delimited.search")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        normalized = query.strip().lower()
        if not normalized:
            return NodePage(items=(), next_cursor=None, total_count=0)
        nodes = [self._table_node()] if "table".startswith(normalized) else []
        for column in self._preview.schema:
            if normalized in column.name.lower():
                nodes = [self._table_node()]
                break
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("cursor must be a non-negative integer string") from exc
        if start < 0:
            raise ValueError("cursor must be a non-negative integer")
        stop = min(start + page_size, len(nodes))
        return NodePage(
            items=tuple(nodes[start:stop]),
            next_cursor=str(stop) if stop < len(nodes) else None,
            total_count=len(nodes),
        )

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.delimited.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def close(self) -> None:
        self._closed = True

    def _table_node(self) -> ResourceNode:
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, TABLE_NODE_PATH),
            name="table",
            node_kind=NodeKind.RESOURCE,
            domain=DataDomain.TABLE,
            has_children=False,
            summary=f"table rows={self._row_count_label()} columns={len(self._preview.schema)}",
        )

    def _metadata_shape(self) -> tuple[int, int]:
        return (
            int(self._preview.data_row_count or len(self._preview.preview_rows)),
            len(self._preview.schema),
        )

    def _metadata_attributes(self, *, root: bool) -> dict[str, JsonValue]:
        return {
            "format": "DelimitedText",
            "dialect": "TSV" if self._preview.options.delimiter == "\t" else "CSV",
            "confirmed_options": self._preview.options.to_json(),
            "source_fingerprint": self._fingerprint.to_json(),
            "preview_row_count": len(self._preview.preview_rows),
            "data_row_count": self._preview.data_row_count,
            "total_rows_known": self._preview.total_rows_known,
            "source_data_start_line": self._preview.source_data_start_line,
            "synthetic_root": root,
        }

    def _row_count_label(self) -> str:
        if self._preview.data_row_count is None:
            return f">={len(self._preview.preview_rows)}"
        return str(self._preview.data_row_count)

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="Delimited source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )


def _select_columns(
    schema: tuple[ColumnSpec, ...],
    selected_columns: tuple[str, ...],
) -> tuple[ColumnSpec, ...]:
    if not selected_columns:
        return schema
    by_name = {column.name: column for column in schema}
    missing = [name for name in selected_columns if name not in by_name]
    if missing:
        raise DataViewerError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Requested delimited table column was not found.",
            operation="source.delimited.select_columns",
            details={"missing_columns": [str(name) for name in missing]},
        )
    return tuple(by_name[name] for name in selected_columns)


def _schema_index(schema: tuple[ColumnSpec, ...], name: str) -> int:
    for index, column in enumerate(schema):
        if column.name == name:
            return index
    raise DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested delimited table column was not found.",
        operation="source.delimited.schema_index",
        details={"column": name},
    )


def _column_arrays(
    schema: tuple[ColumnSpec, ...],
    rows: list[tuple[object, ...]],
) -> tuple[np.ndarray[Any, np.dtype[np.generic]], ...]:
    arrays: list[np.ndarray[Any, np.dtype[np.generic]]] = []
    for column_index, column in enumerate(schema):
        values = [row[column_index] for row in rows]
        arrays.append(np.asarray(values, dtype=_numpy_dtype(column.dtype)))
    return tuple(arrays)


def _numpy_dtype(dtype: str) -> Any:
    if dtype == "int64":
        return np.int64
    if dtype == "float64":
        return np.float64
    if dtype == "bool":
        return np.bool_
    return np.str_


def _table_payload_bytes(payload: TablePayload) -> int:
    total = 0
    for values in payload.column_values:
        total += int(values.nbytes)
        if values.dtype.kind in {"U", "S", "O"}:
            total += sum(len(str(value).encode("utf-8")) for value in values.tolist())
    return total


def _estimated_preview_logical_size(preview: DelimitedPreview) -> int:
    if not preview.preview_rows:
        return 0
    return sum(
        len(value.encode("utf-8"))
        for row in preview.preview_rows
        for value in row
    )


def _fingerprint(path: Path) -> SourceFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to stat delimited source.",
            operation="source.delimited.fingerprint",
            details={"path": str(path)},
            cause=exc,
        ) from exc
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


def _resource_not_found(resource_id: ResourceId, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested delimited resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details={"resource_id": resource_id.to_json()},
    )


def _raise_if_cancelled(cancellation: object, *, operation: str) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="Delimited source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = ["DelimitedSourceSession"]
