# Configuration Reference

Piedalmetry is configured via a TOML file, by default at
`/etc/piedalmetry/config.toml`. Copy `config.example.toml` from the
repository root to get started.

## File Location

| Context | Path |
|---------|------|
| System service (default) | `/etc/piedalmetry/config.toml` |
| Development / custom | Pass `--config <path>` to any CLI command |

## Validation

Config is validated at startup. Invalid values produce a clear error:

```text
Config validation failed:
  - Invalid value for motor.min_brake_pressure: 150 (valid: 0-99)
```

## Sections

### `[general]`

| Key | Type | Default | Valid | Description |
|-----|------|---------|-------|-------------|
| `mock_mode` | bool | `false` | — | Skip real GPIO; use mock motor driver |
| `log_level` | string | `"INFO"` | `DEBUG` `INFO` `WARNING` `ERROR` | Logging verbosity |
| `log_target` | string | `"stdout"` | `journald` `stdout` `file` | Log destination |

```toml
[general]
mock_mode = false
log_level = "INFO"
log_target = "stdout"
```

`log_target = "journald"` routes logs to systemd journal (recommended
when running as a service). `log_target = "file"` writes to
`/var/log/piedalmetry.log`.

### `[motor]`

| Key | Type | Default | Valid | Description |
|-----|------|---------|-------|-------------|
| `gpio_ena` | int | `18` | 0–27 | BCM pin for ENA (PWM speed) |
| `gpio_in1` | int | `23` | 0–27 | BCM pin for IN1 (direction) |
| `gpio_in2` | int | `24` | 0–27 | BCM pin for IN2 (direction) |
| `pwm_frequency` | int | `1000` | 50–25000 | PWM frequency in Hz |
| `min_brake_pressure` | int | `30` | 0–99 | Brake % below which motor is off |
| `min_motor_strength` | int | `50` | 1–99 | Motor % when brake = `min_brake_pressure` |
| `min_car_speed` | int | `5` | 0–500 | Car speed (km/h) below which motor is off |
| `response_exponent` | float | `1.0` | 0.1–10.0 | Response curve shape (1.0 = linear) |
| `top_limit_pattern` | int | `0` | 0 or (`min_brake_pressure`+1)–100 | Brake % above which motor pulses; `0` = disabled |

```toml
[motor]
gpio_ena = 18
gpio_in1 = 23
gpio_in2 = 24
pwm_frequency = 1000
min_brake_pressure = 30
min_motor_strength = 50
min_car_speed = 5
response_exponent = 2.0
top_limit_pattern = 0
```

**Mapping curve**: Scales from `(min_brake_pressure → min_motor_strength)`
to `(100% → 100%)`. Below `min_brake_pressure` the motor is off.

**`response_exponent`**: Controls the shape of the brake-to-motor curve.
- `1.0` — linear (proportional)
- `> 1.0` — power curve: quiet under light braking, aggressive under heavy
- `2.0` — quadratic; recommended for realistic haptic rumble feel

**`top_limit_pattern`**: When set to a non-zero value, the motor switches
from continuous rotation to a rapid burst pattern at/above that brake
percentage — 100% duty in 80 ms on/off cycles (~6 Hz), simulating the feel
of a car on the verge of skidding. Must be greater than `min_brake_pressure`.
Set to `0` to disable (default).

See [docs/hardware/rpi2b-pinout.md](hardware/rpi2b-pinout.md) for BCM
pin numbering. Defaults match the standard Piedalmetry wiring.

### `[anti_fluctuation]`

| Key | Type | Default | Valid | Description |
|-----|------|---------|-------|-------------|
| `dead_zone` | float | `2.0` | 0.0–50.0 | Min % change to update motor output |
| `ema_alpha` | float | `0.3` | 0.0–1.0 | EMA smoothing factor (0.0 = disabled) |

```toml
[anti_fluctuation]
dead_zone = 2.0
ema_alpha = 0.3
```

`dead_zone`: Changes smaller than this are ignored to prevent motor
flutter from telemetry noise. Increase (try 3–5%) if the motor
chatters at a steady brake position.

`ema_alpha`: Controls exponential moving average smoothing. Lower
values produce smoother output but add latency. `0.0` disables EMA
entirely (dead-zone only). `1.0` means no smoothing (every sample
passes through).

### `[playstation]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ip` | string | `""` | PlayStation IP address |
| `label` | string | `""` | Human-friendly name for this console |

```toml
[playstation]
ip = "192.168.1.50"
label = "PS5"
```

If `ip` is empty, the service attempts UDP broadcast discovery on
startup (same-subnet only). For cross-subnet setups (Pi on a different
subnet than the PS5), the IP must be set manually.

On successful discovery, the IP is written back to this file. If the
console becomes unreachable (3 consecutive failures with ≥3s spacing),
the IP is cleared and discovery re-runs.

## How to Verify Configuration

```bash
# Check for validation errors:
uv run python -m piedalmetry run --config /etc/piedalmetry/config.toml --mock
# If config is valid, mock mode starts without error

# Run diagnostics:
piedalmetry troubleshoot
```

## CLI Overrides

CLI flags override config file values for the duration of the command:

```bash
piedalmetry run --log-level DEBUG    # Override log_level
piedalmetry run --mock               # Override mock_mode
```

The config file is the canonical source of truth for all other settings.

## References

- [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry) —
  protocol defaults (port 33740, heartbeat to 33739)
- [snipem/gt7dashboard](https://github.com/snipem/gt7dashboard) —
  GT7 integration patterns
