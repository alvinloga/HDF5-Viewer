"""JSON structured source adapter package for Data Viewer v1."""

from .adapter import JSONAdapter
from .session import JSONSourceSession

__all__ = ["JSONAdapter", "JSONSourceSession"]
