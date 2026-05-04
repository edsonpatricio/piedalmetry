"""Status LED controller — GPIO pin configurable via [led] config section.

Blinks while searching for GT7 telemetry; goes solid when connected;
turns off on shutdown.

Uses the same gpiozero/lgpio setup as the motor controller.
"""

from __future__ import annotations

import abc
import logging
import os

_log = logging.getLogger("piedalmetry.led.controller")


class LedControllerBase(abc.ABC):
    """Abstract base for LED controllers (real and mock)."""

    @abc.abstractmethod
    def on(self) -> None:
        """Turn the LED on (solid)."""

    @abc.abstractmethod
    def off(self) -> None:
        """Turn the LED off."""

    @abc.abstractmethod
    def blink(self, on_time: float = 0.5, off_time: float = 0.5) -> None:
        """Blink the LED in the background. Calling on() or off() stops it."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Release GPIO resources."""


class LedController(LedControllerBase):
    """Status LED using gpiozero (lgpio backend).

    Args:
        gpio_pin: BCM pin number for the LED (default 17, physical pin 11).
    """

    def __init__(self, gpio_pin: int = 17) -> None:
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")

            from gpiozero import Device, LED  # type: ignore[import-untyped]
            from gpiozero.pins.lgpio import LGPIOFactory  # type: ignore[import-untyped]

            if not isinstance(Device.pin_factory, LGPIOFactory):
                Device.pin_factory = LGPIOFactory()

            self._led = LED(gpio_pin, initial_value=False)
        finally:
            os.chdir(original_cwd)

    def on(self) -> None:
        self._led.on()

    def off(self) -> None:
        self._led.off()

    def blink(self, on_time: float = 0.5, off_time: float = 0.5) -> None:
        self._led.blink(on_time=on_time, off_time=off_time, background=True)

    def cleanup(self) -> None:
        try:
            self.off()
            self._led.close()
        except Exception:
            pass


class MockLedController(LedControllerBase):
    """LED controller that records state without GPIO access."""

    def __init__(self) -> None:
        self._state = "off"  # "on", "off", "blink"

    def on(self) -> None:
        self._state = "on"
        _log.info("LED: ON (mock)")

    def off(self) -> None:
        self._state = "off"
        _log.info("LED: OFF (mock)")

    def blink(self, on_time: float = 0.5, off_time: float = 0.5) -> None:
        self._state = "blink"
        _log.info("LED: BLINK (mock)")

    def cleanup(self) -> None:
        pass

    @property
    def is_on(self) -> bool:
        return self._state == "on"

    @property
    def state(self) -> str:
        return self._state
