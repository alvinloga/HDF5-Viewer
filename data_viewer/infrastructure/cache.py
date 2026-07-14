"""Bounded disk cache with byte/entry/age budgets and deterministic eviction."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable


def _now_epoch() -> float:
    return time.time()


def _normalize_key(value: str) -> str:
    if not value:
        raise ValueError("cache key must be a non-empty string")
    return str(value)


def _safe_filename(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
    return f"cache-{digest}.bin"


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
        suffix=".tmp",
        prefix=path.name + ".",
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp_path.replace(path)


@dataclass(frozen=True, slots=True)
class CacheLimits:
    """Byte/entry/age limits for the managed cache."""

    max_total_bytes: int
    max_entry_count: int
    max_entry_age_seconds: int

    def __post_init__(self) -> None:
        for label, value in (
            ("max_total_bytes", self.max_total_bytes),
            ("max_entry_count", self.max_entry_count),
            ("max_entry_age_seconds", self.max_entry_age_seconds),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{label} must be an integer")
            if value < 0:
                raise ValueError(f"{label} must be non-negative")


DEFAULT_LIMITS = CacheLimits(
    max_total_bytes=2 * 1024 * 1024 * 1024,
    max_entry_count=256,
    max_entry_age_seconds=60 * 60 * 24 * 7,
)


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """A single cache item persisted as a bounded file."""

    key: str
    path: Path
    size_bytes: int
    created_at: float
    last_accessed_at: float
    checksum: str = ""

    def to_json(self) -> dict[str, float | int | str]:
        return {
            "key": self.key,
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "checksum": self.checksum,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> "CacheEntry":
        try:
            size_bytes_raw = value["size_bytes"]
            if not isinstance(size_bytes_raw, int):
                raise TypeError("size_bytes must be an integer")
            created_raw = value["created_at"]
            if not isinstance(created_raw, int | float):
                raise TypeError("created_at must be numeric")
            last_access_raw = value["last_accessed_at"]
            if not isinstance(last_access_raw, int | float):
                raise TypeError("last_accessed_at must be numeric")
            checksum_raw = value.get("checksum", "")
            if not isinstance(checksum_raw, str):
                raise TypeError("checksum must be a string")
            return cls(
                key=str(value["key"]),
                path=Path(str(value["path"])),
                size_bytes=size_bytes_raw,
                created_at=float(created_raw),
                last_accessed_at=float(last_access_raw),
                checksum=checksum_raw,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid cache entry payload: {error}") from error


@dataclass
class BoundedCache:
    """
    Minimal file-backed LRU-ish cache for extracted temporary artifacts.

    Keys are mapped to deterministic files inside a cache root directory.
    """

    root: Path
    limits: CacheLimits = DEFAULT_LIMITS
    clock: Callable[[], float] = _now_epoch
    index_name: str = "cache-index.json"
    tombstone_name: str = "cache-tombstone.json"
    index: dict[str, CacheEntry] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.root = self.root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not isinstance(self.limits, CacheLimits):
            raise TypeError("limits must be CacheLimits")
        self._load_index()

    def __len__(self) -> int:
        self.cleanup()
        return len(self.index)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    @property
    def current_bytes(self) -> int:
        self.cleanup()
        return self._total_bytes()

    @property
    def count(self) -> int:
        return len(self)

    def get(self, key: str) -> Path | None:
        """Return the cached file path and update access time."""
        key = _normalize_key(key)
        self._refresh()
        entry = self.index.get(key)
        if entry is None or not entry.path.exists():
            if entry is not None:
                self._remove_entry(key, reason="missing")
            return None

        now = self.clock()
        self.index[key] = replace(
            entry,
            last_accessed_at=now,
        )
        self._persist()
        return entry.path

    def put_bytes(self, key: str, data: bytes) -> Path:
        """
        Write bytes into the cache and return the concrete cached file path.

        Existing keys are replaced.
        """
        key = _normalize_key(key)
        now = self.clock()
        target_name = _safe_filename(key)
        target_path = self.root / target_name
        checksum = hashlib.sha256(data).hexdigest()
        size_bytes = len(data)

        with tempfile.NamedTemporaryFile(
            mode="wb", dir=self.root, delete=False, suffix=".tmp", prefix="cache-write-"
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        os.replace(temp_path, target_path)

        existing = self.index.get(key)
        if existing is not None and existing.path != target_path:
            self._remove_entry(key, reason="replace")

        self.index[key] = CacheEntry(
            key=key,
            path=target_path,
            size_bytes=size_bytes,
            created_at=now,
            last_accessed_at=now,
            checksum=checksum,
        )
        self._enforce_limits()
        self._persist()
        return target_path

    def put_path(self, key: str, source: Path) -> Path:
        """Copy a file into cache and return the new cached file path."""
        key = _normalize_key(key)
        source = source.expanduser()
        if not source.exists():
            raise FileNotFoundError(f"cache source missing: {source}")

        now = self.clock()
        checksum = hashlib.sha256()
        size_bytes = 0
        with source.open("rb") as source_handle, tempfile.NamedTemporaryFile(
            mode="wb", dir=self.root, delete=False, suffix=".tmp", prefix="cache-write-"
        ) as handle:
            temp_path = Path(handle.name)
            while chunk := source_handle.read(1024 * 1024):
                checksum.update(chunk)
                size_bytes += len(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        target_path = self.root / _safe_filename(key)
        os.replace(temp_path, target_path)

        existing = self.index.get(key)
        if existing is not None and existing.path != target_path:
            self._remove_entry(key, reason="replace")

        self.index[key] = CacheEntry(
            key=key,
            path=target_path,
            size_bytes=size_bytes,
            created_at=now,
            last_accessed_at=now,
            checksum=checksum.hexdigest(),
        )
        self._enforce_limits()
        self._persist()
        return target_path

    def cleanup(self) -> None:
        """Remove expired or missing entries."""
        self._refresh()

    def clear(self) -> None:
        """Remove every cache entry and all associated files."""
        for key in list(self.index):
            self._remove_entry(key, reason="clear")
        self._persist()

    def write_tombstone(self, *, reason: str = "") -> Path:
        """Write a startup/shutdown tombstone for startup cleanup diagnostics."""
        tombstone = self.root / self.tombstone_name
        payload = {
            "created_at": self.clock(),
            "count": len(self.index),
            "total_bytes": self._total_bytes(),
            "reason": reason,
        }
        _atomic_write_json(tombstone, payload)
        return tombstone

    def _refresh(self) -> None:
        self._remove_expired()
        self._remove_stale_files()
        self._enforce_limits()

    def _remove_expired(self) -> None:
        now = self.clock()
        if self.limits.max_entry_age_seconds <= 0:
            return
        for key, entry in list(self.index.items()):
            age = now - entry.created_at
            if age > self.limits.max_entry_age_seconds:
                self._remove_entry(key, reason="expired")

    def _remove_stale_files(self) -> None:
        for key, entry in list(self.index.items()):
            if not entry.path.exists():
                self._remove_entry(key, reason="stale-file")

    def _enforce_limits(self) -> None:
        if self.limits.max_entry_count <= 0 and self.limits.max_total_bytes <= 0:
            return

        while True:
            over_count = (
                self.limits.max_entry_count > 0 and len(self.index) > self.limits.max_entry_count
            )
            total_bytes = self._total_bytes()
            over_bytes = (
                self.limits.max_total_bytes > 0
                and total_bytes > self.limits.max_total_bytes
            )
            if not over_count and not over_bytes:
                return

            oldest_key: str | None = None
            oldest_access = self.clock()
            for key, entry in self.index.items():
                if oldest_key is None or entry.last_accessed_at < oldest_access:
                    oldest_key = key
                    oldest_access = entry.last_accessed_at
            if oldest_key is None:
                return
            self._remove_entry(oldest_key, reason="evict")

    def _total_bytes(self) -> int:
        total = 0
        for entry in self.index.values():
            if not entry.path.exists():
                continue
            total += entry.size_bytes
        return total

    def _remove_entry(self, key: str, *, reason: str) -> None:
        entry = self.index.pop(key, None)
        if entry is None:
            return
        try:
            entry.path.unlink()
        except OSError:
            pass
        if reason:
            self._append_tombstone(
                {
                    "key": entry.key,
                    "path": str(entry.path),
                    "reason": reason,
                    "at": self.clock(),
                }
            )
        self._persist()

    def _append_tombstone(self, record: dict[str, object]) -> None:
        tombstone = self.root / self.tombstone_name
        tombstone_records: list[object]
        if tombstone.exists():
            try:
                payload = json.loads(tombstone.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    tombstone_records = payload
                elif isinstance(payload, dict):
                    tombstone_records = payload.get("records", [])
                    if not isinstance(tombstone_records, list):
                        tombstone_records = []
                else:
                    tombstone_records = []
            except (OSError, json.JSONDecodeError):
                tombstone_records = []
        else:
            tombstone_records = []
        tombstone_records.append(record)
        _atomic_write_json(tombstone, tombstone_records)

    def _load_index(self) -> None:
        index_path = self.root / self.index_name
        if not index_path.exists():
            return
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            entries = payload.get("entries")
            if not isinstance(entries, list):
                return
            for raw in entries:
                if not isinstance(raw, dict):
                    continue
                entry = CacheEntry.from_json(raw)
                self.index[entry.key] = entry
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            # Corrupt index is non-fatal; keep an empty cache and continue.
            self.index = {}
            return

        self._refresh()

    def _persist(self) -> None:
        payload = {
            "schema_version": 1,
            "updated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock())),
            "entries": [entry.to_json() for entry in self.index.values()],
        }
        _atomic_write_json(self.root / self.index_name, payload)
