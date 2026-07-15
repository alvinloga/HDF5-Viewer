"""DV-0905 session restore and external-change detection contracts."""

from __future__ import annotations

from pathlib import Path

from data_viewer.app.session_restore import (
    ChangeDecisionKind,
    ExternalChangeDetector,
    ExternalChangeKind,
    RestoreDecisionKind,
    SessionRestorePolicy,
    SessionRestoreService,
)
from data_viewer.domain import SourceFingerprint


def test_startup_restore_asks_before_opening_previous_workspace(tmp_path: Path) -> None:
    workspace_path = tmp_path / "study.dvw"
    workspace_path.write_text("{}", encoding="utf-8")
    service = SessionRestoreService(policy=SessionRestorePolicy.ASK)

    service.record_workspace_pointer(workspace_path)
    decision = service.startup_decision()

    assert decision.kind is RestoreDecisionKind.ASK
    assert decision.workspace_path == workspace_path.resolve()
    assert decision.safe_actions == ("restore", "skip", "forget")


def test_startup_restore_skips_missing_or_after_clean_shutdown(tmp_path: Path) -> None:
    missing = tmp_path / "missing.dvw"
    clean_service = SessionRestoreService(policy=SessionRestorePolicy.ASK)
    clean_service.record_workspace_pointer(missing)
    clean_service.record_clean_shutdown()

    assert clean_service.startup_decision().kind is RestoreDecisionKind.SKIP

    auto_service = SessionRestoreService(policy=SessionRestorePolicy.ALWAYS)
    auto_service.record_workspace_pointer(missing)
    decision = auto_service.startup_decision()

    assert decision.kind is RestoreDecisionKind.MISSING
    assert decision.safe_actions == ("locate", "forget")


def test_crash_recovery_pointer_survives_restart_until_user_decides(tmp_path: Path) -> None:
    workspace_path = tmp_path / "crashed.dvw"
    workspace_path.write_text("{}", encoding="utf-8")
    persisted = {}
    service = SessionRestoreService(policy=SessionRestorePolicy.ALWAYS, state=persisted)

    service.record_workspace_pointer(workspace_path)
    restarted = SessionRestoreService(policy=SessionRestorePolicy.ALWAYS, state=persisted)
    decision = restarted.startup_decision()

    assert decision.kind is RestoreDecisionKind.RESTORE
    assert decision.workspace_path == workspace_path.resolve()


def test_external_change_with_dirty_patches_requires_save_as_or_cancel() -> None:
    detector = ExternalChangeDetector()
    original = SourceFingerprint(size_bytes=10, modified_time_ns=100, content_tag="old")
    observed = SourceFingerprint(size_bytes=11, modified_time_ns=200, content_tag="new")

    event = detector.detect(
        source_uri="file:///tmp/data.csv",
        expected=original,
        observed=observed,
        dirty_patches=True,
    )

    assert event.kind is ExternalChangeKind.CHANGED
    assert event.dirty_patches
    assert event.safe_actions == ("reload_discard_local_patches", "save_as", "cancel")
    assert event.default_action is ChangeDecisionKind.CANCEL

    decision = detector.decide(event, ChangeDecisionKind.RELOAD)
    assert decision.kind is ChangeDecisionKind.CANCEL
    assert decision.reason == "dirty_reload_requires_discard"


def test_external_delete_and_replace_have_explicit_actions() -> None:
    detector = ExternalChangeDetector()
    original = SourceFingerprint(size_bytes=10, modified_time_ns=100)

    deleted = detector.detect(
        source_uri="file:///tmp/data.csv",
        expected=original,
        observed=None,
        dirty_patches=False,
    )
    assert deleted.kind is ExternalChangeKind.DELETED
    assert deleted.safe_actions == ("save_as", "close_reference", "cancel")

    replaced = detector.detect(
        source_uri="file:///tmp/data.csv",
        expected=original,
        observed=SourceFingerprint(size_bytes=10, modified_time_ns=100, content_tag="different"),
        dirty_patches=False,
    )
    assert replaced.kind is ExternalChangeKind.REPLACED
    assert replaced.safe_actions == ("reload", "save_as", "cancel")


def test_self_save_event_updates_baseline_without_false_conflict() -> None:
    detector = ExternalChangeDetector()
    original = SourceFingerprint(size_bytes=10, modified_time_ns=100)
    saved = SourceFingerprint(size_bytes=12, modified_time_ns=120)

    detector.record_self_save("file:///tmp/data.csv", saved)
    event = detector.detect(
        source_uri="file:///tmp/data.csv",
        expected=original,
        observed=saved,
        dirty_patches=False,
    )

    assert event.kind is ExternalChangeKind.SELF_SAVE
    assert event.conflict is False
    assert event.updated_fingerprint == saved
