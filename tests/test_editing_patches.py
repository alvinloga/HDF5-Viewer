"""Patch model and history behavior used by safe editing."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.domain import ResourceId, SourceFingerprint
from data_viewer.editing import (
    AttributePatch,
    CellPatch,
    ChangeSet,
    EditHistory,
    TextPatch,
    fingerprint_value,
)


def test_change_set_rejects_patches_from_different_source_uris(tmp_path: Path) -> None:
    source_a = SourceFingerprint(size_bytes=10, modified_time_ns=100)
    changeset = ChangeSet(source_fingerprint=source_a)
    resource_a = ResourceId.from_file(tmp_path / "a.h5", "/dataset")
    resource_b = ResourceId.from_file(tmp_path / "b.h5", "/dataset")
    patch_a = CellPatch(resource_a, (0,), fingerprint_value("a"), "A")
    patch_b = CellPatch(resource_b, (0,), fingerprint_value("a"), "A")

    first = changeset.with_patch(patch_a)
    _ = first.with_patch(patch_a)
    assert not first.is_clean
    assert (
        changeset.with_patch(patch_a).with_patch(patch_a).patches
        == first.with_patch(patch_a).patches
    )
    # different source URI is rejected only when both patches are known:
    with pytest.raises(ValueError, match="one source URI"):
        changeset.with_patch(patch_a).with_patch(patch_b)


def test_change_set_timestamp_is_stable_after_append(tmp_path: Path) -> None:
    source = SourceFingerprint(size_bytes=2, modified_time_ns=1)
    resource = ResourceId.from_file(tmp_path / "x.h5", "/x")
    patch = CellPatch(resource, (0, 1), fingerprint_value("A"), "B")

    changeset = ChangeSet(source_fingerprint=source)
    after = changeset.with_patch(patch)

    assert changeset.created_at_utc == after.created_at_utc
    assert not after.is_clean


def test_fingerprint_value_is_deterministic_for_scalar_and_structured_values() -> None:
    first = fingerprint_value({"b": 2, "a": 1})
    second = fingerprint_value({"a": 1, "b": 2})
    complex_value = fingerprint_value({"z": 1 + 2j})

    assert first == second
    assert complex_value.startswith("blake2s:")


def test_text_patch_and_attribute_patch_validation(tmp_path: Path) -> None:
    resource = ResourceId.from_file(tmp_path / "table.txt", "/table")
    text = TextPatch(resource, 0, 4, fingerprint_value("abcd"), "")
    assert text.start_offset == 0
    assert text.end_offset == 4

    attr = AttributePatch(resource, "dtype", fingerprint_value("float"), 1.0)
    assert attr.name == "dtype"


def test_edit_history_undo_redo_and_discard(tmp_path: Path) -> None:
    source = SourceFingerprint(size_bytes=16, modified_time_ns=123)
    resource = ResourceId.from_file(tmp_path / "undo.h5", "/dataset")
    patch_1 = CellPatch(resource, (0,), fingerprint_value("old"), "new")
    patch_2 = AttributePatch(resource, "unit", fingerprint_value("m"), "cm")

    history = EditHistory.create(source)
    staged = history.with_patch(patch_1).with_patch(patch_2)
    assert staged.can_undo is True
    assert staged.applied_patch_count == 2
    assert staged.can_redo is False

    after_undo, undone_patch = staged.undo()
    assert undone_patch == patch_2
    assert after_undo.applied_patch_count == 1
    assert after_undo.can_redo is True
    assert after_undo.redo_stack == (patch_2,)

    after_undo_again, undone_second = after_undo.undo()
    assert undone_second == patch_1
    assert after_undo_again.is_clean is True
    assert after_undo_again.can_redo is True

    after_redo, redone_patch = after_undo_again.redo()
    assert redone_patch == patch_1
    assert after_redo.applied_patch_count == 1

    discarded = after_undo_again.discard_all()
    assert discarded.is_clean is True
    assert discarded.can_redo is False
