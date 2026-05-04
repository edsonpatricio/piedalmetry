# Piedalmetry

Real-time brake-pressure-to-motor-vibration feedback for Gran Turismo 7,
running on a Raspberry Pi 2B. When you brake in GT7, a rumble motor
wired to the Pi vibrates proportionally — giving tactile brake feedback
through your pedals.

## How It Works

1. GT7 broadcasts UDP telemetry (Salsa20-encrypted) on port 33740
2. Piedalmetry decrypts each packet and extracts brake pressure and car speed
3. An anti-fluctuation filter (dead-zone + EMA) smooths noisy input
4. A configurable linear mapping converts brake % to motor PWM duty cycle
5. An L298N motor driver receives the PWM signal and drives the 12V rumble motor

## Hardware

- Raspberry Pi 2 Model B (DietPi)
  - This is a really old one, but it's more than enough.
- L298N dual H-bridge motor driver module
  - https://pt.aliexpress.com/item/1005006739178065.html
  - Up to 2 motors
- 12V DC rumble motor (R260)
  - https://pt.aliexpress.com/item/1005010209259017.html
- 12V 1A power supply for the motor

Wiring: [docs/hardware/wiring.md](docs/hardware/wiring.md)

## Dependencies
- Python 3.11+
- uv
- Others described in the uv pyproject.toml

## Quick Start

```bash
# On the Pi:
cd ~/dev/piedalmetry
uv sync
sudo mkdir -p /etc/piedalmetry
sudo cp config.example.toml /etc/piedalmetry/config.toml
# Edit config: set playstation.ip and verify GPIO pins
sudo $(uv run which python) -m piedalmetry install
piedalmetry status
```

Full installation guide: [docs/installation.md](docs/installation.md)

## CLI Commands

| Command | Description |
|---------|-------------|
| `piedalmetry run` | Start the telemetry listener and motor driver |
| `piedalmetry mock --sweep` | Sweep motor 0→100→0 without a PS5 |
| `piedalmetry mock --brake 50` | Hold motor at 50% without a PS5 |
| `piedalmetry discover` | Find PS5 on the network |
| `piedalmetry install` | Install as systemd service |
| `piedalmetry uninstall` | Remove systemd service |
| `piedalmetry status` | Show service status |
| `piedalmetry start / stop / restart` | Control the service |
| `piedalmetry log` | View service logs |
| `piedalmetry troubleshoot` | Run diagnostics |


### Running directly from the source with uv
```bash
uv run python -m piedalmetry run --config config.example.toml --log-level INFO
```

## Configuration

All parameters are in a validated TOML config file. Copy
`config.example.toml` to `/etc/piedalmetry/config.toml` and edit:

```toml
[brake]
brake_gpio_ena = 18         # BCM GPIO for PWM (pin 12)
brake_gpio_in1 = 23         # BCM GPIO for direction IN1 (pin 16)
brake_gpio_in2 = 24         # BCM GPIO for direction IN2 (pin 18)
brake_min_pressure = 10
brake_min_strength = 50
brake_top_limit_pattern = 98

[playstation]
ip = "192.168.1.50"         # PS5 IP; leave empty for auto-discovery
label = "PS5"
```

Full reference: [docs/configuration.md](docs/configuration.md)

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Logging](docs/logging.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Hardware Wiring](docs/hardware/wiring.md)
- [RPi 2B GPIO Pinout](docs/hardware/rpi2b-pinout.md)
- [L298N Pinout](docs/hardware/l298n-pinout.md)

## Development

```bash
# Run tests (no hardware required):
uv run pytest tests/unit/ -v

# Linting and formatting:
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type checking:
uv run mypy src/
```

## Acknowledgments

GT7 telemetry protocol knowledge from:

- **[Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry)** —
  Salsa20 key derivation, packet structure, heartbeat mechanism.
  Originally derived from
  [lmirel/mfc](https://github.com/lmirel/mfc/blob/master/clients/gt7racedata.py)
  and the
  [GTPlanet motion-rig thread](https://www.gtplanet.net/forum/threads/gt7-is-compatible-with-motion-rig.410728).

- **[snipem/gt7dashboard](https://github.com/snipem/gt7dashboard)** —
  Full-featured GT7 telemetry dashboard with extensive protocol handling,
  test data samples, and real-world integration patterns.
