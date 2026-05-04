"""Shutdown button controller — monitors a GPIO pin for HIGH→LOW transition.

Active-LOW push button: wire GPIO 3 (physical pin 5) → normally-open button → GND.
GPIO 3 has a hardware 1.8 kΩ pull-up — no external resistor needed.

Only a HIGH→LOW *transition* triggers the callback. If the pin is already
LOW at boot (button held on power-on) no shutdown fires until the button
is released and pressed again. If the pin stays HIGH and is never pressed,
nothing happens.
"""

from __future__ import annotations

import abc
import logging
import os
from collections.abc import Callable
from contextlib import suppress

_log = logging.getLogger("piedalmetry.shutdown_button.controller")


class ShutdownButtonBase(abc.ABC):
    """Abstract base for shutdown button controllers (real and mock)."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Release GPIO resources."""


class ShutdownButtonController(ShutdownButtonBase):
    """Monitors a GPIO pin for HIGH→LOW transition using gpiozero Button.

    Args:
        gpio_pin: BCM pin to monitor (default 3, physical pin 5).
        on_shutdown: Callback invoked on button press (HIGH→LOW transition).
    """

    def __init__(self, gpio_pin: int, on_shutdown: Callable[[], None]) -> None:
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")

            from gpiozero import Button, Device  # type: ignore[import-untyped]
            from gpiozero.pins.lgpio import LGPIOFactory  # type: ignore[import-untyped]

            if not isinstance(Device.pin_factory, LGPIOFactory):
                Device.pin_factory = LGPIOFactory()

            self._button = Button(gpio_pin, pull_up=True, bounce_time=0.1)
            self._button.when_pressed = on_shutdown
            _log.info("Shutdown button active gpio_pin=%d", gpio_pin)
        finally:
            os.chdir(original_cwd)

    def cleanup(self) -> None:
        with suppress(Exception):
            self._button.close()


class MockShutdownButtonController(ShutdownButtonBase):
    """No-op shutdown button for mock mode. Use trigger() in tests."""

    def __init__(self, on_shutdown: Callable[[], None] | None = None) -> None:
        self._on_shutdown = on_shutdown

    def trigger(self) -> None:
        """Simulate a button press (test helper)."""
        if self._on_shutdown:
            self._on_shutdown()

    def cleanup(self) -> None:
        pass
