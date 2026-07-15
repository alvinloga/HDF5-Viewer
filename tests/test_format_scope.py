"""First-release format-scope regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_viewer.domain import DataViewerError, ErrorCode
from data_viewer.gui.shell import create_source_registry
from gui.sidebar.folder_explorer import FolderExplorerTree


class _NeverCancelled:
    is_cancelled = False


def test_v1_registry_rejects_netcdf_and_zarr_as_unsupported(tmp_path: Path) -> None:
    registry = create_source_registry()
    unsupported_paths = [
        tmp_path / "sample.nc",
        tmp_path / "sample.nc4",
        tmp_path / "sample.netcdf",
        tmp_path / "sample.zarr",
    ]
    for path in unsupported_paths:
        path.write_bytes(b"not a registered first-release format")

    for path in unsupported_paths:
        with pytest.raises(DataViewerError) as exc_info:
            registry.select_adapter(path, cancellation=_NeverCancelled())

        assert exc_info.value.code is ErrorCode.SOURCE_UNSUPPORTED
        assert ".zarr" not in exc_info.value.details["adapter_ids"]
        assert "netcdf" not in str(exc_info.value.details["adapter_ids"]).lower()
        assert "zarr" not in str(exc_info.value.details["adapter_ids"]).lower()


def test_legacy_folder_explorer_defaults_do_not_advertise_zarr() -> None:
    filters = FolderExplorerTree._DEFAULT_FILE_FILTERS

    assert ".zarr" not in filters
    assert all("zarr" not in extension.lower() for extension in filters)


def test_target_entrypoint_does_not_import_netcdf_or_zarr_sources() -> None:
    main_source = Path("data_viewer/__main__.py").read_text(encoding="utf-8")

    assert "plugins.external.netcdf_source" not in main_source
    assert "plugins.external.zarr_source" not in main_source
    assert "NetCDFSource" not in main_source
    assert "ZarrSource" not in main_source


def test_requirements_do_not_ship_netcdf_or_zarr_dependency_claims() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8").lower()

    assert "netcdf" not in requirements
    assert "zarr" not in requirements


def test_legacy_external_netcdf_and_zarr_source_files_are_removed() -> None:
    assert not Path("plugins/external/netcdf_source.py").exists()
    assert not Path("plugins/external/zarr_source.py").exists()
