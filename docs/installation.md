# Installation Guide

**Target**: Raspberry Pi 2 Model B running DietPi v10.x

## Prerequisites

- DietPi installed and SSH accessible (`ssh dietpi@<pi-ip>`)
- Python 3.11+ available on the Pi
- `uv` package manager installed
- Hardware wired per [docs/hardware/wiring.md](hardware/wiring.md)
- GT7 running on a PlayStation on the local network

### Install Python 3.11 on DietPi

```bash
# Check current Python version
python3 --version

# If < 3.11, install via dietpi-software or apt:
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv
```

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or using pip:
pip3 install uv
```

Verify:

```bash
uv --version
```

### Install lgpio (required for GPIO on DietPi)

```bash
sudo apt-get install -y python3-lgpio
```

## Step 1 — Clone the Repository

The repository is mirrored on the Pi at `/home/dietpi/dev/pidalmetry`.
If not yet present:

```bash
cd ~/dev
git clone <repo-url> pidalmetry
cd pidalmetry
```

## Step 2 — Install Dependencies

```bash
cd ~/dev/pidalmetry
uv sync
```

Expected output: all packages installed without errors.

Verify:

```bash
uv run python -c "import Crypto; import click; print('deps OK')"
```

## Step 3 — Create the Configuration File

```bash
sudo mkdir -p /etc/pidalmetry
sudo cp config.example.toml /etc/pidalmetry/config.toml
sudo nano /etc/pidalmetry/config.toml
```

**Required edits**:

1. Set `playstation.ip` to your PS5 IP address (e.g. `"192.168.1.50"`).
   Leave empty to use auto-discovery (same subnet only).
2. Verify `motor.gpio_ena`, `motor.gpio_in1`, `motor.gpio_in2` match
   your physical wiring (defaults are 18/23/24).

See [docs/configuration.md](configuration.md) for all options.

## Step 4 — Test Without Hardware (Mock Mode)

Verify the installation without requiring a PlayStation or motor:

```bash
cd ~/dev/pidalmetry
uv run python -m pidalmetry run --mock --log-level DEBUG
# Ctrl+C to stop
```

Verify a sweep test:

```bash
uv run python -m pidalmetry mock --sweep --duration 5
# Should log motor_pct values sweeping 0→100→0 without errors
```

## Step 5 — Test With Real Hardware

With the motor wired and a GT7 session active:

```bash
cd ~/dev/pidalmetry
uv run python -m pidalmetry run --config /etc/pidalmetry/config.toml --log-level DEBUG
# Brake in GT7 → motor should vibrate proportionally
# Ctrl+C to stop
```

## Step 6 — Install as a systemd Service

```bash
cd ~/dev/pidalmetry
sudo uv run python -m pidalmetry install --config /etc/pidalmetry/config.toml
```

This installs `/etc/systemd/system/pidalmetry.service` and enables it
to start on boot.

Verify:

```bash
pidalmetry status    # Should show: active (running)
pidalmetry log --lines 10
```

## Step 7 — Verify Service Survives Reboot

```bash
sudo reboot
# After reboot:
ssh dietpi@<pi-ip>
pidalmetry status    # Should show: active (running)
```

## Uninstall

```bash
sudo pidalmetry uninstall
```

This stops the service, disables it, and removes the unit file.
The config file at `/etc/pidalmetry/config.toml` is preserved.

## Troubleshooting Installation

Run the built-in diagnostics:

```bash
pidalmetry troubleshoot
```

See [docs/troubleshooting.md](troubleshooting.md) for common failure modes.

## References

- [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry) —
  GT7 UDP telemetry protocol
- [snipem/gt7dashboard](https://github.com/snipem/gt7dashboard) —
  GT7 integration patterns
