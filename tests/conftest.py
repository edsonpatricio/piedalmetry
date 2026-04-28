"""Shared test fixtures for Pidalmetry test suite.

References:
  - Bornhall/gt7telemetry: Salsa20 key, IV derivation, packet offsets
  - snipem/gt7dashboard: extended telemetry field documentation
"""

from __future__ import annotations

import struct
from typing import Any

import pytest
from Crypto.Cipher import Salsa20

# ---------------------------------------------------------------------------
# GT7 protocol constants (from gt7telemetry reference)
# ---------------------------------------------------------------------------
GT7_SALSA_KEY = b"Simulator Interface Packet GT7 ver 0.0"[:32]
GT7_MAGIC = 0x47375330
SEND_PORT = 33739
RECV_PORT = 33740


def _build_raw_packet(
    brake: int = 0,
    speed_mps: float = 0.0,
    throttle: int = 0,
    packet_id: int = 1,
) -> bytes:
    """Build an *encrypted* GT7-style telemetry packet.

    Only the fields we care about are populated; the rest is zeroed.
    The packet is encrypted with the standard GT7 Salsa20 parameters.
    """
    # Start with a 296-byte zeroed buffer
    buf = bytearray(296)

    # Magic at 0x00
    struct.pack_into("<I", buf, 0x00, GT7_MAGIC)
    # Speed (m/s float) at 0x4C
    struct.pack_into("<f", buf, 0x4C, speed_mps)
    # Packet ID at 0x70
    struct.pack_into("<i", buf, 0x70, packet_id)
    # Throttle at 0x91
    struct.pack_into("B", buf, 0x91, throttle)
    # Brake at 0x92
    struct.pack_into("B", buf, 0x92, brake)

    # OIV at 0x40 — use a fixed nonce for deterministic tests
    oiv = 0x12345678
    struct.pack_into("<I", buf, 0x40, oiv)

    # Encrypt
    iv2 = oiv ^ 0xDEADBEAF
    iv_bytes = struct.pack("<I", iv2) + struct.pack("<I", oiv)
    cipher = Salsa20.new(key=GT7_SALSA_KEY, nonce=iv_bytes)
    encrypted = bytearray(cipher.encrypt(bytes(buf)))

    # Patch OIV back into the encrypted output at 0x40-0x43.
    # In the real GT7 protocol, the OIV is readable from the raw
    # (encrypted) packet — the console writes it after encryption.
    struct.pack_into("<I", encrypted, 0x40, oiv)

    return bytes(encrypted)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_config() -> dict[str, Any]:
    """Return a valid in-memory config dict matching config.example.toml."""
    return {
        "general": {
            "mock_mode": True,
            "log_level": "DEBUG",
            "log_target": "stdout",
        },
        "motor": {
            "gpio_ena": 18,
            "gpio_in1": 23,
            "gpio_in2": 24,
            "pwm_frequency": 1000,
            "min_brake_pressure": 30,
            "min_motor_strength": 50,
            "min_car_speed": 5,
        },
        "anti_fluctuation": {
            "dead_zone": 2.0,
            "ema_alpha": 0.3,
        },
        "playstation": {
            "ip": "192.168.1.50",
            "label": "PS5",
        },
    }


@pytest.fixture()
def encrypted_packet() -> bytes:
    """Return an encrypted GT7 packet with 50% brake, 100 km/h."""
    brake_raw = int(50 * 2.55)  # ~127
    speed_mps = 100.0 / 3.6     # ~27.78 m/s
    return _build_raw_packet(brake=brake_raw, speed_mps=speed_mps, packet_id=1)


@pytest.fixture()
def encrypted_packet_zero_brake() -> bytes:
    """Return an encrypted GT7 packet with 0% brake, 100 km/h."""
    speed_mps = 100.0 / 3.6
    return _build_raw_packet(brake=0, speed_mps=speed_mps, packet_id=2)


@pytest.fixture()
def build_packet():
    """Return the packet builder for custom test scenarios."""
    return _build_raw_packet
