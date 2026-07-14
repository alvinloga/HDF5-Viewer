"""Shared XLSX signature constants."""

ZIP_SIGNATURE = b"PK\x03\x04"
OLE_COMPOUND_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

__all__ = ["OLE_COMPOUND_SIGNATURE", "ZIP_SIGNATURE"]
