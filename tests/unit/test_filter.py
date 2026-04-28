"""Unit tests for anti-fluctuation filter — T019."""

from pidalmetry.motor.filter import BrakeFilter


class TestBrakeFilter:
    def test_first_value_passes_through(self) -> None:
        f = BrakeFilter(dead_zone=2.0, ema_alpha=0.3)
        assert f.filter(50.0) == 50.0

    def test_small_jitter_suppressed(self) -> None:
        """±1% jitter around 50% should not change output."""
        f = BrakeFilter(dead_zone=2.0, ema_alpha=0.0)  # no EMA
        f.filter(50.0)  # initial
        assert f.filter(51.0) == 50.0  # within dead zone
        assert f.filter(49.0) == 50.0  # within dead zone
        assert f.filter(50.5) == 50.0  # within dead zone

    def test_large_change_passes(self) -> None:
        """Change > dead_zone should update output."""
        f = BrakeFilter(dead_zone=2.0, ema_alpha=0.0)
        f.filter(50.0)
        result = f.filter(55.0)  # 5% change > 2% dead zone
        assert result == 55.0

    def test_ema_smoothing(self) -> None:
        """With EMA, output should be smoothed."""
        f = BrakeFilter(dead_zone=0.0, ema_alpha=0.5)  # no dead zone
        f.filter(0.0)   # initial = 0
        r1 = f.filter(100.0)  # EMA: 0.5*100 + 0.5*0 = 50
        assert abs(r1 - 50.0) < 0.1

    def test_reset_clears_state(self) -> None:
        f = BrakeFilter(dead_zone=2.0, ema_alpha=0.3)
        f.filter(50.0)
        f.reset()
        # After reset, next value should pass through
        assert f.filter(80.0) == 80.0

    def test_jitter_stream_stable(self) -> None:
        """Simulate 50 packets of ±1.5% jitter — output must remain stable."""
        f = BrakeFilter(dead_zone=2.0, ema_alpha=0.3)
        f.filter(50.0)
        outputs = []
        for i in range(50):
            jitter = 1.5 * (1 if i % 2 == 0 else -1)
            outputs.append(f.filter(50.0 + jitter))
        # All outputs should be the same (within dead zone)
        assert max(outputs) - min(outputs) < 1.0
