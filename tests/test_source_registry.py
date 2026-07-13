"""Contracts for DataSource API v1 and source registry behavior."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from data_viewer.domain import DataViewerError, ErrorCode, ResourceId
from data_viewer.sources.api import (
    DATASOURCE_API_VERSION,
    NodePage,
    ProbeResult,
    ReadRequest,
    SourceAdapter,
    SourceSession,
)
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken
from tests.conformance.source_adapter import (
    FAKE_HEADER,
    FakeArrayAdapter,
    assert_source_adapter_conformance,
    write_fake_source,
)

ROOT = Path(__file__).resolve().parents[1]
BANNED_FORMAT_LIBRARIES = {"h5py", "pandas", "nibabel", "openpyxl", "scipy"}


def test_source_api_exports_exact_v1_contract_values(tmp_path: Path) -> None:
    resource = ResourceId.from_file(tmp_path / "array.fake", "/array")
    request = ReadRequest(resource_id=resource)

    assert DATASOURCE_API_VERSION == 1
    assert request.max_bytes == 256 * 1024 * 1024
    assert NodePage(items=(), next_cursor=None, total_count=0).items == ()
    assert SourceAdapter is not SourceSession

    with pytest.raises(ValueError, match="confidence"):
        ProbeResult(
            adapter_id="bad",
            confidence=101,
            detected_format="bad",
            reason="invalid",
        )

    with pytest.raises(ValueError, match="max_bytes"):
        ReadRequest(resource_id=resource, max_bytes=0)


def test_fake_adapter_passes_shared_conformance(tmp_path: Path) -> None:
    adapter = FakeArrayAdapter()
    registry = SourceRegistry([adapter])
    path = write_fake_source(tmp_path / "sample.fake")

    assert_source_adapter_conformance(registry, path, adapter)


def test_registry_uses_bounded_header_for_probe_arbitration(tmp_path: Path) -> None:
    adapter = FakeArrayAdapter()
    registry = SourceRegistry([adapter], max_probe_bytes=len(FAKE_HEADER))
    path = write_fake_source(tmp_path / "large.fake", payload=b"x" * 4096)

    selected = registry.select_adapter(path, cancellation=CancellationToken())

    assert selected.adapter is adapter
    assert adapter.probe_header_lengths == [len(FAKE_HEADER)]


def test_registry_rejects_duplicate_adapter_ids_and_extensions() -> None:
    duplicate_id = FakeArrayAdapter()
    duplicate_extension = FakeArrayAdapter(adapter_id="other.fake")

    with pytest.raises(DataViewerError) as id_error:
        SourceRegistry([duplicate_id, FakeArrayAdapter()])
    assert id_error.value.code is ErrorCode.SOURCE_AMBIGUOUS
    assert id_error.value.details["duplicate_adapter_id"] == "fake.array"

    with pytest.raises(DataViewerError) as extension_error:
        SourceRegistry([duplicate_id, duplicate_extension])
    assert extension_error.value.code is ErrorCode.SOURCE_AMBIGUOUS
    assert extension_error.value.details["duplicate_extension"] == ".fake"


def test_registry_reports_unsupported_and_ambiguous_probe_results(tmp_path: Path) -> None:
    path = tmp_path / "sample.fake"
    path.write_bytes(b"unknown")

    with pytest.raises(DataViewerError) as unsupported:
        SourceRegistry([FakeArrayAdapter()]).select_adapter(
            path,
            cancellation=CancellationToken(),
        )
    assert unsupported.value.code is ErrorCode.SOURCE_UNSUPPORTED

    first = FakeArrayAdapter(
        adapter_id="first.fake",
        extensions=(".first",),
        confidence=80,
        detected_format="duplicate-format",
    )
    second = FakeArrayAdapter(
        adapter_id="second.fake",
        extensions=(".second",),
        confidence=80,
        detected_format="duplicate-format",
    )
    ambiguous_path = write_fake_source(tmp_path / "ambiguous.first")

    with pytest.raises(DataViewerError) as ambiguous:
        SourceRegistry([first, second]).select_adapter(
            ambiguous_path,
            cancellation=CancellationToken(),
        )
    assert ambiguous.value.code is ErrorCode.SOURCE_AMBIGUOUS
    assert ambiguous.value.details["duplicate_format"] == "duplicate-format"


def test_sources_boundary_does_not_import_raw_format_libraries() -> None:
    for relative in (
        "data_viewer/sources/api.py",
        "data_viewer/sources/registry.py",
    ):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imported_modules = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )

        assert imported_modules.isdisjoint(BANNED_FORMAT_LIBRARIES)
