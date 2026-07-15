"""Session restore policy and external file change decision models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import MutableMapping

from data_viewer.domain import JsonValue, SourceFingerprint


class SessionRestorePolicy(StrEnum):
    """Startup policy for the last workspace pointer."""

    ASK = "ask"
    ALWAYS = "always"
    NEVER = "never"


class RestoreDecisionKind(StrEnum):
    """Startup restore decision kind."""

    ASK = "ask"
    RESTORE = "restore"
    SKIP = "skip"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class RestoreDecision:
    """Safe startup action for a previously open workspace."""

    kind: RestoreDecisionKind
    workspace_path: Path | None
    safe_actions: tuple[str, ...]
    reason: str = ""


class SessionRestoreService:
    """Persist and evaluate the last workspace pointer for startup restore."""

    def __init__(
        self,
        *,
        policy: SessionRestorePolicy = SessionRestorePolicy.ASK,
        state: MutableMapping[str, JsonValue] | None = None,
    ) -> None:
        self._policy = SessionRestorePolicy(policy)
        self._state = state if state is not None else {}

    def record_workspace_pointer(self, workspace_path: Path) -> None:
        """Record the latest workspace pointer as app config/recovery state."""

        self._state["workspace_path"] = str(workspace_path.expanduser().resolve())
        self._state["clean_shutdown"] = False

    def record_clean_shutdown(self) -> None:
        """Mark the last session as closed intentionally."""

        self._state["clean_shutdown"] = True

    def forget_workspace_pointer(self) -> None:
        """Forget any startup restore pointer."""

        self._state.pop("workspace_path", None)
        self._state["clean_shutdown"] = True

    def startup_decision(self) -> RestoreDecision:
        """Return a safe startup decision without opening anything."""

        raw_path = self._state.get("workspace_path")
        if not isinstance(raw_path, str) or not raw_path:
            return RestoreDecision(
                kind=RestoreDecisionKind.SKIP,
                workspace_path=None,
                safe_actions=(),
                reason="no_previous_workspace",
            )
        workspace_path = Path(raw_path).expanduser().resolve()
        if self._policy is SessionRestorePolicy.NEVER or self._state.get("clean_shutdown") is True:
            return RestoreDecision(
                kind=RestoreDecisionKind.SKIP,
                workspace_path=workspace_path,
                safe_actions=("open_other", "forget"),
                reason="restore_policy_skips_previous_workspace",
            )
        if not workspace_path.exists():
            return RestoreDecision(
                kind=RestoreDecisionKind.MISSING,
                workspace_path=workspace_path,
                safe_actions=("locate", "forget"),
                reason="previous_workspace_missing",
            )
        if self._policy is SessionRestorePolicy.ALWAYS:
            return RestoreDecision(
                kind=RestoreDecisionKind.RESTORE,
                workspace_path=workspace_path,
                safe_actions=("restore", "skip"),
                reason="restore_policy_always",
            )
        return RestoreDecision(
            kind=RestoreDecisionKind.ASK,
            workspace_path=workspace_path,
            safe_actions=("restore", "skip", "forget"),
            reason="restore_policy_ask",
        )


class ExternalChangeKind(StrEnum):
    """Classification of file watcher/fingerprint refresh outcomes."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    REPLACED = "replaced"
    DELETED = "deleted"
    SELF_SAVE = "self_save"


class ChangeDecisionKind(StrEnum):
    """User decision for an external change event."""

    RELOAD = "reload"
    RELOAD_DISCARD_LOCAL_PATCHES = "reload_discard_local_patches"
    SAVE_AS = "save_as"
    CLOSE_REFERENCE = "close_reference"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class ExternalChangeEvent:
    """UI-consumable external change notification."""

    source_uri: str
    kind: ExternalChangeKind
    expected_fingerprint: SourceFingerprint
    observed_fingerprint: SourceFingerprint | None
    dirty_patches: bool
    safe_actions: tuple[str, ...]
    default_action: ChangeDecisionKind
    conflict: bool
    updated_fingerprint: SourceFingerprint | None = None


@dataclass(frozen=True, slots=True)
class ChangeDecision:
    """Validated action chosen for an external change event."""

    kind: ChangeDecisionKind
    reason: str = ""


class ExternalChangeDetector:
    """Classify source changes and validate safe remediation choices."""

    def __init__(self) -> None:
        self._self_saves: dict[str, SourceFingerprint] = {}

    def record_self_save(self, source_uri: str, fingerprint: SourceFingerprint) -> None:
        """Record a save initiated by Data Viewer so watcher echoes are ignored."""

        _require_non_empty(source_uri, "source_uri")
        self._self_saves[source_uri] = fingerprint

    def detect(
        self,
        *,
        source_uri: str,
        expected: SourceFingerprint,
        observed: SourceFingerprint | None,
        dirty_patches: bool,
    ) -> ExternalChangeEvent:
        """Classify a watcher/fingerprint refresh result without mutating sources."""

        _require_non_empty(source_uri, "source_uri")
        self_saved = self._self_saves.get(source_uri)
        if observed is not None and self_saved == observed:
            self._self_saves.pop(source_uri, None)
            return ExternalChangeEvent(
                source_uri=source_uri,
                kind=ExternalChangeKind.SELF_SAVE,
                expected_fingerprint=expected,
                observed_fingerprint=observed,
                dirty_patches=dirty_patches,
                safe_actions=(),
                default_action=ChangeDecisionKind.RELOAD,
                conflict=False,
                updated_fingerprint=observed,
            )
        if observed is None:
            return ExternalChangeEvent(
                source_uri=source_uri,
                kind=ExternalChangeKind.DELETED,
                expected_fingerprint=expected,
                observed_fingerprint=None,
                dirty_patches=dirty_patches,
                safe_actions=("save_as", "close_reference", "cancel"),
                default_action=ChangeDecisionKind.CANCEL,
                conflict=dirty_patches,
            )
        if observed == expected:
            return ExternalChangeEvent(
                source_uri=source_uri,
                kind=ExternalChangeKind.UNCHANGED,
                expected_fingerprint=expected,
                observed_fingerprint=observed,
                dirty_patches=dirty_patches,
                safe_actions=(),
                default_action=ChangeDecisionKind.RELOAD,
                conflict=False,
                updated_fingerprint=observed,
            )
        kind = ExternalChangeKind.REPLACED if _same_stat_different_content(expected, observed) else ExternalChangeKind.CHANGED
        if dirty_patches:
            safe_actions = ("reload_discard_local_patches", "save_as", "cancel")
        else:
            safe_actions = ("reload", "save_as", "cancel")
        return ExternalChangeEvent(
            source_uri=source_uri,
            kind=kind,
            expected_fingerprint=expected,
            observed_fingerprint=observed,
            dirty_patches=dirty_patches,
            safe_actions=safe_actions,
            default_action=ChangeDecisionKind.CANCEL,
            conflict=dirty_patches,
        )

    def decide(
        self,
        event: ExternalChangeEvent,
        requested: ChangeDecisionKind,
    ) -> ChangeDecision:
        """Validate a user decision for an external change event."""

        requested = ChangeDecisionKind(requested)
        if event.dirty_patches and requested is ChangeDecisionKind.RELOAD:
            return ChangeDecision(
                kind=ChangeDecisionKind.CANCEL,
                reason="dirty_reload_requires_discard",
            )
        if requested.value not in event.safe_actions and event.safe_actions:
            return ChangeDecision(kind=ChangeDecisionKind.CANCEL, reason="action_not_available")
        return ChangeDecision(kind=requested, reason="accepted")


def _same_stat_different_content(
    expected: SourceFingerprint,
    observed: SourceFingerprint,
) -> bool:
    return (
        expected.size_bytes == observed.size_bytes
        and expected.modified_time_ns == observed.modified_time_ns
        and expected.content_tag != observed.content_tag
    )


def _require_non_empty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")


__all__ = [
    "ChangeDecision",
    "ChangeDecisionKind",
    "ExternalChangeDetector",
    "ExternalChangeEvent",
    "ExternalChangeKind",
    "RestoreDecision",
    "RestoreDecisionKind",
    "SessionRestorePolicy",
    "SessionRestoreService",
]
