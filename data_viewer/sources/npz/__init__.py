"""NPZ source adapter package for Data Viewer v1."""

from .adapter import NPZAdapter, NPZ_MAGIC_PREFIX
from .session import NPZSourceSession, NPZPersistenceResult

__all__ = [
    "NPZAdapter",
    "NPZ_MAGIC_PREFIX",
    "NPZPersistenceResult",
    "NPZSourceSession",
]

