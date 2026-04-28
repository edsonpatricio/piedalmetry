# Pidalmetry

Real-time brake-pressure-to-motor-vibration feedback for Gran Turismo 7,
running on a Raspberry Pi 2B. When you brake in GT7, a rumble motor
wired to the Pi vibrates proportionally — giving tactile brake feedback
through your pedals or seat.

## How It Works

1. GT7 broadcasts UDP telemetry (Salsa20-encrypted) on port 33740
2. Pidalmetry decrypts each packet and extracts brake pressure and car speed
3. An anti-fluctuation filter (dead-zone + EMA) smooths noisy input
4. A configurable linear mapping converts brake % to motor PWM duty cycle
5. An L298N motor driver receives the PWM signal and drives the 12V rumble motor

## Hardware

- Raspberry Pi 2 Model B (DietPi)
- L298N dual H-bridge motor driver module
- 12V DC rumble motor
- 12V power supply for the motor

Wiring: [docs/hardware/wiring.md](docs/hardware/wiring.md)

## Quick Start

```bash
# On the Pi:
cd ~/dev/pidalmetry
uv sync
sudo mkdir -p /etc/pidalmetry
sudo cp config.example.toml /etc/pidalmetry/config.toml
# Edit config: set playstation.ip and verify GPIO pins
sudo uv run python -m pidalmetry install
pidalmetry status
```

Full installation guide: [docs/installation.md](docs/installation.md)

## CLI Commands

| Command | Description |
|---------|-------------|
| `pidalmetry run` | Start the telemetry listener and motor driver |
| `pidalmetry mock --sweep` | Sweep motor 0→100→0 without a PS5 |
| `pidalmetry mock --brake 50` | Hold motor at 50% without a PS5 |
| `pidalmetry discover` | Find PS5 on the network |
| `pidalmetry install` | Install as systemd service |
| `pidalmetry uninstall` | Remove systemd service |
| `pidalmetry status` | Show service status |
| `pidalmetry start / stop / restart` | Control the service |
| `pidalmetry log` | View service logs |
| `pidalmetry troubleshoot` | Run diagnostics |

## Configuration

All parameters are in a validated TOML config file. Copy
`config.example.toml` to `/etc/pidalmetry/config.toml` and edit:

```toml
[motor]
gpio_ena = 18          # BCM GPIO for PWM (pin 12)
gpio_in1 = 23          # BCM GPIO for direction IN1 (pin 16)
gpio_in2 = 24          # BCM GPIO for direction IN2 (pin 18)
min_brake_pressure = 30
min_motor_strength = 50

[playstation]
ip = "192.168.1.50"    # PS5 IP; leave empty for auto-discovery
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
