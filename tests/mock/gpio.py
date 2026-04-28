"""Mock GPIO/PWM interface for testing without real hardware.

Records all PWM duty cycle changes for test assertions.
No real GPIO access — safe to run on x86 development machines.
"""

from __future__ import annotations


class MockPWMPin:
    """Simulates a single PWM output pin."""

    def __init__(self, pin: int, frequency: int = 1000) -> None:
        self.pin = pin
        self.frequency = frequency
        self._duty_cycle: float = 0.0
        self.history: list[float] = []

    @property
    def duty_cycle(self) -> float:
        return self._duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value: float) -> None:
        clamped = max(0.0, min(100.0, value))
        self._duty_cycle = clamped
        self.history.append(clamped)

    def stop(self) -> None:
        self.duty_cycle = 0.0

    def cleanup(self) -> None:
        self.stop()


class MockDigitalPin:
    """Simulates a single digital output pin."""

    def __init__(self, pin: int, initial_value: bool = False) -> None:
        self.pin = pin
        self.value = initial_value
        self.history: list[bool] = [initial_value]

    def set(self, value: bool) -> None:
        self.value = value
        self.history.append(value)

    def cleanup(self) -> None:
        pass


class MockGPIOInterface:
    """Full mock GPIO interface — tracks all pin interactions."""

    def __init__(self) -> None:
        self.pwm_pins: dict[int, MockPWMPin] = {}
        self.digital_pins: dict[int, MockDigitalPin] = {}

    def setup_pwm(self, pin: int, frequency: int = 1000) -> MockPWMPin:
        self.pwm_pins[pin] = MockPWMPin(pin, frequency)
        return self.pwm_pins[pin]

    def setup_digital(self, pin: int, initial_value: bool = False) -> MockDigitalPin:
        self.digital_pins[pin] = MockDigitalPin(pin, initial_value)
        return self.digital_pins[pin]

    def cleanup_all(self) -> None:
        for p in self.pwm_pins.values():
            p.cleanup()
        for p in self.digital_pins.values():
            p.cleanup()

    @property
    def all_pwm_history(self) -> dict[int, list[float]]:
        return {pin: p.history for pin, p in self.pwm_pins.items()}
