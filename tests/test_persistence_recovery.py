"""Persistence recovery marker contract for atomic replacement."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.domain import ErrorCode, SourceFingerprint
from data_viewer.persistence import recovery
from data_viewer.persistence.recovery import (
    RecoveryState,
    discover_recovery_records,
    load_recovery_record,
    marker_path,
    new_recovery_record,
    write_recovery_record,
)


def test_marker_path_adds_dvtrx_prefix_and_suffix(tmp_path: Path) -> None:
    destination = tmp_path / "results.bin"

    marker = marker_path(destination)

    assert marker.name == ".results.bin.dvtrx"
    assert marker.parent == destination.parent


def test_recovery_record_roundtrip_with_optional_fingerprint(tmp_path: Path) -> None:
    destination = tmp_path / "results.bin"
    fingerprint = SourceFingerprint(size_bytes=12, modified_time_ns=3456)
    record = new_recovery_record(
        destination=destination,
        temp_uri="file:///tmp/result.tmp",
        step="write",
        expected_fingerprint=fingerprint,
    )
    assert record.state is RecoveryState.IN_PROGRESS
    assert record.expected_fingerprint == fingerprint

    write_recovery_record(destination, record)
    loaded = load_recovery_record(destination)

    assert loaded is not None
    assert loaded.destination_uri == destination.as_uri()
    assert loaded.temp_uri == "file:///tmp/result.tmp"
    assert loaded.state is RecoveryState.IN_PROGRESS
    assert loaded.step == "write"
    assert loaded.expected_fingerprint == fingerprint


def test_recovery_record_roundtrip_without_expected_fingerprint(tmp_path: Path) -> None:
    destination = tmp_path / "results.bin"
    record = new_recovery_record(destination=destination, step="validate_temp")

    write_recovery_record(destination, record)
    loaded = load_recovery_record(destination)

    assert loaded is not None
    assert loaded.expected_fingerprint is None


def test_load_recovery_record_handles_invalid_payload(tmp_path: Path) -> None:
    bad_payload = tmp_path / marker_path(tmp_path / "x.txt")
    bad_payload.write_text("not-json", encoding="utf-8")

    with pytest.raises(Exception) as exc_info:
        load_recovery_record(tmp_path / "x.txt")

    error = exc_info.value
    assert getattr(error, "code", None) == ErrorCode.WORKSPACE_INVALID


def test_discover_recovery_records_scans_nested_markers_and_skips_invalid(
    tmp_path: Path,
) -> None:
    good_dest_a = tmp_path / "a" / "one.bin"
    good_dest_b = tmp_path / "a" / "b" / "two.bin"
    good_dest_c = tmp_path / "c.bin"
    good_dest_a.parent.mkdir(parents=True)
    good_dest_b.parent.mkdir(parents=True, exist_ok=True)

    write_recovery_record(
        good_dest_a,
        new_recovery_record(destination=good_dest_a, step="temp_create"),
    )
    write_recovery_record(
        good_dest_b,
        new_recovery_record(destination=good_dest_b, step="flush"),
    )
    write_recovery_record(
        good_dest_c,
        new_recovery_record(destination=good_dest_c, step="replace"),
    )

    bad_marker = marker_path(good_dest_c)
    bad_marker.write_text('{"not": "record"}', encoding="utf-8")

    found = discover_recovery_records(tmp_path)

    assert {entry.destination_uri for entry in found} == {
        good_dest_a.as_uri(),
        good_dest_b.as_uri(),
    }


def test_clear_recovery_record_removes_marker(tmp_path: Path) -> None:
    destination = tmp_path / "results.bin"
    write_recovery_record(
        destination,
        new_recovery_record(destination=destination, step="flush"),
    )

    assert load_recovery_record(destination) is not None
    recovery.clear_recovery_record(destination)
    assert marker_path(destination).exists() is False
    assert load_recovery_record(destination) is None
