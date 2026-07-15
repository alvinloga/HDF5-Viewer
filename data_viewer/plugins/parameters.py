"""Parameter schema subset and validation for Plugin API v1."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class ParameterValidationError(ValueError):
    """Raised when a parameter schema or value is invalid."""


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    """One supported v1 parameter property."""

    name: str
    type: str
    title: str
    description: str
    default: object
    enum: tuple[object, ...] = ()
    minimum: float | int | None = None
    maximum: float | int | None = None


@dataclass(frozen=True, slots=True)
class ParameterSchema:
    """Validated immutable parameter schema."""

    properties: tuple[ParameterDefinition, ...]

    def property_names(self) -> tuple[str, ...]:
        """Return stable parameter names in schema order."""

        return tuple(property.name for property in self.properties)


def validate_parameter_schema(schema: Mapping[str, object]) -> ParameterSchema:
    """Validate the supported JSON Schema subset for plugin parameters."""

    if schema.get("type") != "object":
        raise ParameterValidationError("parameters_schema type must be object")
    if schema.get("additionalProperties") is not False:
        raise ParameterValidationError("parameters_schema must set additionalProperties to false")
    raw_properties = schema.get("properties", {})
    if not isinstance(raw_properties, dict):
        raise ParameterValidationError("parameters_schema properties must be an object")

    properties: list[ParameterDefinition] = []
    for name, value in raw_properties.items():
        if not isinstance(name, str) or not name:
            raise ParameterValidationError("parameter names must be non-empty strings")
        if not isinstance(value, dict):
            raise ParameterValidationError(f"{name} must be an object")
        properties.append(_parse_property(name, value))
    return ParameterSchema(properties=tuple(properties))


def default_parameters(schema: ParameterSchema) -> Mapping[str, object]:
    """Return immutable JSON-safe default values."""

    return MappingProxyType({property.name: property.default for property in schema.properties})


def validate_parameters(
    schema: ParameterSchema,
    values: Mapping[str, object],
) -> Mapping[str, object]:
    """Validate and normalize parameter values against the schema."""

    known = {property.name: property for property in schema.properties}
    unknown = sorted(set(values) - set(known))
    if unknown:
        raise ParameterValidationError(f"unknown parameter(s): {', '.join(unknown)}")
    missing = sorted(set(known) - set(values))
    if missing:
        raise ParameterValidationError(f"missing parameter(s): {', '.join(missing)}")
    normalized: dict[str, object] = {}
    for name, definition in known.items():
        normalized[name] = _validate_value(definition, values[name])
    return MappingProxyType(normalized)


def _parse_property(name: str, raw: Mapping[str, object]) -> ParameterDefinition:
    param_type = raw.get("type")
    if param_type not in {"string", "integer", "number", "boolean"}:
        raise ParameterValidationError(f"{name} uses unsupported parameter type {param_type!r}")
    if "default" not in raw:
        raise ParameterValidationError(f"{name} must define a default value")
    enum = raw.get("enum", ())
    if enum != () and not isinstance(enum, list):
        raise ParameterValidationError(f"{name} enum must be a list")
    minimum = raw.get("minimum")
    maximum = raw.get("maximum")
    definition = ParameterDefinition(
        name=name,
        type=str(param_type),
        title=str(raw.get("title") or name.replace("_", " ").title()),
        description=str(raw.get("description") or ""),
        default=raw["default"],
        enum=tuple(enum) if isinstance(enum, list) else (),
        minimum=minimum if isinstance(minimum, (int, float)) else None,
        maximum=maximum if isinstance(maximum, (int, float)) else None,
    )
    _validate_value(definition, definition.default)
    return definition


def _validate_value(definition: ParameterDefinition, value: object) -> object:
    if definition.type == "string":
        if not isinstance(value, str):
            raise ParameterValidationError(f"{definition.name} must be a string")
    elif definition.type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ParameterValidationError(f"{definition.name} must be an integer")
    elif definition.type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ParameterValidationError(f"{definition.name} must be a number")
    elif definition.type == "boolean":
        if not isinstance(value, bool):
            raise ParameterValidationError(f"{definition.name} must be a boolean")
    else:  # pragma: no cover - guarded by schema parser
        raise ParameterValidationError(f"{definition.name} has unsupported type")

    if definition.enum and value not in definition.enum:
        raise ParameterValidationError(f"{definition.name} must be one of {definition.enum}")
    if definition.minimum is not None and isinstance(value, (int, float)) and value < definition.minimum:
        raise ParameterValidationError(f"{definition.name} must be >= {definition.minimum}")
    if definition.maximum is not None and isinstance(value, (int, float)) and value > definition.maximum:
        raise ParameterValidationError(f"{definition.name} must be <= {definition.maximum}")
    return value


__all__ = [
    "ParameterDefinition",
    "ParameterSchema",
    "ParameterValidationError",
    "default_parameters",
    "validate_parameter_schema",
    "validate_parameters",
]
