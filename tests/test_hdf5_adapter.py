"""HDF5 adapter and session behavior for DataSource conformance and lifecycle."""

from __future__ import annotations

from pathlib import Path
import h5py
import pytest

from data_viewer.domain import DataViewerError, DataDomain, ErrorCode, NodeKind, OperationScope
from data_viewer.sources import api as source_api
from data_viewer.sources.hdf5 import HDF5Adapter, HDF5_SIGNATURE, HDF5SourceSession
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken
from tests.conformance.source_adapter import assert_source_adapter_conformance
from tests.conformance.source_adapter import FAKE_HEADER
from tests.fixtures import create_hdf5
from data_viewer.sources.api import ReadRequest


def _write_simple_hdf5(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as source:
        source.create_dataset("array", data=[[1, 2, 3], [4, 5, 6]])
    return path


class _TrackingSession:
    """Proxy that captures close-counting behavior for shared conformance tests."""

    def __init__(self, inner: HDF5SourceSession) -> None:
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

    def close(self) -> None:
        if self._is_closed:
            return
        self._is_closed = True
        self.close_count += 1
        self._inner.close()


class TrackingHDF5Adapter:
    """Adapter wrapper used by shared conformance to verify close lifecycle."""

    adapter_id = "data-viewer.hdf5"
    api_version = source_api.DATASOURCE_API_VERSION
    extensions = (".h5", ".hdf5", ".hdf", ".h5py")

    def __init__(self) -> None:
        self._inner = HDF5Adapter()
        self.last_session: _TrackingSession | None = None

    def probe(self, path: Path, header: bytes):
        return self._inner.probe(path, header)

    def open(self, path: Path, *, cancellation: source_api.CancellationToken):
        self.last_session = _TrackingSession(self._inner.open(path, cancellation=cancellation))
        return self.last_session


def test_hdf5_adapter_passes_shared_conformance(tmp_path: Path) -> None:
    path = _write_simple_hdf5(tmp_path / "sample.h5")
    adapter = TrackingHDF5Adapter()
    registry = SourceRegistry([adapter])

    assert_source_adapter_conformance(registry, path, adapter)

    session = registry.open(path, cancellation=CancellationToken())
    if adapter.last_session is None:
        raise AssertionError("Adapter did not create a session")

    root = session.root()
    first_page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    dataset = first_page.items[0].resource_id
    metadata = session.get_metadata(dataset, cancellation=CancellationToken())

    assert metadata.domain is DataDomain.ARRAY
    assert metadata.node_kind is NodeKind.RESOURCE
    assert metadata.shape == (2, 3)
    assert metadata.dtype == "int64"
    session.close()
    session.close()
    assert adapter.last_session.close_count == 1


def test_hdf5_probe_is_signature_gated(tmp_path: Path) -> None:
    valid = create_hdf5(tmp_path / "valid.h5").path
    malformed = create_hdf5(tmp_path / "malformed.txt")
    malformed.path.write_bytes(FAKE_HEADER + b"not-hdf5")

    assert HDF5Adapter().probe(valid, header=HDF5_SIGNATURE) is not None
    assert HDF5Adapter().probe(malformed.path, header=b"not-signature") is None


def test_hdf5_wrong_extension_is_rejected_by_registry(tmp_path: Path) -> None:
    path = create_hdf5(tmp_path / "wrong_ext.txt").path
    registry = SourceRegistry([HDF5Adapter()])

    with pytest.raises(DataViewerError) as error:
        registry.select_adapter(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_UNSUPPORTED


def test_hdf5_malformed_source_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "malformed.h5"
    path.write_bytes(b"this is not an HDF5 file")
    registry = SourceRegistry([HDF5Adapter()])

    with pytest.raises(DataViewerError) as select_error:
        registry.select_adapter(path, cancellation=CancellationToken())
    assert select_error.value.code is ErrorCode.SOURCE_UNSUPPORTED

    with pytest.raises(DataViewerError) as open_error:
        HDF5Adapter().open(path, cancellation=CancellationToken())
    assert open_error.value.code is ErrorCode.SOURCE_MALFORMED


def test_hdf5_open_locked_file_reports_open_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = create_hdf5(tmp_path / "locked.h5").path

    def raise_permission_error(*_args, **_kwargs) -> None:
        raise PermissionError("locked")

    monkeypatch.setattr(
        "data_viewer.sources.hdf5.session.h5py.File",
        raise_permission_error,
    )

    with pytest.raises(DataViewerError) as error:
        HDF5Adapter().open(path, cancellation=CancellationToken())
    assert error.value.code is ErrorCode.SOURCE_OPEN_FAILED


def test_hdf5_missing_file_rejected(tmp_path: Path) -> None:
    path = tmp_path / "missing.h5"
    registry = SourceRegistry([HDF5Adapter()])

    with pytest.raises(DataViewerError) as error:
        registry.open(path, cancellation=CancellationToken())
    assert error.value.code is ErrorCode.SOURCE_OPEN_FAILED


def test_hdf5_unicode_path_open_and_read(tmp_path: Path) -> None:
    path = create_hdf5(tmp_path / "包含中文" / "样本.h5").path
    registry = SourceRegistry([HDF5Adapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )

    dataset = page.items[0].resource_id
    result = session.read(
        ReadRequest(resource_id=dataset, max_bytes=1024),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    assert result.scope is OperationScope.SLICE
    assert result.payload.values.shape == (2, 3)
    assert result.payload.source_coordinates((1, 2)) == (1, 2)

    session.close()


def test_hdf5_open_and_close_is_stable_under_repetition(tmp_path: Path) -> None:
    path = create_hdf5(tmp_path / "stress.h5").path
    registry = SourceRegistry([HDF5Adapter()])
    token = CancellationToken()

    for _ in range(20):
        session = registry.open(path, cancellation=token)
        session.close()
        session.close()
        with pytest.raises(DataViewerError):
            session.root()
