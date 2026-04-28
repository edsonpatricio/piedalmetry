"""Anti-fluctuation filter: hysteresis dead-zone + optional EMA.

Prevents motor flutter from small, rapid telemetry jitter.
Constitution Principle VII defines the config keys:
  anti_fluctuation.dead_zone  (default 2.0%)
  anti_fluctuation.ema_alpha  (default 0.3, 0.0 = disabled)
"""

from __future__ import annotations

import logging

_log = logging.getLogger("pidalmetry.motor.filter")

# Changes larger than this multiple of dead_zone bypass EMA immediately.
_LARGE_CHANGE_MULTIPLIER = 5.0


class BrakeFilter:
    """Smooth brake pressure values to prevent motor flutter."""

    def __init__(self, dead_zone: float = 2.0, ema_alpha: float = 0.3) -> None:
        self._dead_zone = dead_zone
        self._ema_alpha = ema_alpha
        self._current: float | None = None
        self._ema: float | None = None

    def filter(self, raw_brake: float) -> float:
        """Apply dead-zone + EMA filtering to a raw brake value.

        Large genuine changes (> dead_zone * 5) bypass EMA smoothing so
        the motor responds immediately. Small changes within the dead-zone
        are suppressed to prevent flutter.

        Args:
            raw_brake: Raw brake pressure 0.0–100.0%.

        Returns:
            Filtered brake pressure 0.0–100.0%.
        """
        # First reading — no filtering
        if self._current is None:
            self._current = raw_brake
            self._ema = raw_brake
            _log.debug(
                "filter init raw=%.1f output=%.1f", raw_brake, raw_brake
            )
            return raw_brake

        change = abs(raw_brake - self._current)
        large_change = (
            self._dead_zone > 0.0
            and change > self._dead_zone * _LARGE_CHANGE_MULTIPLIER
        )

        if large_change:
            # Bypass EMA for genuine large transitions
            smoothed = raw_brake
            self._ema = raw_brake
            _log.debug(
                "filter bypass raw=%.1f change=%.1f output=%.1f",
                raw_brake,
                change,
                smoothed,
            )
        elif self._ema_alpha > 0.0 and self._ema is not None:
            self._ema = self._ema_alpha * raw_brake + (1 - self._ema_alpha) * self._ema
            smoothed = self._ema
        else:
            smoothed = raw_brake

        # Dead-zone: only update output if change exceeds threshold
        if abs(smoothed - self._current) > self._dead_zone:
            prev = self._current
            self._current = smoothed
            _log.debug(
                "filter update raw=%.1f smoothed=%.1f prev=%.1f output=%.1f",
                raw_brake,
                smoothed,
                prev,
                self._current,
            )
        else:
            _log.debug(
                "filter suppress raw=%.1f smoothed=%.1f output=%.1f (dead-zone)",
                raw_brake,
                smoothed,
                self._current,
            )

        return self._current

    def reset(self) -> None:
        """Reset filter state on idle transition (motor stops)."""
        prev = self._current if self._current is not None else 0.0
        _log.debug("filter reset prev=%.1f", prev)
        self._current = None
        self._ema = None
