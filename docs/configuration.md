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
  - Invalid value for brake.brake_min_pressure: 150 (valid: 0-99)
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

### `[brake]`

| Key | Type | Default | Valid | Description |
|-----|------|---------|-------|-------------|
| `brake_gpio_ena` | int | `18` | 0–27 | BCM pin for ENA (PWM speed) |
| `brake_gpio_in1` | int | `23` | 0–27 | BCM pin for IN1 (direction) |
| `brake_gpio_in2` | int | `24` | 0–27 | BCM pin for IN2 (direction) |
| `brake_pwm_frequency` | int | `100` | 50–25000 | PWM carrier frequency in Hz |
| `brake_min_pressure` | int | `10` | 0–99 | Brake % below which motor is off |
| `brake_min_strength` | int | `50` | 1–99 | Motor duty % at `brake_min_pressure`; ramps linearly to 100% |
| `brake_min_car_speed` | int | `0` | 0–500 | Car speed (km/h) below which motor is off |
| `brake_min_pulse_freq` | float | `3.0` | 0.1–20.0 | Pulse frequency (Hz) at `brake_min_pressure` |
| `brake_max_pulse_freq` | float | `12.0` | 0.1–20.0 | Pulse frequency (Hz) at `brake_top_limit_pattern` |
| `brake_feedback_exponent` | float | `3.0` | 0.1–10.0 | Response curve exponent for the frequency ramp |
| `brake_top_limit_pattern` | int | `98` | 0 or (`brake_min_pressure`+1)–100 | Brake % above which motor runs continuously; `0` = disabled |
| `brake_foot_sensor_enabled` | bool | `true` | — | Enable foot-on-pedal gate; motor off when no foot detected |
| `brake_foot_sensor_gpio` | int | `25` | 0–27 | BCM signal pin (active LOW, pull-up enabled) |
| `brake_foot_sensor_feed_gpio` | int | `21` | 0–27 | BCM pin driven permanently HIGH to feed the sensor switch |
| `brake_foot_sensor_led_gpio` | int | `6` | 0–27 | BCM pin for foot-detection indicator LED (LOW=off, HIGH=foot detected) |

```toml
[brake]
brake_gpio_ena = 18
brake_gpio_in1 = 23
brake_gpio_in2 = 24
brake_pwm_frequency = 100
brake_min_pressure = 10
brake_min_strength = 50
brake_min_car_speed = 0
brake_min_pulse_freq = 3.0
brake_max_pulse_freq = 12.0
brake_feedback_exponent = 3.0
brake_top_limit_pattern = 98
brake_foot_sensor_enabled = true
brake_foot_sensor_gpio = 25
```

**Three feedback zones**:

| Brake pressure | Motor behaviour |
|----------------|-----------------|
| < `brake_min_pressure` | Off |
| `brake_min_pressure` → `brake_top_limit_pattern` | Pulses; duty ramps linearly `brake_min_strength` → 100%; frequency ramps `brake_min_pulse_freq` → `brake_max_pulse_freq` |
| ≥ `brake_top_limit_pattern` (and > 0) | Continuous 100% — solid resistance wall |

The two dimensions in the pulsed zone are **independent**:
- **Strength** (ON-phase duty): always linear — `brake_feedback_exponent` has no effect on it
- **Frequency**: shaped by `brake_feedback_exponent`

**`brake_min_strength`**: Motor duty during the ON phase at `brake_min_pressure`.
Ramps linearly to 100% at `brake_top_limit_pattern`. Set lower (e.g. `50`) for a
subtle entry feel; set higher (e.g. `85`) for strong feedback from the first brake
input.

**`brake_min_pulse_freq` / `brake_max_pulse_freq`**: Set the pulse rate
range across the braking zone. Frequency is interpolated linearly in Hz
space, giving uniform perceptual steps. Increasing the gap between the two
values makes pressure changes more discriminable.

**`brake_feedback_exponent`**: Bends the frequency ramp without changing its
endpoints.
- `1.0` — linear (equal brake steps → equal frequency steps)
- `> 1.0` — slow start / fast end: subtle response at light braking,
  aggressive near the limit (recommended: `2.0`–`3.0`)
- `< 1.0` — fast start / slow end: immediate response, compressed at high
  pressure

**`brake_top_limit_pattern`**: When non-zero, the motor switches from
frequency-coded pulses to a solid 100% duty above this threshold — simulating
the feel of a car at its braking limit. Must be greater than
`brake_min_pressure`. Set to `0` to disable (default).

**`brake_foot_sensor_*`**: The sensor circuit runs whenever the service is
running (regardless of `brake_foot_sensor_enabled`). The feed pin
(`brake_foot_sensor_feed_gpio`, default physical pin 40) is driven permanently
HIGH. Wire a normally-open switch between the feed pin and the signal pin
(default physical pin 22). When the foot presses the switch the signal pin
goes LOW — detected as foot on pedal. No external resistor needed (internal
pull-up enabled).

`brake_foot_sensor_led_gpio` (default physical pin 31) drives an indicator LED:
LOW when no foot is detected, HIGH when a foot is detected. This LED is always
active — `brake_foot_sensor_enabled` only controls whether the motor is gated
by the sensor, not whether the LED works.

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

| Key | Type | Default | Valid | Description |
|-----|------|---------|-------|-------------|
| `ip` | string | `""` | — | PlayStation IP address |
| `label` | string | `"PS5"` | — | Human-friendly name for this console |
| `ps_conn_led_gpio` | int | `17` | 0–27 | BCM pin for the GT7 connection status LED |

```toml
[playstation]
ip = "192.168.1.50"
label = "PS5"
ps_conn_led_gpio = 17
```

`ps_conn_led_gpio`: LED turns on when the first GT7 telemetry packet is received and
turns off on connection loss or service shutdown. Wire in series with a 220 Ω resistor
between the GPIO pin (physical pin 11 for the default GPIO 17) and GND.

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
