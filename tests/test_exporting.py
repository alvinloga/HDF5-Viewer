"""Export plan, service, and receipt behavior."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from data_viewer.domain import (
    AxisSelection,
    ArrayPayload,
    ColumnSpec,
    NormalizedTablePage,
    ResourceId,
    SelectionSpec,
    SourceFingerprint,
    StructuredPayload,
    TablePayload,
    TextPayload,
)
from data_viewer.exporting import (
    ExportOutcome,
    ExportScope,
    ExportService,
    ExportTargetFormat,
    ExportValueMode,
    build_export_plan,
)
from data_viewer.exporting.receipt import ExportReceipt
from data_viewer.tasks import CancellationToken


def _fingerprint() -> SourceFingerprint:
    return SourceFingerprint(size_bytes=12, modified_time_ns=34)


def _resource(tmp_path: Path) -> ResourceId:
    return ResourceId.from_file(tmp_path / "source.h5", "/array")


def test_export_plan_serializes_explicit_slice_scope_and_value_mode(tmp_path: Path) -> None:
    selection = SelectionSpec.hyperslab(
        AxisSelection.slice(0, start=1, stop=3),
        AxisSelection(axis=1, index=2),
    ).normalize((4, 5)).unwrap()

    plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        resource_id=_resource(tmp_path),
        selection=selection,
        target_path=tmp_path / "slice.npy",
        scope=ExportScope.CURRENT_SLICE,
        value_mode=ExportValueMode.RAW,
    )

    payload = plan.to_json()
    assert payload["scope"] == "current_slice"
    assert payload["value_mode"] == "raw"
    assert payload["target_format"] == "npy"
    assert payload["selection"]["result_shape"] == [2]


def test_export_plan_supports_all_v1_scope_names(tmp_path: Path) -> None:
    selection = SelectionSpec.all().normalize((2, 2)).unwrap()
    table_page = TablePayload(
        columns=(ColumnSpec("name", "str", False),),
        column_values=(np.array(["alice"]),),
        row_offset=4,
        total_rows=10,
    )
    normalized_page = NormalizedTablePage(
        row_offset=4,
        row_limit=1,
        total_rows=10,
        selected_columns=("name",),
    )

    scoped = {
        ExportScope.FULL_RESOURCE: build_export_plan(
            source_fingerprint=_fingerprint(),
            resource_id=_resource(tmp_path),
            target_path=tmp_path / "full.json",
            scope=ExportScope.FULL_RESOURCE,
            value_mode=ExportValueMode.RAW,
        ),
        ExportScope.CURRENT_SLICE: build_export_plan(
            source_fingerprint=_fingerprint(),
            resource_id=_resource(tmp_path),
            selection=selection,
            target_path=tmp_path / "slice.json",
            scope=ExportScope.CURRENT_SLICE,
            value_mode=ExportValueMode.RAW,
        ),
        ExportScope.CURRENT_SELECTION: build_export_plan(
            source_fingerprint=_fingerprint(),
            resource_id=_resource(tmp_path),
            selection=selection,
            target_path=tmp_path / "selection.json",
            scope=ExportScope.CURRENT_SELECTION,
            value_mode=ExportValueMode.DISPLAY,
        ),
        ExportScope.FILTERED_ROWS: build_export_plan(
            source_fingerprint=_fingerprint(),
            resource_id=_resource(tmp_path),
            table_page=normalized_page,
            target_path=tmp_path / "rows.csv",
            scope=ExportScope.FILTERED_ROWS,
            value_mode=ExportValueMode.RAW,
        ),
    }
    plugin_plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        target_path=tmp_path / "plugin.json",
        scope=ExportScope.PLUGIN_RESULT,
        value_mode=ExportValueMode.RAW,
    )
    rendered_plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        target_path=tmp_path / "render.png",
        scope=ExportScope.RENDERED_VISUALIZATION,
        value_mode=ExportValueMode.DISPLAY,
        target_format=ExportTargetFormat.PNG,
    )

    assert table_page.source_cell(0, "name") == (4, "name")
    assert normalized_page.to_json()["row_offset"] == 4
    assert {plan.scope for plan in scoped.values()} == {
        ExportScope.FULL_RESOURCE,
        ExportScope.CURRENT_SLICE,
        ExportScope.CURRENT_SELECTION,
        ExportScope.FILTERED_ROWS,
    }
    assert plugin_plan.scope is ExportScope.PLUGIN_RESULT
    assert rendered_plan.scope is ExportScope.RENDERED_VISUALIZATION


def test_export_service_writes_npy_and_receipt_round_trips(tmp_path: Path) -> None:
    values: np.ndarray = np.arange(6, dtype=np.int16).reshape(2, 3)
    payload = ArrayPayload(values=values, original_shape=(2, 3), selection=SelectionSpec.all())
    plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        resource_id=_resource(tmp_path),
        selection=payload.selection,
        target_path=tmp_path / "array.npy",
        scope=ExportScope.CURRENT_SELECTION,
        value_mode=ExportValueMode.RAW,
    )

    receipt = ExportService(application_version="test-version").export_payload(plan, payload)

    assert receipt.succeeded
    assert receipt.bytes_written > 0
    assert np.array_equal(np.load(tmp_path / "array.npy", allow_pickle=False), values)
    round_trip = ExportReceipt.from_json(receipt.to_json())
    assert round_trip.to_json() == receipt.to_json()


def test_export_service_csv_escapes_formula_like_table_cells(tmp_path: Path) -> None:
    payload = TablePayload(
        columns=(ColumnSpec("label", "str", False), ColumnSpec("value", "str", False)),
        column_values=(np.array(["safe", "=1+1"]), np.array(["+ok", "@cmd"])),
        row_offset=0,
        total_rows=2,
    )
    plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        resource_id=_resource(tmp_path),
        table_page=NormalizedTablePage(
            row_offset=0,
            row_limit=2,
            total_rows=2,
            selected_columns=("label", "value"),
        ),
        target_path=tmp_path / "table.csv",
        scope=ExportScope.FILTERED_ROWS,
        value_mode=ExportValueMode.DISPLAY,
        target_format=ExportTargetFormat.CSV,
    )

    receipt = ExportService(application_version="test-version").export_payload(plan, payload)

    assert receipt.succeeded
    assert "CSV export escapes spreadsheet formula-like text cells." in receipt.warnings
    assert (tmp_path / "table.csv").read_text(encoding="utf-8").splitlines() == [
        "label,value",
        "safe,'+ok",
        "'=1+1,'@cmd",
    ]


def test_export_service_refuses_overwrite_without_permission(tmp_path: Path) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old", encoding="utf-8")
    plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        resource_id=_resource(tmp_path),
        target_path=target,
        scope=ExportScope.FULL_RESOURCE,
        value_mode=ExportValueMode.RAW,
    )

    receipt = ExportService(application_version="test-version").export_payload(
        plan,
        TextPayload("new", offset=0, is_complete=True),
    )

    assert receipt.outcome is ExportOutcome.FAILED
    assert target.read_text(encoding="utf-8") == "old"


def test_export_service_records_cancelled_receipt_without_writing(tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()
    target = tmp_path / "cancelled.json"
    plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        target_path=target,
        scope=ExportScope.PLUGIN_RESULT,
        value_mode=ExportValueMode.RAW,
    )

    receipt = ExportService(application_version="test-version").export_payload(
        plan,
        StructuredPayload({"ok": True}),
        cancellation=token,
    )

    assert receipt.outcome is ExportOutcome.CANCELLED
    assert not target.exists()


def test_export_service_records_unsupported_conversion_failure(tmp_path: Path) -> None:
    plan = build_export_plan(
        source_fingerprint=_fingerprint(),
        target_path=tmp_path / "bad.npy",
        scope=ExportScope.PLUGIN_RESULT,
        value_mode=ExportValueMode.RAW,
        target_format=ExportTargetFormat.NPY,
    )

    receipt = ExportService(application_version="test-version").export_payload(
        plan,
        {"not": "array"},
    )

    assert receipt.outcome is ExportOutcome.FAILED
    assert receipt.error_code is not None
    assert not (tmp_path / "bad.npy").exists()
