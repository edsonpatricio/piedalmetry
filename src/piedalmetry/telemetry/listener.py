"""UDP telemetry listener — receives and decrypts GT7 packets.

Runs in a dedicated thread for multi-core utilisation. If no IP is
configured, runs discovery automatically. Tracks consecutive failures
and re-discovers if the console becomes unreachable.

References:
  - Bornhall/gt7telemetry: heartbeat every ~100 packets
  - GT7 protocol: send port 33739, receive port 33740
"""

from __future__ import annotations

import contextlib
import logging
import socket
import threading
import time
from collections.abc import Callable

from piedalmetry.telemetry.decrypt import decrypt
from piedalmetry.telemetry.discovery import DiscoveryManager
from piedalmetry.telemetry.parser import TelemetryPacket, parse

_log = logging.getLogger("piedalmetry.telemetry.listener")

SEND_PORT = 33739
RECV_PORT = 33740
HEARTBEAT = b"A"
_HEARTBEAT_INTERVAL = 100  # packets between heartbeats
_TIMEOUT_SECONDS = 2.0
_REDISCOVERY_WAIT = 5.0   # seconds between failed discovery attempts


class TelemetryListener:
    """Listen for GT7 telemetry via UDP in a background thread.

    If ps_ip is empty, performs automatic broadcast discovery first.
    Tracks consecutive packet-receive failures; after 3 failures
    (≥3s apart) clears the stored IP and re-discovers using the
    already-bound socket so port 33740 is never contested.

    Args:
        ps_ip: PlayStation IP address (empty string = auto-discover).
        on_packet: Callback invoked with each parsed TelemetryPacket.
        on_ip_discovered: Optional callback when IP is discovered/updated.
        on_connected: Optional callback fired when the first valid packet
            arrives after a disconnected state.
        on_disconnected: Optional callback fired when 3 consecutive
            failures trigger re-discovery.
        discovery_timeout: Seconds to wait for a single discovery attempt.
    """

    def __init__(
        self,
        ps_ip: str,
        on_packet: Callable[[TelemetryPacket], None],
        on_ip_discovered: Callable[[str], None] | None = None,
        on_connected: Callable[[], None] | None = None,
        on_disconnected: Callable[[], None] | None = None,
        discovery_timeout: float = 10.0,
    ) -> None:
        self._discovery = DiscoveryManager(
            initial_ip=ps_ip,
            retry_interval=3.0,
            discovery_timeout=discovery_timeout,
        )
        self._on_packet = on_packet
        self._on_ip_discovered = on_ip_discovered
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_pkt_id = 0
        self._pkt_count = 0
        self._connected = False

    @property
    def current_ip(self) -> str:
        return self._discovery.target_ip

    def start(self) -> None:
        """Start the listener thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="telemetry-listener",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the listener thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def _ensure_ip(self) -> bool:
        """Ensure we have a target IP, running discovery if needed.

        Called once before the socket is bound, so it creates its own
        temporary socket for the initial discovery attempt.

        Returns:
            True if an IP is available, False if discovery failed.
        """
        if self._discovery.target_ip:
            return True

        _log.info("No PlayStation IP configured — starting discovery")
        ip = self._discovery.run_discovery()
        if ip:
            if self._on_ip_discovered:
                self._on_ip_discovered(ip)
            return True

        _log.error("Discovery failed — no PlayStation found")
        return False

    def _listen_loop(self) -> None:
        """Main receive loop — runs in dedicated thread."""
        if not self._ensure_ip():
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", RECV_PORT))
        sock.settimeout(_TIMEOUT_SECONDS)

        self._send_heartbeat(sock)

        while self._running:
            if not self._discovery.target_ip:
                # Step 1: try directed reconnect to last known IP (fast path,
                # avoids broadcast and does not trigger on_ip_discovered).
                ip = self._discovery.retry_last_ip(sock=sock)
                if ip:
                    _log.info(
                        "Reconnected to last known ps_ip=%s", ip
                    )
                    sock.settimeout(_TIMEOUT_SECONDS)
                    self._send_heartbeat(sock)
                    continue

                # Step 2: last IP unreachable — full broadcast discovery.
                _log.info("Last IP unreachable — running broadcast re-discovery")
                ip = self._discovery.run_discovery(sock=sock)
                if ip:
                    if self._on_ip_discovered:
                        self._on_ip_discovered(ip)
                    sock.settimeout(_TIMEOUT_SECONDS)
                    self._send_heartbeat(sock)
                else:
                    # Discovery failed; wait before retrying.
                    time.sleep(_REDISCOVERY_WAIT)
                continue

            try:
                data, _addr = sock.recvfrom(4096)
                self._pkt_count += 1
                self._discovery.record_success()

                decrypted = decrypt(data)
                if decrypted is None:
                    continue

                pkt = parse(decrypted)
                if not pkt.is_valid:
                    continue

                if pkt.packet_id > self._last_pkt_id:
                    self._last_pkt_id = pkt.packet_id
                    if not self._connected:
                        self._connected = True
                        if self._on_connected:
                            self._on_connected()
                    self._on_packet(pkt)

                if self._pkt_count >= _HEARTBEAT_INTERVAL:
                    self._send_heartbeat(sock)
                    self._pkt_count = 0

            except TimeoutError:
                self._send_heartbeat(sock)
                should_rediscover = self._discovery.record_failure()
                if should_rediscover:
                    _log.warning(
                        "3 consecutive failures — re-discovering PlayStation"
                    )
                    if self._connected:
                        self._connected = False
                        if self._on_disconnected:
                            self._on_disconnected()
                    # IP is now cleared; next loop iteration runs discovery.

            except OSError:
                if self._running:
                    time.sleep(0.5)

        sock.close()

    def _send_heartbeat(self, sock: socket.socket) -> None:
        """Send GT7 heartbeat to maintain telemetry stream."""
        ip = self._discovery.target_ip
        if not ip:
            return
        with contextlib.suppress(OSError):
            sock.sendto(HEARTBEAT, (ip, SEND_PORT))
