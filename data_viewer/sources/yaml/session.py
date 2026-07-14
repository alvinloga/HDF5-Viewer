"""Session implementation for read-only restricted YAML structured resources."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from data_viewer.domain import (
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
    StructuredPayload,
)
from data_viewer.sources.api import NodePage, ProgressCallback, ReadRequest

DEFAULT_MAX_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_DEPTH = 128
DEFAULT_MAX_COLLECTION_LENGTH = 100_000
DEFAULT_MAX_STRING_LENGTH = 16 * 1024 * 1024
DEFAULT_MAX_ALIASES = 10_000

_ALIAS_RE = re.compile(r"(?<![\w*-])\*([A-Za-z0-9_-]+)")
_MERGE_KEY_RE = re.compile(r"(?m)^\s*<<\s*:")


@dataclass(frozen=True, slots=True)
class _YAMLKeyMetadata:
    path: str
    key_type: str
    original_key: str


@dataclass(frozen=True, slots=True)
class _YAMLSemantics:
    alias_count: int
    merge_key_count: int


@dataclass(frozen=True, slots=True)
class _ParsedYAML:
    value: JsonValue
    key_metadata: Mapping[str, _YAMLKeyMetadata]
    semantics: _YAMLSemantics


class YAMLSourceSession:
    """One owned YAML source session with JSON Pointer resource paths."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_collection_length: int = DEFAULT_MAX_COLLECTION_LENGTH,
        max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
        max_aliases: int = DEFAULT_MAX_ALIASES,
    ) -> None:
        self._path = path
        self._source_uri = path.resolve(strict=False).as_uri()
        self._closed = False
        self._encoding = _detect_encoding(path)
        self._fingerprint = _fingerprint(path)
        self._max_bytes = _positive(max_bytes, "max_bytes")
        self._max_depth = _positive(max_depth, "max_depth")
        self._max_collection_length = _positive(
            max_collection_length,
            "max_collection_length",
        )
        self._max_string_length = _positive(max_string_length, "max_string_length")
        self._max_aliases = _non_negative(max_aliases, "max_aliases")
        self._parsed = self._parse()
        _validate_budget(
            self._parsed.value,
            max_depth=self._max_depth,
            max_collection_length=self._max_collection_length,
            max_string_length=self._max_string_length,
        )

    @property
    def source_uri(self) -> str:
        return self._source_uri

    @property
    def fingerprint(self) -> SourceFingerprint:
        return self._fingerprint

    @property
    def capabilities(self) -> SourceCapability:
        return SourceCapability.HIERARCHY | SourceCapability.SEARCH | SourceCapability.SAVE_AS

    def root(self) -> ResourceNode:
        self._ensure_open(operation="source.yaml.root")
        return self._node_for("/", self._parsed.value)

    def list_children(
        self,
        parent: ResourceId,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.yaml.list_children")
        _raise_if_cancelled(cancellation, operation="source.yaml.list_children")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        parent_value = self._value_for(parent, operation="source.yaml.list_children")
        child_items = tuple(self._iter_children(parent.node_path, parent_value))
        start = _cursor_to_index(cursor)
        stop = min(start + page_size, len(child_items))
        return NodePage(
            items=child_items[start:stop],
            next_cursor=str(stop) if stop < len(child_items) else None,
            total_count=len(child_items),
        )

    def get_metadata(
        self,
        resource: ResourceId,
        *,
        cancellation: object,
    ) -> DataMetadata:
        self._ensure_open(operation="source.yaml.get_metadata")
        _raise_if_cancelled(cancellation, operation="source.yaml.get_metadata")
        value = self._value_for(resource, operation="source.yaml.get_metadata")
        return DataMetadata(
            resource_id=resource,
            name=_node_name(resource.node_path, self._path.name),
            domain=DataDomain.STRUCTURED,
            node_kind=NodeKind.CONTAINER if _has_children(value) else NodeKind.RESOURCE,
            shape=_shape_for(value),
            dtype="yaml",
            logical_size_bytes=_yaml_json_size(value),
            storage_size_bytes=self._path.stat().st_size,
            capabilities=self.capabilities,
            attributes=self._metadata_attributes(resource.node_path, value),
        )

    def read(
        self,
        request: ReadRequest,
        *,
        cancellation: object,
        progress: ProgressCallback,
    ) -> ReadResult:
        self._ensure_open(operation="source.yaml.read")
        _raise_if_cancelled(cancellation, operation="source.yaml.read")
        if request.scope is not OperationScope.FULL:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="YAML structured reads support FULL scope only.",
                operation="source.yaml.read",
                resource_id=request.resource_id,
                details={"scope": request.scope.value},
            )
        if request.selection.axes or request.row_offset is not None or request.row_limit is not None:
            raise DataViewerError(
                code=ErrorCode.CAPABILITY_UNAVAILABLE,
                message="YAML structured reads do not support array/table selections.",
                operation="source.yaml.read",
                resource_id=request.resource_id,
            )
        progress(0, 1, "start")
        value = self._value_for(request.resource_id, operation="source.yaml.read")
        size = _yaml_json_size(value)
        if size > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="YAML structured payload exceeds the requested read budget.",
                operation="source.yaml.read",
                resource_id=request.resource_id,
                details={"bytes_read": size, "max_bytes": request.max_bytes},
            )
        progress(1, 1, "done")
        return ReadResult(
            payload=StructuredPayload(value),
            scope=OperationScope.FULL,
            bytes_read=size,
            is_sampled=False,
            sample=request.sample,
            warnings=self._warnings(),
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: object,
    ) -> NodePage:
        self._ensure_open(operation="source.yaml.search")
        _raise_if_cancelled(cancellation, operation="source.yaml.search")
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        normalized = query.strip().lower()
        if not normalized:
            return NodePage(items=(), next_cursor=None, total_count=0)
        matches = tuple(
            self._node_for(path, value)
            for path, value in _walk("/", self._parsed.value)
            if normalized in _node_name(path, self._path.name).lower()
            or normalized in path.lower()
        )
        start = _cursor_to_index(cursor)
        stop = min(start + page_size, len(matches))
        return NodePage(
            items=matches[start:stop],
            next_cursor=str(stop) if stop < len(matches) else None,
            total_count=len(matches),
        )

    def refresh_fingerprint(self) -> SourceFingerprint:
        self._ensure_open(operation="source.yaml.refresh_fingerprint")
        self._fingerprint = _fingerprint(self._path)
        return self._fingerprint

    def close(self) -> None:
        self._closed = True

    def _parse(self) -> _ParsedYAML:
        try:
            stat = self._path.stat()
        except OSError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to stat YAML source.",
                operation="source.yaml.parse",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc
        if stat.st_size > self._max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="YAML source exceeds the configured file-size budget.",
                operation="source.yaml.parse",
                details={
                    "path": str(self._path),
                    "size_bytes": stat.st_size,
                    "max_bytes": self._max_bytes,
                },
            )
        try:
            text = self._path.read_text(encoding=self._encoding)
        except UnicodeDecodeError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="YAML source cannot be decoded with strict UTF-8.",
                operation="source.yaml.parse",
                details={
                    "path": str(self._path),
                    "encoding": self._encoding,
                    "replacement_characters": False,
                },
                cause=exc,
            ) from exc
        except OSError as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_OPEN_FAILED,
                message="Unable to open YAML source.",
                operation="source.yaml.parse",
                details={"path": str(self._path)},
                cause=exc,
            ) from exc
        semantics = _scan_yaml_semantics(text)
        if semantics.alias_count > self._max_aliases:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="YAML alias count exceeds the configured budget.",
                operation="source.yaml.validate_aliases",
                details={
                    "alias_count": semantics.alias_count,
                    "max_aliases": self._max_aliases,
                },
            )
        raw_value = yaml.safe_load(text)
        key_metadata: dict[str, _YAMLKeyMetadata] = {}
        value = _normalize_yaml_value(
            raw_value,
            path="/",
            key_metadata=key_metadata,
            active_ids=set(),
        )
        return _ParsedYAML(
            value=cast(JsonValue, value),
            key_metadata=key_metadata,
            semantics=semantics,
        )

    def _node_for(self, node_path: str, value: JsonValue) -> ResourceNode:
        return ResourceNode(
            resource_id=ResourceId(self._source_uri, node_path),
            name=_node_name(node_path, self._path.name),
            node_kind=NodeKind.CONTAINER if _has_children(value) else NodeKind.RESOURCE,
            domain=DataDomain.STRUCTURED,
            has_children=_has_children(value),
            summary=f"yaml { _yaml_type(value) }",
        )

    def _iter_children(
        self,
        parent_path: str,
        value: JsonValue,
    ) -> Iterator[ResourceNode]:
        if isinstance(value, dict):
            for key, child in value.items():
                yield self._node_for(_pointer_join(parent_path, key), child)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield self._node_for(_pointer_join(parent_path, str(index)), child)

    def _value_for(self, resource: ResourceId, *, operation: str) -> JsonValue:
        if resource.source_uri != self._source_uri:
            raise _resource_not_found(resource, operation=operation)
        current = self._parsed.value
        if resource.node_path in {"", "/"}:
            return current
        for part in resource.node_path.strip("/").split("/"):
            key = _pointer_unescape(part)
            if isinstance(current, dict):
                if key not in current:
                    raise _resource_not_found(resource, operation=operation)
                current = current[key]
            elif isinstance(current, list):
                try:
                    index = int(key)
                except ValueError as exc:
                    raise _resource_not_found(resource, operation=operation) from exc
                try:
                    current = current[index]
                except IndexError as exc:
                    raise _resource_not_found(resource, operation=operation) from exc
            else:
                raise _resource_not_found(resource, operation=operation)
        return current

    def _metadata_attributes(self, node_path: str, value: JsonValue) -> dict[str, JsonValue]:
        semantics = self._parsed.semantics
        attributes: dict[str, JsonValue] = {
            "format": "YAML",
            "encoding": self._encoding,
            "yaml_type": _yaml_type(value),
            "source_fingerprint": self._fingerprint.to_json(),
            "yaml_alias_count": semantics.alias_count,
            "yaml_merge_key_count": semantics.merge_key_count,
            "yaml_resolved_view": semantics.alias_count > 0 or semantics.merge_key_count > 0,
            "read_only": True,
        }
        root_key_metadata: list[JsonValue] = [
            {
                "path": item.path,
                "yaml_key_type": item.key_type,
                "yaml_original_key": item.original_key,
            }
            for item in self._parsed.key_metadata.values()
        ]
        attributes["yaml_nonstring_keys"] = root_key_metadata
        if key_info := self._parsed.key_metadata.get(node_path):
            attributes["yaml_key_type"] = key_info.key_type
            attributes["yaml_original_key"] = key_info.original_key
        return attributes

    def _warnings(self) -> tuple[str, ...]:
        semantics = self._parsed.semantics
        warnings: list[str] = []
        if semantics.alias_count:
            warnings.append(
                "YAML aliases were detected; Data Viewer displays the safe_load resolved structure.",
            )
        if semantics.merge_key_count:
            warnings.append(
                "YAML merge keys were detected; Data Viewer displays merged mapping values.",
            )
        return tuple(warnings)

    def _ensure_open(self, operation: str) -> None:
        if self._closed:
            raise DataViewerError(
                code=ErrorCode.SOURCE_CLOSED,
                message="YAML source session is closed.",
                operation=operation,
                details={"source_uri": self._source_uri},
            )


def _detect_encoding(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            prefix = handle.read(3)
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to read YAML source.",
            operation="source.yaml.detect_encoding",
            details={"path": str(path)},
            cause=exc,
        ) from exc
    return "utf-8-sig" if prefix.startswith(b"\xef\xbb\xbf") else "utf-8"


def _scan_yaml_semantics(text: str) -> _YAMLSemantics:
    return _YAMLSemantics(
        alias_count=len(_ALIAS_RE.findall(text)),
        merge_key_count=len(_MERGE_KEY_RE.findall(text)),
    )


def _normalize_yaml_value(
    value: Any,
    *,
    path: str,
    key_metadata: dict[str, _YAMLKeyMetadata],
    active_ids: set[int],
) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return cast(JsonValue, value)
    value_id = id(value)
    if value_id in active_ids:
        raise DataViewerError(
            code=ErrorCode.SOURCE_MALFORMED,
            message="YAML recursive aliases cannot be represented as structured data.",
            operation="source.yaml.normalize",
            details={"path": path},
        )
    if isinstance(value, list):
        active_ids.add(value_id)
        try:
            return [
                _normalize_yaml_value(
                    child,
                    path=_pointer_join(path, str(index)),
                    key_metadata=key_metadata,
                    active_ids=active_ids,
                )
                for index, child in enumerate(value)
            ]
        finally:
            active_ids.remove(value_id)
    if isinstance(value, dict):
        active_ids.add(value_id)
        try:
            normalized: dict[str, JsonValue] = {}
            for key, child in value.items():
                display_key = _display_key(key)
                child_path = _pointer_join(path, display_key)
                if display_key in normalized:
                    raise DataViewerError(
                        code=ErrorCode.SOURCE_MALFORMED,
                        message="YAML mapping keys collide after display-safe normalization.",
                        operation="source.yaml.normalize",
                        details={"path": path, "display_key": display_key},
                    )
                if not isinstance(key, str):
                    key_metadata[child_path] = _YAMLKeyMetadata(
                        path=child_path,
                        key_type=_yaml_key_type(key),
                        original_key=_display_key(key),
                    )
                normalized[display_key] = _normalize_yaml_value(
                    child,
                    path=child_path,
                    key_metadata=key_metadata,
                    active_ids=active_ids,
                )
            return normalized
        finally:
            active_ids.remove(value_id)
    return str(value)


def _validate_budget(
    value: JsonValue,
    *,
    max_depth: int,
    max_collection_length: int,
    max_string_length: int,
) -> None:
    def visit(item: JsonValue, depth: int, path: str) -> None:
        if depth > max_depth:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="YAML nesting depth exceeds the configured budget.",
                operation="source.yaml.validate_budget",
                details={"path": path, "max_depth": max_depth},
            )
        if isinstance(item, str) and len(item) > max_string_length:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="YAML string length exceeds the configured budget.",
                operation="source.yaml.validate_budget",
                details={
                    "path": path,
                    "string_length": len(item),
                    "max_string_length": max_string_length,
                },
            )
        if isinstance(item, dict):
            if len(item) > max_collection_length:
                raise DataViewerError(
                    code=ErrorCode.BUDGET_EXCEEDED,
                    message="YAML mapping length exceeds the configured budget.",
                    operation="source.yaml.validate_budget",
                    details={
                        "path": path,
                        "collection_length": len(item),
                        "max_collection_length": max_collection_length,
                    },
                )
            for key, child in item.items():
                visit(child, depth + 1, _pointer_join(path, key))
        elif isinstance(item, list):
            if len(item) > max_collection_length:
                raise DataViewerError(
                    code=ErrorCode.BUDGET_EXCEEDED,
                    message="YAML sequence length exceeds the configured budget.",
                    operation="source.yaml.validate_budget",
                    details={
                        "path": path,
                        "collection_length": len(item),
                        "max_collection_length": max_collection_length,
                    },
                )
            for index, child in enumerate(item):
                visit(child, depth + 1, _pointer_join(path, str(index)))

    visit(value, 0, "/")


def _walk(path: str, value: JsonValue) -> Iterator[tuple[str, JsonValue]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(_pointer_join(path, key), child)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(_pointer_join(path, str(index)), child)


def _pointer_join(parent: str, token: str) -> str:
    escaped = token.replace("~", "~0").replace("/", "~1")
    if parent in {"", "/"}:
        return "/" + escaped
    return parent.rstrip("/") + "/" + escaped


def _pointer_unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _node_name(node_path: str, root_name: str) -> str:
    if node_path in {"", "/"}:
        return root_name
    return _pointer_unescape(node_path.rsplit("/", 1)[-1])


def _has_children(value: JsonValue) -> bool:
    return isinstance(value, (dict, list)) and bool(value)


def _yaml_type(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "sequence"
    if isinstance(value, dict):
        return "mapping"
    return type(value).__name__


def _yaml_key_type(value: object) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if value is None:
        return "null"
    return type(value).__name__


def _display_key(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def _shape_for(value: JsonValue) -> tuple[int, ...]:
    if isinstance(value, dict | list):
        return (len(value),)
    return ()


def _yaml_json_size(value: JsonValue) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _cursor_to_index(cursor: str | None) -> int:
    try:
        start = int(cursor or 0)
    except ValueError as exc:
        raise ValueError("cursor must be a non-negative integer string") from exc
    if start < 0:
        raise ValueError("cursor must be a non-negative integer")
    return start


def _fingerprint(path: Path) -> SourceFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise DataViewerError(
            code=ErrorCode.SOURCE_OPEN_FAILED,
            message="Unable to stat YAML source.",
            operation="source.yaml.fingerprint",
            details={"path": str(path)},
            cause=exc,
        ) from exc
    return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)


def _positive(value: int, label: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return int(value)


def _non_negative(value: int, label: str) -> int:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return int(value)


def _resource_not_found(resource_id: ResourceId, *, operation: str) -> DataViewerError:
    return DataViewerError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="Requested YAML resource was not found.",
        operation=operation,
        resource_id=resource_id,
        details={"resource_id": resource_id.to_json()},
    )


def _raise_if_cancelled(cancellation: object, *, operation: str) -> None:
    if getattr(cancellation, "is_cancelled", False):
        raise DataViewerError(
            code=ErrorCode.READ_CANCELLED,
            message="YAML source operation was cancelled.",
            operation=operation,
            retryable=True,
        )


__all__ = ["YAMLSourceSession"]
