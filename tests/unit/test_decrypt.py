"""Unit tests for Salsa20 decryption — T009."""


from piedalmetry.telemetry.decrypt import decrypt


class TestDecrypt:
    def test_valid_packet_decrypts(self, encrypted_packet: bytes) -> None:
        result = decrypt(encrypted_packet)
        assert result is not None
        assert len(result) > 0

    def test_magic_number_valid(self, encrypted_packet: bytes) -> None:
        import struct
        result = decrypt(encrypted_packet)
        assert result is not None
        magic = struct.unpack_from("<I", result, 0x00)[0]
        assert magic == 0x47375330

    def test_invalid_magic_returns_none(self) -> None:
        # Send garbage data — should not match magic after "decryption"
        result = decrypt(b"\x00" * 296)
        assert result is None

    def test_too_short_packet_returns_none(self) -> None:
        result = decrypt(b"\x00" * 10)
        assert result is None

    def test_iv_derivation_uses_oiv_xor(self, encrypted_packet: bytes) -> None:
        """Verify the OIV at 0x40 is used correctly in decryption."""
        # If decryption succeeds and magic validates, IV was derived correctly
        result = decrypt(encrypted_packet)
        assert result is not None
