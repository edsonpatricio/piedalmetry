"""Unit tests for MockFootSensorController."""

from __future__ import annotations

from piedalmetry.foot_sensor.controller import MockFootSensorController


class TestMockFootSensorController:
    def test_defaults_to_foot_detected(self) -> None:
        sensor = MockFootSensorController()
        assert sensor.is_foot_detected() is True

    def test_can_initialise_without_foot(self) -> None:
        sensor = MockFootSensorController(foot_present=False)
        assert sensor.is_foot_detected() is False

    def test_set_foot_detected_true(self) -> None:
        sensor = MockFootSensorController(foot_present=False)
        sensor.set_foot_detected(True)
        assert sensor.is_foot_detected() is True

    def test_set_foot_detected_false(self) -> None:
        sensor = MockFootSensorController()
        sensor.set_foot_detected(False)
        assert sensor.is_foot_detected() is False

    def test_cleanup_does_not_raise(self) -> None:
        sensor = MockFootSensorController()
        sensor.cleanup()  # must not raise
