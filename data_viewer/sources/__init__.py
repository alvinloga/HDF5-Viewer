"""DataSource API and registry primitives for Data Viewer v1."""

from .api import (
    DATASOURCE_API_VERSION,
    CancellationToken,
    NodePage,
    ProbeResult,
    ProgressCallback,
    ReadRequest,
    SourceAdapter,
    SourceSession,
)
from .registry import ManagedSourceSession, SelectedAdapter, SourceRegistry

__all__ = [
    "DATASOURCE_API_VERSION",
    "CancellationToken",
    "ManagedSourceSession",
    "NodePage",
    "ProbeResult",
    "ProgressCallback",
    "ReadRequest",
    "SelectedAdapter",
    "SourceAdapter",
    "SourceRegistry",
    "SourceSession",
]
