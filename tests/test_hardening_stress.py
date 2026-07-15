"""DV-1002 stress, leak, and adversarial hardening contracts."""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pytest

from data_viewer.app.export_queue import ExportQueueService
from data_viewer.app.navigation import NavigationService, SearchIndexEntry, SearchQuery
from data_viewer.domain import (
    ArrayPayload,
    DataViewerError,
    ErrorCode,
    ResourceId,
    SelectionSpec,
    SourceFingerprint,
)
from data_viewer.exporting import (
    ExportScope,
    ExportTargetFormat,
    ExportValueMode,
    build_export_plan,
)
from data_viewer.sources.gzip.cache import ExtractionLimits, ManagedExtractionCache
from data_viewer.tasks import CancellationToken, TaskState
from data_viewer.workspace import WorkspaceService, WorkspaceValidationError


def test_many_successful_exports_do_not_retain_task_payloads(tmp_path: Path) -> None:
    queue = ExportQueueService(application_version="test-version")
    payload = _array_payload(np.arange(4))

    for index in range(25):
        queue.enqueue(
            _export_plan(tmp_path, f"out-{index}.npy"),
            payload,
            owner_id="source:1",
        )

    while queue.pending_count:
        snapshot = queue.run_next()
        assert snapshot is not None
        assert snapshot.state is TaskState.SUCCEEDED

    assert len(queue.receipts()) == 25
    assert queue.retained_task_count == 0


def test_rapid_navigation_search_honors_cancellation_without_partial_results() -> None:
    service = NavigationService()
    entries = tuple(
        SearchIndexEntry(
            source_id="src",
            resource_path=f"/group/{index}",
            name=f"dataset_{index}",
            resource_domain="array",
            dtype="float64",
            shape=(index + 1,),
        )
        for index in range(500)
    )
    token = CancellationToken()
    token.cancel()

    with pytest.raises(DataViewerError) as exc_info:
        service.search(entries, SearchQuery(text="dataset"), cancellation=token)

    assert exc_info.value.code is ErrorCode.TASK_CANCELLED


def test_adversarial_workspace_depth_fails_structured_without_recursing_forever() -> None:
    nested: object = {"leaf": "value"}
    for _ in range(80):
        nested = {"next": nested}
    payload = {
        "schema_version": 1,
        "app": {"name": "Data Viewer", "version": "1.0.0"},
        "workspace_id": "workspace",
        "title": "Too deep",
        "created_at": "2026-07-15T00:00:00Z",
        "updated_at": "2026-07-15T00:00:00Z",
        "path_base": "workspace_directory",
        "sources": [],
        "views": [],
        "comparisons": [],
        "plugin_results": [],
        "layout": {},
        "preferences": {},
        "extensions": {"attack": nested},
    }

    with pytest.raises(WorkspaceValidationError, match="nesting budget"):
        WorkspaceService(max_depth=16).loads(__import__("json").dumps(payload))


def test_gzip_budget_failure_removes_incomplete_cache_files(tmp_path: Path) -> None:
    source = tmp_path / "bomb.txt.gz"
    source.write_bytes(gzip.compress(b"x" * 4096))
    cache = ManagedExtractionCache(
        tmp_path / "cache",
        limits=ExtractionLimits(max_decompressed_bytes=128),
    )

    with pytest.raises(DataViewerError) as exc_info:
        cache.extract(source, cancellation=CancellationToken())

    assert exc_info.value.code is ErrorCode.BUDGET_EXCEEDED
    assert tuple((tmp_path / "cache").glob("*.incomplete")) == ()


def _fingerprint() -> SourceFingerprint:
    return SourceFingerprint(size_bytes=12, modified_time_ns=34, content_tag="hardening")


def _resource(tmp_path: Path) -> ResourceId:
    return ResourceId.from_file(tmp_path / "source.h5", "/array")


def _export_plan(tmp_path: Path, name: str):
    return build_export_plan(
        source_fingerprint=_fingerprint(),
        resource_id=_resource(tmp_path),
        target_path=tmp_path / name,
        target_format=ExportTargetFormat.NPY,
        scope=ExportScope.FULL_RESOURCE,
        value_mode=ExportValueMode.RAW,
    )


def _array_payload(values: np.ndarray) -> ArrayPayload:
    return ArrayPayload(
        values=values,
        original_shape=values.shape,
        selection=SelectionSpec.all(),
    )
