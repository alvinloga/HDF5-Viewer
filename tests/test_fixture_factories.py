"""Contract tests for deterministic, generated scientific-data fixtures."""

from __future__ import annotations

import csv

import h5py
import numpy as np

from tests.fixtures.factories import create_csv, create_hdf5, create_npy


def test_hdf5_factory_creates_a_reopenable_hierarchy(tmp_path) -> None:
    artifact = create_hdf5(tmp_path / "fixture.h5")

    assert artifact.format == "hdf5"
    assert artifact.parameters == {"layout": "minimal-scientific-v1"}
    with h5py.File(artifact.path, "r") as file:
        assert file["/measurements"].shape == (2, 3)
        np.testing.assert_array_equal(file["/measurements"][:], [[1, 2, 3], [4, 5, 6]])
        assert file["/measurements"].attrs["units"] == "a.u."
        assert file["/metadata/scalar"][()] == 7


def test_npy_factory_round_trips_without_object_payloads(tmp_path) -> None:
    artifact = create_npy(tmp_path / "fixture.npy")

    assert artifact.format == "npy"
    assert artifact.parameters == {"shape": (2, 3), "dtype": "int64"}
    np.testing.assert_array_equal(
        np.load(artifact.path, allow_pickle=False),
        [[1, 2, 3], [4, 5, 6]],
    )


def test_csv_factory_writes_deterministic_utf8_rows(tmp_path) -> None:
    first = create_csv(tmp_path / "first.csv")
    second = create_csv(tmp_path / "second.csv")

    assert first.format == "csv"
    assert first.parameters == {"columns": ("sample", "value"), "rows": 3}
    assert first.path.read_bytes() == second.path.read_bytes()
    with first.path.open("r", encoding="utf-8", newline="") as file:
        assert list(csv.reader(file)) == [
            ["sample", "value"],
            ["0", "1.5"],
            ["1", "2.5"],
            ["2", "3.5"],
        ]
