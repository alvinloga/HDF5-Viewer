"""In-memory patch history for undo/redo and discard semantics."""

from __future__ import annotations

from dataclasses import dataclass

from data_viewer.domain import SourceFingerprint

from .patches import ChangeSet, EditPatch


@dataclass(frozen=True, slots=True)
class EditHistory:
    """Immutable history stack for one source fingerprint."""

    changeset: ChangeSet
    redo_stack: tuple[EditPatch, ...] = ()

    @classmethod
    def create(cls, source_fingerprint: SourceFingerprint) -> "EditHistory":
        return cls(changeset=ChangeSet(source_fingerprint=source_fingerprint))

    @property
    def is_clean(self) -> bool:
        return self.changeset.is_clean

    @property
    def dirty(self) -> bool:
        return not self.is_clean

    @property
    def can_undo(self) -> bool:
        return len(self.changeset.patches) > 0

    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    @property
    def applied_patch_count(self) -> int:
        return len(self.changeset.patches)

    @property
    def undone_patch_count(self) -> int:
        return len(self.redo_stack)

    def with_patch(self, patch: EditPatch) -> "EditHistory":
        """Return a new history after applying one more user edit."""
        return EditHistory(
            changeset=self.changeset.with_patch(patch),
            redo_stack=(),
        )

    def undo(self) -> tuple["EditHistory", EditPatch]:
        """Undo the most recent patch and return it."""
        if not self.can_undo:
            raise ValueError("no patch is available to undo")
        patch = self.changeset.patches[-1]
        return (
            EditHistory(
                changeset=self.changeset.truncate_to(len(self.changeset.patches) - 1),
                redo_stack=(patch, *self.redo_stack),
            ),
            patch,
        )

    def redo(self) -> tuple["EditHistory", EditPatch]:
        """Redo the most recently undone patch."""
        if not self.can_redo:
            raise ValueError("no patch is available to redo")
        patch = self.redo_stack[0]
        return (
            EditHistory(
                changeset=self.changeset.with_patch(patch),
                redo_stack=self.redo_stack[1:],
            ),
            patch,
        )

    def discard_all(self) -> "EditHistory":
        """Discard all pending and redoable patches."""
        return EditHistory(
            changeset=ChangeSet(
                source_fingerprint=self.changeset.source_fingerprint,
                created_at_utc=self.changeset.created_at_utc,
            )
        )


__all__ = ["EditHistory"]
