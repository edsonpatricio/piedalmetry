"""Systemd service installer and uninstaller."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_UNIT_PATH = Path("/etc/systemd/system/piedalmetry.service")

_UNIT_TEMPLATE = """\
[Unit]
Description=Piedalmetry GT7 Brake-to-Motor Feedback
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory=/tmp
ExecStart={python} -m piedalmetry run --config {config_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def install_service(config_path: str = "/etc/piedalmetry/config.toml") -> None:
    """Install piedalmetry as a systemd service."""
    if os.geteuid() != 0:
        print("ERROR: install requires root. Run with sudo.", file=sys.stderr)
        sys.exit(1)

    user = os.environ.get("SUDO_USER") or os.environ.get("USER", "dietpi")
    python = sys.executable

    unit_content = _UNIT_TEMPLATE.format(
        user=user,
        python=python,
        config_path=config_path,
    )

    _UNIT_PATH.write_text(unit_content)
    print(f"Created {_UNIT_PATH}")
    print(f"  User:    {user}")
    print(f"  Python:  {python}")
    print(f"  Config:  {config_path}")

    # Symlink piedalmetry CLI into /usr/local/bin so it's on PATH for all users
    # without needing shell profile changes.
    venv_bin = Path(python).parent
    cli_src = venv_bin / "piedalmetry"
    cli_link = Path("/usr/local/bin/piedalmetry")
    if cli_src.exists():
        cli_link.unlink(missing_ok=True)
        cli_link.symlink_to(cli_src)
        print(f"  Symlinked: {cli_link} → {cli_src}")

    # Ensure the config file is readable by the service user (not just root).
    config = Path(config_path)
    if config.exists():
        config.chmod(0o644)
        config.parent.chmod(0o755)
        print(f"  Permissions set: {config_path} → 644")

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "piedalmetry"], check=True)
    subprocess.run(["systemctl", "start", "piedalmetry"], check=True)
    print("Service installed and started.")


def uninstall_service() -> None:
    """Stop, disable, and remove the piedalmetry systemd service."""
    if os.geteuid() != 0:
        print("ERROR: uninstall requires root. Run with sudo.", file=sys.stderr)
        sys.exit(1)

    subprocess.run(["systemctl", "stop", "piedalmetry"], check=False)
    subprocess.run(["systemctl", "disable", "piedalmetry"], check=False)

    if _UNIT_PATH.exists():
        _UNIT_PATH.unlink()
        print(f"Removed {_UNIT_PATH}")

    cli_link = Path("/usr/local/bin/piedalmetry")
    if cli_link.is_symlink():
        cli_link.unlink()
        print(f"Removed {cli_link}")

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    print("Service uninstalled.")
