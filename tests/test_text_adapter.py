"""TXT text/table dual-mode adapter behavior for DataSource v1."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.domain import (
    DataDomain,
    DataViewerError,
    ErrorCode,
    OperationScope,
    ResourceId,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.domain.payload import TablePayload, TextPayload
from data_viewer.editing import ChangeSet, TextPatch, fingerprint_value
from data_viewer.editing.review import SaveStrategy
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.delimited import DelimitedTextOptions
from data_viewer.sources.text import (
    TextMode,
    TextPersistenceResult,
    TextSourceSession,
    TXTAdapter,
)
from data_viewer.tasks import CancellationToken


def _write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding, newline="")
    return path


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _single_child(session: TextSourceSession) -> ResourceId:
    page = session.list_children(
        session.root().resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    assert len(page.items) == 1
    return page.items[0].resource_id


def test_txt_adapter_opens_strict_utf8_text_without_table_inference(tmp_path: Path) -> None:
    path = _write_text(tmp_path / "notes.txt", "time value\n1 1e-3\n2 2e-3\n")
    session = TXTAdapter().open(path, cancellation=CancellationToken())
    resource = _single_child(session)
    metadata = session.get_metadata(resource, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(
            resource_id=resource,
            scope=OperationScope.PAGE,
            row_offset=0,
            row_limit=12,
            max_bytes=128,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.domain is DataDomain.TEXT
    assert SourceCapability.STREAMING_READ in metadata.capabilities
    assert metadata.attributes["mode"] == "text"
    assert isinstance(result.payload, TextPayload)
    assert result.payload.text == "time value\n1"
    assert result.payload.offset == 0
    assert result.payload.is_complete is False
    session.close()


def test_txt_strict_decode_failure_is_structured(tmp_path: Path) -> None:
    path = tmp_path / "latin1.txt"
    path.write_bytes(b"caf\xe9")

    with pytest.raises(DataViewerError) as error:
        TXTAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_MALFORMED
    assert error.value.details["replacement_characters"] is False


def test_txt_text_patch_rewrites_atomically_and_preserves_line_endings(
    tmp_path: Path,
) -> None:
    path = _write_text(tmp_path / "editable.txt", "alpha\r\nbeta")
    session = TXTAdapter().open(path, cancellation=CancellationToken())
    resource = _single_child(session)
    changeset = ChangeSet(
        source_fingerprint=session.fingerprint,
        patches=(TextPatch(resource, 7, 11, fingerprint_value("beta"), "BETA"),),
    )

    result = session.apply_change_set(changeset, cancellation=CancellationToken())

    assert isinstance(result, TextPersistenceResult)
    assert result.strategy is SaveStrategy.REPLACEMENT
    assert result.changed_ranges == 1
    assert _read_text(path) == "alpha\r\nBETA"
    session.close()


def test_txt_text_patch_rejects_stale_fingerprint(tmp_path: Path) -> None:
    path = _write_text(tmp_path / "stale.txt", "alpha\n")
    session = TXTAdapter().open(path, cancellation=CancellationToken())
    resource = _single_child(session)
    changeset = ChangeSet(
        source_fingerprint=SourceFingerprint(size_bytes=0, modified_time_ns=0),
        patches=(TextPatch(resource, 0, 5, fingerprint_value("alpha"), "ALPHA"),),
    )

    with pytest.raises(DataViewerError) as error:
        session.apply_change_set(changeset, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_CHANGED
    assert _read_text(path) == "alpha\n"
    session.close()


def test_txt_table_mode_requires_explicit_options_and_reuses_table_semantics(
    tmp_path: Path,
) -> None:
    path = _write_text(tmp_path / "table.txt", "id|label\n1|alpha\n2|beta\n")
    options = DelimitedTextOptions.for_path(path)
    options = DelimitedTextOptions(delimiter="|", encoding=options.encoding)
    session = TextSourceSession(path, mode=TextMode.TABLE, table_options=options)
    resource = _single_child(session)
    metadata = session.get_metadata(resource, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(resource_id=resource, scope=OperationScope.PAGE, row_offset=1, row_limit=1),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.domain is DataDomain.TABLE
    assert metadata.attributes["mode"] == "table"
    assert isinstance(result.payload, TablePayload)
    assert result.payload.column_values[1].tolist() == ["beta"]
    session.close()
