"""Delimited CSV/TSV adapter and import-preview behavior for DataSource v1."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pytest

from data_viewer.domain import (
    DataDomain,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ResourceId,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.domain.payload import TablePayload
from data_viewer.editing import CellPatch, ChangeSet, fingerprint_value
from data_viewer.editing.review import SaveStrategy
from data_viewer.persistence.transaction import TransactionStep
from data_viewer.sources import api as source_api
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.delimited import (
    DelimitedSourceSession,
    DelimitedTextAdapter,
    DelimitedTextOptions,
    preview_delimited_source,
)
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken
from tests.conformance.source_adapter import assert_table_source_adapter_conformance
from tests.conformance.source_adapter import FAKE_HEADER


def _write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding, newline="")
    return path


def _read_text(path: Path, *, encoding: str = "utf-8") -> str:
    with path.open("r", encoding=encoding, newline="") as handle:
        return handle.read()


def _table_resource(session: source_api.SourceSession) -> ResourceId:
    page = session.list_children(
        session.root().resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    assert len(page.items) == 1
    return page.items[0].resource_id


class _TrackingSession:
    """Proxy that captures close-counting behavior for shared conformance tests."""

    def __init__(self, inner: DelimitedSourceSession) -> None:
        self._inner = inner
        self.close_count = 0
        self._is_closed = False

    @property
    def source_uri(self) -> str:
        return self._inner.source_uri

    @property
    def fingerprint(self):
        return self._inner.fingerprint

    @property
    def capabilities(self):
        return self._inner.capabilities

    def root(self):
        return self._inner.root()

    def list_children(
        self,
        parent,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: source_api.CancellationToken,
    ):
        return self._inner.list_children(
            parent,
            cursor=cursor,
            page_size=page_size,
            cancellation=cancellation,
        )

    def get_metadata(self, resource, *, cancellation: source_api.CancellationToken):
        return self._inner.get_metadata(resource, cancellation=cancellation)

    def read(
        self,
        request,
        *,
        cancellation: source_api.CancellationToken,
        progress,
    ):
        return self._inner.read(
            request,
            cancellation=cancellation,
            progress=progress,
        )

    def search(
        self,
        query: str,
        *,
        cursor: str | None,
        page_size: int,
        cancellation: source_api.CancellationToken,
    ):
        return self._inner.search(
            query,
            cursor=cursor,
            page_size=page_size,
            cancellation=cancellation,
        )

    def refresh_fingerprint(self):
        return self._inner.refresh_fingerprint()

    def close(self) -> None:
        if self._is_closed:
            return
        self._is_closed = True
        self.close_count += 1
        self._inner.close()


class TrackingDelimitedTextAdapter:
    """Adapter wrapper used by shared conformance to verify close lifecycle."""

    adapter_id = "data-viewer.delimited"
    api_version = source_api.DATASOURCE_API_VERSION
    extensions = (".csv", ".tsv")

    def __init__(self) -> None:
        self._inner = DelimitedTextAdapter()
        self.last_session: _TrackingSession | None = None

    def probe(self, path: Path, header: bytes):
        return self._inner.probe(path, header)

    def open(self, path: Path, *, cancellation: source_api.CancellationToken):
        self.last_session = _TrackingSession(self._inner.open(path, cancellation=cancellation))
        return self.last_session


def test_delimited_adapter_passes_table_conformance(tmp_path: Path) -> None:
    path = _write_text(tmp_path / "sample.csv", "a,b,c\n1,2,3\n4,5,6\n")
    adapter = TrackingDelimitedTextAdapter()
    registry = SourceRegistry([adapter])

    assert_table_source_adapter_conformance(
        registry,
        path,
        adapter,  # type: ignore[arg-type]
        expected_columns=("a", "b", "c"),
        expected_rows=2,
    )


def test_delimited_probe_is_extension_and_strict_utf8_gated(tmp_path: Path) -> None:
    valid = _write_text(tmp_path / "valid.csv", "a,b\n1,2\n")
    wrong_extension = _write_text(tmp_path / "wrong.txt", "a,b\n1,2\n")
    invalid_utf8 = tmp_path / "invalid.csv"
    invalid_utf8.write_bytes(b"a,b\n1,\xff\n")
    adapter = DelimitedTextAdapter()

    assert adapter.probe(valid, header=valid.read_bytes()) is not None
    assert adapter.probe(wrong_extension, header=wrong_extension.read_bytes()) is None
    assert adapter.probe(invalid_utf8, header=invalid_utf8.read_bytes()) is None


def test_csv_preview_records_explicit_options_schema_bom_and_missing_tokens(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes(
        b"\xef\xbb\xbfid,name,score\n1,Alice,9.5\n2,\"Bob, Jr\",NA\n"
    )

    preview = preview_delimited_source(path)
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)
    metadata = session.get_metadata(resource, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(
            resource_id=resource,
            scope=OperationScope.PAGE,
            row_offset=0,
            row_limit=2,
            max_bytes=4096,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert preview.options.encoding == "utf-8-sig"
    assert preview.options.delimiter == ","
    assert preview.schema[0].name == "id"
    assert preview.schema[2].nullable is True
    assert metadata.domain is DataDomain.TABLE
    assert metadata.node_kind is NodeKind.RESOURCE
    assert metadata.shape == (2, 3)
    confirmed_options = cast(dict[str, object], metadata.attributes["confirmed_options"])
    assert confirmed_options["encoding"] == "utf-8-sig"
    assert confirmed_options["delimiter"] == ","
    assert metadata.attributes["preview_row_count"] == 2
    assert SourceCapability.PAGED_ROWS in metadata.capabilities
    assert SourceCapability.EDIT_PATCH in metadata.capabilities
    assert SourceCapability.ATOMIC_REWRITE in metadata.capabilities
    assert isinstance(result.payload, TablePayload)
    assert result.payload.column_values[1].tolist() == ["Alice", "Bob, Jr"]
    assert np.isnan(result.payload.column_values[2][1])
    session.close()


def test_tsv_default_dialect_unicode_and_selected_columns(tmp_path: Path) -> None:
    path = _write_text(tmp_path / "unicode.tsv", "id\tlabel\tvalue\n1\tα\t10\n2\tβ\t20\n")
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)

    result = session.read(
        ReadRequest(
            resource_id=resource,
            scope=OperationScope.PAGE,
            row_offset=1,
            row_limit=1,
            selected_columns=("label",),
            max_bytes=4096,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert isinstance(result.payload, TablePayload)
    assert tuple(column.name for column in result.payload.columns) == ("label",)
    assert result.payload.column_values[0].tolist() == ["β"]
    assert result.payload.source_row(0) == 1
    session.close()


def test_delimited_strict_decode_failure_raises_without_replacement(
    tmp_path: Path,
) -> None:
    path = tmp_path / "latin1.csv"
    path.write_bytes("name\ncafé\n".encode("latin-1"))

    with pytest.raises(DataViewerError) as error:
        DelimitedTextAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_MALFORMED
    assert error.value.details["encoding"] == "utf-8"
    assert error.value.details["replacement_characters"] is False


def test_delimited_malformed_csv_quote_is_rejected(tmp_path: Path) -> None:
    path = _write_text(tmp_path / "broken.csv", 'a,b\n"unterminated,2\n')

    with pytest.raises(DataViewerError) as error:
        DelimitedTextAdapter().open(path, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_MALFORMED


def test_delimited_large_file_uses_paged_reads_and_stable_row_identity(
    tmp_path: Path,
) -> None:
    rows = ["id,value"]
    rows.extend(f"{index},{index * 2}" for index in range(2_000))
    path = _write_text(tmp_path / "large.csv", "\n".join(rows) + "\n")
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)

    result = session.read(
        ReadRequest(
            resource_id=resource,
            scope=OperationScope.PAGE,
            row_offset=1_200,
            row_limit=3,
            selected_columns=("value",),
            max_bytes=4096,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert isinstance(result.payload, TablePayload)
    assert result.payload.row_offset == 1_200
    assert result.payload.source_row(2) == 1_202
    assert result.payload.column_values[0].tolist() == [2400, 2402, 2404]
    session.close()


def test_delimited_confirmed_dtype_override_prevents_silent_reinference(
    tmp_path: Path,
) -> None:
    path = _write_text(tmp_path / "ids.csv", "id,value\n001,10\n002,20\n")
    options = DelimitedTextOptions.for_path(path).with_dtype_overrides({"id": "string"})
    session = DelimitedSourceSession(path, options=options)
    resource = _table_resource(session)
    metadata = session.get_metadata(resource, cancellation=CancellationToken())
    result = session.read(
        ReadRequest(
            resource_id=resource,
            scope=OperationScope.PAGE,
            row_offset=0,
            row_limit=2,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert metadata.columns[0].dtype == "string"
    assert isinstance(result.payload, TablePayload)
    assert result.payload.column_values[0].tolist() == ["001", "002"]
    assert result.payload.column_values[1].tolist() == [10, 20]
    session.close()


def test_delimited_malformed_missing_source_and_wrong_resource_errors(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "fake.csv"
    malformed.write_bytes(FAKE_HEADER + b"\xff")

    with pytest.raises(DataViewerError) as malformed_error:
        DelimitedTextAdapter().open(malformed, cancellation=CancellationToken())
    assert malformed_error.value.code is ErrorCode.SOURCE_MALFORMED

    missing = tmp_path / "missing.csv"
    with pytest.raises(DataViewerError) as missing_error:
        DelimitedTextAdapter().open(missing, cancellation=CancellationToken())
    assert missing_error.value.code is ErrorCode.SOURCE_OPEN_FAILED

    valid = _write_text(tmp_path / "valid.csv", "a,b\n1,2\n")
    session = DelimitedTextAdapter().open(valid, cancellation=CancellationToken())
    with pytest.raises(DataViewerError) as resource_error:
        session.read(
            ReadRequest(resource_id=ResourceId(session.source_uri, "/missing")),
            cancellation=CancellationToken(),
            progress=lambda _done, _total, _message: None,
        )
    assert resource_error.value.code is ErrorCode.RESOURCE_NOT_FOUND
    session.close()


def test_csv_apply_cell_patches_rewrites_with_confirmed_dialect_and_schema(
    tmp_path: Path,
) -> None:
    path = _write_text(
        tmp_path / "editable.csv",
        'id,name,score\n1,"Alice, A",9.5\n2,Bob,NA\n',
    )
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)
    metadata = session.get_metadata(resource, cancellation=CancellationToken())
    changeset = ChangeSet(
        source_fingerprint=session.fingerprint,
        patches=(
            CellPatch(
                resource_id=resource,
                coordinate=(1, 1),
                old_value_fingerprint=fingerprint_value("Bob"),
                new_value="Bobby",
            ),
            CellPatch(
                resource_id=resource,
                coordinate=(0, 2),
                old_value_fingerprint=fingerprint_value(9.5),
                new_value=10.25,
            ),
        ),
    )

    result = session.apply_change_set(changeset, cancellation=CancellationToken())

    assert result.strategy is SaveStrategy.REPLACEMENT
    assert result.changed_coordinates == 2
    assert SourceCapability.EDIT_PATCH in session.capabilities
    assert SourceCapability.ATOMIC_REWRITE in session.capabilities
    assert metadata.columns[2].dtype == "float64"
    assert _read_text(path) == (
        'id,name,score\n1,"Alice, A",10.25\n2,Bobby,NA\n'
    )
    read_back = session.read(
        ReadRequest(resource_id=resource, scope=OperationScope.PAGE, row_offset=0, row_limit=2),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    assert isinstance(read_back.payload, TablePayload)
    assert read_back.payload.column_values[1].tolist() == ["Alice, A", "Bobby"]
    assert read_back.payload.column_values[2].tolist()[0] == 10.25
    assert np.isnan(read_back.payload.column_values[2].tolist()[1])
    session.close()


def test_tsv_apply_cell_patch_preserves_tab_dialect_and_original_row_coordinates(
    tmp_path: Path,
) -> None:
    path = _write_text(tmp_path / "editable.tsv", "id\tlabel\tvalue\n1\talpha\t10\n2\tbeta\t20\n")
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)
    changeset = ChangeSet(
        source_fingerprint=session.fingerprint,
        patches=(
            CellPatch(
                resource_id=resource,
                coordinate=(1, 2),
                old_value_fingerprint=fingerprint_value(20),
                new_value=25,
            ),
        ),
    )

    session.apply_change_set(changeset, cancellation=CancellationToken())

    assert _read_text(path) == (
        "id\tlabel\tvalue\n1\talpha\t10\n2\tbeta\t25\n"
    )
    session.close()


def test_delimited_apply_patch_preserves_line_endings_and_final_newline_state(
    tmp_path: Path,
) -> None:
    path = _write_text(tmp_path / "line-endings.csv", "id,value\r\n1,10\r\n2,20")
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)
    changeset = ChangeSet(
        source_fingerprint=session.fingerprint,
        patches=(
            CellPatch(
                resource_id=resource,
                coordinate=(1, 1),
                old_value_fingerprint=fingerprint_value(20),
                new_value=21,
            ),
        ),
    )

    session.apply_change_set(changeset, cancellation=CancellationToken())

    assert _read_text(path) == "id,value\r\n1,10\r\n2,21"
    session.close()


def test_delimited_apply_changeset_rejects_stale_source_fingerprint(
    tmp_path: Path,
) -> None:
    path = _write_text(tmp_path / "stale.csv", "id,value\n1,10\n")
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)
    changeset = ChangeSet(
        source_fingerprint=SourceFingerprint(size_bytes=0, modified_time_ns=0),
        patches=(CellPatch(resource, (0, 1), fingerprint_value(10), 20),),
    )

    with pytest.raises(DataViewerError) as error:
        session.apply_change_set(changeset, cancellation=CancellationToken())

    assert error.value.code is ErrorCode.SOURCE_CHANGED
    assert _read_text(path) == "id,value\n1,10\n"
    session.close()


def test_delimited_edit_fault_leaves_original_table_unchanged(tmp_path: Path) -> None:
    path = _write_text(tmp_path / "fault.csv", "id,value\n1,10\n")
    session = DelimitedTextAdapter().open(path, cancellation=CancellationToken())
    resource = _table_resource(session)
    changeset = ChangeSet(
        source_fingerprint=session.fingerprint,
        patches=(CellPatch(resource, (0, 1), fingerprint_value(10), 20),),
    )

    def fail_on_replace(step: TransactionStep) -> None:
        if step is TransactionStep.REPLACE:
            raise RuntimeError("injected replace failure")

    with pytest.raises(DataViewerError):
        session.apply_change_set(
            changeset,
            cancellation=CancellationToken(),
            failure_injector=fail_on_replace,
        )

    assert _read_text(path) == "id,value\n1,10\n"
    session.close()
