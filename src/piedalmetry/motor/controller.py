"""Motor PWM controller — wraps gpiozero (lgpio backend) for L298N.

Constitution Principle I: GPIO pins documented in config.example.toml.
Hardware: ENA=GPIO18 (pin12), IN1=GPIO23 (pin16), IN2=GPIO24 (pin18).

gpiozero is used with the lgpio pin factory because:
  - It's available via apt (python3-lgpio) on DietPi
  - lgpio uses kernel gpiochip, not the deprecated /dev/mem
  - NOTE: lgpio creates notification pipes in CWD — we temporarily
    switch to /tmp during GPIO init to avoid filesystem issues.
"""

from __future__ import annotations

import abc
import os


class MotorControllerBase(abc.ABC):
    """Abstract base for motor controllers (real and mock)."""

    @abc.abstractmethod
    def set_duty_cycle(self, duty_pct: float) -> None:
        """Set motor PWM duty cycle (0.0–100.0%)."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop the motor (duty cycle 0)."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Release GPIO resources."""


class MotorController(MotorControllerBase):
    """Real motor controller using gpiozero (lgpio backend) for PWM.

    Args:
        gpio_ena: BCM pin for ENA (PWM speed control).
        gpio_in1: BCM pin for IN1 (direction).
        gpio_in2: BCM pin for IN2 (direction).
        pwm_frequency: PWM frequency in Hz.
    """

    def __init__(
        self,
        gpio_ena: int = 18,
        gpio_in1: int = 23,
        gpio_in2: int = 24,
        pwm_frequency: int = 1000,
    ) -> None:
        # lgpio creates notification pipes (.lgd-nfy*) in the CWD.
        # If CWD is a network mount or read-only FS, this fails.
        # Temporarily switch to /tmp for GPIO init.
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")

            from gpiozero import (  # type: ignore[import-untyped]
                Device,  # type: ignore[import-untyped]
                DigitalOutputDevice,
                PWMOutputDevice,
            )
            from gpiozero.pins.lgpio import LGPIOFactory  # type: ignore[import-untyped]

            Device.pin_factory = LGPIOFactory()

            self._ena_pin = gpio_ena
            self._in1_pin = gpio_in1
            self._in2_pin = gpio_in2

            # Direction: IN1=HIGH, IN2=LOW (forward)
            self._in1 = DigitalOutputDevice(gpio_in1, initial_value=True)
            self._in2 = DigitalOutputDevice(gpio_in2, initial_value=False)

            # PWM on ENA for speed control (gpiozero uses 0.0–1.0 range)
            self._ena = PWMOutputDevice(
                gpio_ena,
                frequency=pwm_frequency,
                initial_value=0.0,
            )
        finally:
            os.chdir(original_cwd)

    def set_duty_cycle(self, duty_pct: float) -> None:
        """Set motor PWM duty cycle (0.0–100.0%)."""
        clamped = max(0.0, min(100.0, duty_pct))
        self._ena.value = clamped / 100.0  # gpiozero uses 0.0–1.0

    def stop(self) -> None:
        """Stop the motor."""
        self._ena.value = 0.0

    def cleanup(self) -> None:
        """Release GPIO resources."""
        try:
            self.stop()
            self._ena.close()
            self._in1.close()
            self._in2.close()
        except Exception:
            pass
