"""Telemetry packet parser — struct unpacking of decrypted GT7 data.

References:
  - Bornhall/gt7telemetry: offset 0x92 (brake), 0x4C (speed), 0x70 (pktid)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelemetryPacket:
    """Parsed telemetry frame from a decrypted GT7 packet."""

    packet_id: int
    brake_pressure: float   # 0.0–100.0 %
    car_speed_kph: float    # km/h
    throttle: float         # 0.0–100.0 %
    is_valid: bool


def parse(data: bytes) -> TelemetryPacket:
    """Parse a decrypted GT7 packet into a TelemetryPacket.

    Args:
        data: Decrypted bytes (>= 0x93 bytes long).

    Returns:
        TelemetryPacket with extracted fields.
    """
    if len(data) < 0x93:
        return TelemetryPacket(
            packet_id=0,
            brake_pressure=0.0,
            car_speed_kph=0.0,
            throttle=0.0,
            is_valid=False,
        )

    # Magic validation
    magic = struct.unpack_from("<I", data, 0x00)[0]
    is_valid = magic == 0x47375330

    # Packet ID at 0x70 (int32)
    packet_id = struct.unpack_from("<i", data, 0x70)[0]

    # Car speed at 0x4C (float, m/s → km/h)
    speed_mps = struct.unpack_from("<f", data, 0x4C)[0]
    car_speed_kph = max(0.0, speed_mps * 3.6)

    # Throttle at 0x91 (uint8, 0-255 → 0-100%)
    throttle_raw = struct.unpack_from("B", data, 0x91)[0]
    throttle = min(100.0, throttle_raw / 2.55)

    # Brake at 0x92 (uint8, 0-255 → 0-100%)
    brake_raw = struct.unpack_from("B", data, 0x92)[0]
    brake_pressure = min(100.0, brake_raw / 2.55)

    return TelemetryPacket(
        packet_id=packet_id,
        brake_pressure=brake_pressure,
        car_speed_kph=car_speed_kph,
        throttle=throttle,
        is_valid=is_valid,
    )
