"""Main service runner — connects listener → filter → mapping → motor.

The telemetry listener runs in a dedicated thread (multi-core).
The main thread processes packets and drives the motor.
"""

from __future__ import annotations

import signal
import subprocess
import threading
import time
from collections import deque
from typing import Any

from piedalmetry.config import AppConfig
from piedalmetry.foot_sensor.controller import (
    FootSensorBase,
    FootSensorController,
    MockFootSensorController,
)
from piedalmetry.led.controller import LedController, LedControllerBase, MockLedController
from piedalmetry.logging import LatencyTracker, setup_logging
from piedalmetry.motor.controller import MotorController, MotorControllerBase
from piedalmetry.motor.filter import BrakeFilter
from piedalmetry.motor.mapping import map_brake_to_pulse_half_period
from piedalmetry.motor.mock import MockMotorController
from piedalmetry.shutdown_button.controller import (
    MockShutdownButtonController,
    ShutdownButtonBase,
    ShutdownButtonController,
)
from piedalmetry.telemetry.listener import TelemetryListener
from piedalmetry.telemetry.parser import TelemetryPacket


class Runner:
    """Orchestrate the telemetry → motor pipeline."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._logger = setup_logging(config.log_level, config.log_target)
        self._filter = BrakeFilter(
            dead_zone=config.anti_fluctuation.dead_zone,
            ema_alpha=config.anti_fluctuation.ema_alpha,
        )
        self._tracker = LatencyTracker(self._logger, "pipeline")
        self._running = False
        self._packet_queue: deque[TelemetryPacket] = deque(maxlen=1)
        self._pulse_on = True
        self._pulse_last_toggle = 0.0
        self._foot_led_on = False

        self._shutdown_requested = False

        # Select motor controller
        self._motor: MotorControllerBase
        self._led: LedControllerBase
        self._foot_led: LedControllerBase
        self._foot_sensor: FootSensorBase
        self._shutdown_button: ShutdownButtonBase
        if config.mock_mode:
            self._motor = MockMotorController()
            self._led = MockLedController()
            self._foot_led = MockLedController()
            self._foot_sensor = MockFootSensorController()
            self._shutdown_button = MockShutdownButtonController()
            self._logger.info("Motor controller: MOCK mode")
        else:
            self._motor = MotorController(
                gpio_ena=config.brake.gpio_ena,
                gpio_in1=config.brake.gpio_in1,
                gpio_in2=config.brake.gpio_in2,
                pwm_frequency=config.brake.pwm_frequency,
            )
            self._led = LedController(config.playstation.conn_led_gpio)
            self._foot_led = LedController(config.brake.foot_sensor_led_gpio)
            # Always instantiate the real sensor so the foot LED works even when
            # foot_sensor_enabled = false (which only gates the motor).
            self._foot_sensor = FootSensorController(
                config.brake.foot_sensor_gpio,
                config.brake.foot_sensor_feed_gpio,
            )
            if config.shutdown_button_gpio >= 0:
                def _on_shutdown_press() -> None:
                    self._logger.info(
                        "Shutdown button pressed — initiating system shutdown"
                    )
                    self._shutdown_requested = True
                    self._running = False

                self._shutdown_button = ShutdownButtonController(
                    config.shutdown_button_gpio, _on_shutdown_press
                )
            else:
                self._shutdown_button = MockShutdownButtonController()
                self._logger.info("Shutdown button: disabled (gpio=-1)")

    def _on_packet(self, pkt: TelemetryPacket) -> None:
        """Callback from listener thread — enqueue latest packet."""
        self._packet_queue.append(pkt)

    def run(self) -> None:
        """Start the main loop. Blocks until SIGINT/SIGTERM."""
        self._running = True
        stop_event = threading.Event()

        def _signal_handler(sig: int, frame: Any) -> None:
            self._logger.info(f"Received signal {sig}, shutting down")
            self._running = False
            stop_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        ps_ip = self._config.playstation.ip

        b = self._config.brake
        af = self._config.anti_fluctuation
        self._logger.info(
            "Configuration",
            extra={"kv": {
                "mock_mode": self._config.mock_mode,
                "ps_conn_led_gpio": self._config.playstation.conn_led_gpio,
                "ps_label": self._config.playstation.label or "(none)",
                "shutdown_button_gpio": (
                    self._config.shutdown_button_gpio
                    if self._config.shutdown_button_gpio >= 0
                    else "disabled"
                ),
                "brake_gpio_ena": b.gpio_ena,
                "brake_gpio_in1": b.gpio_in1,
                "brake_gpio_in2": b.gpio_in2,
                "brake_pwm_frequency": b.pwm_frequency,
                "brake_min_pressure": b.min_pressure,
                "brake_min_strength": b.min_strength,
                "brake_min_car_speed": b.min_car_speed,
                "brake_min_pulse_freq": b.min_pulse_freq,
                "brake_max_pulse_freq": b.max_pulse_freq,
                "brake_feedback_exponent": b.feedback_exponent,
                "brake_top_limit_pattern": b.top_limit_pattern if b.top_limit_pattern > 0 else "disabled",
                "brake_foot_sensor_enabled": b.foot_sensor_enabled,
                "brake_foot_sensor_gpio": b.foot_sensor_gpio,
                "brake_foot_sensor_feed_gpio": b.foot_sensor_feed_gpio,
                "brake_foot_sensor_led_gpio": b.foot_sensor_led_gpio,
                "af_dead_zone": af.dead_zone,
                "af_ema_alpha": af.ema_alpha,
            }},
        )

        self._logger.info(
            "Starting telemetry listener",
            extra={"kv": {"ps_ip": ps_ip or "auto-discover"}},
        )

        self._led.blink()

        def _on_ip_discovered(ip: str) -> None:
            self._logger.info(
                "PlayStation discovered — persisting IP",
                extra={"kv": {"ps_ip": ip}},
            )
            from piedalmetry.config import write_back_ip
            try:
                write_back_ip(self._config, ip)
            except PermissionError:
                self._logger.warning(
                    "Cannot persist IP — config not writable (run reinstall to fix)",
                    extra={"kv": {"ps_ip": ip}},
                )

        def _on_connected() -> None:
            self._led.on()
            self._logger.info("GT7 telemetry connected")

        def _on_disconnected() -> None:
            self._led.blink()
            self._logger.warning("GT7 telemetry connection lost — re-discovering")

        listener = TelemetryListener(
            ps_ip,
            self._on_packet,
            on_ip_discovered=_on_ip_discovered,
            on_connected=_on_connected,
            on_disconnected=_on_disconnected,
        )
        listener.start()

        self._logger.info("Pipeline running — press Ctrl+C to stop")

        try:
            while self._running:
                # Foot LED: always reflects sensor state (independent of foot_sensor_enabled)
                foot_on = self._foot_sensor.is_foot_detected()
                if foot_on != self._foot_led_on:
                    self._foot_led_on = foot_on
                    if foot_on:
                        self._foot_led.on()
                    else:
                        self._foot_led.off()

                if not self._packet_queue:
                    time.sleep(0.001)  # 1ms yield
                    continue

                self._tracker.start()
                pkt = self._packet_queue.popleft()

                # Speed gate
                if pkt.car_speed_kph < self._config.brake.min_car_speed:
                    self._motor.stop()
                    self._filter.reset()
                    continue

                # Foot sensor motor gate (only when enabled)
                if self._config.brake.foot_sensor_enabled and not foot_on:
                    self._motor.stop()
                    self._filter.reset()
                    continue

                # Filter brake pressure
                filtered = self._filter.filter(pkt.brake_pressure)

                min_brake = self._config.brake.min_pressure
                top_limit = self._config.brake.top_limit_pattern

                if filtered < min_brake:
                    self._pulse_on = True
                    self._pulse_last_toggle = 0.0
                    duty = 0.0
                elif top_limit > 0 and filtered >= top_limit:
                    # Continuous 100% — solid resistance wall above threshold
                    self._pulse_on = True
                    duty = 100.0
                else:
                    # Pulsed zone: frequency shaped by exponent, strength linear
                    half_period = map_brake_to_pulse_half_period(
                        filtered, min_brake, top_limit,
                        self._config.brake.min_pulse_freq,
                        self._config.brake.max_pulse_freq,
                        exponent=self._config.brake.feedback_exponent,
                    )
                    effective_top = top_limit if top_limit > 0 else 100
                    span = effective_top - min_brake
                    t_linear = max(0.0, min(1.0, (filtered - min_brake) / span)) if span > 0 else 1.0
                    min_str = self._config.brake.min_strength
                    strength = min_str + t_linear * (100.0 - min_str)
                    now = time.monotonic()
                    if now - self._pulse_last_toggle >= half_period:
                        self._pulse_on = not self._pulse_on
                        self._pulse_last_toggle = now
                    duty = strength if self._pulse_on else 0.0

                self._motor.set_duty_cycle(duty)
                self._tracker.stop_and_log()

                self._logger.debug(
                    "Cycle",
                    extra={"kv": {
                        "brake_pct": f"{pkt.brake_pressure:.1f}",
                        "filtered": f"{filtered:.1f}",
                        "motor_pct": f"{duty:.1f}",
                        "speed_kph": f"{pkt.car_speed_kph:.1f}",
                    }},
                )
        finally:
            listener.stop()
            self._led.off()
            self._led.cleanup()
            self._foot_led.off()
            self._foot_led.cleanup()
            self._motor.cleanup()
            self._foot_sensor.cleanup()
            self._shutdown_button.cleanup()
            self._logger.info("Pipeline stopped")
            if self._shutdown_requested:
                self._logger.info("Issuing system shutdown")
                subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)

    def run_mock_sweep(self, duration: float = 10.0) -> None:
        """Run a sweep 0→100→0 on the motor for testing."""
        import math

        self._logger.info(
            "Mock sweep started",
            extra={"kv": {"duration_s": duration}},
        )
        start = time.monotonic()

        try:
            while time.monotonic() - start < duration:
                elapsed = time.monotonic() - start
                # Sine wave 0→100→0
                brake = 50.0 + 50.0 * math.sin(
                    2 * math.pi * elapsed / duration - math.pi / 2
                )
                brake = max(0.0, min(100.0, brake))

                filtered = self._filter.filter(brake)
                duty = 100.0 if filtered >= self._config.brake.min_pressure else 0.0
                self._motor.set_duty_cycle(duty)
                self._logger.debug(
                    "Sweep",
                    extra={"kv": {
                        "brake_pct": f"{brake:.1f}",
                        "motor_pct": f"{duty:.1f}",
                    }},
                )
                time.sleep(0.02)  # 50 Hz update rate
        finally:
            self._motor.stop()
            self._motor.cleanup()
            self._logger.info("Mock sweep completed")

    def run_fixed_brake(self, brake_pct: float, duration: float = 5.0) -> None:
        """Run motor at a fixed brake percentage for testing."""
        filtered = self._filter.filter(brake_pct)
        duty = 100.0 if filtered >= self._config.brake.min_pressure else 0.0
        self._logger.info(
            "Fixed brake test",
            extra={"kv": {
                "brake_pct": f"{brake_pct:.1f}",
                "motor_pct": f"{duty:.1f}",
                "duration_s": duration,
            }},
        )
        self._motor.set_duty_cycle(duty)
        try:
            time.sleep(duration)
        finally:
            self._motor.stop()
            self._motor.cleanup()
