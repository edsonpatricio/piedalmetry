"""CLI entry point for Piedalmetry.

Sub-commands: run, mock, discover, install, uninstall, status, start,
stop, restart, log, troubleshoot.
"""

from __future__ import annotations

import subprocess
import sys

import click

from piedalmetry.config import ConfigError, load_config

DEFAULT_CONFIG = "/etc/piedalmetry/config.toml"


@click.group()
@click.version_option(package_name="piedalmetry")
def main() -> None:
    """Piedalmetry — GT7 brake-pressure-to-motor rumble feedback."""


@main.command()
@click.option(
    "--config", "config_path", default=DEFAULT_CONFIG,
    help="Path to config.toml", type=click.Path(),
)
@click.option("--mock", is_flag=True, default=False, help="Enable mock mode")
@click.option(
    "--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default=None, help="Override log level",
)
def run(config_path: str, mock: bool, log_level: str | None) -> None:
    """Start the telemetry listener and motor controller."""
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    if mock:
        cfg.mock_mode = True
    if log_level:
        cfg.log_level = log_level

    from piedalmetry.service.runner import Runner

    runner = Runner(cfg)
    runner.run()


@main.command()
@click.option(
    "--config", "config_path", default=DEFAULT_CONFIG,
    help="Path to config.toml", type=click.Path(),
)
@click.option("--brake", type=float, default=None, help="Fixed brake %")
@click.option("--sweep", is_flag=True, default=False, help="Sweep 0→100→0")
@click.option("--duration", type=int, default=10, help="Duration in seconds")
def mock(config_path: str, brake: float | None, sweep: bool, duration: int) -> None:
    """Exercise the motor mapping without a live GT7 session."""
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    from piedalmetry.service.runner import Runner

    runner = Runner(cfg)
    if sweep:
        runner.run_mock_sweep(duration=float(duration))
    elif brake is not None:
        runner.run_fixed_brake(brake, duration=float(duration))
    else:
        click.echo("Specify --brake PCT or --sweep")
        sys.exit(1)


@main.command()
@click.option("--timeout", type=int, default=10, help="Discovery timeout (seconds)")
def discover(timeout: int) -> None:
    """Discover PlayStation consoles on the network."""
    from piedalmetry.telemetry.discovery import discover_playstation

    click.echo(f"Searching for PlayStation (timeout={timeout}s)...")
    ip = discover_playstation(timeout=float(timeout))
    if ip:
        click.echo(f"Found PlayStation at: {ip}")
    else:
        click.echo("No PlayStation found on the network.")


@main.command()
@click.option(
    "--config", "config_path", default=DEFAULT_CONFIG,
    help="Path to config.toml", type=click.Path(),
)
def install(config_path: str) -> None:
    """Install piedalmetry as a systemd service."""
    from piedalmetry.service.installer import install_service

    install_service(config_path)


@main.command()
def uninstall() -> None:
    """Remove the piedalmetry systemd service."""
    from piedalmetry.service.installer import uninstall_service

    uninstall_service()


@main.command()
def status() -> None:
    """Show service status."""
    subprocess.run(["systemctl", "status", "piedalmetry"], check=False)


@main.command()
def start() -> None:
    """Start the piedalmetry service."""
    subprocess.run(["sudo", "systemctl", "start", "piedalmetry"], check=False)


@main.command()
def stop() -> None:
    """Stop the piedalmetry service."""
    subprocess.run(["sudo", "systemctl", "stop", "piedalmetry"], check=False)


@main.command()
def restart() -> None:
    """Restart the piedalmetry service."""
    subprocess.run(["sudo", "systemctl", "restart", "piedalmetry"], check=False)


@main.command(name="log")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option(
    "--level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default=None, help="Filter by log level",
)
@click.option("--since", type=str, default=None, help="Show logs since timestamp")
def log_cmd(lines: int, follow: bool, level: str | None, since: str | None) -> None:
    """View piedalmetry service logs."""
    cmd = ["journalctl", "-u", "piedalmetry", f"-n{lines}", "--no-pager"]
    if follow:
        cmd.append("-f")
    if since:
        cmd.extend(["--since", since])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    output = result.stdout
    if level:
        output = "\n".join(
            line for line in output.splitlines()
            if f"level={level}" in line
        )
    click.echo(output)


@main.command()
@click.option(
    "--config", "config_path", default=DEFAULT_CONFIG,
    help="Path to config.toml", type=click.Path(),
)
def troubleshoot(config_path: str) -> None:
    """Run diagnostic checks and report system health."""
    checks: list[tuple[str, str, str]] = []

    # 1. Config file
    try:
        cfg = load_config(config_path)
        checks.append(("Config file", "PASS", str(config_path)))
    except Exception as e:
        checks.append(("Config file", "FAIL", str(e)))
        cfg = None

    # 2. GPIO access
    try:
        from gpiozero import Device  # type: ignore[import-untyped]
        # Verify we can access the default pin factory
        _factory = Device.pin_factory
        checks.append(("GPIO access", "PASS", f"pin_factory={type(_factory).__name__}"))
    except Exception as e:
        checks.append(("GPIO access", "FAIL", str(e)))

    # 3. PS5 reachable
    if cfg and cfg.playstation.ip:
        ret = subprocess.run(
            ["ping", "-c", "1", "-W", "2", cfg.playstation.ip],
            capture_output=True, check=False,
        )
        if ret.returncode == 0:
            checks.append(("PS5 reachable", "PASS", cfg.playstation.ip))
        else:
            checks.append((
                "PS5 reachable", "WARN", f"ping failed for {cfg.playstation.ip}"
            ))
    else:
        checks.append(("PS5 reachable", "SKIP", "No IP configured"))

    # 4. Port 33740 free
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", 33740))
        s.close()
        checks.append(("Port 33740", "PASS", "available"))
    except OSError:
        checks.append(("Port 33740", "FAIL", "port already in use"))

    # Display results
    click.echo("\n  Piedalmetry Diagnostics")
    click.echo("  " + "=" * 50)
    _icons = {"PASS": "✅", "WARN": "⚠️", "SKIP": "⏭️"}
    for name, status, detail in checks:
        icon = _icons.get(status, "❌")
        click.echo(f"  {icon} {name:<20} {status:<6} {detail}")
    click.echo()
