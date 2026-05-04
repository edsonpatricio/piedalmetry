"""Unit tests for MockLedController."""

from __future__ import annotations

from piedalmetry.led.controller import MockLedController


class TestMockLedController:
    def test_initial_state_is_off(self) -> None:
        led = MockLedController()
        assert led.state == "off"
        assert led.is_on is False

    def test_on_sets_state(self) -> None:
        led = MockLedController()
        led.on()
        assert led.state == "on"
        assert led.is_on is True

    def test_off_sets_state(self) -> None:
        led = MockLedController()
        led.on()
        led.off()
        assert led.state == "off"
        assert led.is_on is False

    def test_blink_sets_state(self) -> None:
        led = MockLedController()
        led.blink()
        assert led.state == "blink"
        assert led.is_on is False

    def test_on_after_blink_stops_blink(self) -> None:
        led = MockLedController()
        led.blink()
        led.on()
        assert led.state == "on"

    def test_off_after_blink_stops_blink(self) -> None:
        led = MockLedController()
        led.blink()
        led.off()
        assert led.state == "off"

    def test_cleanup_does_not_raise(self) -> None:
        led = MockLedController()
        led.cleanup()
