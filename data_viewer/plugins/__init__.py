"""Target Data Viewer plugin platform package."""

from data_viewer.plugins.api import PLUGIN_API_VERSION, DataViewerPlugin, ResultKind
from data_viewer.plugins.manifests import PluginManifest, PluginManifestError
from data_viewer.plugins.registry import BuiltinPluginRegistry, discover_builtin_plugins

__all__ = [
    "PLUGIN_API_VERSION",
    "BuiltinPluginRegistry",
    "DataViewerPlugin",
    "PluginManifest",
    "PluginManifestError",
    "ResultKind",
    "discover_builtin_plugins",
]
