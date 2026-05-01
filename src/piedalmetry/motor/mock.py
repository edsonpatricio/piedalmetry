"""Mock motor controller for development and CI — no GPIO access.

Records all duty cycle changes for test assertions.
"""

from __future__ import annotations

from piedalmetry.motor.controller import MotorControllerBase


class MockMotorController(MotorControllerBase):
    """Motor controller that records actions without accessing GPIO."""

    def __init__(self) -> None:
        self._duty_history: list[float] = []
        self._running = False

    def set_duty_cycle(self, duty_pct: float) -> None:
        """Record a duty cycle change."""
        clamped = max(0.0, min(100.0, duty_pct))
        self._duty_history.append(clamped)
        self._running = clamped > 0.0

    def stop(self) -> None:
        """Record motor stop."""
        self._duty_history.append(0.0)
        self._running = False

    def cleanup(self) -> None:
        """No-op for mock."""

    @property
    def duty_history(self) -> list[float]:
        """Return the full history of duty cycle values."""
        return list(self._duty_history)

    @property
    def is_running(self) -> bool:
        return self._running
