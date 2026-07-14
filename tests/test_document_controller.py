"""Contracts for document-owned source sessions and request generations."""

from __future__ import annotations

from threading import Event, Thread
from time import monotonic

import pytest

from data_viewer.app.active_context import ActiveContext
from data_viewer.app.documents import (
    DocumentController,
    DocumentStatus,
)
from data_viewer.domain import DataViewerError, ErrorCode, ResourceId
from data_viewer.editing.patches import CellPatch, fingerprint_value
from data_viewer.editing.review import SaveStrategy
from data_viewer.editing.session import EditCloseAction, EditSessionState
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken, TaskState
from tests.conformance.source_adapter import FakeArrayAdapter, write_fake_source


def test_document_controller_owns_one_source_session(tmp_path) -> None:
    adapter = FakeArrayAdapter()
    path = write_fake_source(tmp_path / "owned.fake")
    document = DocumentController.open_path(
        path,
        registry=SourceRegistry([adapter]),
        cancellation=CancellationToken(),
    )

    root = document.root(cancellation=CancellationToken())
    page = document.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )

    assert document.source_uri == path.resolve(strict=False).as_uri()
    assert page.items[0].resource_id.source_uri == document.source_uri
    assert adapter.last_session is not None

    document.close()
    document.close()

    assert adapter.last_session.close_count == 1
    assert document.snapshot().status is DocumentStatus.CLOSED
    with pytest.raises(DataViewerError) as closed_error:
        document.root(cancellation=CancellationToken())
    assert closed_error.value.code is ErrorCode.SOURCE_CLOSED


def test_navigation_generation_rejects_stale_task_results(tmp_path) -> None:
    document = _open_fake_document(tmp_path)
    root = document.root(cancellation=CancellationToken())
    resource = document.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    ).items[0].resource_id

    first_request = document.navigate_to(resource)
    stale_task = document.create_task("read")
    stale_task.start()
    second_request = document.navigate_to(resource)

    assert second_request.request_generation == first_request.request_generation + 1
    assert not document.accepts_task_result(stale_task.snapshot())

    current_task = document.create_task("read")
    current_task.start()
    assert document.accepts_task_result(current_task.snapshot())

    stale_task.request_cancel()
    stale_task.cancelled()
    current_task.succeed("ok")


def test_close_waits_for_active_task_before_closing_session(tmp_path) -> None:
    adapter = FakeArrayAdapter()
    path = write_fake_source(tmp_path / "task-close.fake")
    document = DocumentController.open_path(
        path,
        registry=SourceRegistry([adapter]),
        cancellation=CancellationToken(),
    )
    task = document.create_task("read")
    task.start()
    closed = Event()

    closer = Thread(target=lambda: (document.close(), closed.set()))
    closer.start()
    _wait_until(lambda: document.snapshot().status is DocumentStatus.CLOSING)

    assert task.cancellation.is_cancelled
    assert task.snapshot().state is TaskState.CANCELLING
    assert not closed.is_set()

    task.cancelled()
    closer.join(timeout=2)

    assert closed.is_set()
    assert adapter.last_session is not None
    assert adapter.last_session.close_count == 1
    assert document.snapshot().status is DocumentStatus.CLOSED


def test_close_waits_for_active_io_lease_before_closing_session(tmp_path) -> None:
    adapter = FakeArrayAdapter()
    path = write_fake_source(tmp_path / "lease-close.fake")
    document = DocumentController.open_path(
        path,
        registry=SourceRegistry([adapter]),
        cancellation=CancellationToken(),
    )
    lease_entered = Event()
    release_lease = Event()
    closed = Event()

    def hold_lease() -> None:
        with document.acquire_io_lease(cancellation=CancellationToken()):
            lease_entered.set()
            release_lease.wait(timeout=2)

    worker = Thread(target=hold_lease)
    worker.start()
    assert lease_entered.wait(timeout=2)

    closer = Thread(target=lambda: (document.close(), closed.set()))
    closer.start()
    _wait_until(lambda: document.snapshot().status is DocumentStatus.CLOSING)

    assert document.snapshot().active_io_count == 1
    assert not closed.is_set()

    release_lease.set()
    worker.join(timeout=2)
    closer.join(timeout=2)

    assert closed.is_set()
    assert adapter.last_session is not None
    assert adapter.last_session.close_count == 1


def test_active_context_tracks_document_and_resource_without_widgets(tmp_path) -> None:
    document = _open_fake_document(tmp_path)
    root = document.root(cancellation=CancellationToken())
    resource = document.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    ).items[0].resource_id
    request = document.navigate_to(resource)
    context = ActiveContext()

    context.activate_document(document.snapshot())
    context.activate_request(request)
    snapshot = context.snapshot()

    assert snapshot.document_id == document.document_id
    assert snapshot.resource_id == resource
    assert snapshot.request_generation == request.request_generation
    assert context.matches(document.snapshot())

    document.navigate_to(ResourceId(document.source_uri, "/array"))
    assert not context.matches(document.snapshot())


def test_dirty_and_task_hooks_track_non_gui_state(tmp_path) -> None:
    document = _open_fake_document(tmp_path)

    assert document.mark_dirty().dirty_count == 1
    assert document.mark_dirty().dirty_count == 2
    assert document.clear_dirty().dirty_count == 0

    task = document.create_task("read")
    assert document.snapshot().active_task_count == 1

    task.start()
    task.fail(
        DataViewerError(
            code=ErrorCode.TASK_FAILED,
            message="read failed",
            operation="read",
        )
    )

    assert document.snapshot().active_task_count == 0


def test_editing_state_is_reflected_in_document_snapshot(tmp_path) -> None:
    document = _open_fake_document(tmp_path)
    resource = ResourceId(document.source_uri, "/array")
    snapshot = document.snapshot()
    assert snapshot.edit_state is EditSessionState.CLEAN
    assert snapshot.edit_patch_count == 0

    snapshot = document.apply_edit_patch(
        CellPatch(
            resource,
            (0,),
            fingerprint_value("0"),
            "99",
        )
    )
    assert snapshot.edit_state is EditSessionState.DIRTY
    assert snapshot.edit_patch_count == 1

    snapshot_undo, patch = document.undo_edit()
    assert snapshot_undo.edit_state is EditSessionState.CLEAN
    assert patch.resource_id == resource
    assert snapshot_undo.edit_patch_count == 0

    snapshot = document.apply_edit_patch(
        CellPatch(
            resource,
            (0,),
            fingerprint_value("0"),
            "42",
        )
    )
    review = document.build_edit_save_review(
        target_uri=document.source_uri,
        strategy=SaveStrategy.REPLACEMENT,
    )
    assert review.patch_count == 1
    assert review.target_uri == document.source_uri
    assert review.changed_patch_kinds == (("cell", 1),)
    assert review.estimated_size_bytes > 0

    snapshot = document.discard_edit_changes()
    assert snapshot.edit_state is EditSessionState.CLEAN
    assert snapshot.edit_patch_count == 0


def test_close_dirty_document_supports_cancel_discard_choices(tmp_path) -> None:
    path = write_fake_source(tmp_path / "close-edit.fake")
    document = DocumentController.open_path(
        path,
        registry=SourceRegistry([FakeArrayAdapter()]),
        cancellation=CancellationToken(),
    )
    resource = ResourceId(document.source_uri, "/array")

    document.apply_edit_patch(
        CellPatch(
            resource,
            (0,),
            fingerprint_value("0"),
            "1",
        )
    )
    with pytest.raises(DataViewerError) as err:
        document.close(edit_close_action=EditCloseAction.CANCEL)
    assert err.value.code is ErrorCode.EDIT_CONFLICT

    # External edit changes should move the state to conflict
    path.write_bytes(path.read_bytes() + b"x")
    snapshot = document.refresh_edit_fingerprint(cancellation=CancellationToken())
    assert snapshot.edit_state is EditSessionState.CONFLICTED

    document.close(edit_close_action=EditCloseAction.DISCARD)
    assert document.snapshot().status is DocumentStatus.CLOSED


def _open_fake_document(tmp_path) -> DocumentController:
    path = write_fake_source(tmp_path / "document.fake")
    return DocumentController.open_path(
        path,
        registry=SourceRegistry([FakeArrayAdapter()]),
        cancellation=CancellationToken(),
    )


def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
    raise AssertionError("condition was not reached before timeout")
