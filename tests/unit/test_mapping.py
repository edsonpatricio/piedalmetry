"""Unit tests for brake-to-motor mapping — T018."""

from piedalmetry.motor.mapping import map_brake_to_motor, map_brake_to_pulse_half_period


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


class TestPulseHalfPeriod:
    def test_at_min_brake_returns_low_freq_half_period(self) -> None:
        freq_low = 2.0
        result = map_brake_to_pulse_half_period(20.0, min_brake=20, top_limit=98, freq_low=freq_low, freq_high=8.0)
        expected = 1.0 / (2.0 * freq_low)
        assert abs(result - expected) < 0.001

    def test_at_top_limit_returns_high_freq_half_period(self) -> None:
        freq_high = 8.0
        result = map_brake_to_pulse_half_period(98.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=freq_high)
        expected = 1.0 / (2.0 * freq_high)
        assert abs(result - expected) < 0.001

    def test_midpoint_is_between_low_and_high(self) -> None:
        slow = 1.0 / (2.0 * 1.0)
        fast = 1.0 / (2.0 * 8.0)
        result = map_brake_to_pulse_half_period(59.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0)
        assert fast < result < slow

    def test_monotonically_decreasing(self) -> None:
        periods = [
            map_brake_to_pulse_half_period(p, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0)
            for p in [20.0, 35.0, 50.0, 70.0, 90.0, 98.0]
        ]
        for i in range(1, len(periods)):
            assert periods[i] <= periods[i - 1], (
                f"Period increased: {periods[i - 1]:.4f} → {periods[i]:.4f}"
            )

    def test_top_limit_zero_uses_full_range(self) -> None:
        freq_high = 8.0
        result = map_brake_to_pulse_half_period(100.0, min_brake=20, top_limit=0, freq_low=1.0, freq_high=freq_high)
        expected = 1.0 / (2.0 * freq_high)
        assert abs(result - expected) < 0.001

    def test_below_min_brake_clamps_to_low_freq(self) -> None:
        freq_low = 1.0
        result = map_brake_to_pulse_half_period(10.0, min_brake=20, top_limit=98, freq_low=freq_low, freq_high=8.0)
        expected = 1.0 / (2.0 * freq_low)
        assert abs(result - expected) < 0.001

    def test_exponent_gt1_slows_low_brake_ramp(self) -> None:
        # With exponent>1, midpoint freq should be below linear midpoint
        mid_linear = map_brake_to_pulse_half_period(59.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0, exponent=1.0)
        mid_curved = map_brake_to_pulse_half_period(59.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0, exponent=2.0)
        # exponent>1 → t shrinks → lower freq → longer half-period at midpoint
        assert mid_curved > mid_linear

    def test_exponent_lt1_boosts_low_brake_ramp(self) -> None:
        mid_linear = map_brake_to_pulse_half_period(59.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0, exponent=1.0)
        mid_curved = map_brake_to_pulse_half_period(59.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0, exponent=0.5)
        # exponent<1 → t grows → higher freq → shorter half-period at midpoint
        assert mid_curved < mid_linear

    def test_endpoints_unchanged_by_exponent(self) -> None:
        for exp in [0.5, 1.0, 2.0, 3.0]:
            at_min = map_brake_to_pulse_half_period(20.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0, exponent=exp)
            at_max = map_brake_to_pulse_half_period(98.0, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0, exponent=exp)
            assert abs(at_min - 0.5) < 0.001, f"exponent={exp}: min endpoint changed"
            assert abs(at_max - 0.0625) < 0.001, f"exponent={exp}: max endpoint changed"

    def test_frequency_ramp_is_linear(self) -> None:
        # Equal brake steps should produce equal frequency steps
        brakes = [20.0, 38.5, 57.0, 75.5, 94.0]  # equal 18.5% steps within [20, 98]
        half_periods = [
            map_brake_to_pulse_half_period(b, min_brake=20, top_limit=98, freq_low=1.0, freq_high=8.0)
            for b in brakes
        ]
        freqs = [1.0 / (2.0 * hp) for hp in half_periods]
        steps = [freqs[i + 1] - freqs[i] for i in range(len(freqs) - 1)]
        for step in steps:
            assert abs(step - steps[0]) < 0.01, f"Frequency ramp not linear: {steps}"
