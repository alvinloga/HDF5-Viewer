"""Versioned `.dvw` workspace manifest model and deterministic persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from importlib import resources
import json
from pathlib import Path
from typing import cast

from data_viewer.domain import FrozenJsonMapping, JsonValue, SourceFingerprint
from data_viewer.persistence.transaction import (
    AtomicReplacementService,
    FailureInjector,
)


WORKSPACE_SCHEMA_VERSION = 1
WORKSPACE_SCHEMA_URI = "https://dataviewer.local/schemas/workspace-v1.schema.json"
FORBIDDEN_KEYS = {
    "credentials",
    "password",
    "token",
    "secret",
    "file_contents",
    "bulk_data",
    "embedded_data",
    "python_object",
    "executable",
    "plugin_instance",
}


class WorkspaceValidationError(ValueError):
    """Raised when a workspace manifest is invalid or unsafe."""


class WorkspaceVersionError(WorkspaceValidationError):
    """Raised when a workspace uses an unsupported newer schema version."""


@dataclass(frozen=True, slots=True)
class WorkspaceSource:
    """External source reference persisted in a workspace."""

    source_id: str
    display_name: str
    path: str
    path_kind: str
    format_id: str
    fingerprint: Mapping[str, JsonValue]
    open_options: Mapping[str, JsonValue] = field(default_factory=dict)
    status_hint: str = "available"
    extensions: Mapping[str, JsonValue] = field(default_factory=dict)
    unknown_fields: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.display_name, "display_name")
        _require_non_empty(self.path, "path")
        if self.path_kind not in {"relative", "absolute"}:
            raise WorkspaceValidationError("source path_kind must be relative or absolute")
        _require_non_empty(self.format_id, "format_id")
        if "$" in self.path or "%" in self.path:
            raise WorkspaceValidationError("workspace source paths must not use interpolation")
        object.__setattr__(self, "fingerprint", FrozenJsonMapping(self.fingerprint))
        object.__setattr__(self, "open_options", FrozenJsonMapping(self.open_options))
        object.__setattr__(self, "extensions", FrozenJsonMapping(self.extensions))
        object.__setattr__(self, "unknown_fields", FrozenJsonMapping(self.unknown_fields))

    def to_json(self) -> dict[str, JsonValue]:
        data = FrozenJsonMapping(self.unknown_fields).to_json()
        data.update(
            {
                "source_id": self.source_id,
                "display_name": self.display_name,
                "path": self.path,
                "path_kind": self.path_kind,
                "format_id": self.format_id,
                "fingerprint": FrozenJsonMapping(self.fingerprint).to_json(),
                "open_options": FrozenJsonMapping(self.open_options).to_json(),
                "status_hint": self.status_hint,
                "extensions": FrozenJsonMapping(self.extensions).to_json(),
            }
        )
        return data

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "WorkspaceSource":
        known = {
            "source_id",
            "display_name",
            "path",
            "path_kind",
            "format_id",
            "fingerprint",
            "open_options",
            "status_hint",
            "extensions",
        }
        return cls(
            source_id=str(value["source_id"]),
            display_name=str(value["display_name"]),
            path=str(value["path"]),
            path_kind=str(value["path_kind"]),
            format_id=str(value["format_id"]),
            fingerprint=_expect_mapping(value.get("fingerprint", {}), "source fingerprint"),
            open_options=_expect_mapping(value.get("open_options", {}), "source open_options"),
            status_hint=str(value.get("status_hint", "available")),
            extensions=_expect_mapping(value.get("extensions", {}), "source extensions"),
            unknown_fields={key: item for key, item in value.items() if key not in known},
        )


@dataclass(frozen=True, slots=True)
class WorkspaceView:
    """Semantic workspace view state."""

    view_id: str
    source_id: str
    resource_path: str
    resource_domain: str
    view_type: str
    selection: Mapping[str, JsonValue]
    cursor: tuple[int, ...] = ()
    scroll: Mapping[str, JsonValue] = field(default_factory=dict)
    display: Mapping[str, JsonValue] = field(default_factory=dict)
    split_group: str = ""
    pinned: bool = False
    extensions: Mapping[str, JsonValue] = field(default_factory=dict)
    unknown_fields: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (
            ("view_id", self.view_id),
            ("source_id", self.source_id),
            ("resource_path", self.resource_path),
            ("resource_domain", self.resource_domain),
            ("view_type", self.view_type),
        ):
            _require_non_empty(value, label)
        object.__setattr__(self, "selection", FrozenJsonMapping(self.selection))
        object.__setattr__(self, "cursor", tuple(self.cursor))
        object.__setattr__(self, "scroll", FrozenJsonMapping(self.scroll))
        object.__setattr__(self, "display", FrozenJsonMapping(self.display))
        object.__setattr__(self, "extensions", FrozenJsonMapping(self.extensions))
        object.__setattr__(self, "unknown_fields", FrozenJsonMapping(self.unknown_fields))

    def to_json(self) -> dict[str, JsonValue]:
        data = FrozenJsonMapping(self.unknown_fields).to_json()
        data.update(
            {
                "view_id": self.view_id,
                "source_id": self.source_id,
                "resource_path": self.resource_path,
                "resource_domain": self.resource_domain,
                "view_type": self.view_type,
                "selection": FrozenJsonMapping(self.selection).to_json(),
                "cursor": list(self.cursor),
                "scroll": FrozenJsonMapping(self.scroll).to_json(),
                "display": FrozenJsonMapping(self.display).to_json(),
                "split_group": self.split_group,
                "pinned": self.pinned,
                "extensions": FrozenJsonMapping(self.extensions).to_json(),
            }
        )
        return data

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "WorkspaceView":
        known = {
            "view_id",
            "source_id",
            "resource_path",
            "resource_domain",
            "view_type",
            "selection",
            "cursor",
            "scroll",
            "display",
            "split_group",
            "pinned",
            "extensions",
        }
        return cls(
            view_id=str(value["view_id"]),
            source_id=str(value["source_id"]),
            resource_path=str(value["resource_path"]),
            resource_domain=str(value["resource_domain"]),
            view_type=str(value["view_type"]),
            selection=_expect_mapping(value.get("selection", {"kind": "all"}), "view selection"),
            cursor=tuple(_expect_int(item, "cursor item") for item in _expect_list(value.get("cursor", []), "cursor")),
            scroll=_expect_mapping(value.get("scroll", {}), "view scroll"),
            display=_expect_mapping(value.get("display", {}), "view display"),
            split_group=str(value.get("split_group", "")),
            pinned=_expect_bool(value.get("pinned", False), "view pinned"),
            extensions=_expect_mapping(value.get("extensions", {}), "view extensions"),
            unknown_fields={key: item for key, item in value.items() if key not in known},
        )


@dataclass(frozen=True, slots=True)
class WorkspaceManifest:
    """Data Viewer workspace manifest with runtime dirty flags kept separate."""

    workspace_id: str
    title: str
    created_at: str
    updated_at: str
    schema_version: int = WORKSPACE_SCHEMA_VERSION
    app: Mapping[str, JsonValue] = field(
        default_factory=lambda: {"name": "Data Viewer", "version": "1.0.0"}
    )
    path_base: str = "workspace_directory"
    sources: tuple[WorkspaceSource, ...] = ()
    views: tuple[WorkspaceView, ...] = ()
    comparisons: tuple[Mapping[str, JsonValue], ...] = ()
    plugin_results: tuple[Mapping[str, JsonValue], ...] = ()
    layout: Mapping[str, JsonValue] = field(default_factory=dict)
    preferences: Mapping[str, JsonValue] = field(default_factory=dict)
    extensions: Mapping[str, JsonValue] = field(default_factory=dict)
    unknown_fields: Mapping[str, JsonValue] = field(default_factory=dict)
    source_dirty: bool = False
    workspace_dirty: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceVersionError(f"Unsupported workspace schema_version {self.schema_version}")
        for label, value in (
            ("workspace_id", self.workspace_id),
            ("title", self.title),
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            _require_non_empty(value, label)
        if self.path_base != "workspace_directory":
            raise WorkspaceValidationError("path_base must be workspace_directory")
        object.__setattr__(self, "app", FrozenJsonMapping(self.app))
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "views", tuple(self.views))
        object.__setattr__(self, "comparisons", tuple(FrozenJsonMapping(item) for item in self.comparisons))
        object.__setattr__(self, "plugin_results", tuple(FrozenJsonMapping(item) for item in self.plugin_results))
        object.__setattr__(self, "layout", FrozenJsonMapping(self.layout))
        object.__setattr__(self, "preferences", FrozenJsonMapping(self.preferences))
        object.__setattr__(self, "extensions", FrozenJsonMapping(self.extensions))
        object.__setattr__(self, "unknown_fields", FrozenJsonMapping(self.unknown_fields))

    def with_updates(self, **updates: object) -> "WorkspaceManifest":
        """Return a modified manifest; dirty flags remain runtime-only."""

        return cast("WorkspaceManifest", replace(self, **updates))  # type: ignore[arg-type]

    def to_json(self) -> dict[str, JsonValue]:
        data = FrozenJsonMapping(self.unknown_fields).to_json()
        data.update(
            {
                "$schema": WORKSPACE_SCHEMA_URI,
                "schema_version": self.schema_version,
                "app": FrozenJsonMapping(self.app).to_json(),
                "workspace_id": self.workspace_id,
                "title": self.title,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "path_base": self.path_base,
                "sources": [source.to_json() for source in self.sources],
                "views": [view.to_json() for view in self.views],
                "comparisons": [FrozenJsonMapping(item).to_json() for item in self.comparisons],
                "plugin_results": [FrozenJsonMapping(item).to_json() for item in self.plugin_results],
                "layout": FrozenJsonMapping(self.layout).to_json(),
                "preferences": FrozenJsonMapping(self.preferences).to_json(),
                "extensions": FrozenJsonMapping(self.extensions).to_json(),
            }
        )
        return data

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "WorkspaceManifest":
        version = _expect_int(value.get("schema_version"), "schema_version")
        if version > WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceVersionError(f"Unsupported newer workspace schema_version {version}")
        if version != WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceValidationError(f"Unsupported workspace schema_version {version}")
        known = {
            "$schema",
            "schema_version",
            "app",
            "workspace_id",
            "title",
            "created_at",
            "updated_at",
            "path_base",
            "sources",
            "views",
            "comparisons",
            "plugin_results",
            "layout",
            "preferences",
            "extensions",
        }
        return cls(
            schema_version=version,
            app=_expect_mapping(value.get("app", {}), "app"),
            workspace_id=str(value["workspace_id"]),
            title=str(value["title"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            path_base=str(value.get("path_base", "workspace_directory")),
            sources=tuple(
                WorkspaceSource.from_json(_expect_mapping(item, "source"))
                for item in _expect_list(value.get("sources", []), "sources")
            ),
            views=tuple(
                WorkspaceView.from_json(_expect_mapping(item, "view"))
                for item in _expect_list(value.get("views", []), "views")
            ),
            comparisons=tuple(
                _expect_mapping(item, "comparison")
                for item in _expect_list(value.get("comparisons", []), "comparisons")
            ),
            plugin_results=tuple(
                _expect_mapping(item, "plugin result")
                for item in _expect_list(value.get("plugin_results", []), "plugin_results")
            ),
            layout=_expect_mapping(value.get("layout", {}), "layout"),
            preferences=_expect_mapping(value.get("preferences", {}), "preferences"),
            extensions=_expect_mapping(value.get("extensions", {}), "extensions"),
            unknown_fields={key: item for key, item in value.items() if key not in known},
        )


class WorkspaceService:
    """Validate, serialize, load, and atomically save `.dvw` manifests."""

    def __init__(
        self,
        *,
        max_bytes: int = 4 * 1024 * 1024,
        max_depth: int = 64,
        transaction: AtomicReplacementService | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._max_depth = max_depth
        self._transaction = transaction or AtomicReplacementService()

    def schema_path(self) -> Path:
        with resources.as_file(
            resources.files("data_viewer.workspace.schema").joinpath("workspace-v1.schema.json")
        ) as path:
            return path

    def dumps(self, manifest: WorkspaceManifest) -> str:
        payload = manifest.with_updates(source_dirty=False, workspace_dirty=False).to_json()
        self._validate_json(payload)
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def loads(self, text: str) -> WorkspaceManifest:
        encoded = text.encode("utf-8")
        if len(encoded) > self._max_bytes:
            raise WorkspaceValidationError("workspace manifest exceeds workspace byte budget")
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WorkspaceValidationError("workspace manifest is not valid JSON") from exc
        _check_depth(value, max_depth=self._max_depth)
        _reject_forbidden_keys(value)
        if not isinstance(value, Mapping):
            raise WorkspaceValidationError("workspace manifest must be a JSON object")
        mapping = cast(Mapping[str, JsonValue], value)
        version = mapping.get("schema_version")
        if isinstance(version, int) and not isinstance(version, bool) and version > WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceVersionError(f"Unsupported newer workspace schema_version {version}")
        self._validate_json(mapping)
        return WorkspaceManifest.from_json(mapping)

    def load(self, path: Path) -> WorkspaceManifest:
        return self.loads(path.read_text(encoding="utf-8"))

    def save(
        self,
        path: Path,
        manifest: WorkspaceManifest,
        *,
        failure_injector: FailureInjector | None = None,
    ) -> None:
        text = self.dumps(manifest)
        payload = text.encode("utf-8")

        def write_payload(destination: Path) -> None:
            destination.write_bytes(payload)

        def validate_payload(candidate: Path) -> SourceFingerprint:
            self.load(candidate)
            stat = candidate.stat()
            return SourceFingerprint(size_bytes=stat.st_size, modified_time_ns=stat.st_mtime_ns)

        self._transaction.run_replacement(
            path if path.exists() else None,
            path,
            write_payload=write_payload,
            validate_payload=validate_payload,
            estimated_output_bytes=len(payload),
            failure_injector=failure_injector,
        )

    def resolve_source_path(self, source: WorkspaceSource, workspace_path: Path) -> Path:
        if source.path_kind == "absolute":
            return Path(source.path)
        if Path(source.path).is_absolute():
            raise WorkspaceValidationError("relative workspace source path is absolute")
        return (workspace_path.parent / source.path).resolve()

    def _load_schema(self) -> Mapping[str, object]:
        return json.loads(self.schema_path().read_text(encoding="utf-8"))

    def _validate_json(self, value: Mapping[str, object]) -> None:
        _validate_workspace_shape(value)


def _require_non_empty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise WorkspaceValidationError(f"{label} must be a non-empty string")


def _reject_forbidden_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise WorkspaceValidationError(f"forbidden workspace key: {key}")
            _reject_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _check_depth(value: object, *, max_depth: int, depth: int = 0) -> None:
    if depth > max_depth:
        raise WorkspaceValidationError("workspace manifest exceeds workspace nesting budget")
    if isinstance(value, Mapping):
        for item in value.values():
            _check_depth(item, max_depth=max_depth, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_depth(item, max_depth=max_depth, depth=depth + 1)


def _expect_mapping(value: object, label: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise WorkspaceValidationError(f"{label} must be an object")
    return cast(Mapping[str, JsonValue], value)


def _expect_list(value: object, label: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise WorkspaceValidationError(f"{label} must be an array")
    return cast(list[JsonValue], value)


def _expect_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise WorkspaceValidationError(f"{label} must be boolean")
    return value


def _expect_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkspaceValidationError(f"{label} must be an integer")
    return value


def _validate_workspace_shape(value: Mapping[str, object]) -> None:
    required = (
        "schema_version",
        "app",
        "workspace_id",
        "title",
        "created_at",
        "updated_at",
        "path_base",
        "sources",
        "views",
        "comparisons",
        "plugin_results",
        "layout",
        "preferences",
        "extensions",
    )
    for key in required:
        if key not in value:
            raise WorkspaceValidationError(f"workspace schema validation failed at <root>: missing {key}")
    if value["schema_version"] != WORKSPACE_SCHEMA_VERSION:
        raise WorkspaceValidationError("workspace schema validation failed at schema_version")
    _expect_mapping(value["app"], "app")
    for key in ("workspace_id", "title", "created_at", "updated_at"):
        if not isinstance(value[key], str) or not value[key]:
            raise WorkspaceValidationError(f"workspace schema validation failed at {key}")
    if value["path_base"] != "workspace_directory":
        raise WorkspaceValidationError("workspace schema validation failed at path_base")
    for label in ("sources", "views", "comparisons", "plugin_results"):
        _expect_list(value[label], label)
    for label in ("layout", "preferences", "extensions"):
        _expect_mapping(value[label], label)
    for source in _expect_list(value["sources"], "sources"):
        source_map = _expect_mapping(source, "source")
        for key in ("source_id", "display_name", "path", "path_kind", "format_id", "fingerprint"):
            if key not in source_map:
                raise WorkspaceValidationError(f"workspace schema validation failed at sources.{key}")
        if source_map["path_kind"] not in {"relative", "absolute"}:
            raise WorkspaceValidationError("workspace schema validation failed at sources.path_kind")
    for view in _expect_list(value["views"], "views"):
        view_map = _expect_mapping(view, "view")
        for key in ("view_id", "source_id", "resource_path", "resource_domain", "view_type", "selection"):
            if key not in view_map:
                raise WorkspaceValidationError(f"workspace schema validation failed at views.{key}")
