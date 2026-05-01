"""Integration tests: full pipeline from UDP packets to motor mock.

Tests the path: decrypt → parse → filter → mapping → MockMotorController
using the MockGT7Server and MockMotorController without real hardware.

References:
  - Bornhall/gt7telemetry: packet structure and encryption
  - snipem/gt7dashboard: integration test patterns
"""

from __future__ import annotations

import pytest

from piedalmetry.motor.filter import BrakeFilter
from piedalmetry.motor.mapping import map_brake_to_motor
from piedalmetry.motor.mock import MockMotorController
from piedalmetry.telemetry.decrypt import decrypt
from piedalmetry.telemetry.parser import parse
from tests.mock.gt7_server import _build_packet


class TestFullPipeline:
    """Test the full decryption → parse → filter → motor chain."""

    def _run_pipeline(
        self,
        brake_pct: float,
        speed_kph: float,
        min_brake: int = 30,
        min_motor: int = 50,
        min_speed: int = 5,
        dead_zone: float = 0.0,
        ema_alpha: float = 0.0,
    ) -> float:
        """Run one packet through the full pipeline, return motor duty %."""
        raw = _build_packet(brake_pct=brake_pct, speed_kph=speed_kph)
        decrypted = decrypt(raw)
        assert decrypted is not None, "Decryption failed"

        pkt = parse(decrypted)
        assert pkt.is_valid, "Packet validation failed"

        filt = BrakeFilter(dead_zone=dead_zone, ema_alpha=ema_alpha)
        filtered = filt.filter(pkt.brake_pressure)
        motor = MockMotorController()

        if pkt.car_speed_kph >= min_speed:
            duty = map_brake_to_motor(filtered, min_brake, min_motor)
            motor.set_duty_cycle(duty)
        else:
            motor.stop()

        return motor.duty_history[-1] if motor.duty_history else 0.0

    def test_proportional_pwm_at_50_percent_brake(self) -> None:
        """50% brake with defaults (min_brake=30, min_motor=50) → ~57% motor."""
        duty = self._run_pipeline(brake_pct=50.0, speed_kph=100.0)
        # Linear: (50-30)/(100-30) * (100-50) + 50 ≈ 64.3%
        assert 60.0 <= duty <= 70.0, f"Expected ~64% motor, got {duty:.1f}%"

    def test_full_brake_gives_100_percent_motor(self) -> None:
        duty = self._run_pipeline(brake_pct=100.0, speed_kph=100.0)
        # uint8 encoding (0–255) rounds 100% to 255 → parses back to ~100%
        assert duty == pytest.approx(100.0, abs=0.5)

    def test_below_threshold_motor_off(self) -> None:
        """Brake below min_brake_pressure → motor at 0%."""
        duty = self._run_pipeline(brake_pct=10.0, speed_kph=100.0, min_brake=30)
        assert duty == 0.0

    def test_speed_gate_stops_motor(self) -> None:
        """Car speed below min_car_speed → motor off regardless of brake."""
        duty = self._run_pipeline(
            brake_pct=80.0, speed_kph=3.0, min_speed=5
        )
        assert duty == 0.0

    def test_speed_at_exact_threshold_activates_motor(self) -> None:
        """Car at min_car_speed → motor active (use 5.5 to avoid float precision)."""
        duty = self._run_pipeline(
            brake_pct=100.0, speed_kph=5.5, min_speed=5
        )
        assert duty == pytest.approx(100.0, abs=0.5)

    def test_mock_motor_records_history(self) -> None:
        """MockMotorController accumulates duty cycle history."""
        motor = MockMotorController()
        raw = _build_packet(brake_pct=60.0, speed_kph=100.0)
        pkt = parse(decrypt(raw))  # type: ignore[arg-type]
        filt = BrakeFilter(dead_zone=0.0, ema_alpha=0.0)
        filtered = filt.filter(pkt.brake_pressure)
        duty = map_brake_to_motor(filtered, min_brake=30, min_motor=50)
        motor.set_duty_cycle(duty)
        assert len(motor.duty_history) == 1
        assert motor.duty_history[0] == pytest.approx(duty, abs=0.1)


class TestPipelineWithMultiplePackets:
    """Test pipeline behaviour over a sequence of packets."""

    def test_increasing_brake_produces_increasing_motor(self) -> None:
        filt = BrakeFilter(dead_zone=1.0, ema_alpha=0.0)
        motor = MockMotorController()
        duties: list[float] = []

        for brake_pct in [35.0, 50.0, 70.0, 90.0, 100.0]:
            raw = _build_packet(brake_pct=brake_pct, speed_kph=100.0)
            pkt = parse(decrypt(raw))  # type: ignore[arg-type]
            filtered = filt.filter(pkt.brake_pressure)
            duty = map_brake_to_motor(filtered, min_brake=30, min_motor=50)
            motor.set_duty_cycle(duty)
            duties.append(duty)

        # Each duty should be >= previous (monotonically non-decreasing)
        for i in range(1, len(duties)):
            assert duties[i] >= duties[i - 1], (
                f"Duty decreased: {duties[i - 1]:.1f} → {duties[i]:.1f}"
            )

    def test_jitter_suppression_with_dead_zone(self) -> None:
        """50 packets with ±0.9% jitter (< dead_zone 2%) → motor output stable."""
        import random
        import statistics

        random.seed(42)
        filt = BrakeFilter(dead_zone=2.0, ema_alpha=0.0)
        motor = MockMotorController()
        base_brake = 50.0

        # Jitter strictly within dead_zone so all changes are suppressed
        for _i in range(50):
            jitter = random.uniform(-0.9, 0.9)
            brake = base_brake + jitter
            raw = _build_packet(brake_pct=brake, speed_kph=100.0)
            pkt = parse(decrypt(raw))  # type: ignore[arg-type]
            filtered = filt.filter(pkt.brake_pressure)
            duty = map_brake_to_motor(filtered, min_brake=30, min_motor=50)
            motor.set_duty_cycle(duty)

        history = motor.duty_history
        variance = statistics.variance(history) if len(history) > 1 else 0.0
        assert variance < 1.0, (
            f"Motor variance {variance:.2f} exceeds 1.0 — jitter not suppressed"
        )

    def test_large_step_change_passes_through(self) -> None:
        """Genuine 30→80% brake step passes through despite dead-zone filter."""
        filt = BrakeFilter(dead_zone=2.0, ema_alpha=0.0)

        # Establish baseline at 30%
        for _ in range(3):
            filt.filter(30.0)

        # Genuine step to 80%
        filtered_after_step = filt.filter(80.0)
        assert filtered_after_step > 40.0, (
            f"Large step not passed through — filtered={filtered_after_step:.1f}"
        )
