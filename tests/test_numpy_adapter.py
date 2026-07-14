"""NPY adapter and writer behavior for DataSource v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from data_viewer.domain import (
    ArrayPayload,
    AxisSelection,
    DataDomain,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ResourceId,
    SelectionSpec,
    SourceFingerprint,
)
from data_viewer.editing import CellPatch, ChangeSet, fingerprint_value
from data_viewer.editing.review import SaveStrategy
from data_viewer.sources import api as source_api
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.numpy import NPYAdapter, NPY_MAGIC_PREFIX, NPYSourceSession
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken
from tests.conformance.source_adapter import assert_source_adapter_conformance
from tests.conformance.source_adapter import FAKE_HEADER


def _write_npy(path: Path, values: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, values, allow_pickle=False)
    return path


def _array_resource(session: source_api.SourceSession) -> ResourceId:
    root = session.root()
    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    assert len(page.items) == 1
    return page.items[0].resource_id


class _TrackingSession:
    """Proxy that captures close-counting behavior for shared conformance tests."""

    def __init__(self, inner: NPYSourceSession) -> None:
        self._inner = inner
        self.close_count = 0
        self._is_closed = False

    @property
    def source_uri(self) -> str:
        return self._inner.source_uri

    @property
    def fingerprint(self):
        return self._inner.fingerprint

    @property
    def capabilities(self):
        return self._inner.capabilities

    def root(self):
        return self._inner.root()

    def list_children(
        self,
        parent,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: source_api.CancellationToken,
    ):
        return self._inner.list_children(
            parent,
            cursor=cursor,
            page_size=page_size,
            cancellation=cancellation,
        )

    def get_metadata(self, resource, *, cancellation: source_api.CancellationToken):
        return self._inner.get_metadata(resource, cancellation=cancellation)

    def read(
        self,
        request,
        *,
        cancellation: source_api.CancellationToken,
        progress,
    ):
        return self._inner.read(
            request,
            cancellation=cancellation,
            progress=progress,
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: source_api.CancellationToken,
    ):
        return self._inner.search(
            query,
            cursor=cursor,
            page_size=page_size,
            cancellation=cancellation,
        )

    def refresh_fingerprint(self):
        return self._inner.refresh_fingerprint()

    def apply_change_set(self, changeset, *, cancellation):
        return self._inner.apply_change_set(changeset, cancellation=cancellation)

    def close(self) -> None:
        if self._is_closed:
            return
        self._is_closed = True
        self.close_count += 1
        self._inner.close()


class TrackingNPYAdapter:
    """Adapter wrapper used by shared conformance to verify close lifecycle."""

    adapter_id = "data-viewer.npy"
    api_version = source_api.DATASOURCE_API_VERSION
    extensions = (".npy",)

    def __init__(self) -> None:
        self._inner = NPYAdapter()
        self.last_session: _TrackingSession | None = None

    def probe(self, path: Path, header: bytes):
        return self._inner.probe(path, header)

    def open(self, path: Path, *, cancellation: source_api.CancellationToken):
        self.last_session = _TrackingSession(self._inner.open(path, cancellation=cancellation))
        return self.last_session


def test_npy_adapter_passes_shared_conformance(tmp_path: Path) -> None:
    path = _write_npy(tmp_path / "sample.npy", np.arange(6, dtype=np.int64).reshape(2, 3))
    adapter = TrackingNPYAdapter()
    registry = SourceRegistry([adapter])

    assert_source_adapter_conformance(registry, path, adapter)  # type: ignore[arg-type]

    session = registry.open(path, cancellation=CancellationToken())
    if adapter.last_session is None:
        raise AssertionError("Adapter did not create a session")

    resource = _array_resource(session)
    metadata = session.get_metadata(resource, cancellation=CancellationToken())

    assert metadata.domain is DataDomain.ARRAY
    assert metadata.node_kind is NodeKind.RESOURCE
    assert metadata.shape == (2, 3)
    assert metadata.dtype == "int64"
    fingerprint_value_json = metadata.attributes["source_fingerprint"]
    assert isinstance(fingerprint_value_json, dict)
    assert SourceFingerprint.from_json(fingerprint_value_json)
    session.close()
    session.close()
    assert adapter.last_session.close_count == 1


def test_npy_probe_is_signature_and_extension_gated(tmp_path: Path) -> None:
    valid = _write_npy(tmp_path / "valid.npy", np.arange(3))
    wrong_extension = _write_npy(tmp_path / "wrong.txt", np.arange(3))
    malformed = tmp_path / "malformed.npy"
    malformed.write_bytes(FAKE_HEADER + b"not-npy")

    adapter = NPYAdapter()

    assert adapter.probe(valid, header=NPY_MAGIC_PREFIX + b"\x01\x00") is not None
    assert adapter.probe(wrong_extension, header=NPY_MAGIC_PREFIX + b"\x01\x00") is None
    assert adapter.probe(malformed, header=malformed.read_bytes()) is None


def test_npy_open_object_array_rejects_pickle_deserialization(tmp_path: Path) -> None:
    path = tmp_path / "object.npy"
    np.save(path, np.array([{"unsafe": "object"}], dtype=object), allow_pickle=True)

    with pytest.raises(DataViewerError) as error:
        NPYAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_MALFORMED
    assert error.value.details["allow_pickle"] is False


def test_npy_reads_scalar_empty_order_byte_order_and_structured_dtype(
    tmp_path: Path,
) -> None:
    cases: list[tuple[str, np.ndarray, tuple[int, ...], Any]] = [
        ("scalar", np.array(42, dtype=np.dtype(">i2")), (), 42),
        ("empty", np.empty((0, 3), dtype=np.float32), (0, 3), []),
        ("fortran", np.asfortranarray(np.arange(6, dtype=np.int16).reshape(2, 3)), (2, 3), [[0, 1, 2], [3, 4, 5]]),
        (
            "structured",
            np.array([(1, 1.5), (2, 2.5)], dtype=[("id", ">i4"), ("value", "<f8")]),
            (2,),
            None,
        ),
    ]

    for name, values, expected_shape, expected_list in cases:
        path = _write_npy(tmp_path / f"{name}.npy", values)
        session = NPYAdapter().open(path, cancellation=CancellationToken())
        resource = _array_resource(session)
        metadata = session.get_metadata(resource, cancellation=CancellationToken())
        result = session.read(
            ReadRequest(resource_id=resource, max_bytes=1024),
            cancellation=CancellationToken(),
            progress=lambda _done, _total, _message: None,
        )

        assert result.scope is OperationScope.SLICE
        assert isinstance(result.payload, ArrayPayload)
        assert result.payload.values.shape == expected_shape
        assert result.payload.values.dtype == values.dtype
        assert metadata.attributes["fortran_order"] is bool(values.flags.f_contiguous and not values.flags.c_contiguous)
        assert metadata.attributes["byte_order"] == values.dtype.byteorder
        if expected_list is not None:
            assert result.payload.values.tolist() == expected_list
        else:
            assert result.payload.values.dtype.fields is not None
            assert cast(Any, result.payload.values)["id"].tolist() == [1, 2]
        session.close()


def test_npy_read_uses_normalized_selection_and_budget(tmp_path: Path) -> None:
    path = _write_npy(tmp_path / "matrix.npy", np.arange(18, dtype=np.int8).reshape(3, 6))
    session = NPYAdapter().open(path, cancellation=CancellationToken())
    resource = _array_resource(session)
    selection = SelectionSpec.hyperslab(
        AxisSelection.slice(0, start=1, stop=3),
        AxisSelection.slice(1, start=1, stop=5, step=2),
    )

    result = session.read(
        ReadRequest(resource_id=resource, selection=selection, max_bytes=1024),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert isinstance(result.payload, ArrayPayload)
    assert result.payload.values.tolist() == [[7, 9], [13, 15]]
    assert result.payload.source_coordinates((1, 1)) == (2, 3)

    with pytest.raises(DataViewerError) as error:
        session.read(
            ReadRequest(resource_id=resource, selection=selection, max_bytes=1),
            cancellation=CancellationToken(),
            progress=lambda _done, _total, _message: None,
        )
    assert error.value.code is ErrorCode.BUDGET_EXCEEDED
    session.close()


def test_npy_apply_cell_patch_uses_verified_replacement_and_preserves_layout(
    tmp_path: Path,
) -> None:
    values = np.asfortranarray(np.arange(6, dtype=np.dtype(">i2")).reshape(2, 3))
    path = _write_npy(tmp_path / "editable.npy", values)
    session = NPYAdapter().open(path, cancellation=CancellationToken())
    resource = _array_resource(session)
    changeset = ChangeSet(
        source_fingerprint=session.fingerprint,
        patches=(
            CellPatch(
                resource_id=resource,
                coordinate=(1, 2),
                old_value_fingerprint=fingerprint_value(5),
                new_value=55,
            ),
        ),
    )

    result = session.apply_change_set(changeset, cancellation=CancellationToken())

    assert result.strategy is SaveStrategy.REPLACEMENT
    assert result.changed_coordinates == 1
    reopened = np.load(path, allow_pickle=False, mmap_mode="r")
    assert reopened.dtype == values.dtype
    assert reopened.flags.f_contiguous
    assert reopened.tolist() == [[0, 1, 2], [3, 4, 55]]
    read_back = session.read(
        ReadRequest(resource_id=resource, max_bytes=1024),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    assert isinstance(read_back.payload, ArrayPayload)
    assert read_back.payload.values.tolist() == [[0, 1, 2], [3, 4, 55]]
    session.close()


def test_npy_apply_changeset_rejects_stale_source_fingerprint(tmp_path: Path) -> None:
    path = _write_npy(tmp_path / "stale.npy", np.arange(3, dtype=np.int64))
    session = NPYAdapter().open(path, cancellation=CancellationToken())
    resource = _array_resource(session)
    changeset = ChangeSet(
        source_fingerprint=SourceFingerprint(size_bytes=0, modified_time_ns=0),
        patches=(CellPatch(resource, (0,), fingerprint_value(0), 99),),
    )

    with pytest.raises(DataViewerError) as error:
        session.apply_change_set(changeset, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_CHANGED
    assert np.load(path, allow_pickle=False).tolist() == [0, 1, 2]
    session.close()
