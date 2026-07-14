"""Restricted YAML structured adapter behavior for DataSource v1."""

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
from data_viewer.sources.registry import SourceRegistry
from data_viewer.sources.yaml import YAMLAdapter, YAMLSourceSession
from data_viewer.tasks import CancellationToken


def _write_yaml(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    return path


def test_yaml_adapter_opens_hierarchy_with_typed_key_metadata(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "sample.yaml",
        """
1: one
nested:
  list:
    - true
slash/key: value
""".lstrip(),
    )
    registry = SourceRegistry([YAMLAdapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    root_page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )

    assert root.domain is DataDomain.STRUCTURED
    assert [item.resource_id.node_path for item in root_page.items] == [
        "/1",
        "/nested",
        "/slash~1key",
    ]
    typed_key = ResourceId(session.source_uri, "/1")
    metadata = session.get_metadata(typed_key, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(resource_id=typed_key, scope=OperationScope.FULL, max_bytes=4096),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.domain is DataDomain.STRUCTURED
    assert metadata.node_kind is NodeKind.RESOURCE
    assert metadata.attributes["yaml_type"] == "string"
    assert metadata.attributes["yaml_key_type"] == "int"
    assert metadata.attributes["yaml_original_key"] == "1"
    assert SourceCapability.EDIT_PATCH not in metadata.capabilities
    assert SourceCapability.ATOMIC_REWRITE not in metadata.capabilities
    assert isinstance(result.payload, StructuredPayload)
    assert result.payload.value == "one"
    session.close()


def test_yaml_safe_loader_rejects_python_and_custom_tags(tmp_path: Path) -> None:
    python_tag = _write_yaml(
        tmp_path / "python.yaml",
        '!!python/object/apply:os.system ["echo unsafe"]',
    )
    custom_tag = _write_yaml(tmp_path / "custom.yaml", "!app value")

    for path in (python_tag, custom_tag):
        with pytest.raises(DataViewerError) as error:
            YAMLAdapter().open(path, cancellation=CancellationToken())
        assert error.value.code is ErrorCode.SOURCE_MALFORMED


def test_yaml_alias_and_merge_semantics_are_reported_and_limited(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "merge.yaml",
        """
defaults: &defaults
  a: 1
item:
  <<: *defaults
  b: 2
again: *defaults
""".lstrip(),
    )
    session = YAMLAdapter().open(path, cancellation=CancellationToken())
    metadata = session.get_metadata(session.root().resource_id, cancellation=CancellationToken())
    item_result = session.read(
        ReadRequest(resource_id=ResourceId(session.source_uri, "/item"), scope=OperationScope.FULL),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.attributes["yaml_alias_count"] == 2
    assert metadata.attributes["yaml_merge_key_count"] == 1
    assert "YAML aliases" in item_result.warnings[0]
    assert isinstance(item_result.payload, StructuredPayload)
    assert item_result.payload.value == {"a": 1, "b": 2}
    session.close()

    with pytest.raises(DataViewerError) as alias_error:
        YAMLSourceSession(path, max_aliases=1)
    assert alias_error.value.code is ErrorCode.BUDGET_EXCEEDED


def test_yaml_rejects_invalid_encoding_malformed_and_budget_excess(
    tmp_path: Path,
) -> None:
    invalid_encoding = tmp_path / "latin1.yaml"
    invalid_encoding.write_bytes(b'name: caf\xe9')
    malformed = _write_yaml(tmp_path / "bad.yaml", "key: [unterminated")
    too_deep = _write_yaml(tmp_path / "deep.yaml", "a:\n  b:\n    c: 1\n")
    too_many = _write_yaml(tmp_path / "many.yaml", "[1, 2, 3]")
    too_long = _write_yaml(tmp_path / "long.yaml", "s: abcdef")

    with pytest.raises(DataViewerError) as encoding_error:
        YAMLAdapter().open(invalid_encoding, cancellation=CancellationToken())
    assert encoding_error.value.code is ErrorCode.SOURCE_MALFORMED
    assert encoding_error.value.details["replacement_characters"] is False

    with pytest.raises(DataViewerError) as malformed_error:
        YAMLAdapter().open(malformed, cancellation=CancellationToken())
    assert malformed_error.value.code is ErrorCode.SOURCE_MALFORMED

    with pytest.raises(DataViewerError) as depth_error:
        YAMLSourceSession(too_deep, max_depth=2)
    assert depth_error.value.code is ErrorCode.BUDGET_EXCEEDED

    with pytest.raises(DataViewerError) as collection_error:
        YAMLSourceSession(too_many, max_collection_length=2)
    assert collection_error.value.code is ErrorCode.BUDGET_EXCEEDED

    with pytest.raises(DataViewerError) as string_error:
        YAMLSourceSession(too_long, max_string_length=5)
    assert string_error.value.code is ErrorCode.BUDGET_EXCEEDED


def test_yaml_search_pagination_scalar_root_and_close_lifecycle(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path / "search.yml", "alpha: 1\nbeta: 2\ngamma: 3\n")
    scalar = _write_yaml(tmp_path / "scalar.yaml", "42\n")
    session = YAMLAdapter().open(path, cancellation=CancellationToken())
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
    scalar_session = YAMLAdapter().open(scalar, cancellation=CancellationToken())
    scalar_metadata = scalar_session.get_metadata(
        scalar_session.root().resource_id,
        cancellation=CancellationToken(),
    )

    assert page.next_cursor == "2"
    assert page.total_count == 3
    assert [item.name for item in search.items] == ["gamma"]
    assert scalar_metadata.node_kind is NodeKind.RESOURCE
    assert scalar_metadata.attributes["yaml_type"] == "number"
    session.close()
    scalar_session.close()
    with pytest.raises(DataViewerError) as closed_error:
        session.root()
    assert closed_error.value.code is ErrorCode.SOURCE_CLOSED
