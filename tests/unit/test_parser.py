"""Unit tests for telemetry packet parser — T010."""


from tests.conftest import _build_raw_packet

from piedalmetry.telemetry.decrypt import decrypt
from piedalmetry.telemetry.parser import parse


class TestParser:
    def test_brake_extraction(self) -> None:
        """50% brake → raw ~127 → parsed ~49.8%."""
        brake_raw = int(50 * 2.55)  # 127
        pkt = _build_raw_packet(brake=brake_raw, speed_mps=30.0, packet_id=1)
        decrypted = decrypt(pkt)
        assert decrypted is not None
        result = parse(decrypted)
        assert result.is_valid
        assert abs(result.brake_pressure - 49.8) < 1.0  # ~50%

    def test_zero_brake(self) -> None:
        pkt = _build_raw_packet(brake=0, speed_mps=30.0, packet_id=1)
        decrypted = decrypt(pkt)
        assert decrypted is not None
        result = parse(decrypted)
        assert result.brake_pressure == 0.0

    def test_full_brake(self) -> None:
        pkt = _build_raw_packet(brake=255, speed_mps=30.0, packet_id=1)
        decrypted = decrypt(pkt)
        assert decrypted is not None
        result = parse(decrypted)
        assert result.brake_pressure == 100.0

    def test_speed_extraction(self) -> None:
        """27.78 m/s → 100 km/h."""
        speed_mps = 100.0 / 3.6
        pkt = _build_raw_packet(brake=0, speed_mps=speed_mps, packet_id=1)
        decrypted = decrypt(pkt)
        assert decrypted is not None
        result = parse(decrypted)
        assert abs(result.car_speed_kph - 100.0) < 0.1

    def test_packet_id(self) -> None:
        pkt = _build_raw_packet(brake=0, speed_mps=0.0, packet_id=42)
        decrypted = decrypt(pkt)
        assert decrypted is not None
        result = parse(decrypted)
        assert result.packet_id == 42

    def test_too_short_packet(self) -> None:
        result = parse(b"\x00" * 10)
        assert not result.is_valid
