"""Packaging contracts for Data Viewer PyInstaller artifacts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from data_viewer import __version__
from tools.build_pyinstaller_artifact import artifact_name, executable_name, platform_tag


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_COMPACT_NAME = "HDF5" + "Viewer"


def test_data_viewer_pyinstaller_spec_uses_current_product_name() -> None:
    spec = PROJECT_ROOT / "packaging" / "DataViewer.spec"
    text = spec.read_text(encoding="utf-8")

    assert "DataViewer" in text
    assert LEGACY_COMPACT_NAME not in text
    assert "data_viewer" in text
    assert "pyinstaller_entry.py" in text


def test_packaging_artifact_names_are_data_viewer_and_platform_specific() -> None:
    assert artifact_name(version=__version__, platform="win32") == (
        f"DataViewer-{__version__}-windows-x86_64.zip"
    )
    assert artifact_name(version=__version__, platform="linux") == (
        f"DataViewer-{__version__}-linux-x86_64.tar.gz"
    )
    assert executable_name(platform="win32") == "DataViewer.exe"
    assert executable_name(platform="linux") == "DataViewer"
    assert platform_tag("win32") == "windows-x86_64"
    assert platform_tag("linux") == "linux-x86_64"


def test_ci_builds_and_uploads_data_viewer_pyinstaller_artifacts() -> None:
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    steps = workflow["jobs"]["quality"]["steps"]
    step_names = [step["name"] for step in steps]

    assert "Build Data Viewer PyInstaller artifact" in step_names
    assert "Smoke-test Data Viewer executable" in step_names
    assert "Upload Data Viewer package artifact" in step_names


def test_ci_compile_gate_excludes_legacy_runtime_paths() -> None:
    """DV-1008 keeps release compile gates focused on target Data Viewer paths."""

    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    steps = workflow["jobs"]["quality"]["steps"]
    compile_step = next(step for step in steps if step["name"] == "Compile Data Viewer target paths")
    compile_command = compile_step["run"]

    assert "data_viewer" in compile_command
    assert ".github/scripts" in compile_command
    assert "tools" in compile_command
    for legacy_path in ("core", "gui", "plugins", "services", "utils", "main.py"):
        assert legacy_path not in compile_command


def test_legacy_pyinstaller_build_entrypoints_are_removed() -> None:
    """DV-1008 removes obsolete legacy release launchers from the root packaging surface."""

    for legacy_entrypoint in (
        "HDF5Viewer.spec",
        "build_windows.py",
        "build_windows.bat",
        "main.py",
    ):
        assert not (PROJECT_ROOT / legacy_entrypoint).exists()

    build_script = PROJECT_ROOT / "build.py"
    text = build_script.read_text(encoding="utf-8")
    assert "Data Viewer" in text
    assert "tools/build_pyinstaller_artifact.py" in text
    for legacy_token in ("HDF5Viewer", "HDF5Viewer.spec", "main.py", "hdf5viewer_build"):
        assert legacy_token not in text


def test_root_build_wrapper_does_not_shadow_pypa_build_module() -> None:
    """DV-1008 keeps the standard wheel/sdist build entry point usable."""

    result = subprocess.run(
        [sys.executable, "-m", "build", "--version"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert "build.py: error" not in result.stderr
    assert "Traceback" not in result.stderr
    if result.returncode == 0:
        assert "build " in result.stdout
    else:
        assert "PyPA build is not installed" in result.stderr


def test_legacy_packaged_build_smoke_suite_is_removed() -> None:
    """DV-1008 uses target artifact smoke tests instead of legacy source imports."""

    legacy_packaged_suite = PROJECT_ROOT / "tests" / "test_packaged.py"
    assert not legacy_packaged_suite.exists()

    target_smoke = (PROJECT_ROOT / "tests" / "test_installed_artifact_smoke.py").read_text(
        encoding="utf-8"
    )
    assert "run_installed_artifact_smoke" in target_smoke
    assert "--ci-smoke" in target_smoke

    for legacy_import in ("from core", "from gui", "from plugins", "from services"):
        assert legacy_import not in target_smoke


def test_legacy_final_integration_smoke_script_is_removed() -> None:
    """DV-1008 removes the obsolete source-import final integration script."""

    legacy_final_suite = PROJECT_ROOT / "tests" / "test_final.py"
    assert not legacy_final_suite.exists()

    environment_test = (
        PROJECT_ROOT / "tests" / "test_test_environment.py"
    ).read_text(encoding="utf-8")
    assert "test_final.py" not in environment_test

    for target_test in (
        "tests/test_data_viewer_package.py",
        "tests/test_installed_artifact_smoke.py",
        "tests/test_source_registry.py",
        "tests/test_hdf5_adapter.py",
    ):
        assert (PROJECT_ROOT / target_test).exists()


def test_legacy_all_features_smoke_script_is_removed() -> None:
    """DV-1008 removes the obsolete comprehensive legacy smoke script."""

    legacy_all_features_suite = PROJECT_ROOT / "tests" / "test_all_features.py"
    assert not legacy_all_features_suite.exists()

    environment_test = (
        PROJECT_ROOT / "tests" / "test_test_environment.py"
    ).read_text(encoding="utf-8")
    assert "test_all_features.py" not in environment_test

    for retained_suite in (
        "tests/test_gui_shell.py",
        "tests/test_gui_base_views.py",
        "tests/test_gui_state_components.py",
        "tests/test_source_registry.py",
        "tests/test_hdf5_adapter.py",
        "tests/test_plugin_registry.py",
        "tests/test_navigation_search.py",
    ):
        assert (PROJECT_ROOT / retained_suite).exists()


def test_legacy_comprehensive_suite_is_removed() -> None:
    """DV-1008 removes the obsolete legacy comprehensive source-import suite."""

    assert not (PROJECT_ROOT / "tests" / "test_comprehensive.py").exists()

    for retained_target_suite in (
        "tests/test_gui_shell.py",
        "tests/test_gui_base_views.py",
        "tests/test_gui_dialogs.py",
        "tests/test_gui_i18n_accessibility.py",
        "tests/test_gui_state_components.py",
        "tests/test_gui_theme.py",
        "tests/test_source_registry.py",
        "tests/test_hdf5_adapter.py",
        "tests/test_plugin_registry.py",
        "tests/test_plugin_runner.py",
        "tests/test_navigation_search.py",
        "tests/test_command_registry.py",
        "tests/test_editing_session.py",
        "tests/test_exporting.py",
    ):
        assert (PROJECT_ROOT / retained_target_suite).exists()


def test_legacy_core_unit_suite_is_removed() -> None:
    """DV-1008 removes the obsolete legacy core unit suite."""

    assert not (PROJECT_ROOT / "tests" / "test_core.py").exists()

    for retained_target_suite in (
        "tests/test_source_registry.py",
        "tests/test_hdf5_adapter.py",
        "tests/test_infrastructure_cache.py",
        "tests/test_task_lifecycle.py",
        "tests/test_selection_payload_types.py",
    ):
        assert (PROJECT_ROOT / retained_target_suite).exists()


def test_legacy_integration_suite_is_removed() -> None:
    """DV-1008 removes the obsolete legacy source-import integration suite."""

    assert not (PROJECT_ROOT / "tests" / "test_integration.py").exists()

    for retained_target_suite in (
        "tests/test_hdf5_adapter.py",
        "tests/test_plugin_runner.py",
        "tests/test_plugin_registry.py",
        "tests/test_exporting.py",
        "tests/test_source_registry.py",
    ):
        assert (PROJECT_ROOT / retained_target_suite).exists()


def test_legacy_edge_case_suite_is_removed() -> None:
    """DV-1008 removes the obsolete legacy edge-case source-import suite."""

    assert not (PROJECT_ROOT / "tests" / "test_edge_cases.py").exists()

    for retained_target_suite in (
        "tests/test_hdf5_adapter.py",
        "tests/test_selection_payload_types.py",
        "tests/test_builtin_statistics_plugins.py",
        "tests/test_exporting.py",
        "tests/test_infrastructure_cache.py",
        "tests/test_error_diagnostics.py",
        "tests/test_gui_base_views.py",
    ):
        assert (PROJECT_ROOT / retained_target_suite).exists()


def test_legacy_phase1_gui_smoke_suite_is_removed() -> None:
    """DV-1008 removes the obsolete legacy Phase 1 GUI smoke suite."""

    assert not (PROJECT_ROOT / "tests" / "test_phase1.py").exists()

    environment_test = (
        PROJECT_ROOT / "tests" / "test_test_environment.py"
    ).read_text(encoding="utf-8")
    assert "test_phase1.py" not in environment_test

    for retained_target_suite in (
        "tests/test_gui_shell.py",
        "tests/test_gui_base_views.py",
        "tests/test_gui_state_components.py",
    ):
        assert (PROJECT_ROOT / retained_target_suite).exists()


def test_legacy_gui_interaction_suite_is_removed() -> None:
    """DV-1008 removes the obsolete legacy GUI interaction source-import suite."""

    assert not (PROJECT_ROOT / "tests" / "test_gui_interaction.py").exists()

    for retained_target_suite in (
        "tests/test_gui_shell.py",
        "tests/test_gui_base_views.py",
        "tests/test_gui_dialogs.py",
        "tests/test_gui_i18n_accessibility.py",
        "tests/test_gui_state_components.py",
        "tests/test_gui_theme.py",
        "tests/test_navigation_search.py",
        "tests/test_command_registry.py",
    ):
        assert (PROJECT_ROOT / retained_target_suite).exists()


def test_legacy_stress_suite_is_removed() -> None:
    """DV-1008 removes the obsolete legacy stress source-import suite."""

    assert not (PROJECT_ROOT / "tests" / "test_stress.py").exists()

    for retained_target_suite in (
        "tests/test_hardening_stress.py",
        "tests/test_hdf5_adapter.py",
        "tests/test_infrastructure_cache.py",
        "tests/test_gzip_extraction_cache.py",
        "tests/test_task_lifecycle.py",
        "tests/test_performance_budgets.py",
    ):
        assert (PROJECT_ROOT / retained_target_suite).exists()


def test_format_scope_tests_do_not_import_legacy_gui() -> None:
    """DV-1008 keeps first-release format scope checks on the target registry."""

    format_scope_test = (PROJECT_ROOT / "tests" / "test_format_scope.py").read_text(
        encoding="utf-8"
    )

    assert "from gui." not in format_scope_test
    assert "import gui." not in format_scope_test


def test_test_environment_files_do_not_import_legacy_runtime() -> None:
    """DV-1008 removes legacy runtime cleanup hooks from target pytest configuration."""

    for relative_path in (
        "tests/conftest.py",
        "tests/test_test_environment.py",
    ):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for legacy_import in (
            "from core",
            "import core",
            "from gui",
            "import gui",
            "from plugins",
            "import plugins",
            "from services",
            "import services",
        ):
            assert legacy_import not in text


def test_legacy_empty_utils_package_is_removed() -> None:
    """DV-1008 removes the empty legacy utils compatibility package."""

    assert not (PROJECT_ROOT / "utils").exists()

    for retained_target_module in (
        "data_viewer/domain/resources.py",
        "data_viewer/domain/payload.py",
        "data_viewer/infrastructure/paths.py",
        "data_viewer/infrastructure/config.py",
    ):
        assert (PROJECT_ROOT / retained_target_module).exists()


def test_legacy_services_package_is_removed() -> None:
    """DV-1008 removes obsolete legacy service modules after target parity coverage."""

    assert not (PROJECT_ROOT / "services").exists()

    for retained_target_path in (
        "data_viewer/app/export_queue.py",
        "data_viewer/app/navigation.py",
        "data_viewer/exporting/service.py",
        "tests/test_exporting.py",
        "tests/test_navigation_search.py",
        "tests/test_export_queue_diagnostics.py",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()


def test_legacy_builtin_plugins_package_is_removed() -> None:
    """DV-1008 removes obsolete GUI-coupled legacy built-in plugins."""

    assert not (PROJECT_ROOT / "plugins" / "builtin").exists()

    for retained_target_path in (
        "data_viewer/plugins/builtin/dataset_profile/plugin.py",
        "data_viewer/plugins/builtin/plots/plugin.py",
        "tests/test_builtin_statistics_plugins.py",
        "tests/test_builtin_plot_plugins.py",
        "tests/test_builtin_heatmap_plugins.py",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()


def test_legacy_plugins_package_is_removed() -> None:
    """DV-1008 removes the obsolete legacy plugin API package."""

    assert not (PROJECT_ROOT / "plugins").exists()

    for retained_target_path in (
        "data_viewer/plugins/api.py",
        "data_viewer/plugins/manifests.py",
        "data_viewer/plugins/registry.py",
        "data_viewer/plugins/runner.py",
        "docs/PLUGIN_API.md",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()


def test_legacy_core_cache_module_is_removed() -> None:
    """DV-1008 removes the obsolete in-memory legacy core cache module."""

    assert not (PROJECT_ROOT / "core" / "cache.py").exists()

    for retained_target_path in (
        "data_viewer/infrastructure/cache.py",
        "tests/test_infrastructure_cache.py",
        "tests/test_gzip_extraction_cache.py",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()


def test_legacy_core_event_bus_module_is_removed() -> None:
    """DV-1008 removes the obsolete global legacy event bus module."""

    assert not (PROJECT_ROOT / "core" / "event_bus.py").exists()

    for retained_target_path in (
        "data_viewer/tasks/dispatcher.py",
        "data_viewer/tasks/state.py",
        "data_viewer/app/commands.py",
        "data_viewer/app/diagnostics.py",
        "tests/test_task_lifecycle.py",
        "tests/test_command_registry.py",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()


def test_legacy_core_slicer_module_is_removed() -> None:
    """DV-1008 removes the obsolete legacy string-based slicer module."""

    assert not (PROJECT_ROOT / "core" / "slicer.py").exists()

    for retained_target_path in (
        "data_viewer/domain/selection.py",
        "data_viewer/domain/payload.py",
        "data_viewer/gui/shell.py",
        "data_viewer/gui/views.py",
        "tests/test_selection_payload_types.py",
        "tests/test_gui_base_views.py",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()


def test_legacy_core_async_loader_module_is_removed() -> None:
    """DV-1008 removes the obsolete synchronous legacy async-loader shim."""

    assert not (PROJECT_ROOT / "core" / "async_loader.py").exists()

    for retained_target_path in (
        "data_viewer/tasks/cancellation.py",
        "data_viewer/tasks/dispatcher.py",
        "data_viewer/tasks/state.py",
        "data_viewer/app/documents.py",
        "tests/test_task_lifecycle.py",
        "tests/test_document_controller.py",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()


def test_legacy_gui_sidebar_package_is_removed() -> None:
    """DV-1008 removes obsolete legacy sidebar panels after target parity coverage."""

    assert not (PROJECT_ROOT / "gui" / "sidebar").exists()

    for retained_target_path in (
        "data_viewer/app/navigation.py",
        "data_viewer/gui/shell.py",
        "data_viewer/plugins/registry.py",
        "tests/test_navigation_search.py",
        "tests/test_gui_shell.py",
        "tests/test_plugin_registry.py",
    ):
        assert (PROJECT_ROOT / retained_target_path).exists()
