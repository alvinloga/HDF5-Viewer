"""Transaction recovery marker helpers.

Recovery records document interrupted replacement attempts so startup can present
resumable metadata and safe cleanup actions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
import json
import os
import tempfile
from typing import Any

from data_viewer.domain import ErrorCode, SourceFingerprint
from data_viewer.domain.errors import DataViewerError


class RecoveryState(StrEnum):
    """Lifecycle state for a replacement transaction."""

    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class RecoveryRecord:
    """Structured persistence marker for one replacement attempt."""

    destination_uri: str
    temp_uri: str | None
    state: RecoveryState
    step: str
    created_at_utc: str
    last_error: str | None = None
    expected_fingerprint: SourceFingerprint | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", RecoveryState(self.state))
        if not self.destination_uri:
            raise ValueError("destination URI must not be empty")
        if not self.step:
            raise ValueError("step must be a non-empty string")
        if not self.created_at_utc:
            raise ValueError("created_at_utc must be a non-empty UTC string")

    def with_state(
        self,
        *,
        state: RecoveryState,
        step: str,
        last_error: str | None = None,
    ) -> "RecoveryRecord":
        """Create a copy with updated lifecycle state."""

        return replace(self, state=state, step=step, last_error=last_error)

    def to_json(self) -> dict[str, Any]:
        return {
            "destination_uri": self.destination_uri,
            "temp_uri": self.temp_uri,
            "state": self.state.value,
            "step": self.step,
            "created_at_utc": self.created_at_utc,
            "last_error": self.last_error,
            "expected_fingerprint": (
                self.expected_fingerprint.to_json()
                if self.expected_fingerprint is not None
                else None
            ),
        }

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "RecoveryRecord":
        expected_fingerprint = value.get("expected_fingerprint")
        return cls(
            destination_uri=str(value["destination_uri"]),
            temp_uri=(
                str(value["temp_uri"])
                if value.get("temp_uri") is not None
                else None
            ),
            state=RecoveryState(str(value["state"])),
            step=str(value["step"]),
            created_at_utc=str(value["created_at_utc"]),
            last_error=str(value["last_error"])
            if value.get("last_error") is not None
            else None,
            expected_fingerprint=(
                SourceFingerprint.from_json(expected_fingerprint)
                if isinstance(expected_fingerprint, dict)
                else None
            ),
        )


def marker_path(destination: Path) -> Path:
    """Return the marker location for one destination."""

    return destination.with_name(f".{destination.name}.dvtrx")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
        suffix=".tmp",
    ) as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def write_recovery_record(path: Path, record: RecoveryRecord) -> None:
    """Persist a recovery marker atomically."""

    _atomic_write_json(marker_path(path), record.to_json())


def clear_recovery_record(path: Path) -> None:
    """Remove recovery marker when it is no longer required."""

    marker = marker_path(path)
    try:
        marker.unlink()
    except FileNotFoundError:
        return


def load_recovery_record(path: Path) -> RecoveryRecord | None:
    """Load a marker if it exists.

    `path` is interpreted as the destination path for a pending replacement.
    """

    marker = marker_path(path)
    if not marker.exists():
        return None
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("recovery marker payload is not an object")
        return RecoveryRecord.from_json(payload)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise DataViewerError(
            code=ErrorCode.WORKSPACE_INVALID,
            message="Recovery marker payload is invalid.",
            operation="recovery.load",
            cause=exc,
        ) from exc


def discover_recovery_records(scope: Path) -> tuple[RecoveryRecord, ...]:
    """Discover recovery markers under a directory."""

    if not scope.exists():
        return ()
    records: list[RecoveryRecord] = []
    for entry in scope.rglob("*.dvtrx"):
        if not entry.is_file():
            continue
        destination = entry.with_name(entry.name.removeprefix(".").removesuffix(".dvtrx"))
        try:
            record = load_recovery_record(destination)
        except DataViewerError:
            continue
        if record is not None:
            records.append(record)
    return tuple(records)


def new_recovery_record(
    destination: Path,
    *,
    temp_uri: str | None = None,
    step: str,
    expected_fingerprint: SourceFingerprint | None = None,
) -> RecoveryRecord:
    """Create a new in-progress recovery record for a destination."""

    return RecoveryRecord(
        destination_uri=destination.as_uri(),
        temp_uri=temp_uri,
        state=RecoveryState.IN_PROGRESS,
        step=step,
        created_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        expected_fingerprint=expected_fingerprint,
    )


__all__ = [
    "RecoveryRecord",
    "RecoveryState",
    "clear_recovery_record",
    "discover_recovery_records",
    "load_recovery_record",
    "marker_path",
    "new_recovery_record",
    "write_recovery_record",
]
