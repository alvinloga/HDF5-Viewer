"""DV-0704 typed plugin results, PlotSpec, and provenance contracts."""

from __future__ import annotations

import numpy as np
import pytest

from data_viewer.plugins.api import (
    InputDescriptor,
    PluginResult,
    ResultKind,
    ResultProvenance,
)
from data_viewer.plugins.results import (
    ArrayResultPayload,
    BoundedResultStore,
    PlotMark,
    PlotSpec,
    ResultColumn,
    ResultValidationError,
    TableResultPayload,
    materialize_plugin_result,
    validate_plugin_result,
)


def _descriptor() -> InputDescriptor:
    return InputDescriptor(
        source_id="file:///tmp/source.npy",
        source_fingerprint={"size_bytes": 64, "modified_time_ns": 1, "content_tag": None},
        resource_path="/array",
        domain="array",
        shape=(4, 4),
        dtype="float64",
        selection={"axes": []},
        estimated_elements=16,
        estimated_bytes=128,
    )


def _provenance(*, sampled: bool = False) -> ResultProvenance:
    return ResultProvenance(
        plugin_id="org.dataviewer.result_test",
        plugin_version="1.2.3",
        api_version=1,
        inputs=(_descriptor(),),
        parameters={"nan_policy": "omit"},
        computation_scope="slice",
        sampled=sampled,
    )


def _result(kind: ResultKind, payload: object, *, warnings: tuple[str, ...] = ()) -> PluginResult:
    return PluginResult(
        kind=kind,
        title=f"{kind.value} result",
        payload=payload,
        provenance=_provenance(),
        metadata={"unit": "a.u."},
        warnings=warnings,
    )


def test_summary_table_array_image_and_collection_results_validate_and_export_provenance() -> None:
    """Every non-plot v1 result kind has a typed validated payload and provenance summary."""

    summary = validate_plugin_result(_result(ResultKind.SUMMARY, {"mean": 1.5, "count": 4}))
    table = validate_plugin_result(
        _result(
            ResultKind.TABLE,
            TableResultPayload(
                columns=(ResultColumn("metric", "string"), ResultColumn("value", "float64")),
                rows=({"metric": "mean", "value": 1.5},),
            ),
        )
    )
    array = validate_plugin_result(
        _result(
            ResultKind.ARRAY,
            ArrayResultPayload(
                values=np.arange(4, dtype=np.int16),
                axes=("sample",),
                source_selection={"axes": []},
            ),
        )
    )
    image = validate_plugin_result(
        _result(
            ResultKind.IMAGE,
            ArrayResultPayload(
                values=np.arange(4, dtype=np.uint8).reshape(2, 2),
                axes=("y", "x"),
                source_selection={"axes": []},
            ),
        )
    )
    collection = validate_plugin_result(
        _result(ResultKind.COLLECTION, (summary, table, array, image), warnings=("derived",))
    )

    assert summary.materialization == "inline"
    assert table.payload.rows[0]["metric"] == "mean"
    assert array.payload.values.shape == (4,)
    assert image.result_channel == "workspace.image"
    exported = collection.to_export_record()
    assert exported["plugin_id"] == "org.dataviewer.result_test"
    assert exported["plugin_version"] == "1.2.3"
    assert exported["result_kind"] == "collection"
    assert exported["parameters"] == {"nan_policy": "omit"}
    assert exported["warnings"] == ["derived"]
    assert exported["inputs"][0]["resource_path"] == "/array"


def test_plot_spec_is_declarative_and_renderer_supported() -> None:
    """Plots are declarative specs, not renderer-owned figure objects."""

    plot = validate_plugin_result(
        _result(
            ResultKind.PLOT,
            PlotSpec(
                title="Finite range",
                x_label="sample",
                y_label="value",
                marks=(
                    PlotMark(
                        kind="line",
                        x=(0.0, 1.0, 2.0),
                        y=(3.0, 4.0, 5.0),
                        label="series",
                    ),
                ),
            ),
        )
    )

    assert plot.result_channel == "workspace.plot"
    assert plot.payload.supported_marks == ("line",)
    assert "Finite range" in plot.accessible_summary()


def test_invalid_result_payloads_are_rejected() -> None:
    """Invalid schemas fail before plugin results reach workspace/export UI."""

    with pytest.raises(ResultValidationError, match="summary"):
        validate_plugin_result(_result(ResultKind.SUMMARY, {"bad": object()}))
    with pytest.raises(ResultValidationError, match="plot mark"):
        validate_plugin_result(
            _result(
                ResultKind.PLOT,
                PlotSpec(
                    title="Bad",
                    x_label="x",
                    y_label="y",
                    marks=(PlotMark(kind="line", x=(1.0,), y=(1.0, 2.0)),),
                ),
            )
        )


def test_large_array_materialization_is_bounded_by_result_store() -> None:
    """Large array results are stored only when the result store budget allows it."""

    result = _result(
        ResultKind.ARRAY,
        ArrayResultPayload(
            values=np.arange(32, dtype=np.int64),
            axes=("sample",),
            source_selection={"axes": []},
        ),
    )
    store = BoundedResultStore(max_bytes=512)

    materialized = materialize_plugin_result(result, store=store, inline_budget_bytes=16)

    assert materialized.materialization == "stored"
    assert store.bytes_used == result.payload.values.nbytes
    np.testing.assert_array_equal(store.load_array(materialized.result_id), result.payload.values)

    tiny_store = BoundedResultStore(max_bytes=8)
    with pytest.raises(ResultValidationError, match="budget"):
        materialize_plugin_result(result, store=tiny_store, inline_budget_bytes=16)
