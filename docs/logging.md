# Logging Guide

Piedalmetry emits structured `key=value` logs at every pipeline stage.
All entries include `ts`, `level`, `module`, and `msg` fields. Extra
context is appended as additional `key=value` pairs on the same line.

## Log Format

```text
ts=2026-04-27T10:15:30 level=INFO module=runner msg="Pipeline running — press Ctrl+C to stop"
ts=2026-04-27T10:15:30 level=DEBUG module=runner msg="Cycle" brake_pct=45.1 filtered=44.8 motor_pct=72.3 speed_kph=87.4
ts=2026-04-27T10:15:31 level=DEBUG module=runner msg="pipeline completed" latency_ms=1.23
```

## Log Levels

| Level | When used |
|-------|-----------|
| `DEBUG` | Every telemetry cycle (brake/motor values, latency) |
| `INFO` | Startup, shutdown, discovery success, config load |
| `WARNING` | PS5 unreachable (fail count), recovery attempts |
| `ERROR` | Config errors, missing PS5 IP, fatal errors |

## Key Fields by Module

### `module=runner` (service runner)

| Entry | Level | Extra fields |
|-------|-------|--------------|
| Motor controller started (REAL GPIO) | INFO | `ena` `in1` `in2` |
| Motor controller started (MOCK) | INFO | — |
| Pipeline running | INFO | — |
| Each telemetry cycle | DEBUG | `brake_pct` `filtered` `motor_pct` `speed_kph` |
| Pipeline cycle latency | DEBUG | `latency_ms` |
| Shutdown signal received | INFO | — |
| Pipeline stopped | INFO | — |

### `module=listener` (UDP telemetry listener)

| Entry | Level | Extra fields |
|-------|-------|--------------|
| Started listener thread | DEBUG | — |
| Heartbeat sent | DEBUG | `ps_ip` |
| Packet received | DEBUG | `packet_id` |

### `module=discovery` (PS discovery)

| Entry | Level | Extra fields |
|-------|-------|--------------|
| Discovery started | INFO | `timeout_s` |
| PS found | INFO | `ps_ip` |
| PS not found | WARNING | — |
| Fail count increment | WARNING | `fail_count` `ps_ip` |
| 3 failures — re-discovering | WARNING | — |
| Discovery timeout | ERROR | — |

### `module=config`

| Entry | Level | Extra fields |
|-------|-------|--------------|
| Config loaded | INFO | `path` |
| IP written back | INFO | `ps_ip` |

## Viewing Logs

### When running as a systemd service

```bash
# Last 50 lines:
piedalmetry log

# Last N lines:
piedalmetry log --lines 100

# Follow in real time:
piedalmetry log --follow

# Filter by level:
piedalmetry log --level DEBUG

# Since a timestamp:
piedalmetry log --since "2026-04-27 10:00:00"
```

### Using journalctl directly

```bash
# All piedalmetry logs:
journalctl -u piedalmetry --no-pager

# Follow:
journalctl -u piedalmetry -f

# Last hour:
journalctl -u piedalmetry --since "1 hour ago"

# Filter by level keyword (key=value format):
journalctl -u piedalmetry | grep "level=WARNING"

# Show only brake/motor cycle lines:
journalctl -u piedalmetry | grep "brake_pct="
```

### When running in foreground

Logs go to stdout. Use standard shell tools:

```bash
uv run python -m piedalmetry run --log-level DEBUG 2>&1 | grep "latency_ms"
```

## Changing Log Level at Runtime

The log level is set in the config file and takes effect at next
service start. For one-off changes, use the CLI flag:

```bash
piedalmetry run --log-level DEBUG
```

Or restart the service after editing the config:

```bash
sudo nano /etc/piedalmetry/config.toml   # set log_level = "DEBUG"
piedalmetry restart
```

## Latency Monitoring

Every telemetry cycle logs `latency_ms` at DEBUG level. To monitor
pipeline latency:

```bash
journalctl -u piedalmetry -f | grep "latency_ms"
# Example output:
# latency_ms=0.87
# latency_ms=1.12
# latency_ms=0.94
```

Target: latency < 50ms per cycle. Consistent values above 50ms
indicate a performance issue (check CPU usage, GPIO backend).

## References

- [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry) —
  GT7 protocol (heartbeat, packet structure)
- [snipem/gt7dashboard](https://github.com/snipem/gt7dashboard) —
  GT7 integration patterns
