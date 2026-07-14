"""MATLAB MAT adapter behavior for DataSource v1."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest
import scipy.io
import scipy.sparse as sp

from data_viewer.domain import (
    ArrayPayload,
    DataDomain,
    DataViewerError,
    ErrorCode,
    OperationScope,
    ResourceId,
    SourceCapability,
    StructuredPayload,
    TextPayload,
)
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.mat import MATAdapter, MATSourceSession
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken


def _write_legacy_mat(path: Path) -> Path:
    cell = np.empty((1, 2), dtype=object)
    cell[0, 0] = np.array([[1, 2]], dtype=np.int64)
    cell[0, 1] = "hi"
    scipy.io.savemat(
        path,
        {
            "numeric": np.arange(6, dtype=np.float64).reshape(2, 3),
            "logical": np.array([[True, False]]),
            "chars": "hello",
            "complexv": np.array([[1 + 2j, 3 + 0j]], dtype=np.complex128),
            "sparsev": sp.csc_matrix([[1, 0], [0, 2]], dtype=np.int64),
            "cellv": cell,
            "structv": {"field": np.array([[3, 4]], dtype=np.int64), "name": "bob"},
        },
        do_compression=False,
    )
    return path


def _write_v73_like_mat(path: Path) -> Path:
    with h5py.File(path, "w") as handle:
        handle.attrs["MATLAB_version"] = "7.3"
        numeric = handle.create_dataset("numeric", data=np.arange(4).reshape(2, 2))
        numeric.attrs["MATLAB_class"] = "double"
        logical = handle.create_dataset("logical", data=np.array([[1, 0]], dtype=np.uint8))
        logical.attrs["MATLAB_class"] = "logical"
        chars = handle.create_dataset("chars", data=np.array([ord("o"), ord("k")], dtype=np.uint16))
        chars.attrs["MATLAB_class"] = "char"
        group = handle.create_group("nested")
        group.attrs["MATLAB_class"] = "struct"
        child = group.create_dataset("value", data=np.array([[9]], dtype=np.int64))
        child.attrs["MATLAB_class"] = "int64"
        group["self"] = group
    return path


def test_mat_adapter_opens_legacy_mat_variables_with_explicit_types(tmp_path: Path) -> None:
    path = _write_legacy_mat(tmp_path / "legacy.mat")
    registry = SourceRegistry([MATAdapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=20,
        cancellation=CancellationToken(),
    )

    assert root.domain is DataDomain.HIERARCHICAL_ARRAY
    assert [item.resource_id.node_path for item in page.items] == [
        "/cellv",
        "/chars",
        "/complexv",
        "/logical",
        "/numeric",
        "/sparsev",
        "/structv",
    ]
    root_metadata = session.get_metadata(root.resource_id, cancellation=CancellationToken())
    numeric_metadata = session.get_metadata(
        ResourceId(session.source_uri, "/numeric"),
        cancellation=CancellationToken(),
    )
    char_metadata = session.get_metadata(
        ResourceId(session.source_uri, "/chars"),
        cancellation=CancellationToken(),
    )
    sparse_metadata = session.get_metadata(
        ResourceId(session.source_uri, "/sparsev"),
        cancellation=CancellationToken(),
    )

    assert root_metadata.attributes["mat_version_family"] == "legacy"
    assert root_metadata.attributes["hidden_internal_keys"] == [
        "__globals__",
        "__header__",
        "__version__",
    ]
    assert numeric_metadata.domain is DataDomain.ARRAY
    assert numeric_metadata.shape == (2, 3)
    assert numeric_metadata.attributes["matlab_class"] == "double"
    assert SourceCapability.EDIT_PATCH not in numeric_metadata.capabilities
    assert SourceCapability.ATOMIC_REWRITE not in numeric_metadata.capabilities
    assert char_metadata.domain is DataDomain.TEXT
    assert char_metadata.attributes["matlab_class"] == "char"
    assert sparse_metadata.domain is DataDomain.STRUCTURED
    assert sparse_metadata.attributes["matlab_class"] == "sparse"
    assert sparse_metadata.attributes["nnz"] == 2
    session.close()


def test_mat_reads_arrays_text_sparse_cells_and_struct_fields(tmp_path: Path) -> None:
    path = _write_legacy_mat(tmp_path / "payloads.mat")
    session = MATAdapter().open(path, cancellation=CancellationToken())
    numeric_result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/numeric"),
            scope=OperationScope.SLICE,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    text_result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/chars"),
            scope=OperationScope.FULL,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    sparse_result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/sparsev"),
            scope=OperationScope.FULL,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    cell_page = session.list_children(
        ResourceId(session.source_uri, "/cellv"),
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    struct_page = session.list_children(
        ResourceId(session.source_uri, "/structv/0,0"),
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    field_result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/structv/0,0/field"),
            scope=OperationScope.SLICE,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert isinstance(numeric_result.payload, ArrayPayload)
    np.testing.assert_array_equal(
        numeric_result.payload.values,
        np.arange(6, dtype=np.float64).reshape(2, 3),
    )
    assert isinstance(text_result.payload, TextPayload)
    assert text_result.payload.text == "hello"
    assert isinstance(sparse_result.payload, StructuredPayload)
    assert sparse_result.payload.value == {
        "matlab_class": "sparse",
        "shape": [2, 2],
        "nnz": 2,
        "format": "csc",
        "dtype": "int64",
    }
    assert [item.resource_id.node_path for item in cell_page.items] == [
        "/cellv/0,0",
        "/cellv/0,1",
    ]
    assert sorted(item.name for item in struct_page.items) == ["field", "name"]
    assert isinstance(field_result.payload, ArrayPayload)
    np.testing.assert_array_equal(field_result.payload.values, np.array([[3, 4]], dtype=np.int64))
    session.close()


def test_mat_adapter_detects_hdf5_v73_and_bounds_cycles(tmp_path: Path) -> None:
    path = _write_v73_like_mat(tmp_path / "v73.mat")
    session = MATAdapter().open(path, cancellation=CancellationToken())
    root = session.root()
    metadata = session.get_metadata(root.resource_id, cancellation=CancellationToken())
    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=20,
        cancellation=CancellationToken(),
    )
    nested_page = session.list_children(
        ResourceId(session.source_uri, "/nested"),
        cursor=None,
        page_size=20,
        cancellation=CancellationToken(),
    )
    search = session.search(
        "value",
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    text_result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/chars"),
            scope=OperationScope.FULL,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.attributes["mat_version_family"] == "v7.3"
    assert [item.resource_id.node_path for item in page.items] == [
        "/chars",
        "/logical",
        "/nested",
        "/numeric",
    ]
    assert any(item.resource_id.node_path == "/nested/self" for item in nested_page.items)
    assert [item.resource_id.node_path for item in search.items] == ["/nested/value"]
    assert isinstance(text_result.payload, TextPayload)
    assert text_result.payload.text == "ok"
    session.close()


def test_mat_rejects_wrong_extension_malformed_budget_and_closed_session(
    tmp_path: Path,
) -> None:
    wrong = tmp_path / "sample.bin"
    wrong.write_bytes(b"MATLAB 5.0 MAT-file")
    malformed = tmp_path / "bad.mat"
    malformed.write_bytes(b"not a mat file")
    path = _write_legacy_mat(tmp_path / "budget.mat")

    assert MATAdapter().probe(wrong, wrong.read_bytes()) is None

    with pytest.raises(DataViewerError) as malformed_error:
        MATAdapter().open(malformed, cancellation=CancellationToken())
    assert malformed_error.value.code is ErrorCode.SOURCE_MALFORMED

    with pytest.raises(DataViewerError) as budget_error:
        MATSourceSession(path, max_legacy_variables=1)
    assert budget_error.value.code is ErrorCode.BUDGET_EXCEEDED

    session = MATAdapter().open(path, cancellation=CancellationToken())
    session.close()
    with pytest.raises(DataViewerError) as closed_error:
        session.root()
    assert closed_error.value.code is ErrorCode.SOURCE_CLOSED
