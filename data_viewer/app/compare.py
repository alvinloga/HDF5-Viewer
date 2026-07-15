"""Comparison domain state, validation, and workspace persistence helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from data_viewer.domain import FrozenJsonMapping, JsonValue
from data_viewer.workspace import WorkspaceManifest


class ComparisonAlignmentMode(StrEnum):
    """Explicit comparison alignment modes."""

    BY_INDEX = "by_index"
    BY_AXIS = "by_axis"
    BY_COLUMN = "by_column"


class ComparisonDifferenceMode(StrEnum):
    """Supported persisted difference modes."""

    ABSOLUTE = "absolute"
    LEFT_RELATIVE = "left_relative"


@dataclass(frozen=True, slots=True)
class ColumnMatch:
    """Explicit left/right table column match."""

    left: str
    right: str

    def __post_init__(self) -> None:
        _require_non_empty(self.left, "left column")
        _require_non_empty(self.right, "right column")

    def to_json(self) -> dict[str, JsonValue]:
        return {"left": self.left, "right": self.right}

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ColumnMatch":
        return cls(left=str(value["left"]), right=str(value["right"]))


@dataclass(frozen=True, slots=True)
class ComparisonAlignment:
    """Persisted comparison alignment policy."""

    mode: ComparisonAlignmentMode
    axis_mapping: tuple[int, ...] = ()
    columns: tuple[ColumnMatch, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", ComparisonAlignmentMode(self.mode))
        object.__setattr__(self, "axis_mapping", tuple(self.axis_mapping))
        object.__setattr__(self, "columns", tuple(self.columns))
        if self.mode is ComparisonAlignmentMode.BY_COLUMN and not self.columns:
            raise ComparisonValidationError(
                "column alignment requires at least one explicit column match",
                reason="missing_column_match",
            )

    def to_json(self) -> dict[str, JsonValue]:
        data: dict[str, JsonValue] = {"mode": self.mode.value}
        if self.axis_mapping:
            data["axis_mapping"] = list(self.axis_mapping)
        if self.columns:
            data["columns"] = [column.to_json() for column in self.columns]
        return data

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ComparisonAlignment":
        return cls(
            mode=ComparisonAlignmentMode(str(value["mode"])),
            axis_mapping=tuple(
                _expect_int(item, "axis mapping")
                for item in _expect_list(value.get("axis_mapping", []), "axis_mapping")
            ),
            columns=tuple(
                ColumnMatch.from_json(_expect_mapping(item, "column match"))
                for item in _expect_list(value.get("columns", []), "columns")
            ),
        )


@dataclass(frozen=True, slots=True)
class ComparisonSide:
    """One persisted side of a comparison."""

    source_id: str
    resource_path: str
    resource_domain: str
    display_name: str
    shape: tuple[int, ...] | None
    dtype: str
    columns: tuple[str, ...] = ()
    fingerprint: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (
            ("source_id", self.source_id),
            ("resource_path", self.resource_path),
            ("resource_domain", self.resource_domain),
            ("display_name", self.display_name),
            ("dtype", self.dtype),
        ):
            _require_non_empty(value, label)
        if self.shape is not None:
            if any(isinstance(axis, bool) or axis < 0 for axis in self.shape):
                raise ComparisonValidationError("shape axes must be non-negative", reason="invalid_shape")
            object.__setattr__(self, "shape", tuple(self.shape))
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "fingerprint", FrozenJsonMapping(self.fingerprint))

    @property
    def identity_label(self) -> str:
        return f"{self.source_id}:{self.resource_path}"

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source_id,
            "resource_path": self.resource_path,
            "resource_domain": self.resource_domain,
            "display_name": self.display_name,
            "shape": list(self.shape) if self.shape is not None else None,
            "dtype": self.dtype,
            "columns": list(self.columns),
            "fingerprint": FrozenJsonMapping(self.fingerprint).to_json(),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ComparisonSide":
        raw_shape = value.get("shape")
        shape = None
        if raw_shape is not None:
            shape = tuple(_expect_int(item, "shape axis") for item in _expect_list(raw_shape, "shape"))
        return cls(
            source_id=str(value["source_id"]),
            resource_path=str(value["resource_path"]),
            resource_domain=str(value["resource_domain"]),
            display_name=str(value.get("display_name", value["source_id"])),
            shape=shape,
            dtype=str(value.get("dtype", "unknown")),
            columns=tuple(str(item) for item in _expect_list(value.get("columns", []), "columns")),
            fingerprint=_expect_mapping(value.get("fingerprint", {}), "fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class ComparisonCompatibility:
    """Compatibility decision displayed before payload comparison."""

    shape_compatible: bool
    column_compatible: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ComparisonViewState:
    """UI-consumable comparison state without Qt dependencies."""

    left_identity: str
    right_identity: str
    alignment_label: str
    difference_label: str
    linked_navigation: bool
    compatibility_label: str


@dataclass(frozen=True, slots=True)
class ComparisonState:
    """Validated comparison state persisted in workspace manifests."""

    comparison_id: str
    left: ComparisonSide
    right: ComparisonSide
    alignment: ComparisonAlignment
    difference_mode: ComparisonDifferenceMode
    linked_navigation: bool
    compatibility: ComparisonCompatibility
    result_id: str | None = None
    provenance: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.comparison_id, "comparison_id")
        object.__setattr__(self, "difference_mode", ComparisonDifferenceMode(self.difference_mode))
        object.__setattr__(self, "provenance", FrozenJsonMapping(self.provenance))

    @property
    def view_state(self) -> ComparisonViewState:
        return ComparisonViewState(
            left_identity=self.left.identity_label,
            right_identity=self.right.identity_label,
            alignment_label=_alignment_label(self.alignment),
            difference_label=_difference_label(self.difference_mode),
            linked_navigation=self.linked_navigation,
            compatibility_label=self.compatibility.reason,
        )

    def to_workspace_json(self) -> dict[str, JsonValue]:
        data: dict[str, JsonValue] = {
            "comparison_id": self.comparison_id,
            "left": self.left.to_json(),
            "right": self.right.to_json(),
            "alignment": self.alignment.to_json(),
            "difference_mode": self.difference_mode.value,
            "linked_navigation": self.linked_navigation,
            "compatibility": {
                "shape_compatible": self.compatibility.shape_compatible,
                "column_compatible": self.compatibility.column_compatible,
                "reason": self.compatibility.reason,
            },
            "provenance": FrozenJsonMapping(self.provenance).to_json(),
        }
        if self.result_id is not None:
            data["result_id"] = self.result_id
        return data

    @classmethod
    def from_workspace_json(cls, value: Mapping[str, JsonValue]) -> "ComparisonState":
        compatibility = _expect_mapping(value.get("compatibility", {}), "compatibility")
        return cls(
            comparison_id=str(value["comparison_id"]),
            left=ComparisonSide.from_json(_expect_mapping(value["left"], "left")),
            right=ComparisonSide.from_json(_expect_mapping(value["right"], "right")),
            alignment=ComparisonAlignment.from_json(_expect_mapping(value["alignment"], "alignment")),
            difference_mode=ComparisonDifferenceMode(str(value["difference_mode"])),
            linked_navigation=_expect_bool(value["linked_navigation"], "linked_navigation"),
            compatibility=ComparisonCompatibility(
                shape_compatible=_expect_bool(
                    compatibility.get("shape_compatible", False),
                    "shape_compatible",
                ),
                column_compatible=_expect_bool(
                    compatibility.get("column_compatible", False),
                    "column_compatible",
                ),
                reason=str(compatibility.get("reason", "")),
            ),
            result_id=str(value["result_id"]) if value.get("result_id") is not None else None,
            provenance=_expect_mapping(value.get("provenance", {}), "provenance"),
        )


@dataclass(frozen=True, slots=True)
class ComparisonRestoreError:
    """Invalid comparison entry encountered during workspace restore."""

    comparison_id: str
    reason: str
    message: str


class ComparisonValidationError(ValueError):
    """Raised when a comparison would be ambiguous or unsafe."""

    def __init__(self, message: str, *, reason: str) -> None:
        self.reason = reason
        super().__init__(message)


class ComparisonController:
    """Create, validate, persist, and restore comparison states."""

    def __init__(self) -> None:
        self._restore_errors: tuple[ComparisonRestoreError, ...] = ()

    @property
    def restore_errors(self) -> tuple[ComparisonRestoreError, ...]:
        return self._restore_errors

    def create_comparison(
        self,
        *,
        comparison_id: str,
        left: ComparisonSide,
        right: ComparisonSide,
        alignment: ComparisonAlignment,
        difference_mode: ComparisonDifferenceMode,
        linked_navigation: bool,
        result_id: str | None = None,
    ) -> ComparisonState:
        compatibility = _validate_alignment(left, right, alignment)
        return ComparisonState(
            comparison_id=comparison_id,
            left=left,
            right=right,
            alignment=alignment,
            difference_mode=difference_mode,
            linked_navigation=linked_navigation,
            compatibility=compatibility,
            result_id=result_id,
            provenance={
                "left_source_id": left.source_id,
                "left_resource_path": left.resource_path,
                "left_fingerprint": FrozenJsonMapping(left.fingerprint).to_json(),
                "right_source_id": right.source_id,
                "right_resource_path": right.resource_path,
                "right_fingerprint": FrozenJsonMapping(right.fingerprint).to_json(),
                "alignment_mode": alignment.mode.value,
                "difference_mode": ComparisonDifferenceMode(difference_mode).value,
            },
        )

    def save_to_workspace(
        self,
        manifest: WorkspaceManifest,
        comparison: ComparisonState,
    ) -> WorkspaceManifest:
        replacement = comparison.to_workspace_json()
        comparisons = tuple(
            item
            for item in manifest.comparisons
            if str(item.get("comparison_id", "")) != comparison.comparison_id
        )
        return manifest.with_updates(
            comparisons=(*comparisons, replacement),
            workspace_dirty=True,
        )

    def restore_from_workspace(self, manifest: WorkspaceManifest) -> tuple[ComparisonState, ...]:
        restored: list[ComparisonState] = []
        errors: list[ComparisonRestoreError] = []
        for item in manifest.comparisons:
            comparison_id = str(item.get("comparison_id", ""))
            try:
                state = ComparisonState.from_workspace_json(item)
                _validate_alignment(state.left, state.right, state.alignment)
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(
                    ComparisonRestoreError(
                        comparison_id=comparison_id,
                        reason="invalid_workspace_comparison",
                        message=str(exc),
                    )
                )
                continue
            restored.append(state)
        self._restore_errors = tuple(errors)
        return tuple(restored)


def _validate_alignment(
    left: ComparisonSide,
    right: ComparisonSide,
    alignment: ComparisonAlignment,
) -> ComparisonCompatibility:
    if alignment.mode in {ComparisonAlignmentMode.BY_INDEX, ComparisonAlignmentMode.BY_AXIS}:
        if left.resource_domain != right.resource_domain:
            raise ComparisonValidationError(
                "comparison sides must share a compatible domain",
                reason="domain_mismatch",
            )
        if left.shape is None or right.shape is None or left.shape != right.shape:
            raise ComparisonValidationError(
                f"shape mismatch: {left.shape} != {right.shape}; no implicit broadcasting is allowed",
                reason="shape_mismatch",
            )
        if alignment.mode is ComparisonAlignmentMode.BY_AXIS:
            _validate_axis_mapping(left.shape, alignment.axis_mapping)
            reason = "axis alignment compatible"
        else:
            reason = "exact shape"
        return ComparisonCompatibility(
            shape_compatible=True,
            column_compatible=False,
            reason=reason,
        )
    if alignment.mode is ComparisonAlignmentMode.BY_COLUMN:
        _validate_column_matches(left, right, alignment.columns)
        return ComparisonCompatibility(
            shape_compatible=left.shape == right.shape,
            column_compatible=True,
            reason="explicit column matches",
        )
    raise ComparisonValidationError("unsupported alignment mode", reason="unsupported_alignment")


def _validate_axis_mapping(shape: tuple[int, ...], axis_mapping: tuple[int, ...]) -> None:
    rank = len(shape)
    if len(axis_mapping) != rank or sorted(axis_mapping) != list(range(rank)):
        raise ComparisonValidationError(
            "axis alignment requires an explicit same-rank axis permutation",
            reason="invalid_axis_mapping",
        )


def _validate_column_matches(
    left: ComparisonSide,
    right: ComparisonSide,
    columns: tuple[ColumnMatch, ...],
) -> None:
    left_seen: set[str] = set()
    right_seen: set[str] = set()
    for column in columns:
        if column.left not in left.columns or column.right not in right.columns:
            raise ComparisonValidationError(
                f"unknown comparison column: {column.left}↔{column.right}",
                reason="unknown_column",
            )
        if column.left in left_seen or column.right in right_seen:
            raise ComparisonValidationError(
                "column alignment cannot reuse a left or right column",
                reason="duplicate_column",
            )
        left_seen.add(column.left)
        right_seen.add(column.right)


def _alignment_label(alignment: ComparisonAlignment) -> str:
    if alignment.mode is ComparisonAlignmentMode.BY_INDEX:
        return "Index alignment: exact shape"
    if alignment.mode is ComparisonAlignmentMode.BY_AXIS:
        return "Axis alignment: " + "→".join(str(axis) for axis in alignment.axis_mapping)
    return "Column alignment: " + ", ".join(
        f"{column.left}↔{column.right}" for column in alignment.columns
    )


def _difference_label(mode: ComparisonDifferenceMode) -> str:
    if mode is ComparisonDifferenceMode.ABSOLUTE:
        return "Absolute difference"
    return "Left-relative difference"


def _require_non_empty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ComparisonValidationError(f"{label} must be a non-empty string", reason="invalid_field")


def _expect_mapping(value: object, label: str) -> Mapping[str, JsonValue]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, JsonValue], value)
    raise ComparisonValidationError(f"{label} must be an object", reason="invalid_field")


def _expect_list(value: object, label: str) -> list[JsonValue]:
    if isinstance(value, list):
        return cast(list[JsonValue], value)
    raise ComparisonValidationError(f"{label} must be an array", reason="invalid_field")


def _expect_bool(value: object, label: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ComparisonValidationError(f"{label} must be boolean", reason="invalid_field")


def _expect_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ComparisonValidationError(f"{label} must be integer", reason="invalid_field")
    return value


__all__ = [
    "ColumnMatch",
    "ComparisonAlignment",
    "ComparisonAlignmentMode",
    "ComparisonCompatibility",
    "ComparisonController",
    "ComparisonDifferenceMode",
    "ComparisonRestoreError",
    "ComparisonSide",
    "ComparisonState",
    "ComparisonValidationError",
    "ComparisonViewState",
]
