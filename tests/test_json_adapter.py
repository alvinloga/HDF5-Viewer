"""JSON structured adapter behavior for DataSource v1."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.domain import (
    DataDomain,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ResourceId,
    SourceCapability,
)
from data_viewer.domain.payload import StructuredPayload
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.json import JSONAdapter, JSONSourceSession
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken


def _write_json(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    return path


def test_json_adapter_opens_hierarchy_with_json_pointer_paths(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path / "sample.json",
        '{"alpha": [1, {"beta/gamma": true}], "tilde~key": "value"}',
    )
    registry = SourceRegistry([JSONAdapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    root_page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )

    assert root.domain is DataDomain.STRUCTURED
    assert root.has_children is True
    assert [item.resource_id.node_path for item in root_page.items] == [
        "/alpha",
        "/tilde~0key",
    ]
    alpha_page = session.list_children(
        ResourceId(session.source_uri, "/alpha"),
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    assert [item.resource_id.node_path for item in alpha_page.items] == [
        "/alpha/0",
        "/alpha/1",
    ]
    nested = ResourceId(session.source_uri, "/alpha/1/beta~1gamma")
    metadata = session.get_metadata(nested, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(resource_id=nested, scope=OperationScope.FULL, max_bytes=4096),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.domain is DataDomain.STRUCTURED
    assert metadata.node_kind is NodeKind.RESOURCE
    assert metadata.attributes["json_type"] == "boolean"
    assert SourceCapability.EDIT_PATCH not in metadata.capabilities
    assert SourceCapability.ATOMIC_REWRITE not in metadata.capabilities
    assert isinstance(result.payload, StructuredPayload)
    assert result.payload.value is True
    session.close()


def test_json_adapter_supports_scalar_root_and_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "scalar.json"
    path.write_bytes(b"\xef\xbb\xbf42")
    session = JSONAdapter().open(path, cancellation=CancellationToken())
    metadata = session.get_metadata(session.root().resource_id, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(resource_id=session.root().resource_id, scope=OperationScope.FULL),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.node_kind is NodeKind.RESOURCE
    assert metadata.attributes["json_type"] == "number"
    assert metadata.attributes["encoding"] == "utf-8-sig"
    assert isinstance(result.payload, StructuredPayload)
    assert result.payload.value == 42
    session.close()


def test_json_duplicate_keys_warn_and_use_last_value(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "duplicate.json", '{"a": 1, "a": 2}')
    session = JSONAdapter().open(path, cancellation=CancellationToken())
    metadata = session.get_metadata(session.root().resource_id, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(resource_id=ResourceId(session.source_uri, "/a"), scope=OperationScope.FULL),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.attributes["duplicate_keys"] == ["/a"]
    assert isinstance(result.payload, StructuredPayload)
    assert result.payload.value == 2
    assert "Duplicate JSON object keys" in result.warnings[0]
    session.close()


def test_json_rejects_invalid_encoding_malformed_and_budget_excess(
    tmp_path: Path,
) -> None:
    invalid_encoding = tmp_path / "latin1.json"
    invalid_encoding.write_bytes(b'{"name": "caf\xe9"}')
    malformed = _write_json(tmp_path / "bad.json", '{"unterminated": ')
    too_deep = _write_json(tmp_path / "deep.json", "[[[1]]]")
    too_many = _write_json(tmp_path / "many.json", "[1,2,3]")
    too_long = _write_json(tmp_path / "long.json", '{"s": "abcdef"}')

    with pytest.raises(DataViewerError) as encoding_error:
        JSONAdapter().open(invalid_encoding, cancellation=CancellationToken())
    assert encoding_error.value.code is ErrorCode.SOURCE_MALFORMED
    assert encoding_error.value.details["replacement_characters"] is False

    with pytest.raises(DataViewerError) as malformed_error:
        JSONAdapter().open(malformed, cancellation=CancellationToken())
    assert malformed_error.value.code is ErrorCode.SOURCE_MALFORMED

    with pytest.raises(DataViewerError) as depth_error:
        JSONSourceSession(too_deep, max_depth=2)
    assert depth_error.value.code is ErrorCode.BUDGET_EXCEEDED

    with pytest.raises(DataViewerError) as collection_error:
        JSONSourceSession(too_many, max_collection_length=2)
    assert collection_error.value.code is ErrorCode.BUDGET_EXCEEDED

    with pytest.raises(DataViewerError) as string_error:
        JSONSourceSession(too_long, max_string_length=5)
    assert string_error.value.code is ErrorCode.BUDGET_EXCEEDED


def test_json_search_pagination_and_close_lifecycle(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "search.json", '{"alpha": 1, "beta": 2, "gamma": 3}')
    session = JSONAdapter().open(path, cancellation=CancellationToken())
    page = session.list_children(
        session.root().resource_id,
        cursor=None,
        page_size=2,
        cancellation=CancellationToken(),
    )
    search = session.search(
        "ga",
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )

    assert page.next_cursor == "2"
    assert page.total_count == 3
    assert [item.name for item in search.items] == ["gamma"]
    session.close()
    with pytest.raises(DataViewerError) as closed_error:
        session.root()
    assert closed_error.value.code is ErrorCode.SOURCE_CLOSED
