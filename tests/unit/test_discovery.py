"""Unit tests for PlayStation discovery state machine.

Tests DiscoveryManager logic without real network I/O.
"""

from __future__ import annotations

from unittest.mock import patch

from pidalmetry.telemetry.discovery import DiscoveryManager


class TestDiscoveryManagerStateTransitions:
    """Test the DiscoveryManager state machine logic."""

    def test_initial_state_with_ip(self) -> None:
        mgr = DiscoveryManager(initial_ip="192.168.1.50")
        assert mgr.target_ip == "192.168.1.50"
        assert mgr.fail_count == 0

    def test_initial_state_without_ip(self) -> None:
        mgr = DiscoveryManager(initial_ip="")
        assert mgr.target_ip == ""
        assert mgr.fail_count == 0

    def test_record_success_resets_fail_count(self) -> None:
        mgr = DiscoveryManager(initial_ip="192.168.1.50")
        # Simulate one failure — monotonic must return > retry_interval(3.0)
        # since _last_attempt starts at 0.0
        with patch("pidalmetry.telemetry.discovery.time") as mock_time:
            mock_time.monotonic.return_value = 3.5
            mgr.record_failure()
        assert mgr.fail_count == 1

        mgr.record_success()
        assert mgr.fail_count == 0

    def test_three_consecutive_failures_trigger_rediscovery(self) -> None:
        mgr = DiscoveryManager(
            initial_ip="192.168.1.50",
            retry_interval=3.0,
        )
        # Each call returns a monotonic value > retry_interval ahead of previous
        # _last_attempt starts at 0.0, so first must be > 3.0
        timestamps = [3.5, 7.0, 10.5]
        idx = 0

        def monotonic_side_effect() -> float:
            nonlocal idx
            val = timestamps[idx]
            idx += 1
            return val

        with patch("pidalmetry.telemetry.discovery.time") as mock_time:
            mock_time.monotonic.side_effect = monotonic_side_effect

            rediscover1 = mgr.record_failure()
            assert not rediscover1
            assert mgr.fail_count == 1

            rediscover2 = mgr.record_failure()
            assert not rediscover2
            assert mgr.fail_count == 2

            rediscover3 = mgr.record_failure()
            assert rediscover3, "Third failure should trigger re-discovery"
            assert mgr.fail_count == 0
            assert mgr.target_ip == "", "IP should be cleared after 3 failures"

    def test_failure_ignored_if_too_soon(self) -> None:
        """Second failure within retry_interval of the first is ignored."""
        mgr = DiscoveryManager(
            initial_ip="192.168.1.50",
            retry_interval=3.0,
        )
        with patch("pidalmetry.telemetry.discovery.time") as mock_time:
            # First call: 3.5s after t=0.0 (last_attempt) → accepted
            # Second call: 5.0s - only 1.5s after 3.5 → too soon → ignored
            mock_time.monotonic.side_effect = [3.5, 5.0]
            result1 = mgr.record_failure()
            assert not result1
            assert mgr.fail_count == 1

            result2 = mgr.record_failure()
            assert not result2
            assert mgr.fail_count == 1, "Should not increment — too soon"

    def test_run_discovery_updates_ip_on_success(self) -> None:
        mgr = DiscoveryManager(initial_ip="")

        with patch(
            "pidalmetry.telemetry.discovery.discover_playstation",
            return_value="192.168.1.50",
        ):
            ip = mgr.run_discovery()

        assert ip == "192.168.1.50"
        assert mgr.target_ip == "192.168.1.50"
        assert mgr.fail_count == 0

    def test_run_discovery_returns_none_on_timeout(self) -> None:
        mgr = DiscoveryManager(initial_ip="")

        with patch(
            "pidalmetry.telemetry.discovery.discover_playstation",
            return_value=None,
        ):
            ip = mgr.run_discovery()

        assert ip is None
        assert mgr.target_ip == ""


class TestDiscoverPlaystationFunction:
    """Test discover_playstation with mocked sockets."""

    def test_timeout_returns_none(self) -> None:

        from pidalmetry.telemetry.discovery import discover_playstation

        with patch("pidalmetry.telemetry.discovery.socket.socket") as mock_sock_cls:
            mock_sock = mock_sock_cls.return_value.__enter__.return_value
            mock_sock_cls.return_value = mock_sock
            mock_sock.recvfrom.side_effect = TimeoutError()
            mock_sock.bind.return_value = None
            mock_sock.sendto.return_value = None

            result = discover_playstation(timeout=0.1)

        assert result is None

    def test_successful_response_returns_ip(self) -> None:
        from pidalmetry.telemetry.discovery import discover_playstation

        with patch("pidalmetry.telemetry.discovery.socket.socket") as mock_sock_cls:
            mock_sock = mock_sock_cls.return_value
            mock_sock.recvfrom.return_value = (b"data", ("192.168.1.50", 33740))
            mock_sock.bind.return_value = None
            mock_sock.sendto.return_value = None

            result = discover_playstation(timeout=1.0)

        assert result == "192.168.1.50"
