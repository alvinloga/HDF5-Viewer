"""Edit session state machine for patch-driven safe persistence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from data_viewer.domain import DataViewerError, SourceFingerprint

from .history import EditHistory
from .patches import EditPatch


class EditSessionTransitionError(RuntimeError):
    """Raised for illegal transitions in edit session state."""


class EditSessionState(StrEnum):
    """Document state machine values used for save/conflict tracking."""

    CLEAN = "clean"
    DIRTY = "dirty"
    SAVING = "saving"
    SAVE_FAILED = "save_failed"
    CONFLICTED = "conflicted"


class EditCloseAction(StrEnum):
    """Allowed user actions when closing a modified document."""

    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class EditSession:
    """Immutable edit session state and patch history for one source."""

    source_uri: str
    source_fingerprint: SourceFingerprint
    history: EditHistory
    state: EditSessionState = EditSessionState.CLEAN
    last_error: DataViewerError | None = None

    def __post_init__(self) -> None:
        if not self.source_uri:
            raise ValueError("source URI must not be empty")
        object.__setattr__(self, "state", EditSessionState(self.state))

    @classmethod
    def create(cls, source_uri: str, source_fingerprint: SourceFingerprint) -> "EditSession":
        """Create a clean edit session for one source document."""

        return cls(
            source_uri=source_uri,
            source_fingerprint=source_fingerprint,
            history=EditHistory.create(source_fingerprint),
        )

    @property
    def patch_count(self) -> int:
        """How many patches are currently pending."""

        return self.history.applied_patch_count

    @property
    def is_clean(self) -> bool:
        """Whether there are no pending edits."""

        return self.patch_count == 0

    def with_patch(self, patch: EditPatch) -> "EditSession":
        """Add one patch and move to dirty state."""

        self._ensure_edit_allowed()
        self._validate_patch_source(patch)
        return self._with_state(
            history=self.history.with_patch(patch),
            state=EditSessionState.DIRTY,
            last_error=None,
        )

    def undo(self) -> tuple["EditSession", EditPatch]:
        """Undo the most recent patch."""

        self._ensure_edit_allowed()
        history, patch = self.history.undo()
        return self._with_state(
            history=history,
            state=EditSessionState.DIRTY if history.applied_patch_count else EditSessionState.CLEAN,
            last_error=None,
        ), patch

    def redo(self) -> tuple["EditSession", EditPatch]:
        """Redo the most recently undone patch."""

        self._ensure_edit_allowed()
        history, patch = self.history.redo()
        return self._with_state(
            history=history,
            state=EditSessionState.DIRTY,
            last_error=None,
        ), patch

    def discard(self) -> "EditSession":
        """Discard all local edits and return a clean state."""

        if self.state is EditSessionState.SAVING:
            raise EditSessionTransitionError("cannot discard edits while saving")
        return self._with_state(
            history=self.history.discard_all(),
            state=EditSessionState.CLEAN,
            last_error=None,
        )

    def refresh_fingerprint(self, observed: SourceFingerprint) -> "EditSession":
        """Refresh the source fingerprint and detect conflict conditions."""

        if self.state is EditSessionState.SAVING:
            return self
        if observed == self.source_fingerprint:
            if self.state is EditSessionState.CLEAN and self.patch_count == 0:
                return self
            return self
        if self.patch_count == 0:
            return self._with_state(
                source_fingerprint=observed,
                state=EditSessionState.CLEAN,
                last_error=None,
            )
        return self._with_state(
            source_fingerprint=observed,
            state=EditSessionState.CONFLICTED,
            last_error=None,
        )

    def begin_save(self) -> "EditSession":
        """Move into SAVING state before persistence."""

        if self.patch_count == 0:
            raise EditSessionTransitionError("cannot begin save with no patches")
        if self.state is EditSessionState.SAVING:
            raise EditSessionTransitionError("save already started")
        if self.state is EditSessionState.CONFLICTED:
            raise EditSessionTransitionError("cannot save while conflicted")
        return self._with_state(
            state=EditSessionState.SAVING,
            last_error=None,
        )

    def mark_save_success(self, source_fingerprint: SourceFingerprint) -> "EditSession":
        """Clear edits after successful persistence."""

        if self.state is not EditSessionState.SAVING:
            raise EditSessionTransitionError("save success requires SAVING state")
        return self._with_state(
            source_fingerprint=source_fingerprint,
            history=self.history.discard_all(),
            state=EditSessionState.CLEAN,
            last_error=None,
        )

    def mark_save_failed(self, error: DataViewerError) -> "EditSession":
        """Keep edits and return SAVE_FAILED state."""

        if self.state is not EditSessionState.SAVING:
            raise EditSessionTransitionError("save failed requires SAVING state")
        return self._with_state(state=EditSessionState.SAVE_FAILED, last_error=error)

    def close_action(self, action: EditCloseAction) -> tuple["EditSession", bool]:
        """Handle close intent and return the next edit session state.

        Returns ``(session, should_close_immediately)``.
        """

        if self.state is EditSessionState.CLEAN and self.patch_count == 0:
            return self, True
        if action is EditCloseAction.CANCEL:
            return self, False
        if action is EditCloseAction.SAVE:
            if self.patch_count == 0:
                return self, True
            raise EditSessionTransitionError("save action requires external save flow")
        if action is EditCloseAction.DISCARD:
            return self.discard(), True
        raise ValueError(f"unsupported close action: {action!r}")

    def _with_state(
        self,
        *,
        source_fingerprint: SourceFingerprint | None = None,
        history: EditHistory | None = None,
        state: EditSessionState | None = None,
        last_error: DataViewerError | None = None,
    ) -> "EditSession":
        return replace(
            self,
            source_fingerprint=self.source_fingerprint
            if source_fingerprint is None
            else source_fingerprint,
            history=self.history if history is None else history,
            state=EditSessionState(self.state if state is None else state),
            last_error=last_error,
        )

    def _ensure_edit_allowed(self) -> None:
        if self.state is EditSessionState.SAVING:
            raise EditSessionTransitionError("editing is blocked while saving")
        if self.state is EditSessionState.CONFLICTED:
            raise EditSessionTransitionError(
                "editing is blocked while source is conflicted"
            )

    def _validate_patch_source(self, patch: EditPatch) -> None:
        if patch.resource_id.source_uri != self.source_uri:
            raise ValueError("patch source URI must match edit session source URI")


__all__ = [
    "EditCloseAction",
    "EditSession",
    "EditSessionState",
    "EditSessionTransitionError",
]
