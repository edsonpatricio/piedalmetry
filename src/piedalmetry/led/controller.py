"""Blue status LED controller — GPIO 17 (Physical Pin 11).

Lights up when GT7 telemetry connection is established; turns off on
connection loss or shutdown.

Uses the same gpiozero/lgpio setup as the motor controller.
"""

from __future__ import annotations

import abc
import logging
import os

_log = logging.getLogger("piedalmetry.led.controller")

# BCM GPIO 17, Physical Pin 11 — hardcoded, no config entry needed.
LED_GPIO = 17


class LedControllerBase(abc.ABC):
    """Abstract base for LED controllers (real and mock)."""

    @abc.abstractmethod
    def on(self) -> None:
        """Turn the LED on."""

    @abc.abstractmethod
    def off(self) -> None:
        """Turn the LED off."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Release GPIO resources."""


class LedController(LedControllerBase):
    """Blue status LED using gpiozero (lgpio backend).

    Wiring: GPIO 17 → 220 Ω resistor → LED anode (longer leg) → LED cathode (shorter leg) → GND (Pin 9).
    """

    def __init__(self) -> None:
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")

            from gpiozero import Device, LED  # type: ignore[import-untyped]
            from gpiozero.pins.lgpio import LGPIOFactory  # type: ignore[import-untyped]

            if not isinstance(Device.pin_factory, LGPIOFactory):
                Device.pin_factory = LGPIOFactory()

            self._led = LED(LED_GPIO)
        finally:
            os.chdir(original_cwd)

    def on(self) -> None:
        self._led.on()

    def off(self) -> None:
        self._led.off()

    def cleanup(self) -> None:
        try:
            self.off()
            self._led.close()
        except Exception:
            pass


class MockLedController(LedControllerBase):
    """LED controller that records state without GPIO access."""

    def __init__(self) -> None:
        self._is_on = False

    def on(self) -> None:
        self._is_on = True
        _log.info("LED: ON (mock)")

    def off(self) -> None:
        self._is_on = False
        _log.info("LED: OFF (mock)")

    def cleanup(self) -> None:
        pass

    @property
    def is_on(self) -> bool:
        return self._is_on
