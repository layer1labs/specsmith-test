"""CAN 2.0B frame parser (REQ-001).

Parses both 11-bit (standard) and 29-bit (extended) CAN frame identifiers
from raw byte sequences as produced by the SocketCAN kernel interface.
"""

from __future__ import annotations

from dataclasses import dataclass


_CAN_EFF_FLAG = 0x80000000  # Extended frame flag
_CAN_RTR_FLAG = 0x40000000  # Remote transmission request
_CAN_ERR_FLAG = 0x20000000  # Error frame


@dataclass
class CanFrame:
    """Parsed CAN 2.0B frame."""

    can_id: int          # 11-bit or 29-bit identifier
    is_extended: bool    # True for 29-bit EFF frames
    is_rtr: bool         # Remote transmission request
    dlc: int             # Data length code (0-8)
    data: bytes          # Frame payload (len == dlc)

    @property
    def is_standard(self) -> bool:
        return not self.is_extended


def parse_frame(raw: bytes) -> CanFrame:
    """Parse a 16-byte SocketCAN frame.

    SocketCAN frame layout (from <linux/can.h>):
      [0..3]  can_id   (little-endian uint32, flags in high bits)
      [4]     can_dlc
      [5..7]  pad
      [8..15] data

    Args:
        raw: Exactly 16 bytes from a SocketCAN read().

    Returns:
        Parsed CanFrame.

    Raises:
        ValueError: If raw is not exactly 16 bytes.
    """
    if len(raw) != 16:
        raise ValueError(f"Expected 16 bytes, got {len(raw)}")

    can_id_raw = int.from_bytes(raw[0:4], "little")
    dlc = raw[4] & 0x0F
    data = raw[8: 8 + dlc]

    is_extended = bool(can_id_raw & _CAN_EFF_FLAG)
    is_rtr = bool(can_id_raw & _CAN_RTR_FLAG)

    if is_extended:
        can_id = can_id_raw & 0x1FFFFFFF
    else:
        can_id = (can_id_raw & 0x7FF00000) >> 20

    return CanFrame(
        can_id=can_id,
        is_extended=is_extended,
        is_rtr=is_rtr,
        dlc=dlc,
        data=bytes(data),
    )
