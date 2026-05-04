"""Unit tests for MockShutdownButtonController."""

from __future__ import annotations

from piedalmetry.shutdown_button.controller import MockShutdownButtonController


class TestMockShutdownButtonController:
    def test_trigger_calls_callback(self) -> None:
        called: list[bool] = []
        btn = MockShutdownButtonController(on_shutdown=lambda: called.append(True))
        btn.trigger()
        assert called == [True]

    def test_trigger_without_callback_does_not_raise(self) -> None:
        btn = MockShutdownButtonController()
        btn.trigger()  # must not raise

    def test_cleanup_does_not_raise(self) -> None:
        btn = MockShutdownButtonController()
        btn.cleanup()
