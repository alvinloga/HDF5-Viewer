"""Built-in plugin registry for Plugin API v1."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from importlib import import_module
from pathlib import Path
from typing import Iterable

from data_viewer.plugins.manifests import (
    PluginKind,
    PluginManifest,
    PluginManifestError,
    load_plugin_manifest,
)


@dataclass(frozen=True, slots=True)
class PluginDiagnostic:
    """Structured plugin registry diagnostic."""

    code: str
    message: str
    plugin_id: str | None = None
    manifest_path: str | None = None


class BuiltinPluginRegistry:
    """Validated registry for trusted packaged built-in plugins."""

    def __init__(
        self,
        manifests: Iterable[PluginManifest] = (),
        diagnostics: Iterable[PluginDiagnostic] = (),
    ) -> None:
        self._manifests = tuple(_sort_manifests(tuple(manifests)))
        self._diagnostics = list(diagnostics)

    @classmethod
    def from_manifests(cls, manifests: Iterable[PluginManifest]) -> BuiltinPluginRegistry:
        """Create a registry from already validated manifests."""

        return cls(manifests)

    def available_plugins(self) -> tuple[PluginManifest, ...]:
        """Return deterministic validated plugin manifests."""

        return self._manifests

    def diagnostics(self) -> tuple[PluginDiagnostic, ...]:
        """Return startup and lazy-load diagnostics."""

        return tuple(self._diagnostics)

    def manifest_for(self, plugin_id: str) -> PluginManifest:
        """Return one manifest or raise a structured lookup error."""

        for manifest in self._manifests:
            if manifest.id == plugin_id:
                return manifest
        raise LookupError(f"Plugin not found: {plugin_id}")

    def load_plugin_class(self, plugin_id: str) -> type[object]:
        """Import and return a plugin class lazily from a validated entry point."""

        manifest = self.manifest_for(plugin_id)
        module_name, _, attribute = manifest.entry_point.partition(":")
        try:
            module = import_module(module_name)
            plugin_class = getattr(module, attribute)
        except Exception as error:
            self._diagnostics.append(
                PluginDiagnostic(
                    code="PLUGIN_IMPORT_FAILED",
                    message=f"Could not load plugin {plugin_id}: {error}",
                    plugin_id=plugin_id,
                    manifest_path=_manifest_path_text(manifest),
                )
            )
            raise LookupError(f"Could not load plugin {plugin_id}") from error
        if not isinstance(plugin_class, type):
            self._diagnostics.append(
                PluginDiagnostic(
                    code="PLUGIN_IMPORT_FAILED",
                    message=f"Plugin entry point for {plugin_id} did not resolve to a class",
                    plugin_id=plugin_id,
                    manifest_path=_manifest_path_text(manifest),
                )
            )
            raise LookupError(f"Could not load plugin {plugin_id}")
        return plugin_class


def discover_builtin_plugins(
    manifest_paths: Iterable[Path] | None = None,
) -> BuiltinPluginRegistry:
    """Discover trusted built-in plugin manifests without importing plugin code."""

    paths = tuple(manifest_paths) if manifest_paths is not None else _packaged_builtin_manifest_paths()
    diagnostics: list[PluginDiagnostic] = []
    manifests_by_id: dict[str, PluginManifest] = {}

    for path in paths:
        try:
            manifest = load_plugin_manifest(path)
        except PluginManifestError as error:
            diagnostics.append(
                PluginDiagnostic(
                    code="PLUGIN_MANIFEST_INVALID",
                    message=str(error),
                    manifest_path=str(path),
                )
            )
            continue
        if manifest.id in manifests_by_id:
            diagnostics.append(
                PluginDiagnostic(
                    code="PLUGIN_ID_DUPLICATE",
                    message=f"Duplicate plugin id ignored: {manifest.id}",
                    plugin_id=manifest.id,
                    manifest_path=str(path),
                )
            )
            continue
        manifests_by_id[manifest.id] = manifest

    return BuiltinPluginRegistry(manifests_by_id.values(), diagnostics)


def _packaged_builtin_manifest_paths() -> tuple[Path, ...]:
    try:
        builtin_root = resources.files("data_viewer.plugins.builtin")
    except ModuleNotFoundError:
        return ()
    paths: list[Path] = []
    for child in builtin_root.iterdir():
        manifest = child / "plugin.json"
        if manifest.is_file():
            paths.append(Path(str(manifest)))
    return tuple(sorted(paths, key=lambda path: str(path)))


def _sort_manifests(manifests: tuple[PluginManifest, ...]) -> tuple[PluginManifest, ...]:
    kind_order = {
        PluginKind.ANALYSIS: 0,
        PluginKind.VISUALIZATION: 1,
    }
    return tuple(
        sorted(
            manifests,
            key=lambda manifest: (
                kind_order.get(manifest.kind, 99),
                manifest.name.casefold(),
                manifest.id,
            ),
        )
    )


def _manifest_path_text(manifest: PluginManifest) -> str | None:
    if manifest.manifest_path is None:
        return None
    return str(manifest.manifest_path)


__all__ = [
    "BuiltinPluginRegistry",
    "PluginDiagnostic",
    "discover_builtin_plugins",
]
