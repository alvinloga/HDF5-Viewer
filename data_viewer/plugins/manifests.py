"""Plugin manifest validation for trusted built-in Plugin API v1 packages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from data_viewer.plugins.api import PLUGIN_API_VERSION, ResultKind


PLUGIN_MANIFEST_SCHEMA_VERSION = 1

_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*){2,}$")
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
_ENTRY_POINT_PREFIX = "data_viewer.plugins.builtin."

_MANIFEST_KEYS = {
    "schema_version",
    "api_version",
    "id",
    "name",
    "version",
    "description",
    "entry_point",
    "kind",
    "input",
    "parameters_schema",
    "result_kinds",
    "required_dependencies",
}
_REQUIRED_MANIFEST_KEYS = {
    "schema_version",
    "api_version",
    "id",
    "name",
    "version",
    "description",
    "entry_point",
    "kind",
    "input",
    "parameters_schema",
    "result_kinds",
}
_INPUT_KEYS = {
    "domains",
    "min_ndim",
    "max_ndim",
    "dtype_families",
    "requires_random_access",
    "supports_chunked_input",
    "supports_selection",
}


class PluginKind(StrEnum):
    """Manifest plugin categories used for deterministic ordering."""

    ANALYSIS = "analysis"
    VISUALIZATION = "visualization"


class PluginManifestError(ValueError):
    """Raised when a plugin manifest is malformed or unsupported."""


@dataclass(frozen=True, slots=True)
class PluginInputSpec:
    """Manifest input compatibility declaration."""

    domains: tuple[str, ...]
    min_ndim: int | None
    max_ndim: int | None
    dtype_families: tuple[str, ...]
    requires_random_access: bool
    supports_chunked_input: bool
    supports_selection: bool


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Typed validated plugin manifest."""

    schema_version: int
    api_version: int
    id: str
    name: str
    version: str
    description: str
    entry_point: str
    kind: PluginKind
    input: PluginInputSpec
    parameters_schema: dict[str, object]
    result_kinds: tuple[ResultKind, ...]
    required_dependencies: tuple[str, ...] = ()
    manifest_path: Path | None = None


def load_plugin_manifest(path: Path) -> PluginManifest:
    """Load and validate a plugin manifest file."""

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PluginManifestError(f"Invalid JSON plugin manifest {path}: {error}") from error
    except OSError as error:
        raise PluginManifestError(f"Could not read plugin manifest {path}: {error}") from error
    if not isinstance(data, dict):
        raise PluginManifestError(f"Plugin manifest {path} must be a JSON object")
    return validate_plugin_manifest(data, manifest_path=path)


def validate_plugin_manifest(
    data: dict[str, object],
    *,
    manifest_path: Path | None = None,
) -> PluginManifest:
    """Validate an untrusted manifest dictionary and return typed metadata."""

    _reject_unknown(data, _MANIFEST_KEYS, "manifest")
    _require_keys(data, _REQUIRED_MANIFEST_KEYS, "manifest")

    schema_version = _expect_int(data["schema_version"], "schema_version")
    if schema_version != PLUGIN_MANIFEST_SCHEMA_VERSION:
        raise PluginManifestError(
            f"Unsupported schema_version {schema_version}; expected {PLUGIN_MANIFEST_SCHEMA_VERSION}"
        )

    api_version = _expect_int(data["api_version"], "api_version")
    if api_version != PLUGIN_API_VERSION:
        raise PluginManifestError(f"Unsupported api_version {api_version}; expected {PLUGIN_API_VERSION}")

    plugin_id = _expect_str(data["id"], "id")
    if not _ID_RE.match(plugin_id):
        raise PluginManifestError("Plugin id must be stable reverse-DNS text")

    version = _expect_str(data["version"], "version")
    if not _SEMVER_RE.match(version):
        raise PluginManifestError("Plugin version must use semantic versioning")

    entry_point = _expect_str(data["entry_point"], "entry_point")
    if not entry_point.startswith(_ENTRY_POINT_PREFIX) or ":" not in entry_point:
        raise PluginManifestError("Plugin entry_point must resolve inside data_viewer.plugins.builtin")

    kind_text = _expect_str(data["kind"], "kind")
    try:
        kind = PluginKind(kind_text)
    except ValueError as error:
        raise PluginManifestError(f"Unsupported plugin kind: {kind_text}") from error

    result_kinds = _parse_result_kinds(data["result_kinds"])
    return PluginManifest(
        schema_version=schema_version,
        api_version=api_version,
        id=plugin_id,
        name=_expect_nonempty_str(data["name"], "name"),
        version=version,
        description=_expect_nonempty_str(data["description"], "description"),
        entry_point=entry_point,
        kind=kind,
        input=_parse_input_spec(data["input"]),
        parameters_schema=_parse_parameters_schema(data["parameters_schema"]),
        result_kinds=result_kinds,
        required_dependencies=_parse_required_dependencies(data.get("required_dependencies", [])),
        manifest_path=manifest_path,
    )


def _parse_input_spec(value: object) -> PluginInputSpec:
    if not isinstance(value, dict):
        raise PluginManifestError("input must be an object")
    _reject_unknown(value, _INPUT_KEYS, "input")
    _require_keys(value, _INPUT_KEYS, "input")
    min_ndim = _expect_optional_nonnegative_int(value["min_ndim"], "input.min_ndim")
    max_ndim = _expect_optional_nonnegative_int(value["max_ndim"], "input.max_ndim")
    if min_ndim is not None and max_ndim is not None and min_ndim > max_ndim:
        raise PluginManifestError("input min_ndim must be <= max_ndim")
    return PluginInputSpec(
        domains=_expect_str_tuple(value["domains"], "input.domains"),
        min_ndim=min_ndim,
        max_ndim=max_ndim,
        dtype_families=_expect_str_tuple(value["dtype_families"], "input.dtype_families"),
        requires_random_access=_expect_bool(
            value["requires_random_access"],
            "input.requires_random_access",
        ),
        supports_chunked_input=_expect_bool(
            value["supports_chunked_input"],
            "input.supports_chunked_input",
        ),
        supports_selection=_expect_bool(value["supports_selection"], "input.supports_selection"),
    )


def _parse_parameters_schema(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PluginManifestError("parameters_schema must be an object")
    if value.get("type") != "object":
        raise PluginManifestError("parameters_schema type must be object in v1")
    if value.get("additionalProperties") is not False:
        raise PluginManifestError("parameters_schema must set additionalProperties to false")
    return dict(value)


def _parse_result_kinds(value: object) -> tuple[ResultKind, ...]:
    if not isinstance(value, list) or not value:
        raise PluginManifestError("result_kinds must be a non-empty list")
    kinds: list[ResultKind] = []
    for item in value:
        text = _expect_str(item, "result_kinds")
        try:
            kinds.append(ResultKind(text))
        except ValueError as error:
            raise PluginManifestError(f"Unsupported result_kinds value: {text}") from error
    return tuple(kinds)


def _parse_required_dependencies(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PluginManifestError("required_dependencies must be a list")
    dependencies = tuple(_expect_nonempty_str(item, "required_dependencies") for item in value)
    if len(set(dependencies)) != len(dependencies):
        raise PluginManifestError("required_dependencies must not contain duplicates")
    return dependencies


def _reject_unknown(data: dict[str, object], allowed: set[str], label: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise PluginManifestError(f"unknown {label} keys: {', '.join(unknown)}")


def _require_keys(data: dict[str, object], required: set[str], label: str) -> None:
    missing = sorted(required - set(data))
    if missing:
        raise PluginManifestError(f"Missing {label} keys: {', '.join(missing)}")


def _expect_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise PluginManifestError(f"{field} must be a string")
    return value


def _expect_nonempty_str(value: object, field: str) -> str:
    text = _expect_str(value, field).strip()
    if not text:
        raise PluginManifestError(f"{field} must not be empty")
    return text


def _expect_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PluginManifestError(f"{field} must be an integer")
    return value


def _expect_optional_nonnegative_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    number = _expect_int(value, field)
    if number < 0:
        raise PluginManifestError(f"{field} must be non-negative")
    return number


def _expect_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise PluginManifestError(f"{field} must be a boolean")
    return value


def _expect_str_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PluginManifestError(f"{field} must be a non-empty list")
    items = tuple(_expect_nonempty_str(item, field) for item in value)
    if len(set(items)) != len(items):
        raise PluginManifestError(f"{field} must not contain duplicates")
    return items


__all__ = [
    "PLUGIN_MANIFEST_SCHEMA_VERSION",
    "PluginInputSpec",
    "PluginKind",
    "PluginManifest",
    "PluginManifestError",
    "load_plugin_manifest",
    "validate_plugin_manifest",
]
