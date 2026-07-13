"""Contracts for structured errors and diagnostic values."""

from __future__ import annotations

import math

import pytest

from data_viewer.app.diagnostics import (
    DiagnosticEvent,
    DiagnosticsRedactor,
    DiagnosticsSnapshot,
)
from data_viewer.domain import ResourceId
from data_viewer.domain.errors import (
    DataViewerError,
    ErrorCategory,
    ErrorCode,
    ErrorSeverity,
    ErrorTarget,
    ErrorTargetKind,
)


def test_data_viewer_error_uses_stable_code_defaults_and_json_roundtrip() -> None:
    resource = ResourceId("file:///tmp/example.h5", "/data")
    error = DataViewerError(
        code=ErrorCode.SELECTION_INVALID,
        message="Selection is outside the dataset bounds.",
        operation="read",
        resource_id=resource,
        details={"axis": 0, "index": 10},
        remediation="Choose an index inside the displayed shape.",
    )

    assert error.category == ErrorCategory.SELECTION
    assert error.severity == ErrorSeverity.ERROR
    assert error.retryable is False
    assert error.target == ErrorTarget(ErrorTargetKind.RESOURCE, resource.to_json())

    encoded = error.to_json()

    assert encoded["code"] == "SELECTION_INVALID"
    assert encoded["category"] == "selection"
    assert encoded["resource_id"] == resource.to_json()
    assert encoded["details"] == {"axis": 0, "index": 10}
    assert "traceback" not in encoded
    assert DataViewerError.from_json(encoded).to_json() == encoded


@pytest.mark.parametrize(
    ("code", "category", "retryable"),
    [
        (ErrorCode.SOURCE_CHANGED, ErrorCategory.SOURCE, True),
        (ErrorCode.PLUGIN_FAILED, ErrorCategory.PLUGIN, False),
        (ErrorCode.TASK_CANCELLED, ErrorCategory.TASK, True),
        (ErrorCode.WORKSPACE_INVALID, ErrorCategory.WORKSPACE, False),
        (ErrorCode.CONFIG_INVALID, ErrorCategory.CONFIG, False),
    ],
)
def test_error_codes_map_consistently_across_subsystems(
    code: ErrorCode,
    category: ErrorCategory,
    retryable: bool,
) -> None:
    error = DataViewerError(
        code=code,
        message="A safe summary for the user.",
        operation="test",
    )

    assert error.category == category
    assert error.retryable is retryable


def test_error_separates_safe_user_message_from_exception_cause() -> None:
    try:
        raise RuntimeError("raw parser traceback detail with secret value")
    except RuntimeError as exc:
        error = DataViewerError(
            code=ErrorCode.READ_FAILED,
            message="The selected data could not be read.",
            operation="read",
            cause=exc,
            cause_id="cause-read-001",
            details={"adapter_id": "hdf5", "path": "/safe/redacted"},
        )

    user_message = error.to_user_message()
    log_record = error.to_log_record()

    assert user_message.message == "The selected data could not be read."
    assert "secret" not in user_message.message
    assert "RuntimeError" not in error.to_json()
    assert log_record["cause_id"] == "cause-read-001"
    assert log_record["cause_type"] == "RuntimeError"


def test_error_details_must_be_json_compatible() -> None:
    with pytest.raises(ValueError, match="NaN|infinity"):
        DataViewerError(
            code=ErrorCode.READ_FAILED,
            message="Unsafe detail.",
            operation="read",
            details={"bad": math.inf},
        )


def test_diagnostics_redactor_removes_configured_path_prefixes() -> None:
    redactor = DiagnosticsRedactor(
        sensitive_roots=(
            r"C:\Users\Alvin",
            "/home/alvin",
        )
    )

    redacted = redactor.redact_json(
        {
            "windows_path": r"C:\Users\Alvin\Desktop\data\secret.h5",
            "linux_path": "/home/alvin/data/secret.h5",
            "nested": ["no secret", r"C:\Users\Alvin\Documents\file.csv"],
        }
    )

    assert redacted == {
        "linux_path": "<redacted>/data/secret.h5",
        "nested": ["no secret", "<redacted>/Documents/file.csv"],
        "windows_path": "<redacted>/Desktop/data/secret.h5",
    }


def test_diagnostic_snapshot_contains_safe_errors_without_tracebacks() -> None:
    error = DataViewerError(
        code=ErrorCode.WORKSPACE_INVALID,
        message="Workspace manifest is invalid.",
        operation="workspace.open",
        details={"path": r"C:\Users\Alvin\workspace.dvw"},
        cause=ValueError("schema stack trace should not be exported"),
        cause_id="cause-workspace-001",
    )
    redactor = DiagnosticsRedactor((r"C:\Users\Alvin",))
    event = DiagnosticEvent.from_error(error, redactor=redactor)
    snapshot = DiagnosticsSnapshot.from_events(
        events=(event,),
        app_version="1.0.0.dev0",
        platform="Windows",
        python_version="3.12.13",
    )

    encoded = snapshot.to_json()

    assert encoded["app_version"] == "1.0.0.dev0"
    assert encoded["events"][0]["error"]["details"] == {
        "path": "<redacted>/workspace.dvw"
    }
    assert encoded["events"][0]["error"]["cause_id"] == "cause-workspace-001"
    assert "schema stack trace" not in str(encoded)
