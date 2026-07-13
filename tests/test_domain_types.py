"""Contracts for the first Data Viewer domain value types."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from data_viewer.domain import (
    ColumnSpec,
    DataDomain,
    DataMetadata,
    FrozenJsonMapping,
    NodeKind,
    ResourceId,
    ResourceNode,
    SourceCapability,
    SourceFingerprint,
    SpatialMetadata,
    capabilities_from_names,
    capabilities_to_names,
)


def test_resource_id_uses_canonical_file_uri_and_node_path(tmp_path: Path) -> None:
    source_path = tmp_path / "Example File.h5"

    resource = ResourceId.from_file(source_path, "group//dataset/")

    assert resource.source_uri == source_path.resolve(strict=False).as_uri()
    assert resource.node_path == "/group/dataset"
    assert resource.to_json() == {
        "source_uri": source_path.resolve(strict=False).as_uri(),
        "node_path": "/group/dataset",
    }
    assert ResourceId.from_json(resource.to_json()) == resource
    assert len({resource, ResourceId(resource.source_uri, "/group/dataset")}) == 1


@pytest.mark.parametrize(
    ("source_uri", "node_path"),
    [
        ("", "/dataset"),
        ("not-a-uri", "/dataset"),
        ("file:///tmp/example.h5", "dataset"),
        ("file:///tmp/example.h5", "/group/../dataset"),
        ("file:///tmp/example.h5", "/group/./dataset"),
    ],
)
def test_resource_id_rejects_ambiguous_identity(
    source_uri: str, node_path: str
) -> None:
    with pytest.raises(ValueError):
        ResourceId(source_uri, node_path)


def test_domain_and_capability_values_are_stable_and_json_safe() -> None:
    capabilities = SourceCapability.HIERARCHY | SourceCapability.RANDOM_SLICE

    assert DataDomain.ARRAY.value == "array"
    assert DataDomain.VOLUME.value == "volume"
    assert NodeKind.RESOURCE.value == "resource"
    assert capabilities_to_names(capabilities) == ("HIERARCHY", "RANDOM_SLICE")
    assert capabilities_from_names(("RANDOM_SLICE", "HIERARCHY")) == capabilities
    assert capabilities_to_names(SourceCapability.NONE) == ()

    with pytest.raises(ValueError):
        capabilities_from_names(("HIERARCHY", "NOT_A_CAPABILITY"))


def test_metadata_values_are_immutable_hashable_and_json_serializable(
    tmp_path: Path,
) -> None:
    resource = ResourceId.from_file(tmp_path / "volume.nii", "/volume")
    attributes = {"units": ["mm", "s"], "nested": {"valid": True}}
    column = ColumnSpec("intensity", "float32", nullable=False)
    spatial = SpatialMetadata(
        affine=((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)),
        voxel_sizes=(1.0, 1.0, 1.5),
        axis_codes=("R", "A", "S"),
        units=("mm", "sec"),
    )

    metadata = DataMetadata(
        resource_id=resource,
        name="volume",
        domain=DataDomain.VOLUME,
        node_kind=NodeKind.RESOURCE,
        shape=(64, 64, 32),
        dtype="float32",
        logical_size_bytes=524288,
        storage_size_bytes=262144,
        capabilities=SourceCapability.RANDOM_SLICE
        | SourceCapability.SPATIAL_METADATA,
        attributes=attributes,
        columns=(column,),
        spatial=spatial,
    )
    attributes["nested"] = {"valid": False}

    encoded = metadata.to_json()

    assert metadata.attributes["nested"] == {"valid": True}
    assert encoded["resource_id"] == resource.to_json()
    assert encoded["domain"] == "volume"
    assert encoded["capabilities"] == ["RANDOM_SLICE", "SPATIAL_METADATA"]
    assert encoded["shape"] == [64, 64, 32]
    assert encoded["attributes"] == {
        "nested": {"valid": True},
        "units": ["mm", "s"],
    }
    assert json.loads(json.dumps(encoded)) == encoded
    assert hash(metadata) == hash(
        DataMetadata.from_json(metadata.to_json())
    )


def test_metadata_rejects_non_json_attributes_and_negative_sizes(
    tmp_path: Path,
) -> None:
    resource = ResourceId.from_file(tmp_path / "array.npy", "/array")

    with pytest.raises(ValueError):
        FrozenJsonMapping({"bad": math.inf})

    with pytest.raises(ValueError):
        SourceFingerprint(size_bytes=-1, modified_time_ns=0)

    with pytest.raises(ValueError):
        DataMetadata(
            resource_id=resource,
            name="array",
            domain=DataDomain.ARRAY,
            node_kind=NodeKind.RESOURCE,
            shape=(-1,),
        )


def test_resource_node_serializes_without_payload_or_library_objects(
    tmp_path: Path,
) -> None:
    resource = ResourceId.from_file(tmp_path / "table.csv", "/table")
    node = ResourceNode(
        resource_id=resource,
        name="table",
        node_kind=NodeKind.RESOURCE,
        domain=DataDomain.TABLE,
        has_children=False,
        summary="10 rows",
    )

    assert node.to_json() == {
        "resource_id": resource.to_json(),
        "name": "table",
        "node_kind": "resource",
        "domain": "table",
        "has_children": False,
        "summary": "10 rows",
    }
