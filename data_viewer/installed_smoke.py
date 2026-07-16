"""Functional smoke workflow executed from installed Data Viewer artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
import gzip
import json
import os
from pathlib import Path
from collections.abc import Mapping
from typing import Any, cast

import h5py
import nibabel as nib
import numpy as np
from PySide6.QtWidgets import QApplication

from data_viewer import __version__
from data_viewer.app.documents import DocumentController
from data_viewer.domain import (
    OperationScope,
    ResourceId,
    SelectionSpec,
)
from data_viewer.exporting import (
    ExportScope,
    ExportService,
    ExportValueMode,
    build_export_plan,
)
from data_viewer.gui.shell import DataViewerShell, create_source_registry
from data_viewer.plugins.api import DataViewerPlugin
from data_viewer.plugins.parameters import (
    default_parameters,
    validate_parameter_schema,
    validate_parameters,
)
from data_viewer.plugins.registry import discover_builtin_plugins
from data_viewer.plugins.results import validate_plugin_result
from data_viewer.plugins.runner import PluginInputBinding, PluginRunRequest, PluginRunner
from data_viewer.sources import ReadRequest
from data_viewer.tasks import CancellationToken, TaskState
from data_viewer.workspace import WorkspaceManifest, WorkspaceService, WorkspaceSource, WorkspaceView


DATASET_PROFILE_ID = "org.dataviewer.dataset_profile"


def run_installed_artifact_smoke(
    *,
    workspace_dir: Path,
    report_path: Path,
    screenshot_path: Path | None = None,
) -> dict[str, Any]:
    """Run a representative installed-artifact workflow and write evidence files."""

    workspace_dir = workspace_dir.resolve()
    fixture_dir = workspace_dir / "fixtures"
    output_dir = workspace_dir / "outputs"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    fixtures = _create_smoke_fixtures(fixture_dir)

    registry = create_source_registry()
    opened: list[dict[str, Any]] = []
    documents: list[DocumentController] = []
    plugin_report: dict[str, Any] | None = None
    export_report: dict[str, Any] | None = None
    workspace_report: dict[str, Any] | None = None

    try:
        hdf5_document, hdf5_resource = _open_and_read(
            fixtures["hdf5"],
            registry=registry,
            expected_format="hdf5",
            opened=opened,
            resource_path="/array",
        )
        documents.append(hdf5_document)

        csv_document, csv_resource = _open_and_read(
            fixtures["csv"],
            registry=registry,
            expected_format="csv",
            opened=opened,
            scope=OperationScope.PAGE,
        )
        documents.append(csv_document)

        nifti_document, _nifti_resource = _open_and_read(
            fixtures["nifti"],
            registry=registry,
            expected_format="nifti",
            opened=opened,
            resource_path="/volume",
        )
        documents.append(nifti_document)

        gzip_document, _gzip_resource = _open_and_read(
            fixtures["gzip_csv"],
            registry=registry,
            expected_format="gzip-csv",
            opened=opened,
            scope=OperationScope.PAGE,
        )
        documents.append(gzip_document)

        plugin_report = _run_dataset_profile_plugin(
            document=hdf5_document,
            resource_id=hdf5_resource,
        )
        export_report = _export_plugin_report(
            document=hdf5_document,
            resource_id=hdf5_resource,
            plugin_report=plugin_report,
            target_path=output_dir / "dataset-profile.json",
        )
        workspace_report = _save_and_load_workspace(
            workspace_path=output_dir / "installed-smoke.dvw",
            csv_path=fixtures["csv"],
            csv_document=csv_document,
            csv_resource=csv_resource,
            opened=opened,
        )
        if screenshot_path is not None:
            _capture_offscreen_screenshot(screenshot_path)
    finally:
        closed_count = 0
        for document in documents:
            document.close(timeout=2.0)
            closed_count += 1

    if plugin_report is None or export_report is None or workspace_report is None:
        raise RuntimeError("installed artifact smoke did not complete all phases")

    report: dict[str, Any] = {
        "status": "passed",
        "application": {"name": "Data Viewer", "version": __version__},
        "created_at_utc": _utc_now(),
        "workspace_dir": str(workspace_dir),
        "opened": opened,
        "plugin": plugin_report,
        "export": export_report,
        "workspace": workspace_report,
        "screenshot": str(screenshot_path) if screenshot_path is not None else None,
        "closed_documents": closed_count,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _create_smoke_fixtures(fixture_dir: Path) -> dict[str, Path]:
    hdf5_path = fixture_dir / "representative.h5"
    with h5py.File(hdf5_path, "w") as hdf5_file:
        hdf5_file.create_dataset(
            "array",
            data=np.array([[1.0, 2.0, 3.0], [4.0, np.nan, 6.0]], dtype=np.float64),
        )

    csv_path = fixture_dir / "representative.csv"
    csv_path.write_text("id,value\n1,10.5\n2,20.25\n", encoding="utf-8")

    gzip_csv_path = fixture_dir / "representative.csv.gz"
    with gzip.open(gzip_csv_path, "wt", encoding="utf-8", newline="") as gzip_file:
        gzip_file.write("id,value\n1,100\n2,200\n")

    nifti_path = fixture_dir / "representative.nii.gz"
    volume = np.arange(24, dtype=np.int16).reshape((2, 3, 4))
    image = nib.Nifti1Image(volume, np.eye(4))
    nib.save(image, nifti_path)
    return {
        "hdf5": hdf5_path,
        "csv": csv_path,
        "gzip_csv": gzip_csv_path,
        "nifti": nifti_path,
    }


def _open_and_read(
    path: Path,
    *,
    registry,
    expected_format: str,
    opened: list[dict[str, Any]],
    resource_path: str | None = None,
    scope: OperationScope = OperationScope.SLICE,
) -> tuple[DocumentController, ResourceId]:
    document = DocumentController.open_path(
        path,
        registry=registry,
        cancellation=CancellationToken(),
    )
    root = document.root(cancellation=CancellationToken())
    page = document.list_children(
        root.resource_id,
        cursor=None,
        page_size=20,
        cancellation=CancellationToken(),
    )
    resource = (
        ResourceId(document.source_uri, resource_path)
        if resource_path is not None
        else page.items[0].resource_id
    )
    metadata = document.get_metadata(resource, cancellation=CancellationToken())
    read_request = ReadRequest(
        resource_id=resource,
        selection=SelectionSpec.all(),
        scope=scope,
        max_bytes=1024 * 1024,
        row_offset=0 if scope is OperationScope.PAGE else None,
        row_limit=10 if scope is OperationScope.PAGE else None,
    )
    result = document.read(
        read_request,
        cancellation=CancellationToken(),
        progress=lambda _done, _total, _message: None,
    )
    opened.append(
        {
            "format": expected_format,
            "path": str(path),
            "resource_path": resource.node_path,
            "domain": metadata.domain.value,
            "shape": list(metadata.shape),
            "dtype": metadata.dtype,
            "scope": result.scope.value,
        }
    )
    return document, resource


def _run_dataset_profile_plugin(
    *,
    document: DocumentController,
    resource_id: ResourceId,
) -> dict[str, Any]:
    registry = discover_builtin_plugins()
    manifest = registry.manifest_for(DATASET_PROFILE_ID)
    plugin_class = registry.load_plugin_class(DATASET_PROFILE_ID)
    plugin = cast(DataViewerPlugin, plugin_class())
    schema = validate_parameter_schema(manifest.parameters_schema)
    parameters = validate_parameters(schema, default_parameters(schema))
    snapshot = PluginRunner().run(
        PluginRunRequest(
            manifest=manifest,
            plugin=plugin,
            document=document,
            inputs=(PluginInputBinding(resource_id=resource_id, selection=SelectionSpec.all()),),
            parameters=parameters,
            memory_budget_bytes=1024 * 1024,
            temp_budget_bytes=1024 * 1024,
        )
    )
    if snapshot.state is not TaskState.SUCCEEDED:
        message = snapshot.error.message if snapshot.error is not None else "unknown plugin failure"
        raise RuntimeError(f"Dataset Profile smoke failed: {message}")
    result = validate_plugin_result(snapshot.result)
    return {
        "plugin_id": result.provenance.plugin_id,
        "plugin_version": result.provenance.plugin_version,
        "state": snapshot.state.value,
        "result_kind": result.kind.value,
        "payload": dict(_mapping_payload(result.payload)),
    }


def _export_plugin_report(
    *,
    document: DocumentController,
    resource_id: ResourceId,
    plugin_report: dict[str, Any],
    target_path: Path,
) -> dict[str, Any]:
    plan = build_export_plan(
        source_fingerprint=document.snapshot().fingerprint,
        target_path=target_path,
        scope=ExportScope.PLUGIN_RESULT,
        value_mode=ExportValueMode.DISPLAY,
        resource_id=resource_id,
        parameters={"plugin_id": DATASET_PROFILE_ID},
        overwrite=True,
    )
    receipt = ExportService().export_payload(plan, plugin_report)
    if not receipt.succeeded:
        raise RuntimeError(f"Smoke export failed: {receipt.error_message}")
    data = receipt.to_json()
    return {
        "outcome": data["outcome"],
        "target_path": data["target_path"],
        "bytes_written": data["bytes_written"],
        "target_format": data["target_format"],
    }


def _save_and_load_workspace(
    *,
    workspace_path: Path,
    csv_path: Path,
    csv_document: DocumentController,
    csv_resource: ResourceId,
    opened: list[dict[str, Any]],
) -> dict[str, Any]:
    service = WorkspaceService()
    relative = Path(os.path.relpath(csv_path, workspace_path.parent))
    manifest = WorkspaceManifest(
        workspace_id="installed-smoke",
        title="Installed smoke workspace",
        created_at="2026-07-15T00:00:00Z",
        updated_at="2026-07-15T00:00:00Z",
        sources=(
            WorkspaceSource(
                source_id="csv-source",
                display_name=csv_path.name,
                path=str(relative),
                path_kind="relative",
                format_id="csv",
                fingerprint=csv_document.snapshot().fingerprint.to_json(),
            ),
        ),
        views=(
            WorkspaceView(
                view_id="csv-table",
                source_id="csv-source",
                resource_path=csv_resource.node_path,
                resource_domain="table",
                view_type="table",
                selection={"kind": "all"},
            ),
        ),
    )
    service.save(workspace_path, manifest)
    loaded = service.load(workspace_path)
    resolved = service.resolve_source_path(loaded.sources[0], workspace_path)
    opened.append(
        {
            "format": "workspace",
            "path": str(workspace_path),
            "sources": len(loaded.sources),
            "views": len(loaded.views),
            "resolved_source_exists": resolved.exists(),
        }
    )
    return {
        "path": str(workspace_path),
        "sources": len(loaded.sources),
        "views": len(loaded.views),
        "resolved_source": str(resolved),
    }


def _capture_offscreen_screenshot(path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(["data-viewer-ci-smoke"])
    shell = DataViewerShell()
    try:
        shell.resize(1024, 768)
        shell.show()
        app.processEvents()
        image = shell.grab()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(path)):
            raise RuntimeError(f"Could not save smoke screenshot: {path}")
    finally:
        shell.close()
        app.processEvents()
        if owns_app:
            app.quit()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mapping_payload(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("Dataset Profile did not return a summary mapping")
    return payload


__all__ = ["run_installed_artifact_smoke"]
