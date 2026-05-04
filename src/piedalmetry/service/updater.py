"""Update piedalmetry from a GitHub release archive.

Downloads a tar.gz archive (no git required — avoids CIFS .git chmod issues),
overwrites source files, re-syncs the venv, and restarts the service.
"""

from __future__ import annotations

import json
import os
import pwd
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


def _detect_venv() -> Path:
    # Primary: parse the systemd service file — the installer bakes the venv
    # Python path into ExecStart, so this is reliable regardless of how sudo
    # replaces sys.executable with /usr/bin/python3.
    import re
    unit = Path("/etc/systemd/system/piedalmetry.service")
    if unit.exists():
        m = re.search(r"ExecStart=(\S+)\s+-m\s+piedalmetry", unit.read_text())
        if m:
            venv_python = Path(m.group(1))
            if venv_python.exists():
                return venv_python.parents[1]

    # Fallback: follow the /usr/local/bin/piedalmetry symlink if present.
    cli_link = Path("/usr/local/bin/piedalmetry")
    if cli_link.is_symlink():
        return cli_link.resolve().parents[1]

    # Last resort: sys.executable without .resolve() (avoids following
    # python3 → /usr/bin/python3 → parents[1] = /usr).
    return Path(sys.executable).parents[1]


def _sync_venv(project_root: Path) -> None:
    print("Syncing dependencies...")
    venv_path = _detect_venv()
    # Run as the venv owner so uv doesn't install files owned by root,
    # which would break subsequent non-root uv sync calls.
    venv_owner = pwd.getpwuid(venv_path.stat().st_uid).pw_name
    print(f"  Venv:    {venv_path} (owner: {venv_owner})")
    subprocess.run(
        ["sudo", "-u", venv_owner, "uv", "sync"],
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
