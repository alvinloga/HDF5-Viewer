"""Typed immutable patches and deterministic value fingerprints for edit history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import blake2s
from json import dumps
from typing import Any

from data_viewer.domain import ResourceId, SourceFingerprint

ScalarValue = str | int | float | bool | complex | None
MappingRow = dict[str, ScalarValue]
PatchValue = ScalarValue | MappingRow


@dataclass(frozen=True, slots=True)
class CellPatch:
    """An immutable patch against one array-like coordinate."""

    resource_id: ResourceId
    coordinate: tuple[int, ...]
    old_value_fingerprint: str
    new_value: ScalarValue

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", ResourceId.from_json(self.resource_id.to_json()))
        if not self.coordinate:
            raise ValueError("cell coordinate must not be empty")
        if any(not isinstance(index, int) or index < 0 for index in self.coordinate):
            raise ValueError("cell coordinates must be non-negative integers")
        if not self.old_value_fingerprint:
            raise ValueError("old_value_fingerprint must be non-empty")


@dataclass(frozen=True, slots=True)
class TextPatch:
    """An immutable text replacement patch by byte offsets."""

    resource_id: ResourceId
    start_offset: int
    end_offset: int
    old_text_fingerprint: str
    replacement: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", ResourceId.from_json(self.resource_id.to_json()))
        if self.start_offset < 0:
            raise ValueError("start_offset must be >= 0")
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must be >= start_offset")
        if not self.old_text_fingerprint:
            raise ValueError("old_text_fingerprint must be non-empty")
        if self.replacement is None:
            raise ValueError("replacement must be a string")


@dataclass(frozen=True, slots=True)
class AttributePatch:
    """An immutable metadata attribute patch."""

    resource_id: ResourceId
    name: str
    old_value_fingerprint: str | None
    new_value: PatchValue

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", ResourceId.from_json(self.resource_id.to_json()))
        if not self.name:
            raise ValueError("attribute name must not be empty")


EditPatch = CellPatch | TextPatch | AttributePatch


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """Immutable set of patches scoped to one source revision."""

    source_fingerprint: SourceFingerprint
    patches: tuple[EditPatch, ...] = ()
    created_at_utc: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "patches", tuple(self.patches))
        if self.created_at_utc == "":
            object.__setattr__(
                self,
                "created_at_utc",
                datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            )
        if not self.patches:
            return
        base_source = self.patches[0].resource_id.source_uri
        for patch in self.patches:
            if patch.resource_id.source_uri != base_source:
                raise ValueError("all patches in a changeset must belong to one source URI")

    @property
    def is_clean(self) -> bool:
        return len(self.patches) == 0

    @property
    def has_data_patches(self) -> bool:
        return any(isinstance(patch, (CellPatch, AttributePatch)) for patch in self.patches)

    def with_patch(self, patch: EditPatch) -> "ChangeSet":
        """Return a new changeset with one additional patch."""
        return ChangeSet(
            source_fingerprint=self.source_fingerprint,
            patches=(*self.patches, patch),
            created_at_utc=self.created_at_utc,
        )

    def with_patches(self, *patches: EditPatch) -> "ChangeSet":
        """Return a new changeset with one or more additional patches."""
        if not patches:
            return self
        return ChangeSet(
            source_fingerprint=self.source_fingerprint,
            patches=(*self.patches, *patches),
            created_at_utc=self.created_at_utc,
        )

    def truncate_to(self, count: int) -> "ChangeSet":
        """Return a copy truncated to the first ``count`` patches."""
        if not 0 <= count <= len(self.patches):
            raise ValueError("truncate count must be between 0 and patch count")
        if count == len(self.patches):
            return self
        return ChangeSet(
            source_fingerprint=self.source_fingerprint,
            patches=self.patches[:count],
            created_at_utc=self.created_at_utc,
        )


def fingerprint_value(value: ScalarValue | MappingRow | None) -> str:
    """Create a deterministic fingerprint for immutable patch values."""

    payload = _normalize_value_for_fingerprint(value)
    encoded = dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8",
    )
    return f"blake2s:{blake2s(encoded).hexdigest()}"


def _normalize_value_for_fingerprint(
    value: ScalarValue | MappingRow | None,
) -> Any:
    if isinstance(value, dict):
        return {"__dict__": {key: _normalize_value_for_fingerprint(value[key]) for key in sorted(value)}}
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float, str)) or value is None:
        return value
    if isinstance(value, complex):
        return {"__complex__": [value.real, value.imag]}
    if isinstance(value, list):
        return [_normalize_value_for_fingerprint(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_value_for_fingerprint(item) for item in value)
    raise ValueError(f"unsupported patch value type: {type(value).__name__}")


__all__ = [
    "AttributePatch",
    "CellPatch",
    "ChangeSet",
    "EditPatch",
    "MappingRow",
    "PatchValue",
    "ScalarValue",
    "TextPatch",
    "fingerprint_value",
]
