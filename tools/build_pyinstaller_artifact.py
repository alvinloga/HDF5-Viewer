"""Build deterministic-enough Data Viewer PyInstaller artifacts for CI."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_viewer import __version__  # noqa: E402


APP_NAME = "DataViewer"


def platform_tag(platform: str = sys.platform) -> str:
    """Return the release platform tag for the current Python platform."""

    if platform.startswith("win"):
        return "windows-x86_64"
    if platform.startswith("linux"):
        return "linux-x86_64"
    raise ValueError(f"Unsupported packaging platform: {platform}")


def executable_name(platform: str = sys.platform) -> str:
    """Return the bundled executable name for a platform."""

    return f"{APP_NAME}.exe" if platform.startswith("win") else APP_NAME


def artifact_name(*, version: str = __version__, platform: str = sys.platform) -> str:
    """Return the final archive filename."""

    tag = platform_tag(platform)
    suffix = "zip" if platform.startswith("win") else "tar.gz"
    return f"{APP_NAME}-{version}-{tag}.{suffix}"


def build_pyinstaller_distribution(
    *,
    project_root: Path,
    dist_dir: Path,
    work_dir: Path,
) -> Path:
    """Run PyInstaller and return the created onedir distribution."""

    spec = project_root / "packaging" / "DataViewer.spec"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec),
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
    ]
    subprocess.run(command, cwd=project_root, check=True)
    bundle_dir = dist_dir / APP_NAME
    executable = bundle_dir / executable_name()
    if not executable.exists():
        raise FileNotFoundError(f"PyInstaller did not create expected executable: {executable}")
    return bundle_dir


def archive_distribution(
    *,
    bundle_dir: Path,
    output_dir: Path,
    version: str = __version__,
    platform: str = sys.platform,
) -> Path:
    """Archive a PyInstaller onedir distribution."""

    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / artifact_name(version=version, platform=platform)
    if archive.exists():
        archive.unlink()

    if platform.startswith("win"):
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
            for path in sorted(bundle_dir.rglob("*")):
                if path.is_file():
                    zip_file.write(path, path.relative_to(bundle_dir.parent))
    else:
        with tarfile.open(archive, "w:gz") as tar_file:
            tar_file.add(bundle_dir, arcname=bundle_dir.name)
    return archive


def write_manifest(
    *,
    output_dir: Path,
    archive: Path,
    bundle_dir: Path,
    version: str = __version__,
) -> Path:
    """Write a JSON manifest consumed by CI smoke steps."""

    manifest = {
        "app_name": APP_NAME,
        "version": version,
        "platform": platform_tag(),
        "artifact": str(archive),
        "bundle_dir": str(bundle_dir),
        "executable": str(bundle_dir / executable_name()),
    }
    path = output_dir / "pyinstaller-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Data Viewer PyInstaller artifact.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts") / "package")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist") / "pyinstaller")
    parser.add_argument("--work-dir", type=Path, default=Path("build") / "pyinstaller")
    parser.add_argument("--skip-build", action="store_true", help="Archive an existing dist bundle.")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    dist_dir = (project_root / args.dist_dir).resolve()
    work_dir = (project_root / args.work_dir).resolve()
    output_dir = (project_root / args.output_dir).resolve()

    if not args.skip_build:
        shutil.rmtree(dist_dir, ignore_errors=True)
        shutil.rmtree(work_dir, ignore_errors=True)
        bundle_dir = build_pyinstaller_distribution(
            project_root=project_root,
            dist_dir=dist_dir,
            work_dir=work_dir,
        )
    else:
        bundle_dir = dist_dir / APP_NAME

    archive = archive_distribution(bundle_dir=bundle_dir, output_dir=output_dir)
    manifest = write_manifest(output_dir=output_dir, archive=archive, bundle_dir=bundle_dir)
    print(json.dumps({"archive": str(archive), "manifest": str(manifest)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
