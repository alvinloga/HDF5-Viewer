"""TXT text/table source adapter package for Data Viewer v1."""

from .adapter import TXTAdapter
from .session import TextMode, TextPersistenceResult, TextSourceSession

__all__ = [
    "TXTAdapter",
    "TextMode",
    "TextPersistenceResult",
    "TextSourceSession",
]
