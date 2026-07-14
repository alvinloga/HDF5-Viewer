"""NIfTI adapter and coordinate model behavior for DataSource v1."""

from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from data_viewer.domain import (
    AxisSelection,
    DataDomain,
    DataViewerError,
    ErrorCode,
    OperationScope,
    ResourceId,
    SelectionSpec,
    SourceCapability,
    VolumePayload,
)
from data_viewer.sources.api import ReadRequest
from data_viewer.sources.nifti import NIFTIAdapter, NIFTISourceSession
from data_viewer.sources.registry import SourceRegistry
from data_viewer.tasks import CancellationToken


def _write_nifti(
    path: Path,
    *,
    shape: tuple[int, ...] = (2, 3, 4, 5),
) -> tuple[Path, np.ndarray, np.ndarray]:
    data = np.arange(np.prod(shape), dtype=np.int16).reshape(shape)
    affine = np.array(
        [
            [2.0, 0.0, 0.0, 10.0],
            [0.0, 3.0, 0.0, 20.0],
            [0.0, 0.0, 4.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    image = nib.Nifti1Image(data, affine)
    image.header.set_xyzt_units("mm", "sec")
    image.header.set_intent("estimate")
    image.header.set_slope_inter(2.0, 10.0)
    nib.save(image, path)
    return path, data, affine


def test_nifti_adapter_opens_native_nii_gz_with_spatial_metadata(tmp_path: Path) -> None:
    path, _data, affine = _write_nifti(tmp_path / "image.nii.gz")
    registry = SourceRegistry([NIFTIAdapter()])
    session = registry.open(path, cancellation=CancellationToken())
    root = session.root()
    page = session.list_children(
        root.resource_id,
        cursor=None,
        page_size=10,
        cancellation=CancellationToken(),
    )
    metadata = session.get_metadata(
        ResourceId(session.source_uri, "/volume"),
        cancellation=CancellationToken(),
    )

    assert root.domain is DataDomain.VOLUME
    assert [item.resource_id.node_path for item in page.items] == ["/volume"]
    assert metadata.domain is DataDomain.VOLUME
    assert metadata.shape == (2, 3, 4, 5)
    assert metadata.dtype == "int16"
    assert metadata.spatial is not None
    assert metadata.spatial.axis_codes == ("R", "A", "S")
    assert metadata.spatial.voxel_sizes == (2.0, 3.0, 4.0, 1.0)
    assert metadata.spatial.units == ("mm", "sec")
    np.testing.assert_allclose(np.array(metadata.spatial.affine), affine)
    assert metadata.attributes["native_nifti_gzip"] is True
    assert metadata.attributes["proxy_type"] == "ArrayProxy"
    assert metadata.attributes["slope_intercept"] == {"slope": 2.0, "intercept": 10.0}
    assert metadata.attributes["header_slope_intercept"] == {"slope": None, "intercept": None}
    assert metadata.attributes["intent"] == {
        "code": 1001,
        "label": "estimate",
        "name": "",
        "parameters": [],
    }
    assert SourceCapability.EDIT_PATCH not in metadata.capabilities
    assert SourceCapability.ATOMIC_REWRITE not in metadata.capabilities
    session.close()


def test_nifti_reads_bounded_proxy_slice_and_coordinate_mapping(tmp_path: Path) -> None:
    path, data, affine = _write_nifti(tmp_path / "slice.nii")
    session = NIFTIAdapter().open(path, cancellation=CancellationToken())
    selection = SelectionSpec.hyperslab(
        AxisSelection.slice(0, start=0, stop=2),
        AxisSelection(axis=1, index=1),
        AxisSelection.slice(2, start=1, stop=4),
        AxisSelection(axis=3, index=2),
    )
    result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/volume"),
            scope=OperationScope.SLICE,
            selection=selection,
            max_bytes=4096,
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert isinstance(result.payload, VolumePayload)
    assert result.payload.values.shape == (2, 3)
    expected_raw = data[:, 1, 1:4, 2]
    np.testing.assert_allclose(result.payload.values, expected_raw * 2.0 + 10.0)
    assert result.payload.selection.source_coordinates((1, 2)) == (1, 1, 3, 2)
    np.testing.assert_allclose(
        np.array(result.payload.spatial.affine),
        affine,
    )
    assert result.warnings == ("NIfTI values are scaled by the source proxy.",)
    session.close()


def test_nifti_voxel_world_mapping_and_no_full_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _data, _affine = _write_nifti(tmp_path / "mapping.nii")
    session = NIFTIAdapter().open(path, cancellation=CancellationToken())

    def fail_get_fdata(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ordinary slice reads must not call get_fdata")

    monkeypatch.setattr(session._image, "get_fdata", fail_get_fdata)  # noqa: SLF001
    world = session.voxel_to_world((1, 2, 3))
    voxel = session.world_to_voxel(world)
    result = session.read(
        ReadRequest(
            resource_id=ResourceId(session.source_uri, "/volume"),
            scope=OperationScope.SLICE,
            selection=SelectionSpec.hyperslab(
                AxisSelection(axis=0, index=1),
                AxisSelection.slice(1, start=0, stop=3),
                AxisSelection(axis=2, index=2),
                AxisSelection(axis=3, index=0),
            ),
        ),
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )

    assert world == (12.0, 26.0, 42.0)
    assert voxel == (1.0, 2.0, 3.0)
    assert isinstance(result.payload, VolumePayload)
    assert result.payload.values.shape == (3,)
    session.close()


def test_nifti_rejects_malformed_budget_and_closed_session(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.nii"
    malformed.write_bytes(b"not a nifti")
    path, _data, _affine = _write_nifti(tmp_path / "budget.nii")

    with pytest.raises(DataViewerError) as malformed_error:
        NIFTIAdapter().open(malformed, cancellation=CancellationToken())
    assert malformed_error.value.code is ErrorCode.SOURCE_MALFORMED

    with pytest.raises(DataViewerError) as budget_error:
        NIFTISourceSession(path, max_voxels=1)
    assert budget_error.value.code is ErrorCode.BUDGET_EXCEEDED

    session = NIFTIAdapter().open(path, cancellation=CancellationToken())
    session.close()
    with pytest.raises(DataViewerError) as closed_error:
        session.root()
    assert closed_error.value.code is ErrorCode.SOURCE_CLOSED
