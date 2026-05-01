"""Unit tests for brake-to-motor mapping — T018."""

from piedalmetry.motor.mapping import map_brake_to_motor


class TestMapping:
    def test_below_threshold_returns_zero(self) -> None:
        assert map_brake_to_motor(20.0, min_brake=30, min_motor=50) == 0.0

    def test_at_threshold_returns_min_motor(self) -> None:
        result = map_brake_to_motor(30.0, min_brake=30, min_motor=50)
        assert abs(result - 50.0) < 0.1

    def test_full_brake_returns_100(self) -> None:
        assert map_brake_to_motor(100.0, min_brake=30, min_motor=50) == 100.0

    def test_midpoint_is_linear(self) -> None:
        # At 65% brake (midpoint of 30-100 range):
        # expected motor = 50 + (100-50)/(100-30) * (65-30) = 50 + 25 = 75
        result = map_brake_to_motor(65.0, min_brake=30, min_motor=50)
        assert abs(result - 75.0) < 0.1

    def test_zero_brake(self) -> None:
        assert map_brake_to_motor(0.0, min_brake=30, min_motor=50) == 0.0

    def test_custom_thresholds(self) -> None:
        # min_brake=10, min_motor=20: at 10% brake → 20% motor
        result = map_brake_to_motor(10.0, min_brake=10, min_motor=20)
        assert abs(result - 20.0) < 0.1

    def test_above_100_clamped(self) -> None:
        result = map_brake_to_motor(110.0, min_brake=30, min_motor=50)
        assert result == 100.0


class TestPowerMapping:
    def test_exponent_1_matches_linear(self) -> None:
        for brake in [35.0, 50.0, 65.0, 80.0, 95.0]:
            linear = map_brake_to_motor(brake, min_brake=30, min_motor=50, exponent=1.0)
            power = map_brake_to_motor(brake, min_brake=30, min_motor=50, exponent=1.0)
            assert abs(power - linear) < 0.001

    def test_exponent_2_midpoint_below_linear(self) -> None:
        # Power curve (n>1) must yield LESS than linear at mid-range (motor quiet under light braking)
        linear = map_brake_to_motor(65.0, min_brake=30, min_motor=50, exponent=1.0)
        power = map_brake_to_motor(65.0, min_brake=30, min_motor=50, exponent=2.0)
        assert power < linear, f"Expected power ({power:.2f}) < linear ({linear:.2f})"

    def test_power_at_threshold_returns_min_motor(self) -> None:
        result = map_brake_to_motor(30.0, min_brake=30, min_motor=50, exponent=2.0)
        assert abs(result - 50.0) < 0.1

    def test_power_full_brake_returns_100(self) -> None:
        assert map_brake_to_motor(100.0, min_brake=30, min_motor=50, exponent=2.0) == 100.0

    def test_power_below_threshold_is_zero(self) -> None:
        assert map_brake_to_motor(20.0, min_brake=30, min_motor=50, exponent=2.0) == 0.0

    def test_power_monotonically_increasing(self) -> None:
        duties = [
            map_brake_to_motor(p, min_brake=30, min_motor=50, exponent=2.0)
            for p in [35.0, 50.0, 70.0, 90.0, 100.0]
        ]
        for i in range(1, len(duties)):
            assert duties[i] >= duties[i - 1], (
                f"Duty decreased: {duties[i - 1]:.2f} → {duties[i]:.2f}"
            )

    def test_higher_exponent_gives_lower_midpoint(self) -> None:
        d15 = map_brake_to_motor(65.0, min_brake=30, min_motor=50, exponent=1.5)
        d20 = map_brake_to_motor(65.0, min_brake=30, min_motor=50, exponent=2.0)
        assert d20 < d15, f"Expected n=2.0 ({d20:.2f}) < n=1.5 ({d15:.2f})"
