"""NPZ adapter and archive-rebuild writer behavior for DataSource v1."""

from __future__ import annotations

import io
import zipfile
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
from data_viewer.sources.npz import NPZAdapter, NPZ_MAGIC_PREFIX, NPZSourceSession
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken
from tests.conformance.source_adapter import assert_source_adapter_conformance


def _npy_bytes(values: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, values, allow_pickle=True)
    return buffer.getvalue()


def _write_npz(path: Path, **arrays: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        cast(Any, np.savez)(handle, **arrays)
    return path


def _write_zip_npz(
    path: Path,
    entries: dict[str, np.ndarray],
    *,
    compression: int = zipfile.ZIP_STORED,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, values in entries.items():
            archive.writestr(name, _npy_bytes(values))
    return path


def _direct_children(session: source_api.SourceSession, parent: ResourceId) -> list[str]:
    page = session.list_children(
        parent,
        cursor=None,
        page_size=20,
        cancellation=CancellationToken(),
    )
    return [node.name for node in page.items]


def _resource_by_path(session: source_api.SourceSession, node_path: str) -> ResourceId:
    return ResourceId(session.source_uri, node_path)


class _TrackingSession:
    """Proxy that captures close-counting behavior for shared conformance tests."""

    def __init__(self, inner: NPZSourceSession) -> None:
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


class TrackingNPZAdapter:
    """Adapter wrapper used by shared conformance to verify close lifecycle."""

    adapter_id = "data-viewer.npz"
    api_version = source_api.DATASOURCE_API_VERSION
    extensions = (".npz",)

    def __init__(self) -> None:
        self._inner = NPZAdapter()
        self.last_session: _TrackingSession | None = None

    def probe(self, path: Path, header: bytes):
        return self._inner.probe(path, header)

    def open(self, path: Path, *, cancellation: source_api.CancellationToken):
        self.last_session = _TrackingSession(self._inner.open(path, cancellation=cancellation))
        return self.last_session


def test_npz_adapter_passes_shared_conformance(tmp_path: Path) -> None:
    path = _write_npz(tmp_path / "sample.npz", array=np.arange(6, dtype=np.int64).reshape(2, 3))
    adapter = TrackingNPZAdapter()
    registry = SourceRegistry([adapter])

    assert_source_adapter_conformance(registry, path, adapter)  # type: ignore[arg-type]

    session = registry.open(path, cancellation=CancellationToken())
    if adapter.last_session is None:
        raise AssertionError("Adapter did not create a session")

    resource = _resource_by_path(session, "/array")
    metadata = session.get_metadata(resource, cancellation=CancellationToken())

    assert metadata.domain is DataDomain.ARRAY
    assert metadata.node_kind is NodeKind.RESOURCE
    assert metadata.shape == (2, 3)
    assert metadata.dtype == "int64"
    assert metadata.attributes["archive_member"] == "array.npy"
    assert SourceFingerprint.from_json(metadata.attributes["source_fingerprint"])  # type: ignore[arg-type]
    session.close()
    session.close()
    assert adapter.last_session.close_count == 1


def test_npz_probe_is_signature_and_extension_gated(tmp_path: Path) -> None:
    valid = _write_npz(tmp_path / "valid.npz", array=np.arange(3))
    wrong_extension = _write_npz(tmp_path / "wrong.zip", array=np.arange(3))
    malformed = tmp_path / "malformed.npz"
    malformed.write_bytes(b"not-a-zip")

    adapter = NPZAdapter()

    assert adapter.probe(valid, header=NPZ_MAGIC_PREFIX + b"\x04") is not None
    assert adapter.probe(wrong_extension, header=NPZ_MAGIC_PREFIX + b"\x04") is None
    assert adapter.probe(malformed, header=malformed.read_bytes()) is None


def test_npz_builds_synthetic_member_hierarchy_and_reads_selection(tmp_path: Path) -> None:
    path = _write_zip_npz(
        tmp_path / "hierarchy.npz",
        {
            "group/a.npy": np.arange(12, dtype=np.int16).reshape(3, 4),
            "group/sub/b.npy": np.arange(5, dtype=np.float32),
            "root.npy": np.array(7, dtype=np.int8),
        },
    )
    session = NPZAdapter().open(path, cancellation=CancellationToken())
    root = session.root()
    group = _resource_by_path(session, "/group")
    array = _resource_by_path(session, "/group/a")

    assert _direct_children(session, root.resource_id) == ["group", "root"]
    assert _direct_children(session, group) == ["a", "sub"]

    metadata = session.get_metadata(array, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(
            resource_id=array,
            selection=SelectionSpec.hyperslab(
                AxisSelection.slice(0, start=1, stop=3),
                AxisSelection.slice(1, start=0, stop=4, step=2),
            ),
            max_bytes=1024,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.shape == (3, 4)
    assert metadata.attributes["archive_member"] == "group/a.npy"
    assert result.scope is OperationScope.SLICE
    assert isinstance(result.payload, ArrayPayload)
    assert result.payload.values.tolist() == [[4, 6], [8, 10]]
    session.close()


def test_npz_rejects_object_arrays_without_pickle_deserialization(tmp_path: Path) -> None:
    path = _write_zip_npz(
        tmp_path / "object.npz",
        {"unsafe.npy": np.array([{"unsafe": "object"}], dtype=object)},
    )

    with pytest.raises(DataViewerError) as error:
        NPZAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_MALFORMED
    assert error.value.details["allow_pickle"] is False


@pytest.mark.parametrize(
    ("member_name", "expected_code"),
    [
        ("../escape.npy", ErrorCode.SOURCE_MALFORMED),
        ("/absolute.npy", ErrorCode.SOURCE_MALFORMED),
    ],
)
def test_npz_rejects_unsafe_member_names(
    tmp_path: Path,
    member_name: str,
    expected_code: ErrorCode,
) -> None:
    path = _write_zip_npz(tmp_path / "unsafe.npz", {member_name: np.arange(3)})

    with pytest.raises(DataViewerError) as error:
        NPZAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is expected_code
    assert error.value.details["archive_member"] == member_name


def test_npz_rejects_duplicate_normalized_member_paths(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.npz"
    values = np.arange(3)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.npy", _npy_bytes(values))
        archive.writestr("./a.npy", _npy_bytes(values + 1))

    with pytest.raises(DataViewerError) as error:
        NPZAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_MALFORMED
    assert error.value.details["node_path"] == "/a"


def test_npz_rejects_zip_encryption_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_npz(tmp_path / "encrypted.npz", array=np.arange(3))
    class EncryptedInfoZipFile(zipfile.ZipFile):
        def infolist(self):  # type: ignore[override]
            infos = super().infolist()
            for info in infos:
                info.flag_bits |= 0x1
            return infos

    monkeypatch.setattr("data_viewer.sources.npz.session.zipfile.ZipFile", EncryptedInfoZipFile)

    with pytest.raises(DataViewerError) as error:
        NPZAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_ENCRYPTED


def test_npz_rejects_member_size_and_compression_ratio_budgets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oversized = _write_npz(tmp_path / "oversized.npz", array=np.arange(12, dtype=np.int64))
    monkeypatch.setattr("data_viewer.sources.npz.session.MAX_MEMBER_UNCOMPRESSED_BYTES", 8)

    with pytest.raises(DataViewerError) as size_error:
        NPZAdapter().open(oversized, cancellation=CancellationToken())

    assert size_error.value.code is ErrorCode.BUDGET_EXCEEDED

    monkeypatch.setattr("data_viewer.sources.npz.session.MAX_MEMBER_UNCOMPRESSED_BYTES", 1_000_000)
    monkeypatch.setattr("data_viewer.sources.npz.session.MAX_COMPRESSION_RATIO", 2)
    compressed = _write_zip_npz(
        tmp_path / "ratio.npz",
        {"zeros.npy": np.zeros(10_000, dtype=np.uint8)},
        compression=zipfile.ZIP_DEFLATED,
    )

    with pytest.raises(DataViewerError) as ratio_error:
        NPZAdapter().open(compressed, cancellation=CancellationToken())

    assert ratio_error.value.code is ErrorCode.BUDGET_EXCEEDED
    assert ratio_error.value.details["budget"] == "compression_ratio"


def test_npz_edit_rebuilds_archive_and_preserves_unaffected_member_semantics(
    tmp_path: Path,
) -> None:
    path = _write_npz(
        tmp_path / "editable.npz",
        first=np.arange(6, dtype=np.int64).reshape(2, 3),
        second=np.array([10, 20, 30], dtype=np.int16),
        third=np.array([100, 200], dtype=np.int32),
    )
    session = NPZAdapter().open(path, cancellation=CancellationToken())
    first = _resource_by_path(session, "/first")
    second = _resource_by_path(session, "/second")
    third = _resource_by_path(session, "/third")
    first_patch = CellPatch(
        resource_id=first,
        coordinate=(1, 2),
        old_value_fingerprint=fingerprint_value(5),
        new_value=99,
    )
    second_patch = CellPatch(
        resource_id=second,
        coordinate=(0,),
        old_value_fingerprint=fingerprint_value(10),
        new_value=11,
    )
    result = session.apply_change_set(
        ChangeSet(source_fingerprint=session.fingerprint).with_patches(
            first_patch,
            second_patch,
        ),
        cancellation=CancellationToken(),
    )

    assert result.strategy is SaveStrategy.REPLACEMENT
    assert result.changed_coordinates == 2
    assert "rebuilt" in " ".join(result.warnings).lower()

    reopened = NPZAdapter().open(path, cancellation=CancellationToken())
    changed = reopened.read(
        ReadRequest(resource_id=first, max_bytes=1024),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    also_changed = reopened.read(
        ReadRequest(resource_id=second, max_bytes=1024),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    untouched = reopened.read(
        ReadRequest(resource_id=third, max_bytes=1024),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert isinstance(changed.payload, ArrayPayload)
    assert isinstance(also_changed.payload, ArrayPayload)
    assert isinstance(untouched.payload, ArrayPayload)
    assert changed.payload.values.tolist() == [[0, 1, 2], [3, 4, 99]]
    assert also_changed.payload.values.tolist() == [11, 20, 30]
    assert untouched.payload.values.tolist() == [100, 200]
    session.close()
    reopened.close()


def test_npz_edit_fault_leaves_original_archive_unchanged(tmp_path: Path) -> None:
    path = _write_npz(tmp_path / "fault.npz", first=np.arange(4, dtype=np.int64))
    original_bytes = path.read_bytes()
    session = NPZAdapter().open(path, cancellation=CancellationToken())
    first = _resource_by_path(session, "/first")
    patch = CellPatch(
        resource_id=first,
        coordinate=(2,),
        old_value_fingerprint=fingerprint_value(2),
        new_value=123,
    )

    with pytest.raises(RuntimeError, match="injected failure"):
        session.apply_change_set(
            ChangeSet(source_fingerprint=session.fingerprint).with_patch(patch),
            cancellation=CancellationToken(),
            failure_injector=lambda _stage: (_ for _ in ()).throw(RuntimeError("injected failure")),
        )

    assert path.read_bytes() == original_bytes
    session.close()
