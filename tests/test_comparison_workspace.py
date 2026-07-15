"""DV-0903 comparison domain, controller, and workspace persistence contracts."""

from __future__ import annotations

import pytest

from data_viewer.app.compare import (
    ColumnMatch,
    ComparisonAlignment,
    ComparisonAlignmentMode,
    ComparisonController,
    ComparisonDifferenceMode,
    ComparisonSide,
    ComparisonValidationError,
)
from data_viewer.workspace import WorkspaceManifest


def test_array_comparison_requires_explicit_exact_index_alignment() -> None:
    controller = ComparisonController()
    left = _array_side("left", shape=(2, 3))
    right = _array_side("right", shape=(2, 3))

    state = controller.create_comparison(
        comparison_id="cmp-1",
        left=left,
        right=right,
        alignment=ComparisonAlignment(mode=ComparisonAlignmentMode.BY_INDEX),
        difference_mode=ComparisonDifferenceMode.ABSOLUTE,
        linked_navigation=True,
    )

    assert state.left.source_id == "left"
    assert state.right.source_id == "right"
    assert state.compatibility.shape_compatible
    assert state.view_state.left_identity == "left:/array"
    assert state.view_state.right_identity == "right:/array"
    assert state.view_state.alignment_label == "Index alignment: exact shape"
    assert state.view_state.difference_label == "Absolute difference"
    assert state.view_state.linked_navigation is True


def test_array_comparison_refuses_implicit_broadcasting() -> None:
    controller = ComparisonController()

    with pytest.raises(ComparisonValidationError) as exc_info:
        controller.create_comparison(
            comparison_id="cmp-bad",
            left=_array_side("left", shape=(2, 3)),
            right=_array_side("right", shape=(3,)),
            alignment=ComparisonAlignment(mode=ComparisonAlignmentMode.BY_INDEX),
            difference_mode=ComparisonDifferenceMode.LEFT_RELATIVE,
            linked_navigation=False,
        )

    assert exc_info.value.reason == "shape_mismatch"
    assert "no implicit broadcasting" in str(exc_info.value)


def test_table_comparison_requires_explicit_column_matching() -> None:
    controller = ComparisonController()
    left = _table_side("left", columns=("time", "value", "error"))
    right = _table_side("right", columns=("t", "value", "sigma"))

    state = controller.create_comparison(
        comparison_id="cmp-columns",
        left=left,
        right=right,
        alignment=ComparisonAlignment(
            mode=ComparisonAlignmentMode.BY_COLUMN,
            columns=(
                ColumnMatch(left="time", right="t"),
                ColumnMatch(left="value", right="value"),
            ),
        ),
        difference_mode=ComparisonDifferenceMode.ABSOLUTE,
        linked_navigation=False,
    )

    assert state.compatibility.column_compatible
    assert state.view_state.alignment_label == "Column alignment: time↔t, value↔value"
    assert state.view_state.linked_navigation is False

    with pytest.raises(ComparisonValidationError) as exc_info:
        controller.create_comparison(
            comparison_id="cmp-missing",
            left=left,
            right=right,
            alignment=ComparisonAlignment(
                mode=ComparisonAlignmentMode.BY_COLUMN,
                columns=(ColumnMatch(left="missing", right="value"),),
            ),
            difference_mode=ComparisonDifferenceMode.ABSOLUTE,
            linked_navigation=False,
        )
    assert exc_info.value.reason == "unknown_column"


def test_comparison_workspace_round_trip_and_restore_provenance() -> None:
    controller = ComparisonController()
    comparison = controller.create_comparison(
        comparison_id="cmp-workspace",
        left=_array_side("left", shape=(4, 4), fingerprint={"size": 10}),
        right=_array_side("right", shape=(4, 4), fingerprint={"size": 20}),
        alignment=ComparisonAlignment(mode=ComparisonAlignmentMode.BY_INDEX),
        difference_mode=ComparisonDifferenceMode.LEFT_RELATIVE,
        linked_navigation=True,
        result_id="result-1",
    )
    manifest = _manifest()

    updated = controller.save_to_workspace(manifest, comparison)
    restored = controller.restore_from_workspace(updated)

    assert updated.workspace_dirty
    assert len(updated.comparisons) == 1
    assert restored[0] == comparison
    assert restored[0].provenance["left_fingerprint"] == {"size": 10}
    assert restored[0].provenance["right_fingerprint"] == {"size": 20}
    assert restored[0].view_state.difference_label == "Left-relative difference"


def test_comparison_restore_reports_invalid_workspace_entries() -> None:
    controller = ComparisonController()
    manifest = _manifest(
        comparisons=(
            {
                "comparison_id": "bad",
                "left": {"source_id": "left"},
                "right": {"source_id": "right"},
                "alignment": {"mode": "by_index"},
                "difference_mode": "absolute",
                "linked_navigation": False,
            },
        )
    )

    restored = controller.restore_from_workspace(manifest)

    assert restored == ()
    assert controller.restore_errors[0].comparison_id == "bad"
    assert controller.restore_errors[0].reason == "invalid_workspace_comparison"


def _array_side(
    source_id: str,
    *,
    shape: tuple[int, ...],
    fingerprint: dict[str, object] | None = None,
) -> ComparisonSide:
    return ComparisonSide(
        source_id=source_id,
        resource_path="/array",
        resource_domain="array",
        display_name=source_id,
        shape=shape,
        dtype="float64",
        columns=(),
        fingerprint=fingerprint or {},
    )


def _table_side(source_id: str, *, columns: tuple[str, ...]) -> ComparisonSide:
    return ComparisonSide(
        source_id=source_id,
        resource_path="/table",
        resource_domain="table",
        display_name=source_id,
        shape=(10, len(columns)),
        dtype="float64",
        columns=columns,
        fingerprint={},
    )


def _manifest(
    *,
    comparisons: tuple[dict[str, object], ...] = (),
) -> WorkspaceManifest:
    return WorkspaceManifest(
        workspace_id="workspace-1",
        title="comparison workspace",
        created_at="2026-07-15T00:00:00Z",
        updated_at="2026-07-15T00:00:00Z",
        comparisons=comparisons,  # type: ignore[arg-type]
    )
