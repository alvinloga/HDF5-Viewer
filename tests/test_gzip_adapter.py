"""Generic gzip wrapper behavior for stream-capable DataSource v1 formats."""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pytest

from data_viewer.domain import DataDomain, DataViewerError, ErrorCode, OperationScope, ResourceId
from data_viewer.domain.payload import StructuredPayload, TablePayload
from data_viewer.gui.shell import create_source_registry
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.json import JSONAdapter
from data_viewer.sources.gzip import GzipAdapter
from data_viewer.tasks import CancellationToken


def _write_gzip(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as handle:
        handle.write(payload)
    return path


def test_json_gzip_wrapper_opens_with_original_resource_identity(tmp_path: Path) -> None:
    path = _write_gzip(tmp_path / "sample.json.gz", b'{"alpha": [1, 2]}')
    registry = create_source_registry()

    selected = registry.select_adapter(path, cancellation=CancellationToken())
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    metadata = session.get_metadata(root.resource_id, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/alpha/1"),
            scope=OperationScope.FULL,
            max_bytes=4096,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert selected.adapter.adapter_id == GzipAdapter.adapter_id
    assert root.resource_id.source_uri == path.resolve(strict=False).as_uri()
    assert page.items[0].resource_id.source_uri == root.resource_id.source_uri
    assert metadata.attributes["gzip_wrapped"] is True
    assert metadata.attributes["inner_adapter_id"] == "data-viewer.json"
    assert metadata.domain is DataDomain.STRUCTURED
    assert isinstance(result.payload, StructuredPayload)
    assert result.payload.value == 2
    assert any("gzip" in warning.lower() for warning in result.warnings)
    session.close()


def test_csv_gzip_wrapper_streams_inner_table_adapter(tmp_path: Path) -> None:
    path = _write_gzip(tmp_path / "table.csv.gz", b"time,value\n0,1.5\n1,2.5\n")
    registry = create_source_registry()
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    table = page.items[0].resource_id
    result = session.read(
        ReadRequest(resource_id=table, scope=OperationScope.PAGE, row_offset=0, row_limit=2),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert isinstance(result.payload, TablePayload)
    assert [column.name for column in result.payload.columns] == ["time", "value"]
    assert np.asarray(result.payload.column_values[1]).tolist() == [1.5, 2.5]
    assert result.payload.source_cell(1, "time") == (1, "time")
    assert any("read-only gzip" in warning.lower() for warning in result.warnings)
    session.close()


def test_gzip_wrapper_preserves_native_nifti_routing(tmp_path: Path) -> None:
    path = _write_gzip(tmp_path / "not_nifti.nii.gz", b"not a nifti header")
    registry = create_source_registry()
    gzip_adapter = GzipAdapter([JSONAdapter()])

    with pytest.raises(DataViewerError) as exc_info:
        registry.select_adapter(path, cancellation=CancellationToken())

    assert gzip_adapter.probe(path, path.read_bytes()) is None
    assert exc_info.value.code is ErrorCode.SOURCE_UNSUPPORTED


def test_gzip_wrapper_rejects_corrupt_and_false_extension_inputs(tmp_path: Path) -> None:
    corrupt = tmp_path / "broken.json.gz"
    corrupt.write_bytes(b"\x1f\x8bnot really complete")
    false_extension = _write_gzip(tmp_path / "wrong.json.gz", b"time,value\n0,1\n")
    registry = create_source_registry()

    with pytest.raises(DataViewerError) as corrupt_error:
        registry.select_adapter(corrupt, cancellation=CancellationToken())
    with pytest.raises(DataViewerError) as false_extension_error:
        registry.select_adapter(false_extension, cancellation=CancellationToken())

    assert corrupt_error.value.code is ErrorCode.SOURCE_MALFORMED
    assert false_extension_error.value.code is ErrorCode.SOURCE_UNSUPPORTED


def test_gzip_wrapper_honors_cancellation_before_probe(tmp_path: Path) -> None:
    path = _write_gzip(tmp_path / "sample.txt.gz", b"hello")
    token = CancellationToken()
    token.cancel()

    with pytest.raises(DataViewerError) as exc_info:
        create_source_registry().select_adapter(path, cancellation=token)

    assert exc_info.value.code is ErrorCode.READ_CANCELLED
