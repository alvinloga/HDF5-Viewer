"""Managed extraction cache for random-access gzip wrappers."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.infrastructure.cache import BoundedCache, CacheLimits
from data_viewer.sources import api as source_api


@dataclass(frozen=True, slots=True)
class ExtractionLimits:
    """Budgets for managed random-access gzip extraction."""

    max_decompressed_bytes: int = 20 * 1024 * 1024 * 1024
    max_compression_ratio: float = 1000.0
    min_free_bytes: int = 0
    max_total_cache_bytes: int = 2 * 1024 * 1024 * 1024
    max_entry_count: int = 256
    max_entry_age_seconds: int = 60 * 60 * 24 * 7

    def __post_init__(self) -> None:
        for label, value in (
            ("max_decompressed_bytes", self.max_decompressed_bytes),
            ("min_free_bytes", self.min_free_bytes),
            ("max_total_cache_bytes", self.max_total_cache_bytes),
            ("max_entry_count", self.max_entry_count),
            ("max_entry_age_seconds", self.max_entry_age_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if (
            isinstance(self.max_compression_ratio, bool)
            or self.max_compression_ratio <= 0
        ):
            raise ValueError("max_compression_ratio must be positive")


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Result of resolving one gzip source into the managed cache."""

    path: Path
    cache_hit: bool
    key: str
    decompressed_size: int


class ManagedExtractionCache:
    """Budgeted cache for random-access gzip extraction products."""

    def __init__(
        self,
        root: Path,
        *,
        limits: ExtractionLimits = ExtractionLimits(),
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.limits = limits
        cache_limits = CacheLimits(
            max_total_bytes=limits.max_total_cache_bytes,
            max_entry_count=limits.max_entry_count,
            max_entry_age_seconds=limits.max_entry_age_seconds,
        )
        if clock is not None:
            self._cache = BoundedCache(self.root, limits=cache_limits, clock=clock)
        else:
            self._cache = BoundedCache(self.root, limits=cache_limits)
        self.cleanup_startup()

    @property
    def entry_count(self) -> int:
        return self._cache.count

    def cached_path_for(self, source: Path) -> Path | None:
        """Return the currently valid cached path for source, if present."""

        return self._cache.get(self.cache_key(source))

    def cache_key(self, source: Path) -> str:
        """Return the canonical cache key for the current source fingerprint."""

        source = source.expanduser().resolve(strict=False)
        stat = source.stat()
        prefix_hash = hashlib.sha256()
        with source.open("rb") as handle:
            prefix_hash.update(handle.read(64 * 1024))
        return "|".join(
            (
                "gzip-random-access-v1",
                source.as_uri(),
                str(stat.st_size),
                str(stat.st_mtime_ns),
                prefix_hash.hexdigest(),
            )
        )

    def extract(
        self,
        source: Path,
        *,
        cancellation: source_api.CancellationToken,
        progress: source_api.ProgressCallback | None = None,
    ) -> ExtractionResult:
        """Resolve source into the managed cache after budget and cancel checks."""

        if cancellation.is_cancelled:
            raise DataViewerError(
                code=ErrorCode.READ_CANCELLED,
                message="Gzip extraction was cancelled.",
                operation="source.gzip.cache.extract",
                retryable=True,
            )
        self._preflight(source)
        key = self.cache_key(source)
        cached = self._cache.get(key)
        if cached is not None:
            return ExtractionResult(
                path=cached,
                cache_hit=True,
                key=key,
                decompressed_size=cached.stat().st_size,
            )

        incomplete_path = self._new_incomplete_path()
        copied = 0
        compressed_size = max(source.stat().st_size, 1)
        try:
            with gzip.open(source, "rb") as source_file, incomplete_path.open(
                "wb"
            ) as target_file:
                while True:
                    if cancellation.is_cancelled:
                        raise DataViewerError(
                            code=ErrorCode.READ_CANCELLED,
                            message="Gzip extraction was cancelled.",
                            operation="source.gzip.cache.extract",
                            retryable=True,
                        )
                    chunk = source_file.read(1024 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    self._check_decompressed_budget(
                        copied,
                        compressed_size=compressed_size,
                    )
                    target_file.write(chunk)
                    if progress is not None:
                        progress(copied, None, "Extracting gzip source")
                target_file.flush()
                os.fsync(target_file.fileno())
            cached_path = self._cache.put_path(key, incomplete_path)
            return ExtractionResult(
                path=cached_path,
                cache_hit=False,
                key=key,
                decompressed_size=copied,
            )
        except DataViewerError:
            raise
        except (EOFError, OSError, gzip.BadGzipFile) as exc:
            raise DataViewerError(
                code=ErrorCode.SOURCE_MALFORMED,
                message="Gzip source is corrupt or truncated.",
                operation="source.gzip.cache.extract",
                details={"path": str(source)},
                cause=exc,
            ) from exc
        finally:
            try:
                incomplete_path.unlink()
            except OSError:
                pass

    def cleanup_startup(self) -> None:
        """Remove abandoned incomplete files and expired indexed entries."""

        for candidate in self.root.glob("*.incomplete"):
            try:
                candidate.unlink()
            except OSError:
                pass
        self._cache.cleanup()

    def _preflight(self, source: Path) -> None:
        free_bytes = shutil.disk_usage(self.root).free
        if free_bytes < self.limits.min_free_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Insufficient free disk space for gzip extraction.",
                operation="source.gzip.cache.preflight",
                details={
                    "free_bytes": free_bytes,
                    "min_free_bytes": self.limits.min_free_bytes,
                    "path": str(source),
                },
            )

    def _check_decompressed_budget(self, copied: int, *, compressed_size: int) -> None:
        if copied > self.limits.max_decompressed_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Gzip decompressed data exceeds the configured cache budget.",
                operation="source.gzip.cache.extract",
                details={
                    "decompressed_bytes": copied,
                    "max_decompressed_bytes": self.limits.max_decompressed_bytes,
                },
            )
        ratio = copied / compressed_size
        if ratio > self.limits.max_compression_ratio:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Gzip compression ratio exceeds the configured cache budget.",
                operation="source.gzip.cache.extract",
                details={
                    "compression_ratio": ratio,
                    "max_compression_ratio": self.limits.max_compression_ratio,
                },
            )

    def _new_incomplete_path(self) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            dir=self.root,
            prefix="gzip-extract-",
            suffix=".incomplete",
            delete=False,
        )
        path = Path(handle.name)
        handle.close()
        return path


__all__ = ["ExtractionLimits", "ExtractionResult", "ManagedExtractionCache"]
