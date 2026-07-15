"""DV-0703 plugin runner and budgeted input-access contracts."""

from __future__ import annotations

from typing import Any

import numpy as np

from data_viewer.app.documents import DocumentController
from data_viewer.domain import (
    ArrayPayload,
    DataDomain,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    NodeKind,
    OperationScope,
    ReadResult,
    ResourceId,
    ResourceNode,
    SelectionSpec,
    SourceCapability,
    SourceFingerprint,
)
from data_viewer.plugins.api import PluginResult, ResultKind, ResultProvenance
from data_viewer.plugins.manifests import validate_plugin_manifest
from data_viewer.plugins.runner import (
    PluginInputBinding,
    PluginRunRequest,
    PluginRunner,
)
from data_viewer.sources import ManagedSourceSession, NodePage, ReadRequest
from data_viewer.tasks import TaskState


def _manifest() -> Any:
    return validate_plugin_manifest(
        {
            "schema_version": 1,
            "api_version": 1,
            "id": "org.dataviewer.runner_test",
            "name": "Runner Test",
            "version": "1.0.0",
            "description": "Exercises runner contracts.",
            "entry_point": "data_viewer.plugins.builtin.runner_test.plugin:RunnerTestPlugin",
            "kind": "analysis",
            "input": {
                "domains": ["array"],
                "min_ndim": 1,
                "max_ndim": None,
                "dtype_families": ["integer", "floating"],
                "requires_random_access": True,
                "supports_chunked_input": True,
                "supports_selection": True,
            },
            "parameters_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "result_kinds": ["summary"],
        }
    )


class FakeArraySession:
    """SourceSession fake that records every bounded read request."""

    def __init__(self, values: np.ndarray) -> None:
        self.values = values
        self.resource_id = ResourceId("file:///tmp/plugin-runner.npy", "/array")
        self.source_uri = self.resource_id.source_uri
        self.fingerprint = SourceFingerprint(size_bytes=values.nbytes, modified_time_ns=1)
        self.capabilities = SourceCapability.RANDOM_SLICE
        self.requests: list[ReadRequest] = []
        self.closed = False
        self.cancel_after_reads: int | None = None

    def root(self) -> ResourceNode:
        return ResourceNode(
            resource_id=ResourceId(self.source_uri, "/"),
            name="root",
            node_kind=NodeKind.ROOT,
            domain=DataDomain.HIERARCHICAL_ARRAY,
            has_children=True,
        )

    def list_children(self, *args: object, **kwargs: object) -> NodePage:
        return NodePage(items=(), next_cursor=None, total_count=0)

    def get_metadata(self, resource: ResourceId, **kwargs: object) -> DataMetadata:
        assert resource == self.resource_id
        return DataMetadata(
            resource_id=self.resource_id,
            name="array",
            domain=DataDomain.ARRAY,
            node_kind=NodeKind.RESOURCE,
            shape=tuple(int(item) for item in self.values.shape),
            dtype=str(self.values.dtype),
            logical_size_bytes=int(self.values.nbytes),
            capabilities=SourceCapability.RANDOM_SLICE,
        )

    def read(self, request: ReadRequest, **kwargs: object) -> ReadResult:
        self.requests.append(request)
        cancellation = kwargs["cancellation"]
        if self.cancel_after_reads is not None and len(self.requests) > self.cancel_after_reads:
            cancellation.raise_if_cancelled(operation="fake.read")
        selection = request.selection.normalize(tuple(int(item) for item in self.values.shape)).unwrap()
        values = self.values[selection.to_numpy_key()]
        if int(values.nbytes) > request.max_bytes:
            raise DataViewerError(
                code=ErrorCode.BUDGET_EXCEEDED,
                message="Fake read exceeded the requested budget.",
                operation="fake.read",
                details={"bytes_read": int(values.nbytes), "max_bytes": request.max_bytes},
            )
        if self.cancel_after_reads is not None and len(self.requests) == self.cancel_after_reads:
            cancellation.cancel()
        return ReadResult(
            payload=ArrayPayload(
                values=np.asarray(values),
                original_shape=tuple(int(item) for item in self.values.shape),
                selection=selection,
            ),
            scope=request.scope,
            bytes_read=int(values.nbytes),
            is_sampled=False,
            sample=None,
        )

    def search(self, *args: object, **kwargs: object) -> NodePage:
        return NodePage(items=(), next_cursor=None, total_count=0)

    def refresh_fingerprint(self) -> SourceFingerprint:
        return self.fingerprint

    def close(self) -> None:
        self.closed = True


def _document(values: np.ndarray) -> tuple[DocumentController, FakeArraySession]:
    fake = FakeArraySession(values)
    document = DocumentController(ManagedSourceSession(fake))
    document.navigate_to(fake.resource_id)
    return document, fake


def _request(
    document: DocumentController,
    resource_id: ResourceId,
    plugin: object,
    *,
    memory_budget_bytes: int = 64,
) -> PluginRunRequest:
    return PluginRunRequest(
        manifest=_manifest(),
        plugin=plugin,
        document=document,
        inputs=(PluginInputBinding(resource_id=resource_id, selection=SelectionSpec.all()),),
        parameters={},
        memory_budget_bytes=memory_budget_bytes,
        temp_budget_bytes=1024,
    )


def test_runner_supplies_budgeted_chunks_without_raw_source_handles() -> None:
    """Plugins receive InputAccess only, and chunk reads keep bounded max_bytes."""

    document, fake = _document(np.arange(8, dtype=np.int64).reshape(4, 2))

    class ChunkPlugin:
        def run(self, context: object) -> PluginResult:
            plugin_context = context
            input_access = plugin_context.inputs[0]  # type: ignore[attr-defined]
            assert not isinstance(input_access, FakeArraySession)
            chunks = list(input_access.iter_chunks(target_bytes=16))
            return PluginResult(
                kind=ResultKind.SUMMARY,
                title="chunks",
                payload={"chunk_count": len(chunks), "total": int(sum(chunk.values.sum() for chunk in chunks))},
                provenance=ResultProvenance(
                    plugin_id="org.dataviewer.runner_test",
                    plugin_version="1.0.0",
                    api_version=1,
                    inputs=(input_access.descriptor,),
                    parameters={},
                    computation_scope="slice",
                    sampled=False,
                ),
                metadata={},
            )

    snapshot = PluginRunner().run(_request(document, fake.resource_id, ChunkPlugin()))

    assert snapshot.state is TaskState.SUCCEEDED
    assert snapshot.result.payload == {"chunk_count": 4, "total": 28}
    assert [request.max_bytes for request in fake.requests] == [16, 16, 16, 16]
    assert all(request.scope is OperationScope.SLICE for request in fake.requests)


def test_runner_fails_without_partial_result_when_input_budget_is_exceeded() -> None:
    """Budget failures become failed task snapshots with no plugin result."""

    document, fake = _document(np.arange(8, dtype=np.int64))

    class FullReadPlugin:
        def run(self, context: object) -> PluginResult:
            input_access = context.inputs[0]  # type: ignore[attr-defined]
            input_access.read({})
            raise AssertionError("read should fail before a result is built")

    snapshot = PluginRunner().run(
        _request(document, fake.resource_id, FullReadPlugin(), memory_budget_bytes=8)
    )

    assert snapshot.state is TaskState.FAILED
    assert snapshot.result is None
    assert snapshot.error is not None
    assert snapshot.error.code is ErrorCode.BUDGET_EXCEEDED
    assert fake.requests[-1].max_bytes == 8


def test_runner_cancels_across_chunks_without_publishing_partial_result() -> None:
    """Cooperative cancellation during chunk iteration ends as cancelled."""

    document, fake = _document(np.arange(8, dtype=np.int64).reshape(4, 2))
    fake.cancel_after_reads = 1

    class CancellingPlugin:
        def run(self, context: object) -> PluginResult:
            input_access = context.inputs[0]  # type: ignore[attr-defined]
            list(input_access.iter_chunks(target_bytes=16))
            raise AssertionError("chunk iteration should cancel before result")

    snapshot = PluginRunner().run(_request(document, fake.resource_id, CancellingPlugin()))

    assert snapshot.state is TaskState.CANCELLED
    assert snapshot.result is None
    assert len(fake.requests) == 1


def test_runner_maps_plugin_exception_to_safe_plugin_error() -> None:
    """Unexpected plugin exceptions keep traceback details out of user JSON."""

    document, fake = _document(np.arange(4, dtype=np.int64))

    class ExplodingPlugin:
        def run(self, context: object) -> PluginResult:
            raise RuntimeError("secret raw traceback detail")

    snapshot = PluginRunner().run(_request(document, fake.resource_id, ExplodingPlugin()))

    assert snapshot.state is TaskState.FAILED
    assert snapshot.result is None
    assert snapshot.error is not None
    assert snapshot.error.code is ErrorCode.PLUGIN_FAILED
    assert snapshot.error.message == "Plugin execution failed."
    assert "secret raw traceback detail" not in str(snapshot.error.to_json())
    assert snapshot.error.cause is not None
