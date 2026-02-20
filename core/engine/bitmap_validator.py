from __future__ import annotations

from dataclasses import dataclass

from core.engine.constants import ChunkA, ChunkB, ChunkC, ChunkD


@dataclass(frozen=True)
class ValidBitmapResult:
    bits: int
    bits_a: int
    bits_b: int
    bits_c: int
    bits_d: int


class InvalidBitmapError(ValueError):
    def __init__(self, *, bits: int, reason: str, message: str):
        self.bits = bits
        self.reason = reason
        super().__init__(message)


_ALLOWED_A = {int(value) for value in ChunkA}
_ALLOWED_B = {int(value) for value in ChunkB}
_ALLOWED_C = {int(value) for value in ChunkC}
_ALLOWED_D = {int(value) for value in ChunkD}


def validate_bitmap(bits: int) -> ValidBitmapResult:
    if not isinstance(bits, int):
        raise InvalidBitmapError(bits=-1, reason="INVALID_TYPE", message="bitmap bits must be int")
    if bits < 0 or bits > 0xFFFF:
        raise InvalidBitmapError(bits=bits, reason="INVALID_RANGE", message="bitmap bits must be 0..65535")

    bits_a = (bits >> 12) & 0xF
    bits_b = (bits >> 8) & 0xF
    bits_c = (bits >> 4) & 0xF
    bits_d = bits & 0xF

    if bits_a not in _ALLOWED_A:
        raise InvalidBitmapError(bits=bits, reason="INVALID_CHUNK_A", message=f"invalid chunk A value: 0x{bits_a:X}")
    if bits_b not in _ALLOWED_B:
        raise InvalidBitmapError(bits=bits, reason="INVALID_CHUNK_B", message=f"invalid chunk B value: 0x{bits_b:X}")
    if bits_c not in _ALLOWED_C:
        raise InvalidBitmapError(bits=bits, reason="INVALID_CHUNK_C", message=f"invalid chunk C value: 0x{bits_c:X}")
    if bits_d not in _ALLOWED_D:
        raise InvalidBitmapError(bits=bits, reason="INVALID_CHUNK_D", message=f"invalid chunk D value: 0x{bits_d:X}")

    return ValidBitmapResult(bits=bits, bits_a=bits_a, bits_b=bits_b, bits_c=bits_c, bits_d=bits_d)
