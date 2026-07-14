"""Editing primitives for safe patch-based persistence."""

from .history import EditHistory
from .patches import (
    AttributePatch,
    CellPatch,
    ChangeSet,
    EditPatch,
    MappingRow,
    PatchValue,
    ScalarValue,
    TextPatch,
    fingerprint_value,
)
from .validation import ValidationPolicy, validate_edit_value

__all__ = [
    "AttributePatch",
    "CellPatch",
    "ChangeSet",
    "EditHistory",
    "EditPatch",
    "MappingRow",
    "PatchValue",
    "ScalarValue",
    "TextPatch",
    "ValidationPolicy",
    "fingerprint_value",
    "validate_edit_value",
]
