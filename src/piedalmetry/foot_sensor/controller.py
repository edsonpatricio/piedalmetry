"""Foot-on-pedal sensor — wraps gpiozero (lgpio backend) for a digital input.

Active-LOW convention: foot on pedal → switch connects pin to GND → pin LOW.
Internal pull-up is enabled on the signal pin; no external resistor is required.

The feed pin is driven permanently HIGH to supply the sensor switch, so no
separate 3.3 V wire is needed — just route the switch between the feed pin
and the signal pin.

Hardware (default):
  Feed: GPIO 21 (pin 40) → one leg of switch
  Signal: GPIO 25 (pin 22) → other leg of switch (active LOW, pull-up enabled)
"""

from __future__ import annotations

import abc
import os


class FootSensorBase(abc.ABC):
    """Abstract base for foot sensor controllers (real and mock)."""

    @abc.abstractmethod
    def is_foot_detected(self) -> bool:
        """Return True when a foot is detected on the pedal."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Release GPIO resources."""


class FootSensorController(FootSensorBase):
    """Real foot sensor using gpiozero (lgpio backend) digital input.

    Args:
        gpio_pin: BCM pin for the signal line (active LOW, pull-up enabled).
        feed_gpio: BCM pin driven permanently HIGH to power the sensor switch.
    """

    def __init__(self, gpio_pin: int = 25, feed_gpio: int = 21) -> None:
        # lgpio creates notification pipes (.lgd-nfy*) in the CWD.
        # Temporarily switch to /tmp during GPIO init.
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")

            from gpiozero import Device  # type: ignore[import-untyped]
            from gpiozero import DigitalInputDevice  # type: ignore[import-untyped]
            from gpiozero import DigitalOutputDevice  # type: ignore[import-untyped]
            from gpiozero.pins.lgpio import LGPIOFactory  # type: ignore[import-untyped]

            Device.pin_factory = LGPIOFactory()

            # Feed pin: permanently HIGH — acts as the 3.3 V supply for the switch.
            self._feed = DigitalOutputDevice(feed_gpio, initial_value=True)

            # Signal pin: pull-up HIGH when no foot, LOW when switch closes to feed.
            # is_active returns True when pin is LOW (active state with pull_up=True).
            self._sensor = DigitalInputDevice(gpio_pin, pull_up=True)
        finally:
            os.chdir(original_cwd)

    def is_foot_detected(self) -> bool:
        return self._sensor.is_active

    def cleanup(self) -> None:
        try:
            self._sensor.close()
            self._feed.close()
        except Exception:
            pass


class MockFootSensorController(FootSensorBase):
    """Mock foot sensor for testing and mock mode.

    Defaults to foot detected so the motor pipeline is not blocked during
    development. Use set_foot_detected() to control state in tests.
    """

    def __init__(self, foot_present: bool = True) -> None:
        self._foot_present = foot_present

    def set_foot_detected(self, value: bool) -> None:
        self._foot_present = value

    def is_foot_detected(self) -> bool:
        return self._foot_present

    def cleanup(self) -> None:
        pass
