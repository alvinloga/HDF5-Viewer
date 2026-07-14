"""Save review model for inspected patch sets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from data_viewer.domain import ResourceId, SourceFingerprint

from .patches import CellPatch, ChangeSet, EditPatch, TextPatch


class SaveStrategy(StrEnum):
    """How persistence should apply the patched edits."""

    IN_PLACE = "in_place"
    REPLACEMENT = "replacement"
    SAVE_AS = "save_as"


@dataclass(frozen=True, slots=True)
class SaveReview:
    """User-facing summary before save."""

    target_uri: str
    strategy: SaveStrategy
    source_fingerprint: SourceFingerprint
    resources: tuple[ResourceId, ...]
    patch_count: int
    changed_patch_kinds: tuple[tuple[str, int], ...]
    estimated_size_bytes: int
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.patch_count < 0:
            raise ValueError("patch_count must be non-negative")
        if self.estimated_size_bytes < 0:
            raise ValueError("estimated_size_bytes must be non-negative")


def build_save_review(
    changeset: ChangeSet,
    *,
    target_uri: str,
    strategy: SaveStrategy,
) -> SaveReview:
    """Build a deterministic review summary from a changeset."""

    if not target_uri:
        raise ValueError("target URI must be a non-empty string")
    return SaveReview(
        target_uri=target_uri,
        strategy=strategy,
        source_fingerprint=changeset.source_fingerprint,
        resources=_unique_resources(changeset.patches),
        patch_count=len(changeset.patches),
        changed_patch_kinds=_count_kinds(changeset.patches),
        estimated_size_bytes=_estimate_changeset_size(changeset.patches),
    )


def build_warnings(
    changeset: ChangeSet,
    resource_warnings: Iterable[str] = (),
) -> tuple[str, ...]:
    """Build additional deterministic warnings for a save review."""

    warnings = list(sorted(resource_warnings))
    if len(changeset.patches) > 1000:
        warnings.append("Large change set may increase persistence time.")
    return tuple(warnings)


def _unique_resources(patches: tuple[EditPatch, ...]) -> tuple[ResourceId, ...]:
    resources = {patch.resource_id for patch in patches}
    ordered = sorted(resources, key=lambda item: (item.source_uri, item.node_path))
    return tuple(ordered)


def _count_kinds(patches: tuple[EditPatch, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for patch in patches:
        key = _patch_kind(patch)
        counts[key] = counts.get(key, 0) + 1
    return tuple((key, counts[key]) for key in sorted(counts))


def _patch_kind(patch: EditPatch) -> str:
    if isinstance(patch, CellPatch):
        return "cell"
    if isinstance(patch, TextPatch):
        return "text"
    return "attribute"


def _estimate_changeset_size(patches: tuple[EditPatch, ...]) -> int:
    total = 0
    for patch in patches:
        total += len(repr(patch))
    return total

__all__ = [
    "SaveReview",
    "SaveStrategy",
    "build_save_review",
    "build_warnings",
]
