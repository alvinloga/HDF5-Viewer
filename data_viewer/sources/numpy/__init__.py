"""NumPy ``.npy`` SourceAdapter for Data Viewer v1."""

from .adapter import NPYAdapter, NPY_MAGIC_PREFIX
from .session import NPYSourceSession, NumpyPersistenceResult

__all__ = [
    "NPYAdapter",
    "NPYSourceSession",
    "NPY_MAGIC_PREFIX",
    "NumpyPersistenceResult",
]
