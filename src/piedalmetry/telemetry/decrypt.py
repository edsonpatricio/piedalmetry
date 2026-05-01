"""Salsa20 decryption wrapper for GT7 telemetry packets.

References:
  - Bornhall/gt7telemetry: key derivation, IV XOR with 0xDEADBEAF
  - GT7 protocol: magic number 0x47375330
"""

from __future__ import annotations

import struct

from Crypto.Cipher import Salsa20

# GT7 Salsa20 key — first 32 bytes of the protocol string
_KEY = b"Simulator Interface Packet GT7 ver 0.0"[:32]

# Valid decrypted packet starts with this magic number
_MAGIC = 0x47375330


def decrypt(raw: bytes) -> bytes | None:
    """Decrypt a raw GT7 telemetry packet.

    Args:
        raw: The encrypted UDP payload (typically ~296 bytes).

    Returns:
        Decrypted bytes if magic number validates, else None.
    """
    if len(raw) < 0x44:
        return None

    # Extract OIV at offset 0x40 (4 bytes, little-endian)
    oiv = int.from_bytes(raw[0x40:0x44], byteorder="little")
    iv2 = oiv ^ 0xDEADBEAF

    # Build 8-byte nonce: iv2 (LE) + oiv (LE)
    nonce = struct.pack("<I", iv2) + struct.pack("<I", oiv)

    cipher = Salsa20.new(key=_KEY, nonce=nonce)
    decrypted = cipher.decrypt(raw)

    # Validate magic number at offset 0x00
    magic = int.from_bytes(decrypted[0:4], byteorder="little")
    if magic != _MAGIC:
        return None

    return decrypted
