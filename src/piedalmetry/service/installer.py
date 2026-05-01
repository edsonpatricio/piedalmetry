"""Systemd service installer and uninstaller."""

from __future__ import annotations

import os
import subprocess
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
ExecStart={uv_path} run python -m piedalmetry run --config {config_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def install_service(config_path: str = "/etc/piedalmetry/config.toml") -> None:
    """Install piedalmetry as a systemd service."""
    uv_path = _find_uv()
    user = os.environ.get("USER", "dietpi")

    unit_content = _UNIT_TEMPLATE.format(
        user=user,
        uv_path=uv_path,
        config_path=config_path,
    )

    _UNIT_PATH.write_text(unit_content)
    print(f"Created {_UNIT_PATH}")

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "piedalmetry"], check=True)
    subprocess.run(["systemctl", "start", "piedalmetry"], check=True)
    print("Service installed and started.")


def uninstall_service() -> None:
    """Stop, disable, and remove the piedalmetry systemd service."""
    subprocess.run(["systemctl", "stop", "piedalmetry"], check=False)
    subprocess.run(["systemctl", "disable", "piedalmetry"], check=False)

    if _UNIT_PATH.exists():
        _UNIT_PATH.unlink()
        print(f"Removed {_UNIT_PATH}")

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    print("Service uninstalled.")


def _find_uv() -> str:
    """Locate the uv binary."""
    result = subprocess.run(
        ["which", "uv"], capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return "/usr/local/bin/uv"
