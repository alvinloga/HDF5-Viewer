"""Managed extraction cache for random-access gzip source wrappers."""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pytest

from data_viewer.domain import DataViewerError, ErrorCode, OperationScope, ResourceId
from data_viewer.domain.payload import ArrayPayload
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.gzip import GzipAdapter
from data_viewer.sources.gzip.cache import ExtractionLimits, ManagedExtractionCache
from data_viewer.sources.numpy import NPYAdapter
from data_viewer.tasks import CancellationToken


def _write_npy_gzip(path: Path, values: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_path = path.with_suffix("")
    np.save(raw_path, values)
    with raw_path.open("rb") as source, gzip.open(path, "wb") as target:
        target.write(source.read())
    raw_path.unlink()
    return path


def _array_resource(session) -> ResourceId:
    page = session.list_children(
        session.root().resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    assert len(page.items) == 1
    return page.items[0].resource_id


def test_random_access_npy_gzip_extracts_to_managed_cache_and_preserves_identity(
    tmp_path: Path,
) -> None:
    source = _write_npy_gzip(
        tmp_path / "array.npy.gz",
        np.arange(12, dtype=np.int16).reshape(3, 4),
    )
    cache = ManagedExtractionCache(tmp_path / "cache")
    adapter = GzipAdapter([NPYAdapter()], extraction_cache=cache)

    session = adapter.open(source, cancellation=CancellationToken())
    resource = _array_resource(session)
    metadata = session.get_metadata(resource, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(resource_id=resource, scope=OperationScope.SLICE),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert resource.source_uri == source.resolve(strict=False).as_uri()
    assert metadata.attributes["gzip_wrapped"] is True
    assert metadata.attributes["gzip_access"] == "managed_random_access_cache"
    assert metadata.attributes["inner_adapter_id"] == "data-viewer.npy"
    assert metadata.attributes["gzip_cache_hit"] is False
    assert isinstance(result.payload, ArrayPayload)
    assert result.payload.values.tolist() == np.arange(12, dtype=np.int16).reshape(3, 4).tolist()
    assert "read-only gzip" in result.warnings[-1].lower()
    assert cache.entry_count == 1
    extracted_path = cache.cached_path_for(source)
    assert extracted_path is not None
    assert extracted_path.exists()

    session.close()
    assert extracted_path.exists()


def test_random_access_npy_gzip_probe_uses_decompressed_prefix(tmp_path: Path) -> None:
    source = _write_npy_gzip(tmp_path / "array.npy.gz", np.arange(4, dtype=np.int16))
    adapter = GzipAdapter([NPYAdapter()], extraction_cache=ManagedExtractionCache(tmp_path / "cache"))

    probe = adapter.probe(source, source.read_bytes()[:64])

    assert probe is not None
    assert probe.adapter_id == "data-viewer.gzip"
    assert probe.detected_format == "gzip(NPY)"


def test_random_access_cache_reuses_same_fingerprint_and_invalidates_changed_source(
    tmp_path: Path,
) -> None:
    source = _write_npy_gzip(tmp_path / "array.npy.gz", np.arange(3, dtype=np.int16))
    cache = ManagedExtractionCache(tmp_path / "cache")
    adapter = GzipAdapter([NPYAdapter()], extraction_cache=cache)

    first = adapter.open(source, cancellation=CancellationToken())
    first_resource = _array_resource(first)
    first_metadata = first.get_metadata(first_resource, cancellation=CancellationToken())
    first_cached = cache.cached_path_for(source)
    first.close()

    second = adapter.open(source, cancellation=CancellationToken())
    second_resource = _array_resource(second)
    second_metadata = second.get_metadata(second_resource, cancellation=CancellationToken())
    second_cached = cache.cached_path_for(source)
    second.close()

    _write_npy_gzip(source, np.arange(4, dtype=np.int16))
    third = adapter.open(source, cancellation=CancellationToken())
    third_cached = cache.cached_path_for(source)
    third.close()

    assert first_metadata.attributes["gzip_cache_hit"] is False
    assert second_metadata.attributes["gzip_cache_hit"] is True
    assert first_cached == second_cached
    assert third_cached != first_cached


def test_extraction_budget_and_ratio_fail_before_cache_entry_is_committed(
    tmp_path: Path,
) -> None:
    source = _write_npy_gzip(tmp_path / "large.npy.gz", np.arange(1024, dtype=np.int16))
    cache = ManagedExtractionCache(
        tmp_path / "cache",
        limits=ExtractionLimits(max_decompressed_bytes=128, max_compression_ratio=1.1),
    )
    adapter = GzipAdapter([NPYAdapter()], extraction_cache=cache)

    with pytest.raises(DataViewerError) as exc_info:
        adapter.open(source, cancellation=CancellationToken())

    assert exc_info.value.code is ErrorCode.BUDGET_EXCEEDED
    assert cache.entry_count == 0
    assert list((tmp_path / "cache").glob("*.incomplete")) == []


def test_extraction_cancellation_removes_incomplete_file(tmp_path: Path) -> None:
    source = _write_npy_gzip(tmp_path / "array.npy.gz", np.arange(256, dtype=np.int16))
    cache = ManagedExtractionCache(tmp_path / "cache")
    adapter = GzipAdapter([NPYAdapter()], extraction_cache=cache)
    token = CancellationToken()
    token.cancel()

    with pytest.raises(DataViewerError) as exc_info:
        adapter.open(source, cancellation=token)

    assert exc_info.value.code is ErrorCode.READ_CANCELLED
    assert cache.entry_count == 0
    assert list((tmp_path / "cache").glob("*.incomplete")) == []


def test_startup_janitor_removes_expired_entries_and_abandoned_incomplete_files(
    tmp_path: Path,
) -> None:
    now = 1000.0
    source = _write_npy_gzip(tmp_path / "array.npy.gz", np.arange(3, dtype=np.int16))
    cache = ManagedExtractionCache(
        tmp_path / "cache",
        limits=ExtractionLimits(max_entry_age_seconds=10),
        clock=lambda: now,
    )
    adapter = GzipAdapter([NPYAdapter()], extraction_cache=cache)
    session = adapter.open(source, cancellation=CancellationToken())
    cached = cache.cached_path_for(source)
    session.close()
    abandoned = tmp_path / "cache" / "abandoned.incomplete"
    abandoned.write_bytes(b"partial")

    expired_cache = ManagedExtractionCache(
        tmp_path / "cache",
        limits=ExtractionLimits(max_entry_age_seconds=10),
        clock=lambda: now + 20,
    )

    assert cached is not None
    assert not cached.exists()
    assert not abandoned.exists()
    assert expired_cache.entry_count == 0
