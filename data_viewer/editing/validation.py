"""Validation helpers for safe, typed edit values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from data_viewer.domain import DataViewerError, ErrorCode

from .patches import ScalarValue


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """Validation policy toggles used before patch creation."""

    allow_nonfinite: bool = False
    allow_string_truncation: bool = False
    strict_text_encoding: bool = True


def validate_edit_value(
    raw_value: Any,
    *,
    dtype: str | np.dtype,
    policy: ValidationPolicy | None = None,
) -> ScalarValue:
    """Validate and normalize a user-provided value for a target dtype."""

    policy = ValidationPolicy() if policy is None else policy
    target = np.dtype(dtype)

    if target.fields:
        return _validate_structured(raw_value, target, policy=policy)

    kind = target.kind
    if kind in {"i", "u"}:
        return _validate_integer(raw_value, target)
    if kind == "b":
        return _validate_boolean(raw_value)
    if kind == "f":
        return _validate_float(raw_value, target, policy=policy)
    if kind == "c":
        return _validate_complex(raw_value, target, policy=policy)
    if kind in {"S", "U"}:
        return _validate_string(raw_value, target, policy=policy)

    raise DataViewerError(
        code=ErrorCode.EDIT_VALIDATION_FAILED,
        message=f"dtype {target.str!r} is not supported for direct editing.",
        operation="validation.validate_edit_value",
        details={"dtype": target.str},
    )


def _validate_integer(
    raw_value: Any,
    target: np.dtype,
) -> ScalarValue:
    if isinstance(raw_value, bool):
        candidate = int(raw_value)
    elif isinstance(raw_value, (int, np.integer)):
        candidate = int(raw_value)
    elif isinstance(raw_value, str):
        try:
            candidate = int(raw_value.strip())
        except ValueError as exc:
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Integer value must be an integer literal.",
                operation="validation._validate_integer",
                details={"raw_value": str(raw_value)},
            ) from exc
    else:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Integer value must be an integer.",
            operation="validation._validate_integer",
            details={"raw_value_type": type(raw_value).__name__},
        )

    limit = np.iinfo(target)
    if candidate < limit.min or candidate > limit.max:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Integer value is outside target dtype bounds.",
            operation="validation._validate_integer",
            details={
                "value": candidate,
                "dtype": target.str,
                "min": limit.min,
                "max": limit.max,
            },
        )

    cast_value = target.type(candidate).item()
    if isinstance(cast_value, np.integer):
        return int(cast_value)
    return int(cast_value)


def _validate_float(
    raw_value: Any,
    target: np.dtype,
    *,
    policy: ValidationPolicy,
) -> ScalarValue:
    parsed = _parse_float(raw_value, operation="validation._validate_float")

    if np.isnan(parsed):
        if not policy.allow_nonfinite:
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Float value NaN is disallowed by policy.",
                operation="validation._validate_float",
                details={"raw_value": str(raw_value), "dtype": target.str},
            )
    elif np.isinf(parsed) and not policy.allow_nonfinite:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Float value is infinite and disallowed by policy.",
            operation="validation._validate_float",
            details={"raw_value": str(raw_value), "dtype": target.str},
        )

    cast_value = float(target.type(parsed).item())
    if not np.isfinite(cast_value) and not policy.allow_nonfinite:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Float value overflows target dtype.",
            operation="validation._validate_float",
            details={"raw_value": str(raw_value), "dtype": target.str},
        )

    return cast_value


def _validate_complex(
    raw_value: Any,
    target: np.dtype,
    *,
    policy: ValidationPolicy,
) -> ScalarValue:
    if isinstance(raw_value, bool):
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Complex value must be a valid complex literal.",
            operation="validation._validate_complex",
            details={"raw_value": str(raw_value)},
        )
    if isinstance(raw_value, np.complexfloating):
        parsed = complex(raw_value)
    elif isinstance(raw_value, complex):
        parsed = complex(raw_value)
    elif isinstance(raw_value, str):
        try:
            parsed = complex(raw_value.strip())
        except ValueError as exc:
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Complex value must be a valid complex literal.",
                operation="validation._validate_complex",
                details={"raw_value": str(raw_value)},
            ) from exc
    else:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Complex value must be an explicit complex-like value.",
            operation="validation._validate_complex",
            details={"raw_value_type": type(raw_value).__name__},
        )

    if not policy.allow_nonfinite and (not np.isfinite(parsed.real) or not np.isfinite(parsed.imag)):
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Complex value contains non-finite parts and is disallowed by policy.",
            operation="validation._validate_complex",
            details={"raw_value": str(raw_value), "dtype": target.str},
        )

    return target.type(parsed).item()


def _validate_boolean(raw_value: Any) -> ScalarValue:
    if isinstance(raw_value, bool):
        return bool(raw_value)
    if isinstance(raw_value, (int, np.integer)):
        if raw_value not in (0, 1):
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Boolean value must be 0 or 1.",
                operation="validation._validate_boolean",
                details={"raw_value": str(raw_value)},
            )
        return bool(raw_value)
    if isinstance(raw_value, str):
        value = raw_value.strip().lower()
        if value in {"true", "1", "t", "yes", "y", "on"}:
            return True
        if value in {"false", "0", "f", "no", "n", "off"}:
            return False

    raise DataViewerError(
        code=ErrorCode.EDIT_VALIDATION_FAILED,
        message="Boolean value is invalid.",
        operation="validation._validate_boolean",
        details={"raw_value_type": type(raw_value).__name__},
    )


def _validate_string(
    raw_value: Any,
    target: np.dtype,
    *,
    policy: ValidationPolicy,
) -> ScalarValue:
    if target.kind == "S":
        return _validate_byte_string(raw_value, target, policy=policy)
    if target.kind == "U":
        return _validate_unicode_string(raw_value, target, policy=policy)
    raise RuntimeError(f"invalid string dtype kind: {target.kind}")


def _validate_byte_string(
    raw_value: Any,
    target: np.dtype,
    *,
    policy: ValidationPolicy,
) -> str:
    limit = target.itemsize
    if isinstance(raw_value, bytes):
        source = _decode_text(
            raw_value,
            strict=policy.strict_text_encoding,
            operation="validation._validate_byte_string",
        )
    elif isinstance(raw_value, str):
        source = raw_value
    else:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="String value must be bytes or text.",
            operation="validation._validate_byte_string",
            details={"raw_value_type": type(raw_value).__name__},
        )

    encoded = source.encode("utf-8")
    if len(encoded) > limit:
        if not policy.allow_string_truncation:
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Fixed-width bytes string would truncate.",
                operation="validation._validate_byte_string",
                details={
                    "raw_length": len(encoded),
                    "max_length": limit,
                    "dtype": target.str,
                    "allow_string_truncation": policy.allow_string_truncation,
                },
            )
        source = source.encode("utf-8")[:limit].decode("utf-8", errors="ignore")

    return source


def _validate_unicode_string(
    raw_value: Any,
    target: np.dtype,
    *,
    policy: ValidationPolicy,
) -> str:
    limit = _max_code_points_for_unicode_dtype(target)
    if isinstance(raw_value, bytes):
        source = _decode_text(
            raw_value,
            strict=policy.strict_text_encoding,
            operation="validation._validate_unicode_string",
        )
    elif isinstance(raw_value, str):
        source = raw_value
    else:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="String value must be bytes or text.",
            operation="validation._validate_unicode_string",
            details={"raw_value_type": type(raw_value).__name__},
        )

    if len(source) > limit:
        if not policy.allow_string_truncation:
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Fixed-width unicode string would truncate.",
                operation="validation._validate_unicode_string",
                details={
                    "raw_length": len(source),
                    "max_length": limit,
                    "dtype": target.str,
                    "allow_string_truncation": policy.allow_string_truncation,
                },
            )
        source = source[:limit]

    return source


def _max_code_points_for_unicode_dtype(target: np.dtype) -> int:
    char_size = np.dtype("U1").itemsize
    if char_size > 0 and target.itemsize > 0 and target.itemsize % char_size == 0:
        return target.itemsize // char_size

    type_text = str(target)
    if len(type_text) > 1 and type_text[0] in "<>|=":
        type_text = type_text[1:]

    if type_text.startswith("U") and len(type_text) > 1:
        try:
            return int(type_text[1:])
        except ValueError:
            pass

    raise DataViewerError(
        code=ErrorCode.EDIT_VALIDATION_FAILED,
        message="Unable to determine unicode dtype width.",
        operation="validation._validate_unicode_string",
        details={"dtype": target.str},
    )


def _decode_text(raw_value: bytes, *, strict: bool, operation: str) -> str:
    try:
        return raw_value.decode("utf-8", errors="strict" if strict else "ignore")
    except UnicodeDecodeError as exc:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Bytes value cannot be decoded with the configured text policy.",
            operation=operation,
            details={
                "raw_value_type": type(raw_value).__name__,
                "strict_text_encoding": strict,
                "encoding": "utf-8",
            },
        ) from exc


def _validate_structured(
    raw_value: Any,
    target: np.dtype,
    *,
    policy: ValidationPolicy,
) -> ScalarValue:
    if not isinstance(raw_value, dict):
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Structured dtype requires a mapping value.",
            operation="validation._validate_structured",
            details={"dtype": target.str, "raw_value_type": type(raw_value).__name__},
        )

    expected_fields = tuple(sorted(field for field in target.fields.keys()))
    if tuple(sorted(raw_value.keys())) != expected_fields:
        raise DataViewerError(
            code=ErrorCode.EDIT_VALIDATION_FAILED,
            message="Structured patch must include exactly target field names.",
            operation="validation._validate_structured",
            details={
                "expected_fields": list(expected_fields),
                "received_fields": sorted(raw_value.keys()),
            },
        )

    normalized: dict[str, ScalarValue] = {}
    for field_name in expected_fields:
        field_type = target.fields[field_name][0]
        normalized[field_name] = validate_edit_value(
            raw_value[field_name],
            dtype=field_type,
            policy=policy,
        )

    return normalized


def _parse_float(raw_value: Any, *, operation: str) -> float:
    if isinstance(raw_value, bool):
        return float(int(raw_value))
    if isinstance(raw_value, (int, float, np.number)):
        return float(raw_value)
    if isinstance(raw_value, str):
        try:
            return float(raw_value.strip())
        except ValueError as exc:
            raise DataViewerError(
                code=ErrorCode.EDIT_VALIDATION_FAILED,
                message="Floating value must be numeric.",
                operation=operation,
                details={"raw_value": str(raw_value)},
            ) from exc
    raise DataViewerError(
        code=ErrorCode.EDIT_VALIDATION_FAILED,
        message="Floating value is invalid type.",
        operation=operation,
        details={"raw_value_type": type(raw_value).__name__},
    )


__all__ = [
    "ValidationPolicy",
    "validate_edit_value",
]
