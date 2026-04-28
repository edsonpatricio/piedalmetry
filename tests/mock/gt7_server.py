"""Mock GT7 telemetry UDP server for integration tests and development.

Replays encrypted GT7 telemetry packets (fixed or sweep mode) in response
to GT7 heartbeats. Enables full pipeline testing without a real PS5.

References:
  - Bornhall/gt7telemetry: Salsa20 encryption, heartbeat on port 33739
  - snipem/gt7dashboard: test data patterns

Usage (in tests):
    server = MockGT7Server(brake_pct=50.0, speed_kph=100.0)
    with server.running():
        # test code that connects to 127.0.0.1:33740

Usage (from command line):
    uv run python tests/mock/gt7_server.py --brake 50 --duration 10
    uv run python tests/mock/gt7_server.py --sweep --duration 10
"""

from __future__ import annotations

import argparse
import math
import socket
import struct
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager

from Crypto.Cipher import Salsa20

_KEY = b"Simulator Interface Packet GT7 ver 0.0"[:32]
_MAGIC = 0x47375330
HEARTBEAT_PORT = 33739
TELEMETRY_PORT = 33740
PACKET_RATE_HZ = 60


def _build_packet(
    brake_pct: float,
    speed_kph: float = 100.0,
    packet_id: int = 1,
) -> bytes:
    """Build an encrypted GT7 telemetry packet with the given brake value."""
    buf = bytearray(296)

    struct.pack_into("<I", buf, 0x00, _MAGIC)
    struct.pack_into("<f", buf, 0x4C, speed_kph / 3.6)
    struct.pack_into("<i", buf, 0x70, packet_id)

    brake_raw = min(255, max(0, round(brake_pct * 2.55)))
    struct.pack_into("B", buf, 0x92, brake_raw)

    oiv = packet_id & 0xFFFFFFFF
    struct.pack_into("<I", buf, 0x40, oiv)

    iv2 = oiv ^ 0xDEADBEAF
    nonce = struct.pack("<I", iv2) + struct.pack("<I", oiv)
    cipher = Salsa20.new(key=_KEY, nonce=nonce)
    encrypted = bytearray(cipher.encrypt(bytes(buf)))
    struct.pack_into("<I", encrypted, 0x40, oiv)

    return bytes(encrypted)


class MockGT7Server:
    """Mock GT7 telemetry server — sends encrypted UDP packets.

    Args:
        brake_pct: Fixed brake pressure (0–100). Ignored if sweep=True.
        speed_kph: Simulated car speed in km/h.
        sweep: If True, ramp brake 0→100→0 on a sine wave.
        sweep_period: Duration of one full sweep cycle in seconds.
        listen_host: Host to bind the heartbeat listener.
        listen_port: Port to listen for heartbeats on.
        send_port: Port to send telemetry packets to.
    """

    def __init__(
        self,
        brake_pct: float = 50.0,
        speed_kph: float = 100.0,
        sweep: bool = False,
        sweep_period: float = 4.0,
        listen_host: str = "127.0.0.1",
        listen_port: int = HEARTBEAT_PORT,
        send_port: int = TELEMETRY_PORT,
    ) -> None:
        self._brake_pct = brake_pct
        self._speed_kph = speed_kph
        self._sweep = sweep
        self._sweep_period = sweep_period
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._send_port = send_port

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._client_addr: tuple[str, int] | None = None
        self._packet_count = 0

    def start(self) -> None:
        """Start the mock server in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="mock-gt7-server",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the mock server."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    @contextmanager
    def running(self) -> Generator[MockGT7Server, None, None]:
        """Context manager: start server, yield self, then stop."""
        self.start()
        try:
            yield self
        finally:
            self.stop()

    @property
    def packets_sent(self) -> int:
        return self._packet_count

    def _run(self) -> None:
        """Server loop: listen for heartbeats, send telemetry on reply."""
        hb_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        hb_sock.settimeout(0.1)
        try:
            hb_sock.bind((self._listen_host, self._listen_port))
        except OSError:
            # Port may be in use in CI — try any available port
            hb_sock.bind(("127.0.0.1", 0))

        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        start_time = time.monotonic()
        packet_id = 1

        try:
            while not self._stop_event.is_set():
                # Check for heartbeat
                try:
                    _data, addr = hb_sock.recvfrom(16)
                    self._client_addr = addr
                except TimeoutError:
                    pass

                if self._client_addr is None:
                    continue

                # Compute brake for this packet
                elapsed = time.monotonic() - start_time
                if self._sweep:
                    brake = 50.0 + 50.0 * math.sin(
                        2 * math.pi * elapsed / self._sweep_period - math.pi / 2
                    )
                    brake = max(0.0, min(100.0, brake))
                else:
                    brake = self._brake_pct

                pkt = _build_packet(brake, self._speed_kph, packet_id)
                dest = (self._client_addr[0], self._send_port)
                send_sock.sendto(pkt, dest)
                self._packet_count += 1
                packet_id += 1

                time.sleep(1.0 / PACKET_RATE_HZ)
        finally:
            hb_sock.close()
            send_sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock GT7 telemetry server")
    parser.add_argument(
        "--brake", type=float, default=50.0, help="Fixed brake %% (0-100)"
    )
    parser.add_argument("--sweep", action="store_true", help="Sweep brake 0→100→0")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    parser.add_argument("--speed", type=float, default=100.0, help="Car speed in km/h")
    args = parser.parse_args()

    server = MockGT7Server(
        brake_pct=args.brake,
        speed_kph=args.speed,
        sweep=args.sweep,
    )
    server.start()
    print(f"Mock GT7 server started (brake={args.brake}%, sweep={args.sweep})")
    print(f"Listening for heartbeats on port {HEARTBEAT_PORT}")
    print(f"Sending telemetry to port {TELEMETRY_PORT}")
    print(f"Running for {args.duration}s — Ctrl+C to stop")

    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        print(f"Sent {server.packets_sent} packets")


if __name__ == "__main__":
    main()
