"""Budgeted Plugin API v1 input access and synchronous runner core."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from math import prod
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from data_viewer.app.documents import DocumentController
from data_viewer.domain import (
    ArrayPayload,
    DataMetadata,
    DataViewerError,
    ErrorCode,
    JsonValue,
    OperationScope,
    ResourceId,
    SelectionSpec,
    TablePayload,
    VolumePayload,
)
from data_viewer.domain.selection import AxisSelection
from data_viewer.plugins.api import (
    DataChunk,
    DataViewerPlugin,
    InputDescriptor,
    PluginContext,
    PluginResult,
)
from data_viewer.plugins.manifests import PluginManifest
from data_viewer.sources import ReadRequest
from data_viewer.tasks import TaskRecord, TaskState


@dataclass(frozen=True, slots=True)
class PluginInputBinding:
    """One selected resource and selection supplied to a plugin run."""

    resource_id: ResourceId
    selection: SelectionSpec = SelectionSpec()


@dataclass(frozen=True, slots=True)
class PluginRunRequest:
    """Validated inputs for one synchronous plugin runner invocation."""

    manifest: PluginManifest
    plugin: DataViewerPlugin
    document: DocumentController
    inputs: tuple[PluginInputBinding, ...]
    parameters: Mapping[str, object]
    memory_budget_bytes: int
    temp_budget_bytes: int
    task: TaskRecord | None = None

    def __post_init__(self) -> None:
        if not self.inputs:
            raise ValueError("plugin run requires at least one input")
        _validate_positive_budget(self.memory_budget_bytes, "memory_budget_bytes")
        _validate_positive_budget(self.temp_budget_bytes, "temp_budget_bytes")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


class BudgetedInputAccess:
    """Document-backed InputAccess that enforces read budgets and cancellation."""

    def __init__(
        self,
        *,
        document: DocumentController,
        binding: PluginInputBinding,
        metadata: DataMetadata,
        task: TaskRecord,
        memory_budget_bytes: int,
    ) -> None:
        self._document = document
        self._binding = binding
        self._metadata = metadata
        self._task = task
        self._memory_budget_bytes = memory_budget_bytes
        self.descriptor = _descriptor_for(document, metadata, binding.selection)

    def read(self, selection: Mapping[str, object]) -> NDArray[np.generic]:
        """Read one bounded explicit selection and return array-like values."""

        self._task.cancellation.raise_if_cancelled(operation="plugin.input.read")
        selection_spec = _selection_from_mapping(selection) if selection else self._binding.selection
        result = self._document.read(
            ReadRequest(
                resource_id=self._binding.resource_id,
                selection=selection_spec,
                scope=OperationScope.SLICE,
                max_bytes=self._memory_budget_bytes,
            ),
            cancellation=self._task.cancellation,
            progress=self._source_progress,
        )
        return _array_like_values(result.payload)

    def iter_chunks(self, target_bytes: int) -> Iterator[DataChunk]:
        """Iterate first-axis chunks without flattening high-dimensional arrays."""

        _validate_positive_budget(target_bytes, "target_bytes")
        chunk_budget = min(target_bytes, self._memory_budget_bytes)
        shape = self._metadata.shape
        if not shape:
            values = self.read({})
            yield DataChunk(
                values=values,
                origin=(),
                selection=self._binding.selection.to_json(),
                is_last=True,
            )
            return

        rows_per_chunk = _rows_per_chunk(
            shape=shape,
            dtype=self._metadata.dtype,
            target_bytes=chunk_budget,
        )
        for start in range(0, shape[0], rows_per_chunk):
            self._task.cancellation.raise_if_cancelled(operation="plugin.input.iter_chunks")
            stop = min(shape[0], start + rows_per_chunk)
            selection = SelectionSpec.hyperslab(AxisSelection.slice(0, start=start, stop=stop))
            result = self._document.read(
                ReadRequest(
                    resource_id=self._binding.resource_id,
                    selection=selection,
                    scope=OperationScope.SLICE,
                    max_bytes=chunk_budget,
                ),
                cancellation=self._task.cancellation,
                progress=self._source_progress,
            )
            yield DataChunk(
                values=_array_like_values(result.payload),
                origin=(start,) + tuple(0 for _axis in shape[1:]),
                selection=selection.to_json(),
                is_last=stop >= shape[0],
            )

    def _source_progress(self, completed: int, total: int | None, message: str) -> None:
        self._task.report_progress(completed=completed, total=total, message=message)


class PluginRunner:
    """Run trusted built-in plugins through budgeted access and task states."""

    def run(self, request: PluginRunRequest):
        """Run a plugin synchronously and return the terminal task snapshot."""

        task = request.task or request.document.create_task(f"plugin.run:{request.manifest.id}")
        try:
            task.start()
            inputs = tuple(
                self._build_input_access(request, binding=binding, task=task)
                for binding in request.inputs
            )
            context = PluginContext(
                run_id=task.task_id,
                inputs=inputs,
                parameters=request.parameters,
                memory_budget_bytes=request.memory_budget_bytes,
                temp_budget_bytes=request.temp_budget_bytes,
                is_cancelled=lambda: task.cancellation.is_cancelled,
                report_progress=lambda fraction, message: _report_plugin_progress(
                    task,
                    fraction,
                    message,
                ),
                emit_warning=lambda _code, _message: None,
            )
            result = request.plugin.run(context)
            task.cancellation.raise_if_cancelled(operation="plugin.run")
            if not isinstance(result, PluginResult):
                raise DataViewerError(
                    code=ErrorCode.PLUGIN_INVALID,
                    message="Plugin returned an invalid result object.",
                    operation="plugin.run",
                    details={"plugin_id": request.manifest.id},
                )
            if not request.document.accepts_task_result(task.snapshot()):
                return task.fail(
                    DataViewerError(
                        code=ErrorCode.TASK_FAILED,
                        message="Plugin result was discarded because the request is stale.",
                        operation="plugin.run",
                        details={"plugin_id": request.manifest.id},
                    )
                )
            return task.succeed(result)
        except DataViewerError as error:
            if error.code in {ErrorCode.TASK_CANCELLED, ErrorCode.READ_CANCELLED}:
                return _cancel_task(task)
            return task.fail(error)
        except Exception as exc:
            return task.fail(
                DataViewerError(
                    code=ErrorCode.PLUGIN_FAILED,
                    message="Plugin execution failed.",
                    operation="plugin.run",
                    details={"plugin_id": request.manifest.id},
                    cause=exc,
                )
            )

    def _build_input_access(
        self,
        request: PluginRunRequest,
        *,
        binding: PluginInputBinding,
        task: TaskRecord,
    ) -> BudgetedInputAccess:
        metadata = request.document.get_metadata(
            binding.resource_id,
            cancellation=task.cancellation,
        )
        return BudgetedInputAccess(
            document=request.document,
            binding=binding,
            metadata=metadata,
            task=task,
            memory_budget_bytes=request.memory_budget_bytes,
        )


def _descriptor_for(
    document: DocumentController,
    metadata: DataMetadata,
    selection: SelectionSpec,
) -> InputDescriptor:
    estimated_elements = prod(metadata.shape) if metadata.shape else 1
    return InputDescriptor(
        source_id=document.source_uri,
        source_fingerprint=document.snapshot().fingerprint.to_json(),
        resource_path=metadata.resource_id.node_path,
        domain=metadata.domain.value,
        shape=metadata.shape,
        dtype=metadata.dtype,
        selection=selection.to_json(),
        estimated_elements=int(estimated_elements),
        estimated_bytes=metadata.logical_size_bytes,
    )


def _selection_from_mapping(selection: Mapping[str, object]) -> SelectionSpec:
    return SelectionSpec.from_json(_json_mapping(selection))


def _json_mapping(value: Mapping[str, object]) -> Mapping[str, JsonValue]:
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise ValueError(f"selection contains non-JSON value: {type(value).__name__}")


def _array_like_values(payload: object) -> NDArray[np.generic]:
    if isinstance(payload, (ArrayPayload, VolumePayload)):
        return payload.values
    if isinstance(payload, TablePayload):
        return np.column_stack(payload.column_values)
    raise DataViewerError(
        code=ErrorCode.CAPABILITY_UNAVAILABLE,
        message="Plugin input access supports array-like payloads only in this runner slice.",
        operation="plugin.input.read",
    )


def _rows_per_chunk(*, shape: tuple[int, ...], dtype: str, target_bytes: int) -> int:
    trailing = prod(shape[1:]) if len(shape) > 1 else 1
    try:
        item_size = np.dtype(dtype).itemsize
    except TypeError:
        item_size = 8
    row_bytes = max(1, int(trailing) * int(item_size))
    return max(1, target_bytes // row_bytes)


def _report_plugin_progress(
    task: TaskRecord,
    fraction: float | None,
    message: str,
) -> None:
    if fraction is None:
        task.report_progress(completed=0, total=None, message=message)
        return
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("plugin progress fraction must be between 0.0 and 1.0")
    task.report_progress(completed=int(fraction * 1000), total=1000, message=message)


def _cancel_task(task: TaskRecord):
    snapshot = task.snapshot()
    if snapshot.state is TaskState.QUEUED:
        return task.request_cancel()
    if snapshot.state is TaskState.RUNNING:
        task.request_cancel()
        return task.cancelled()
    if snapshot.state is TaskState.CANCELLING:
        return task.cancelled()
    return snapshot


def _validate_positive_budget(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")


__all__ = [
    "BudgetedInputAccess",
    "PluginInputBinding",
    "PluginRunRequest",
    "PluginRunner",
]
