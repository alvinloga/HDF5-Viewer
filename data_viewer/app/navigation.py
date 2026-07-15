"""Recent files, favorites, semantic history, and global-search models."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
import re
from pathlib import Path
from typing import cast

from data_viewer.domain import JsonValue
from data_viewer.tasks import CancellationToken


@dataclass(frozen=True, slots=True)
class RecentFile:
    """Application-config recent file entry."""

    path: Path
    pinned: bool = False
    missing: bool = False

    def __post_init__(self) -> None:
        resolved = self.path.expanduser().resolve()
        object.__setattr__(self, "path", resolved)
        object.__setattr__(self, "missing", not resolved.exists())

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "path": str(self.path),
            "pinned": self.pinned,
            "missing": self.missing,
        }


@dataclass(frozen=True, slots=True)
class ResourceFavorite:
    """Favorite resource identified by source ID and node path, not a label."""

    source_id: str
    resource_path: str
    resource_domain: str
    label: str

    def __post_init__(self) -> None:
        for name, value in (
            ("source_id", self.source_id),
            ("resource_path", self.resource_path),
            ("resource_domain", self.resource_domain),
            ("label", self.label),
        ):
            _require_non_empty(value, name)

    @property
    def identity(self) -> tuple[str, str]:
        return (self.source_id, self.resource_path)

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source_id,
            "resource_path": self.resource_path,
            "resource_domain": self.resource_domain,
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class NavigationLocation:
    """Semantic navigation target owned by application state."""

    source_id: str
    resource_path: str
    view_id: str
    split_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("source_id", self.source_id),
            ("resource_path", self.resource_path),
            ("view_id", self.view_id),
            ("split_id", self.split_id),
        ):
            _require_non_empty(value, name)


@dataclass(frozen=True, slots=True)
class NavigationHistory:
    """Immutable back/forward stack for resource/view history."""

    back_stack: tuple[NavigationLocation, ...] = ()
    current: NavigationLocation | None = None
    forward_stack: tuple[NavigationLocation, ...] = ()

    def push(
        self,
        *,
        source_id: str,
        resource_path: str,
        view_id: str,
        split_id: str,
    ) -> "NavigationHistory":
        next_location = NavigationLocation(
            source_id=source_id,
            resource_path=resource_path,
            view_id=view_id,
            split_id=split_id,
        )
        if self.current == next_location:
            return self
        next_back = self.back_stack + ((self.current,) if self.current is not None else ())
        return NavigationHistory(back_stack=next_back, current=next_location, forward_stack=())

    def back(self) -> "NavigationHistory":
        if not self.back_stack or self.current is None:
            return self
        previous = self.back_stack[-1]
        return NavigationHistory(
            back_stack=self.back_stack[:-1],
            current=previous,
            forward_stack=(self.current, *self.forward_stack),
        )

    def forward(self) -> "NavigationHistory":
        if not self.forward_stack or self.current is None:
            return self
        next_location = self.forward_stack[0]
        return NavigationHistory(
            back_stack=(*self.back_stack, self.current),
            current=next_location,
            forward_stack=self.forward_stack[1:],
        )


@dataclass(frozen=True, slots=True)
class SearchIndexEntry:
    """Searchable resource summary built from open source metadata."""

    source_id: str
    resource_path: str
    name: str
    resource_domain: str
    dtype: str
    shape: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("source_id", self.source_id),
            ("resource_path", self.resource_path),
            ("name", self.name),
            ("resource_domain", self.resource_domain),
            ("dtype", self.dtype),
        ):
            _require_non_empty(value, label)
        object.__setattr__(self, "shape", tuple(self.shape))


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Path/name/domain/dtype/shape search filters."""

    text: str = ""
    name: str = ""
    domains: tuple[str, ...] = ()
    dtype: str = ""
    shape: tuple[int, ...] | None = None
    regex: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "domains", tuple(self.domains))
        if self.shape is not None:
            object.__setattr__(self, "shape", tuple(self.shape))


class SearchQueryError(ValueError):
    """Raised when a search query is invalid."""

    def __init__(self, message: str, *, reason: str) -> None:
        self.reason = reason
        super().__init__(message)


class NavigationService:
    """Application-owned navigation state that stays outside `.dvw` workspaces."""

    def __init__(self, *, max_recent: int = 20) -> None:
        self._max_recent = max_recent
        self._recent: OrderedDict[str, RecentFile] = OrderedDict()
        self._favorites: OrderedDict[tuple[str, str], ResourceFavorite] = OrderedDict()

    @property
    def recent_files(self) -> tuple[RecentFile, ...]:
        return tuple(self._recent.values())

    @property
    def favorites(self) -> tuple[ResourceFavorite, ...]:
        return tuple(self._favorites.values())

    def add_recent(self, path: Path) -> None:
        recent = RecentFile(path)
        key = str(recent.path)
        pinned = self._recent[key].pinned if key in self._recent else False
        self._recent.pop(key, None)
        self._recent[key] = replace(recent, pinned=pinned)
        self._trim_recent()

    def set_pinned(self, path: Path, pinned: bool) -> None:
        recent = RecentFile(path)
        key = str(recent.path)
        self._recent[key] = replace(recent, pinned=pinned)
        self._reorder_recent()
        self._trim_recent()

    def recent_remediations(self, path: Path) -> tuple[str, ...]:
        recent = RecentFile(path)
        if recent.missing:
            return ("locate", "remove")
        return ()

    def add_favorite(self, favorite: ResourceFavorite) -> None:
        self._favorites[favorite.identity] = favorite

    def to_app_config(self) -> dict[str, JsonValue]:
        return {
            "recent_files": [recent.to_json() for recent in self.recent_files],
            "favorites": [favorite.to_json() for favorite in self.favorites],
        }

    @classmethod
    def from_app_config(cls, value: Mapping[str, JsonValue]) -> "NavigationService":
        service = cls()
        for item in _expect_list(value.get("recent_files", []), "recent_files"):
            recent = _expect_mapping(item, "recent file")
            path = Path(str(recent["path"]))
            service.add_recent(path)
            service.set_pinned(path, _expect_bool(recent.get("pinned", False), "pinned"))
        for item in _expect_list(value.get("favorites", []), "favorites"):
            favorite = _expect_mapping(item, "favorite")
            service.add_favorite(
                ResourceFavorite(
                    source_id=str(favorite["source_id"]),
                    resource_path=str(favorite["resource_path"]),
                    resource_domain=str(favorite["resource_domain"]),
                    label=str(favorite["label"]),
                )
            )
        return service

    def search(
        self,
        entries: Iterable[SearchIndexEntry],
        query: SearchQuery,
        *,
        cancellation: CancellationToken,
    ) -> dict[str, tuple[SearchIndexEntry, ...]]:
        path_pattern = _compile_pattern(query.text, regex=query.regex) if query.text else None
        name_pattern = _compile_pattern(query.name, regex=query.regex) if query.name else None
        grouped: dict[str, list[SearchIndexEntry]] = {}
        domains = set(query.domains)
        for entry in entries:
            cancellation.raise_if_cancelled(operation="navigation.search")
            if domains and entry.resource_domain not in domains:
                continue
            if query.dtype and query.dtype.lower() not in entry.dtype.lower():
                continue
            if query.shape is not None and entry.shape != query.shape:
                continue
            if path_pattern is not None and not path_pattern.search(entry.resource_path):
                continue
            if name_pattern is not None and not name_pattern.search(entry.name):
                continue
            grouped.setdefault(entry.resource_domain, []).append(entry)
        return {key: tuple(value) for key, value in grouped.items()}

    def _trim_recent(self) -> None:
        self._reorder_recent()
        while len(self._recent) > self._max_recent:
            for key, item in self._recent.items():
                if not item.pinned:
                    self._recent.pop(key)
                    break
            else:
                self._recent.popitem(last=False)

    def _reorder_recent(self) -> None:
        items = sorted(self._recent.values(), key=lambda item: (not item.pinned, str(item.path)))
        self._recent = OrderedDict((str(item.path), item) for item in items)


def _compile_pattern(pattern: str, *, regex: bool) -> re.Pattern[str]:
    if not regex:
        pattern = re.escape(pattern)
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise SearchQueryError("invalid search regular expression", reason="invalid_regex") from exc


def _require_non_empty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")


def _expect_list(value: object, label: str) -> list[JsonValue]:
    if isinstance(value, list):
        return cast(list[JsonValue], value)
    raise ValueError(f"{label} must be an array")


def _expect_mapping(value: object, label: str) -> Mapping[str, JsonValue]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, JsonValue], value)
    raise ValueError(f"{label} must be an object")


def _expect_bool(value: object, label: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{label} must be boolean")


__all__ = [
    "NavigationHistory",
    "NavigationLocation",
    "NavigationService",
    "RecentFile",
    "ResourceFavorite",
    "SearchIndexEntry",
    "SearchQuery",
    "SearchQueryError",
]
