"""State machine and save-review behavior for patch-based editing."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.domain import DataViewerError, ErrorCode, ResourceId, SourceFingerprint
from data_viewer.editing.patches import ChangeSet, CellPatch, fingerprint_value
from data_viewer.editing.review import SaveStrategy, build_save_review, build_warnings
from data_viewer.editing.session import (
    EditCloseAction,
    EditSession,
    EditSessionState,
    EditSessionTransitionError,
)


def _resource(tmp_path: Path, node_path: str = "/array") -> ResourceId:
    source = tmp_path / "source.fake"
    resource = ResourceId.from_file(source, node_path)
    return resource


def test_edit_session_clean_to_dirty_and_undo_redo_discard(tmp_path: Path) -> None:
    fingerprint = SourceFingerprint(size_bytes=12, modified_time_ns=100)
    session = EditSession.create(_resource(tmp_path, "/").source_uri, fingerprint)
    patch_a = CellPatch(_resource(tmp_path, "/array"), (0,), fingerprint_value("old"), "new")
    patch_b = CellPatch(_resource(tmp_path, "/array"), (1,), fingerprint_value("two"), "tree")

    dirty = session.with_patch(patch_a)
    assert dirty.state is EditSessionState.DIRTY
    assert dirty.patch_count == 1

    changed = dirty.with_patch(patch_b)
    assert changed.patch_count == 2

    undone_snapshot, undone = changed.undo()
    assert undone == patch_b
    assert undone_snapshot.patch_count == 1

    redone_snapshot, redone = undone_snapshot.redo()
    assert redone == patch_b
    assert redone_snapshot.patch_count == 2

    discarded = redone_snapshot.discard()
    assert discarded.is_clean
    assert discarded.patch_count == 0
    assert discarded.state is EditSessionState.CLEAN


def test_edit_session_rejects_invalid_patch_source(tmp_path: Path) -> None:
    session = EditSession.create(
        "file:///allowed",
        SourceFingerprint(size_bytes=1, modified_time_ns=1),
    )
    bad_resource = ResourceId.from_file(tmp_path / "other.fake", "/array")

    with pytest.raises(ValueError, match="source URI"):
        session.with_patch(CellPatch(bad_resource, (0,), fingerprint_value("x"), "y"))


def test_edit_session_external_fingerprint_conflict_and_refresh(tmp_path: Path) -> None:
    source = SourceFingerprint(size_bytes=2, modified_time_ns=1)
    session = EditSession.create(_resource(tmp_path, "/").source_uri, source)
    assert session.refresh_fingerprint(source) is session

    changed = session.refresh_fingerprint(SourceFingerprint(size_bytes=3, modified_time_ns=2))
    assert changed.state is EditSessionState.CLEAN

    dirty = changed.with_patch(
        CellPatch(_resource(tmp_path, "/array"), (0,), fingerprint_value("old"), "new")
    )
    conflicted = dirty.refresh_fingerprint(
        SourceFingerprint(size_bytes=4, modified_time_ns=3),
    )
    assert conflicted.state is EditSessionState.CONFLICTED
    assert conflicted.patch_count == 1


def test_edit_session_save_success_and_failure_state_flow(tmp_path: Path) -> None:
    source = SourceFingerprint(size_bytes=2, modified_time_ns=1)
    session = EditSession.create(_resource(tmp_path, "/").source_uri, source).with_patch(
        CellPatch(_resource(tmp_path, "/array"), (0,), fingerprint_value("old"), "new"),
    )
    saving = session.begin_save()
    assert saving.state is EditSessionState.SAVING
    assert saving.patch_count == 1

    success = saving.mark_save_success(SourceFingerprint(size_bytes=3, modified_time_ns=2))
    assert success.state is EditSessionState.CLEAN
    assert success.patch_count == 0

    failed_state = session.begin_save().mark_save_failed(
        DataViewerError(
            code=ErrorCode.SOURCE_CLOSED,
            message="failed",
            operation="edit.save",
        )
    )
    assert failed_state.state is EditSessionState.SAVE_FAILED
    assert failed_state.patch_count == 1
    assert failed_state.last_error is not None


def test_edit_session_close_action_flow() -> None:
    session = EditSession.create(
        "file:///close",
        SourceFingerprint(size_bytes=1, modified_time_ns=1),
    ).with_patch(
        CellPatch(
            ResourceId.from_json({"source_uri": "file:///close", "node_path": "/array"}),
            (0,),
            fingerprint_value("old"),
            "new",
        )
    )

    next_session, should_close = session.close_action(EditCloseAction.CANCEL)
    assert not should_close

    should_close_session, should_close = session.close_action(EditCloseAction.DISCARD)
    assert should_close
    assert should_close_session.patch_count == 0
    assert should_close_session.state is EditSessionState.CLEAN

    with pytest.raises(EditSessionTransitionError):
        session.close_action(EditCloseAction.SAVE)


def test_build_save_review_summarizes_resources_and_warnings(tmp_path: Path) -> None:
    resource = _resource(tmp_path, "/array")
    patches = tuple(
        CellPatch(resource, (index,), fingerprint_value(str(index)), index)
        for index in range(1201)
    )
    changeset = ChangeSet(
        source_fingerprint=SourceFingerprint(size_bytes=10, modified_time_ns=1),
        patches=patches,
    )
    review = build_save_review(
        changeset,
        target_uri="file:///dest",
        strategy=SaveStrategy.REPLACEMENT,
    )
    warnings = build_warnings(changeset)

    assert review.patch_count == len(patches)
    assert review.target_uri == "file:///dest"
    assert review.strategy is SaveStrategy.REPLACEMENT
    assert review.resources == (resource,)
    assert review.changed_patch_kinds == (("cell", 1201),)
    assert review.estimated_size_bytes > 0
    assert any("Large change set" in warning for warning in warnings)
