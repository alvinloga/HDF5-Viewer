"""Workspace restore planning, relocation matching, and degraded state models."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
from pathlib import Path

from data_viewer.domain import JsonValue
from data_viewer.tasks import CancellationToken

from .manifest import WorkspaceManifest, WorkspaceService, WorkspaceSource, WorkspaceView


PREFIX_HASH_BYTES = 64 * 1024


class WorkspaceSourceRestoreStatus(StrEnum):
    """Explicit source restore classifications for degraded workspace loading."""

    AVAILABLE = "available"
    MOVED_CANDIDATE = "moved_candidate"
    MISSING = "missing"
    CHANGED = "changed"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class WorkspaceViewPayloadStatus(StrEnum):
    """Payload readiness for a restored workspace view shell."""

    PENDING = "pending"
    BLOCKED = "blocked"


class PluginResultRestoreStatus(StrEnum):
    """Workspace plugin-result freshness classification."""

    CURRENT = "current"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class WorkspaceSourceRestore:
    """Restore state for one persisted workspace source."""

    source_id: str
    stored_path: Path
    status: WorkspaceSourceRestoreStatus
    resolved_path: Path | None = None
    candidates: tuple[Path, ...] = ()
    reason: str = ""
    fingerprint_changed: bool = False


@dataclass(frozen=True, slots=True)
class WorkspaceViewShell:
    """View shell restored before metadata and payload reads."""

    view_id: str
    source_id: str
    resource_path: str
    resource_domain: str
    view_type: str
    payload_status: WorkspaceViewPayloadStatus
    reason: str = ""


@dataclass(frozen=True, slots=True)
class PluginResultRestore:
    """Freshness state for one persisted plugin result."""

    result_id: str
    plugin_id: str
    status: PluginResultRestoreStatus
    reason: str = ""


@dataclass(frozen=True, slots=True)
class WorkspaceRestorePlan:
    """Complete restore plan that a UI can render as normal or degraded mode."""

    sources: tuple[WorkspaceSourceRestore, ...]
    view_shells: tuple[WorkspaceViewShell, ...]
    plugin_results: tuple[PluginResultRestore, ...]

    @property
    def degraded(self) -> bool:
        return any(
            source.status is not WorkspaceSourceRestoreStatus.AVAILABLE
            for source in self.sources
        ) or any(
            shell.payload_status is WorkspaceViewPayloadStatus.BLOCKED
            for shell in self.view_shells
        ) or any(
            result.status is PluginResultRestoreStatus.STALE
            for result in self.plugin_results
        )

    def source(self, source_id: str) -> WorkspaceSourceRestore:
        for item in self.sources:
            if item.source_id == source_id:
                return item
        raise KeyError(source_id)

    def view_shell(self, view_id: str) -> WorkspaceViewShell:
        for item in self.view_shells:
            if item.view_id == view_id:
                return item
        raise KeyError(view_id)

    def plugin_result(self, result_id: str) -> PluginResultRestore:
        for item in self.plugin_results:
            if item.result_id == result_id:
                return item
        raise KeyError(result_id)


class WorkspaceRestoreCoordinator:
    """Plan workspace restore without mutating the manifest or blocking all sources."""

    def __init__(
        self,
        *,
        workspace_service: WorkspaceService | None = None,
        supported_formats: Iterable[str] | None = None,
        max_relocation_candidates: int = 50,
    ) -> None:
        self._workspace_service = workspace_service or WorkspaceService()
        self._supported_formats = frozenset(supported_formats) if supported_formats is not None else None
        self._max_relocation_candidates = max_relocation_candidates

    def plan_restore(
        self,
        manifest: WorkspaceManifest,
        *,
        workspace_path: Path,
        replacement_roots: Iterable[Path] = (),
        cancellation: CancellationToken | None = None,
    ) -> WorkspaceRestorePlan:
        """Classify sources, prepare view shells, and mark stale plugin results."""

        _raise_if_cancelled(cancellation)
        source_states = tuple(
            self._classify_source(
                source,
                workspace_path=workspace_path,
                replacement_roots=tuple(replacement_roots),
                cancellation=cancellation,
            )
            for source in manifest.sources
        )
        source_by_id = {source.source_id: source for source in source_states}
        view_shells = tuple(_restore_view_shell(view, source_by_id) for view in manifest.views)
        plugin_results = tuple(
            _restore_plugin_result(result, source_by_id) for result in manifest.plugin_results
        )
        return WorkspaceRestorePlan(
            sources=source_states,
            view_shells=view_shells,
            plugin_results=plugin_results,
        )

    async def plan_restore_async(
        self,
        manifest: WorkspaceManifest,
        *,
        workspace_path: Path,
        replacement_roots: Iterable[Path] = (),
        cancellation: CancellationToken | None = None,
    ) -> WorkspaceRestorePlan:
        """Run restore planning asynchronously for UI callers."""

        _raise_if_cancelled(cancellation)
        return await asyncio.to_thread(
            self.plan_restore,
            manifest,
            workspace_path=workspace_path,
            replacement_roots=tuple(replacement_roots),
            cancellation=cancellation,
        )

    def apply_confirmed_relocations(
        self,
        manifest: WorkspaceManifest,
        *,
        workspace_path: Path,
        confirmations: Mapping[str, Path],
    ) -> WorkspaceManifest:
        """Return a dirty manifest with only user-confirmed source paths changed."""

        updated_sources = tuple(
            _relocate_source(source, confirmations[source.source_id], workspace_path)
            if source.source_id in confirmations
            else source
            for source in manifest.sources
        )
        if updated_sources == manifest.sources:
            return manifest
        return manifest.with_updates(sources=updated_sources, workspace_dirty=True)

    def _classify_source(
        self,
        source: WorkspaceSource,
        *,
        workspace_path: Path,
        replacement_roots: tuple[Path, ...],
        cancellation: CancellationToken | None,
    ) -> WorkspaceSourceRestore:
        _raise_if_cancelled(cancellation)
        stored_path = self._workspace_service.resolve_source_path(source, workspace_path)
        if self._supported_formats is not None and source.format_id not in self._supported_formats:
            return WorkspaceSourceRestore(
                source_id=source.source_id,
                stored_path=stored_path,
                status=WorkspaceSourceRestoreStatus.UNSUPPORTED,
                reason=f"Unsupported source format: {source.format_id}",
            )
        try:
            if stored_path.exists():
                if _fingerprint_matches(stored_path, source.fingerprint):
                    return WorkspaceSourceRestore(
                        source_id=source.source_id,
                        stored_path=stored_path,
                        resolved_path=stored_path,
                        status=WorkspaceSourceRestoreStatus.AVAILABLE,
                    )
                return WorkspaceSourceRestore(
                    source_id=source.source_id,
                    stored_path=stored_path,
                    resolved_path=stored_path,
                    status=WorkspaceSourceRestoreStatus.CHANGED,
                    reason="Stored path exists but fingerprint differs.",
                    fingerprint_changed=True,
                )
            candidates = _find_relocation_candidates(
                source,
                replacement_roots,
                cancellation=cancellation,
                max_candidates=self._max_relocation_candidates,
            )
            if len(candidates) == 1:
                return WorkspaceSourceRestore(
                    source_id=source.source_id,
                    stored_path=stored_path,
                    resolved_path=candidates[0],
                    status=WorkspaceSourceRestoreStatus.MOVED_CANDIDATE,
                    candidates=candidates,
                    reason="Stored path is missing; one matching relocation candidate was found.",
                )
            if len(candidates) > 1:
                return WorkspaceSourceRestore(
                    source_id=source.source_id,
                    stored_path=stored_path,
                    status=WorkspaceSourceRestoreStatus.AMBIGUOUS,
                    candidates=candidates,
                    reason="Stored path is missing; multiple matching relocation candidates were found.",
                )
            return WorkspaceSourceRestore(
                source_id=source.source_id,
                stored_path=stored_path,
                status=WorkspaceSourceRestoreStatus.MISSING,
                reason="Stored path does not exist and no matching relocation candidate was found.",
            )
        except OSError as exc:
            return WorkspaceSourceRestore(
                source_id=source.source_id,
                stored_path=stored_path,
                status=WorkspaceSourceRestoreStatus.FAILED,
                reason=type(exc).__name__,
            )


def _restore_view_shell(
    view: WorkspaceView,
    source_by_id: Mapping[str, WorkspaceSourceRestore],
) -> WorkspaceViewShell:
    source_state = source_by_id.get(view.source_id)
    if source_state is None:
        return WorkspaceViewShell(
            view_id=view.view_id,
            source_id=view.source_id,
            resource_path=view.resource_path,
            resource_domain=view.resource_domain,
            view_type=view.view_type,
            payload_status=WorkspaceViewPayloadStatus.BLOCKED,
            reason="View references a source that is not present in the workspace manifest.",
        )
    if source_state.status is WorkspaceSourceRestoreStatus.AVAILABLE:
        return WorkspaceViewShell(
            view_id=view.view_id,
            source_id=view.source_id,
            resource_path=view.resource_path,
            resource_domain=view.resource_domain,
            view_type=view.view_type,
            payload_status=WorkspaceViewPayloadStatus.PENDING,
            reason="View shell restored; metadata and payload are pending bounded reads.",
        )
    return WorkspaceViewShell(
        view_id=view.view_id,
        source_id=view.source_id,
        resource_path=view.resource_path,
        resource_domain=view.resource_domain,
        view_type=view.view_type,
        payload_status=WorkspaceViewPayloadStatus.BLOCKED,
        reason=f"Source restore status is {source_state.status.value}.",
    )


def _restore_plugin_result(
    result: Mapping[str, JsonValue],
    source_by_id: Mapping[str, WorkspaceSourceRestore],
) -> PluginResultRestore:
    result_id = str(result.get("result_id", ""))
    plugin_id = str(result.get("plugin_id", ""))
    for item in _iter_plugin_inputs(result):
        source_id = str(item.get("source_id", ""))
        source_state = source_by_id.get(source_id)
        if source_state is None or source_state.status is not WorkspaceSourceRestoreStatus.AVAILABLE:
            return PluginResultRestore(
                result_id=result_id,
                plugin_id=plugin_id,
                status=PluginResultRestoreStatus.STALE,
                reason=f"Input source {source_id} is not available.",
            )
        stored_fingerprint = item.get("fingerprint")
        if isinstance(stored_fingerprint, Mapping) and not _fingerprint_matches(
            source_state.resolved_path,
            stored_fingerprint,
        ):
            return PluginResultRestore(
                result_id=result_id,
                plugin_id=plugin_id,
                status=PluginResultRestoreStatus.STALE,
                reason=f"Input source {source_id} fingerprint differs.",
            )
    return PluginResultRestore(
        result_id=result_id,
        plugin_id=plugin_id,
        status=PluginResultRestoreStatus.CURRENT,
        reason="Persisted plugin result inputs match restored sources.",
    )


def _iter_plugin_inputs(result: Mapping[str, JsonValue]) -> tuple[Mapping[str, JsonValue], ...]:
    raw_inputs = result.get("inputs", ())
    if not isinstance(raw_inputs, list):
        return ()
    return tuple(item for item in raw_inputs if isinstance(item, Mapping))


def _relocate_source(source: WorkspaceSource, new_path: Path, workspace_path: Path) -> WorkspaceSource:
    relative_path = _relative_posix_path(new_path.resolve(), workspace_path.parent.resolve())
    return replace(source, path=relative_path, path_kind="relative")


def _relative_posix_path(path: Path, base: Path) -> str:
    return Path(*path.relative_to(base).parts).as_posix() if _is_relative_to(path, base) else _os_relpath_posix(path, base)


def _os_relpath_posix(path: Path, base: Path) -> str:
    import os

    return os.path.relpath(path, base).replace("\\", "/")


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _find_relocation_candidates(
    source: WorkspaceSource,
    roots: tuple[Path, ...],
    *,
    cancellation: CancellationToken | None,
    max_candidates: int,
) -> tuple[Path, ...]:
    basename = Path(source.path).name
    candidates: list[Path] = []
    for root in roots:
        _raise_if_cancelled(cancellation)
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob(basename):
            _raise_if_cancelled(cancellation)
            if path.is_file() and _fingerprint_matches(path, source.fingerprint):
                candidates.append(path.resolve())
                if len(candidates) >= max_candidates:
                    return tuple(sorted(candidates))
    return tuple(sorted(candidates))


def _fingerprint_matches(path: Path | None, fingerprint: Mapping[str, JsonValue]) -> bool:
    if path is None:
        return False
    try:
        stat = path.stat()
    except OSError:
        return False
    expected_size = _int_fingerprint_value(fingerprint, "size", "size_bytes")
    if expected_size is not None and stat.st_size != expected_size:
        return False
    expected_mtime = _int_fingerprint_value(fingerprint, "mtime_ns", "modified_time_ns")
    if expected_mtime is not None and stat.st_mtime_ns != expected_mtime:
        return False
    expected_prefix_hash = fingerprint.get("prefix_sha256")
    if isinstance(expected_prefix_hash, str) and _prefix_sha256(path) != expected_prefix_hash:
        return False
    return True


def _int_fingerprint_value(fingerprint: Mapping[str, JsonValue], *keys: str) -> int | None:
    for key in keys:
        value = fingerprint.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _prefix_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read(PREFIX_HASH_BYTES))
    return digest.hexdigest()


def _raise_if_cancelled(cancellation: CancellationToken | None) -> None:
    if cancellation is not None:
        cancellation.raise_if_cancelled(operation="workspace.restore")


__all__ = [
    "PluginResultRestore",
    "PluginResultRestoreStatus",
    "WorkspaceRestoreCoordinator",
    "WorkspaceRestorePlan",
    "WorkspaceSourceRestore",
    "WorkspaceSourceRestoreStatus",
    "WorkspaceViewPayloadStatus",
    "WorkspaceViewShell",
]
