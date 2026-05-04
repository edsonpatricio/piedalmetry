"""Update piedalmetry from a GitHub release archive.

Downloads a tar.gz archive (no git required — avoids CIFS .git chmod issues),
overwrites source files, re-syncs the venv, and restarts the service.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

GITHUB_REPO = "edsonpatricio/piedalmetry"


def update_service(
    release_tag: str | None = None,
    use_main: bool = False,
) -> None:
    """Download and apply a piedalmetry update from GitHub.

    Args:
        release_tag: Specific release tag to install (e.g. "v0.3.0").
            Defaults to the latest published release.
        use_main: If True, download from the main branch instead of a release.
    """
    project_root = Path(__file__).resolve().parents[3]

    if use_main:
        label = "main"
        url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.tar.gz"
    else:
        if release_tag is None:
            print("Fetching latest release tag...")
            release_tag = _get_latest_release_tag()
        label = release_tag
        url = f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{release_tag}.tar.gz"

    print(f"Updating piedalmetry to {label}")
    print(f"  Source:  {url}")
    print(f"  Project: {project_root}")

    archive_path = _download(url)
    try:
        _apply(archive_path, project_root)
    finally:
        Path(archive_path).unlink(missing_ok=True)

    _sync_venv(project_root)
    _restart_service()
    print("Done.")


def _get_latest_release_tag() -> str:
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        tag: str = json.loads(resp.read())["tag_name"]
    print(f"  Latest release: {tag}")
    return tag


def _download(url: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        path = tmp.name
    print("Downloading...")
    urllib.request.urlretrieve(url, path)
    return path


def _apply(archive_path: str, project_root: Path) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(archive_path) as tar:
            tar.extractall(tmpdir)
        extracted = next(Path(tmpdir).iterdir())
        print(f"  Extracted: {extracted.name}")

        shutil.copytree(extracted / "src", project_root / "src", dirs_exist_ok=True)
        shutil.copy2(extracted / "pyproject.toml", project_root / "pyproject.toml")
        shutil.copy2(
            extracted / "config.example.toml",
            project_root / "config.example.toml",
        )
    print("  Files updated.")


def _sync_venv(project_root: Path) -> None:
    print("Syncing dependencies...")
    # Derive venv from the running interpreter without .resolve() — following
    # the python3 symlink would land at /usr/bin/python3 (system Python) and
    # give parents[1] = /usr, which is invalid. The un-resolved path stays
    # inside the venv: <venv>/bin/python3 → parents[1] = <venv>.
    # sudo strips UV_PROJECT_ENVIRONMENT from the environment, so we set it
    # explicitly to prevent uv from trying to recreate .venv on the CIFS mount.
    venv_path = Path(sys.executable).parents[1]
    print(f"  Venv:    {venv_path}")
    subprocess.run(
        ["uv", "sync"],
        cwd=project_root,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(venv_path)},
        check=True,
    )


def _restart_service() -> None:
    print("Restarting service...")
    subprocess.run(
        ["sudo", "systemctl", "restart", "piedalmetry"],
        check=False,
    )
