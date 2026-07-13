"""Canonical resource identity and hierarchy node values."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from .capabilities import DataDomain, NodeKind
from .metadata import JsonValue


@dataclass(frozen=True, slots=True)
class ResourceId:
    """Canonical source URI plus adapter-stable node path."""

    source_uri: str
    node_path: str

    def __post_init__(self) -> None:
        _validate_source_uri(self.source_uri)
        object.__setattr__(
            self,
            "node_path",
            _normalize_node_path(self.node_path, allow_relative=False),
        )

    @classmethod
    def from_file(cls, path: Path, node_path: str = "/") -> "ResourceId":
        source_uri = path.resolve(strict=False).as_uri()
        return cls(
            source_uri=source_uri,
            node_path=_normalize_node_path(node_path, allow_relative=True),
        )

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ResourceId":
        return cls(
            source_uri=str(value["source_uri"]),
            node_path=str(value["node_path"]),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {"source_uri": self.source_uri, "node_path": self.node_path}


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    """Stable source fingerprint values used for conflict checks."""

    size_bytes: int
    modified_time_ns: int
    content_tag: str | None = None

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("fingerprint size must be non-negative")
        if self.modified_time_ns < 0:
            raise ValueError("fingerprint modified time must be non-negative")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "size_bytes": self.size_bytes,
            "modified_time_ns": self.modified_time_ns,
            "content_tag": self.content_tag,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "SourceFingerprint":
        content_tag = value.get("content_tag")
        if content_tag is not None and not isinstance(content_tag, str):
            raise ValueError("fingerprint content tag must be a string or null")
        return cls(
            size_bytes=_expect_int(value["size_bytes"], "fingerprint size"),
            modified_time_ns=_expect_int(
                value["modified_time_ns"],
                "fingerprint modified time",
            ),
            content_tag=content_tag,
        )


@dataclass(frozen=True, slots=True)
class ResourceNode:
    """A node in a source hierarchy without payload data."""

    resource_id: ResourceId
    name: str
    node_kind: NodeKind
    domain: DataDomain
    has_children: bool
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("resource node name must not be empty")
        object.__setattr__(self, "node_kind", NodeKind(self.node_kind))
        object.__setattr__(self, "domain", DataDomain(self.domain))

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "resource_id": self.resource_id.to_json(),
            "name": self.name,
            "node_kind": self.node_kind.value,
            "domain": self.domain.value,
            "has_children": self.has_children,
            "summary": self.summary,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> "ResourceNode":
        return cls(
            resource_id=ResourceId.from_json(
                _expect_mapping(value["resource_id"], "resource_id")
            ),
            name=str(value["name"]),
            node_kind=NodeKind(str(value["node_kind"])),
            domain=DataDomain(str(value["domain"])),
            has_children=_expect_bool(value["has_children"], "has_children"),
            summary=str(value.get("summary", "")),
        )


def _validate_source_uri(source_uri: str) -> None:
    if not source_uri:
        raise ValueError("source URI must not be empty")
    parsed = urlparse(source_uri)
    if not parsed.scheme:
        raise ValueError("source URI must include a scheme")
    if parsed.scheme == "file" and (parsed.query or parsed.fragment or not parsed.path):
        raise ValueError("file source URI must not include query or fragment")


def _normalize_node_path(node_path: str, *, allow_relative: bool) -> str:
    if not node_path:
        return "/"
    path = node_path.replace("\\", "/")
    if not path.startswith("/"):
        if not allow_relative:
            raise ValueError("resource node path must be absolute")
        path = f"/{path}"
    segments: list[str] = []
    for segment in path.split("/"):
        if segment == "":
            continue
        if segment in {".", ".."}:
            raise ValueError("resource node path cannot contain '.' or '..'")
        segments.append(segment)
    return "/" + "/".join(segments) if segments else "/"


def _expect_mapping(value: JsonValue, label: str) -> Mapping[str, JsonValue]:
    if isinstance(value, dict):
        return value
    raise ValueError(f"{label} must be a JSON object")


def _expect_int(value: JsonValue, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer JSON value")
    return value


def _expect_bool(value: JsonValue, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean JSON value")
    return value
