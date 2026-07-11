"""Small deterministic scientific-data fixture factories.

Factories create only test-owned files and return their creation parameters so
callers can report exactly which fixture shape and content they exercised.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import h5py
import numpy as np


@dataclass(frozen=True)
class FixtureArtifact:
    """A generated fixture path with immutable creation metadata."""

    path: Path
    format: str
    parameters: Mapping[str, object]


def _artifact(path: Path, format_name: str, parameters: dict[str, object]) -> FixtureArtifact:
    return FixtureArtifact(
        path=path,
        format=format_name,
        parameters=MappingProxyType(parameters),
    )


def create_hdf5(path: Path) -> FixtureArtifact:
    """Create a minimal deterministic HDF5 hierarchy suitable for reopen tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    measurements = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int64)
    with h5py.File(path, "w") as file:
        dataset = file.create_dataset("measurements", data=measurements)
        dataset.attrs["units"] = "a.u."
        metadata = file.create_group("metadata")
        metadata.create_dataset("scalar", data=np.int64(7))

    return _artifact(path, "hdf5", {"layout": "minimal-scientific-v1"})


def create_npy(path: Path) -> FixtureArtifact:
    """Create a non-object NPY fixture with a fixed numeric payload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int64)
    np.save(path, data, allow_pickle=False)

    return _artifact(path, "npy", {"shape": data.shape, "dtype": str(data.dtype)})


def create_csv(path: Path) -> FixtureArtifact:
    """Create a UTF-8 CSV fixture with stable row order and line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ("sample", "value")
    rows = ((0, 1.5), (1, 2.5), (2, 3.5))
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)

    return _artifact(path, "csv", {"columns": columns, "rows": len(rows)})
