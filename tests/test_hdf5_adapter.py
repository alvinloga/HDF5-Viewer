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


def test_hdf5_hierarchy_listing_is_paginated_and_direct(tmp_path: Path) -> None:
    path = tmp_path / "paged.h5"
    with h5py.File(path, "w") as source:
        source.create_dataset("array_a", data=[[1, 2], [3, 4]])
        source.create_dataset("array_b", data=[[5, 6], [7, 8]])
        group = source.create_group("group")
        group.create_dataset("inner", data=[1, 2, 3])
        group.create_dataset("inner_two", data=[4, 5, 6])

    registry = SourceRegistry([HDF5Adapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()

    first = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=2,
        cancellation=CancellationToken(),
    )
    second = session.list_children(
        root.resource_id,
        cursor=first.next_cursor,
        page_size=2,
        cancellation=CancellationToken(),
    )

    assert len(first.items) == 2
    assert first.next_cursor == "2"
    assert len(second.items) == 1
    assert second.next_cursor is None
    assert {item.name for item in first.items + second.items} == {
        "array_a",
        "array_b",
        "group",
    }

    direct_nodes = {item.name for item in session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    ).items}
    assert direct_nodes == {"array_a", "array_b", "group"}
    session.close()


def test_hdf5_metadata_captures_dataset_layout_fields(tmp_path: Path) -> None:
    import numpy as np

    path = tmp_path / "layout.h5"
    with h5py.File(path, "w") as source:
        source.create_dataset(
            "compressed",
            data=np.arange(12, dtype=np.int16).reshape(3, 4),
            chunks=(2, 2),
            compression="gzip",
            compression_opts=4,
            fillvalue=-1,
        )

    registry = SourceRegistry([HDF5Adapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    items = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=1,
        cancellation=CancellationToken(),
    ).items

    metadata = session.get_metadata(
        items[0].resource_id,
        cancellation=CancellationToken(),
    )
    layout = metadata.attributes["hdf5_layout"]

    assert metadata.domain is DataDomain.ARRAY
    assert layout["chunks"] == [2, 2]
    assert layout["compression"] == "gzip"
    assert layout["compression_opts"] == 4
    assert layout["fill_value"] == -1
    assert metadata.shape == (3, 4)
    session.close()


def test_hdf5_soft_and_external_links_are_explicit_and_broken_links_are_marked(
    tmp_path: Path,
) -> None:
    path = tmp_path / "links.h5"
    with h5py.File(path, "w") as source:
        source.create_dataset("matrix", data=[[1, 2], [3, 4]])
        source["soft_valid"] = h5py.SoftLink("/matrix")
        source["soft_missing"] = h5py.SoftLink("/no_such_node")
        source["external"] = h5py.ExternalLink("missing-target.h5", "/matrix")

    registry = SourceRegistry([HDF5Adapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    nodes = {item.name: item for item in session.list_children(
        root.resource_id,
        cursor=None,
        page_size=20,
        cancellation=CancellationToken(),
    ).items}

    assert nodes["soft_valid"].summary.startswith("soft link ->")
    assert nodes["soft_missing"].summary.startswith("broken soft link ->")
    assert nodes["external"].summary.startswith("external link ->")

    valid_metadata = session.get_metadata(
        nodes["soft_valid"].resource_id,
        cancellation=CancellationToken(),
    )
    missing_metadata = session.get_metadata(
        nodes["soft_missing"].resource_id,
        cancellation=CancellationToken(),
    )
    external_metadata = session.get_metadata(
        nodes["external"].resource_id,
        cancellation=CancellationToken(),
    )

    assert valid_metadata.domain is DataDomain.METADATA
    assert valid_metadata.attributes["link_type"] == "soft"
    assert valid_metadata.attributes["target_found"] is True
    assert missing_metadata.attributes["link_type"] == "soft"
    assert missing_metadata.attributes["target_found"] is False
    assert external_metadata.attributes["link_type"] == "external"
    assert external_metadata.attributes["link_filename"] == "missing-target.h5"
    assert external_metadata.attributes["link_path"] == "/matrix"
    assert external_metadata.attributes["target_found"] is False
    session.close()


def test_hdf5_soft_link_cycle_is_detected_as_broken_link(tmp_path: Path) -> None:
    path = tmp_path / "cycle.h5"
    with h5py.File(path, "w") as source:
        source["cycle"] = h5py.SoftLink("/cycle")

    registry = SourceRegistry([HDF5Adapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    cycle_resource = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    ).items[0]
    metadata = session.get_metadata(
        cycle_resource.resource_id,
        cancellation=CancellationToken(),
    )

    assert metadata.attributes["target_found"] is False
    session.close()


def test_hdf5_list_children_reads_only_direct_parent_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "direct.h5"
    with h5py.File(path, "w") as source:
        current = source
        for depth in range(40):
            current = current.create_group(f"lvl_{depth}")
            current.create_dataset(f"leaf_{depth}", data=[depth])

    original_keys = h5py._hl.group.Group.keys
    calls = {"count": 0}

    def counting_keys(self):
        calls["count"] += 1
        return original_keys(self)

    monkeypatch.setattr("h5py._hl.group.Group.keys", counting_keys)

    registry = SourceRegistry([HDF5Adapter()])
    session = registry.open(path, cancellation=CancellationToken())
    page_size = 5
    root = session.root()
    _ = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=page_size,
        cancellation=CancellationToken(),
    )

    assert calls["count"] <= 1 + page_size * 3
    session.close()
