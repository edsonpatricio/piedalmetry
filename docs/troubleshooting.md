# Troubleshooting Guide

Run the built-in diagnostics first:

```bash
piedalmetry troubleshoot
```

This checks: config file validity, GPIO access, PS5 reachability, and
port 33740 availability, and reports PASS/FAIL for each.

## Common Failure Modes

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| Motor doesn't spin at all | Wrong GPIO pins | Verify BCM pin numbers in config match physical wiring; see [wiring.md](hardware/wiring.md) |
| Motor runs at full speed always | ENA jumper not removed | Remove shorting jumper from L298N ENA; see [l298n-pinout.md](hardware/l298n-pinout.md) |
| Motor chatters / flutters | Dead-zone too small | Increase `anti_fluctuation.dead_zone` (try 3–5%) |
| Motor responds slowly to braking | EMA alpha too low | Increase `anti_fluctuation.ema_alpha` (try 0.5–0.7) |
| `"Config validation error"` on startup | Invalid/missing config key | Read the error message for the exact key; fix value in config.toml |
| `"Config file not found"` | Wrong config path | Use `--config <path>` or copy example: `sudo cp config.example.toml /etc/piedalmetry/config.toml` |
| No telemetry data received | PS5 not found / GT7 not running | Verify GT7 is in an active session; run `piedalmetry discover` |
| `"Permission denied"` on GPIO | User not in gpio group | `sudo usermod -aG gpio $USER`, then log out and back in |
| `"Address already in use"` port 33740 | Another process using the port | `sudo lsof -i :33740` to find and kill the conflicting process |
| Service won't start on boot | Not installed as service | `sudo piedalmetry install` |
| Service starts but stops immediately | Crash on startup — check logs | `piedalmetry log --lines 50 --level ERROR` |
| High latency (`latency_ms` > 50) | System overloaded or throttling | Check CPU (`top`), check temperature (`vcgencmd measure_temp`) |
| `"lgpio: cannot open gpiochip"` | lgpio not installed or no permission | `sudo apt-get install python3-lgpio`; add user to `gpio` group |
| Motor spins wrong direction | OUT1/OUT2 wired in reverse | Swap OUT1 and OUT2 connections at the L298N terminals |
| Discovery fails (cross-subnet) | Broadcast doesn't cross routers | Set `playstation.ip` manually in config; see [configuration.md](configuration.md) |
| Config IP cleared after restart | 3 consecutive PS5 connection failures | Check PS5 is powered on and GT7 is running; verify `playstation.ip` is correct |

## GPIO Diagnostics

```bash
# Check GPIO group membership:
groups $USER

# Manually test GPIO access (lgpio):
python3 -c "import lgpio; h = lgpio.gpiochip_open(0); print('GPIO OK'); lgpio.gpiochip_close(h)"

# Spin motor for 3 seconds to verify hardware wiring:
python3 -c "
import lgpio, time
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, 23, 1)   # IN1 HIGH
lgpio.gpio_claim_output(h, 24, 0)   # IN2 LOW
lgpio.tx_pwm(h, 18, 1000, 50)       # ENA 50% duty
time.sleep(3)
lgpio.tx_pwm(h, 18, 1000, 0)
lgpio.gpiochip_close(h)
print('Motor spin test complete')
"
```

## Network Diagnostics

```bash
# Discover PS5 (works on same subnet):
piedalmetry discover --timeout 10

# Ping PS5 directly:
ping -c 3 192.168.1.50

# Check if port 33740 is in use:
sudo ss -ulnp | grep 33740

# Capture UDP traffic on port 33740:
sudo tcpdump -i eth0 udp port 33740 -c 20
```

## Log-Based Debugging

```bash
# Show all errors:
piedalmetry log --level ERROR --lines 50

# Show last 100 lines including DEBUG:
piedalmetry log --lines 100

# Watch live:
piedalmetry log --follow
```

## Service Lifecycle Issues

```bash
# Check service status:
piedalmetry status

# Force restart:
piedalmetry restart

# View systemd unit file:
cat /etc/systemd/system/piedalmetry.service

# Reload systemd and restart:
sudo systemctl daemon-reload
sudo systemctl restart piedalmetry
```

## Performance Issues on Pi 2B

The RPi 2B is a modest platform. If latency is consistently > 50ms:

1. Check CPU frequency: `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq`
2. Check temperature (throttling occurs above 80°C):
   ```bash
   vcgencmd measure_temp
   ```
3. Reduce EMA computation: set `ema_alpha = 0.0` to disable EMA
4. Increase UDP timeout so the listener thread sleeps less

## References

- [Bornhall/gt7telemetry](https://github.com/Bornhall/gt7telemetry) —
  GT7 protocol (heartbeat 33739, receive 33740)
- [snipem/gt7dashboard](https://github.com/snipem/gt7dashboard) —
  GT7 integration patterns and test data
