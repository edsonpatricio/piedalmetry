# Installation Guide

**Target**: Raspberry Pi 2 Model B running DietPi

## Prerequisites

- DietPi installed and SSH accessible (`ssh dietpi@<pi-ip>`)
- Python 3.11+ available on the Pi (DietPi ships 3.13+; no action needed)
- `uv` package manager installed
- Hardware wired per [docs/hardware/wiring.md](hardware/wiring.md)
- GT7 running on a PlayStation on the local network

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Reload shell so uv is on PATH
source ~/.bashrc
uv --version
```

### Install lgpio (required for GPIO on DietPi)

```bash
sudo apt-get install -y python3-lgpio
```

## Step 1 — Clone the Repository

```bash
mkdir -p ~/dev
cd ~/dev
git clone https://github.com/edsonpatricio/piedalmetry.git
cd piedalmetry
```

## Step 2 — Configure the Environment

> **On a network share (CIFS/Samba)?**
> CIFS doesn't support symlinks. Python virtual environments use symlinks
> extensively, so the venv must live on local storage. Run this once, then
> reload the shell:
>
> ```bash
> cat >> ~/.bashrc << 'EOF'
> export UV_PROJECT_ENVIRONMENT=/home/dietpi/.venv/piedalmetry
> EOF
> source ~/.bashrc
> ```
>
> Skip this block if `~/dev` is on the local SD card.
> The `piedalmetry` CLI is made globally available by the install step (Step 7)
> — no PATH changes are needed.

Install Python dependencies:

```bash
cd ~/dev/piedalmetry
uv sync
```

Verify:

```bash
uv run python -c "import Crypto; import click; print('deps OK')"
```

## Step 3 — Create the Configuration File

```bash
sudo mkdir -p /etc/piedalmetry
sudo cp ~/dev/piedalmetry/config.example.toml /etc/piedalmetry/config.toml
sudo nano /etc/piedalmetry/config.toml
```

**Required edits**:

1. Set `ip` under `[playstation]` to your PS5 IP address (e.g. `"192.168.1.50"`).
   Leave empty to use automatic UDP discovery (same subnet only).
2. Verify the GPIO pins under `[brake]` match your physical wiring.
   Defaults (`brake_gpio_ena = 18`, `brake_gpio_in1 = 23`, `brake_gpio_in2 = 24`)
   match the standard wiring in [docs/hardware/wiring.md](hardware/wiring.md).

See [docs/configuration.md](configuration.md) for all options.

## Step 4 — Test Without Hardware (Mock Mode)

Verify the installation without requiring a PlayStation or motor:

```bash
piedalmetry run --mock --log-level DEBUG
# Ctrl+C to stop
```

Verify the motor mapping sweep:

```bash
piedalmetry mock --sweep --duration 5
# Should log motor_pct values sweeping 0→100→0 without errors
```

## Step 5 — Test With Real Hardware

With the motor wired and a GT7 session active:

```bash
piedalmetry run --log-level DEBUG
# Brake in GT7 → motor should vibrate proportionally
# Ctrl+C to stop
```

## Step 6 — Fix LED Boot State

By default GPIO 17 floats HIGH during boot, which lights the connection LED
before piedalmetry starts. Tell the firmware to drive it LOW from power-on:

```bash
# DietPi (and most Pi OS releases since 2022) use /boot/firmware/config.txt:
echo "gpio=17=op,dl" | sudo tee -a /boot/firmware/config.txt

# Older systems that still use /boot/config.txt:
# echo "gpio=17=op,dl" | sudo tee -a /boot/config.txt
```

Verify:

```bash
grep "gpio=17" /boot/firmware/config.txt
```

The change takes effect on the next reboot. After that the LED stays off
until piedalmetry turns it on when the first GT7 telemetry packet is received.

## Step 7 — Install as a systemd Service

```bash
cd ~/dev/piedalmetry
sudo $(uv run which python) -m piedalmetry install --config /etc/piedalmetry/config.toml
```

`uv run which python` resolves the full path to the venv Python
(e.g. `/home/dietpi/.venv/piedalmetry/bin/python`). Passing it to `sudo`
avoids `sudo uv run`, which tries to recreate the venv as root and fails on
CIFS mounts. The installer bakes that Python path into the systemd `ExecStart`
line so the service never calls uv at runtime.

Verify the service started:

```bash
piedalmetry status
piedalmetry log --lines 20
```

## Step 8 — Verify Service Survives Reboot

```bash
sudo reboot
# After reboot:
ssh dietpi@<pi-ip>
piedalmetry status    # Should show: active (running)
```

## Day-to-day Commands

These work as the `dietpi` user without extra `sudo`:

```bash
piedalmetry status          # Show service status
piedalmetry log             # View recent logs
piedalmetry log -f          # Follow live logs
piedalmetry start           # Start service
piedalmetry stop            # Stop service
piedalmetry restart         # Restart service
piedalmetry troubleshoot    # Run diagnostics
```

## Uninstall

```bash
cd ~/dev/piedalmetry
sudo $(uv run which python) -m piedalmetry uninstall
```

This stops the service, disables it, and removes the unit file.
The config file at `/etc/piedalmetry/config.toml` is preserved.

## References

- [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry) —
  GT7 UDP telemetry protocol
- [snipem/gt7dashboard](https://github.com/snipem/gt7dashboard) —
  GT7 integration patterns
