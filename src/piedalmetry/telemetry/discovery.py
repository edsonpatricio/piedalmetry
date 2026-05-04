"""PlayStation broadcast discovery via GT7 heartbeat protocol.

References:
  - GT7 protocol: heartbeat 'A' on port 33739, response on 33740
  - Cross-subnet note: broadcast discovery only works on same subnet.
    For cross-subnet setups, use directed discovery.
"""

from __future__ import annotations

import logging
import socket
import time

_log = logging.getLogger("piedalmetry.telemetry.discovery")

SEND_PORT = 33739
RECV_PORT = 33740
HEARTBEAT = b"A"


def discover_playstation(
    timeout: float = 10.0,
    target_ip: str = "",
    sock: socket.socket | None = None,
) -> str | None:
    """Discover a PlayStation running GT7 on the network.

    If target_ip is provided, sends a directed heartbeat to verify
    reachability. Otherwise broadcasts on the local subnet.

    If sock is provided the function reuses it (no bind/close). This is
    required when called from inside an already-listening loop so the
    caller's bound port is not contested.

    Returns:
        The PlayStation IP address, or None if not found.
    """
    _log.info(
        "discovery started timeout_s=%.1f directed=%s",
        timeout,
        bool(target_ip),
    )

    _own_socket = sock is None
    if _own_socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", RECV_PORT))

    # Enable broadcast on any socket (new or reused) when we need it.
    # The listener socket is created without SO_BROADCAST; setting it here
    # allows re-discovery broadcasts without recreating the socket.
    if not target_ip:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    sock.settimeout(timeout)

    try:
        if target_ip:
            sock.sendto(HEARTBEAT, (target_ip, SEND_PORT))
        else:
            sock.sendto(HEARTBEAT, ("255.255.255.255", SEND_PORT))

        data, addr = sock.recvfrom(4096)
        if len(data) > 0:
            _log.info("discovery success ps_ip=%s", addr[0])
            return addr[0]
        return None

    except TimeoutError:
        _log.error("discovery timeout after %.1fs — no PlayStation found", timeout)
        return None
    except OSError as exc:
        _log.warning("discovery error: %s", exc)
        return None
    finally:
        if _own_socket:
            sock.close()


class DiscoveryManager:
    """Manages PlayStation discovery with retry and re-discovery logic.

    State machine:
      CheckConfig → Connected (if IP responds)
      CheckConfig → Discovering (if IP empty)
      Connected → FailCount(1-3) → Discovering (after 3 failures)
    """

    def __init__(
        self,
        initial_ip: str = "",
        retry_interval: float = 3.0,
        discovery_timeout: float = 10.0,
    ) -> None:
        self._ip = initial_ip
        self._last_ip = initial_ip  # preserved when _ip is cleared after failures
        self._retry_interval = retry_interval
        self._discovery_timeout = discovery_timeout
        self._fail_count = 0
        self._last_attempt: float = 0.0

    @property
    def target_ip(self) -> str:
        return self._ip

    @property
    def fail_count(self) -> int:
        return self._fail_count

    def record_success(self) -> None:
        """Record a successful connection."""
        self._fail_count = 0

    def record_failure(self) -> bool:
        """Record a connection failure.

        Returns:
            True if re-discovery should be triggered (3 failures reached).
        """
        now = time.monotonic()
        if now - self._last_attempt < self._retry_interval:
            return False

        self._last_attempt = now
        self._fail_count += 1

        _log.warning(
            "discovery failure fail_count=%d ps_ip=%s",
            self._fail_count,
            self._ip,
        )

        if self._fail_count >= 3:
            _log.warning(
                "3 consecutive failures for ps_ip=%s — clearing IP, re-discovering",
                self._ip,
            )
            self._last_ip = self._ip  # save for directed retry before broadcast
            self._ip = ""
            self._fail_count = 0
            return True
        return False

    def retry_last_ip(self, sock: socket.socket | None = None) -> str | None:
        """Try a directed reconnect to the last known IP before broadcasting.

        Called after the IP is cleared by consecutive failures. If the
        PlayStation responds, restores the IP and returns it. Does not
        trigger the on_ip_discovered callback — the IP has not changed.

        Returns:
            The IP if reachable, None if not.
        """
        if not self._last_ip:
            return None
        _log.info(
            "trying last known ps_ip=%s before broadcast", self._last_ip
        )
        ip = discover_playstation(
            timeout=self._discovery_timeout,
            target_ip=self._last_ip,
            sock=sock,
        )
        if ip:
            self._ip = ip
            self._fail_count = 0
        return ip

    def run_discovery(self, sock: socket.socket | None = None) -> str | None:
        """Run broadcast discovery and update internal IP on success.

        Args:
            sock: Optional existing socket to reuse. Pass the listener's
                socket to avoid contesting the already-bound port 33740.
        """
        ip = discover_playstation(
            timeout=self._discovery_timeout,
            target_ip=self._ip,
            sock=sock,
        )
        if ip:
            self._ip = ip
            self._fail_count = 0
            _log.info("discovery manager: connected ps_ip=%s", ip)
        else:
            _log.warning("discovery manager: no PlayStation found")
        return ip
