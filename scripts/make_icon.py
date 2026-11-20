#!/usr/bin/env python3
"""Write the Dues Banshee app icon: a 512x512 opaque RGB PNG (stdlib only).

Usage: python3 scripts/make_icon.py [output_path]

The default output is assets/icon.png in the repository root, whatever the
current working directory is. The output is deterministic: the same bytes on
every run.
"""

import struct
import sys
import zlib
from pathlib import Path

SIZE = 512
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "assets" / "icon.png"

BACKGROUND = (12, 12, 18)
STONE = (122, 126, 136)
STONE_CROSS = (74, 77, 86)
CANDLE = (222, 214, 190)
FLAME = (255, 176, 32)

# Tombstone: a rectangle with a half disc on top.
STONE_LEFT, STONE_RIGHT = 146, 366
STONE_TOP, STONE_BOTTOM = 230, 440
STONE_CX = (STONE_LEFT + STONE_RIGHT) // 2
STONE_R = (STONE_RIGHT - STONE_LEFT) // 2

# Candle with an amber flame, standing to the right of the tombstone.
CANDLE_LEFT, CANDLE_RIGHT = 396, 424
CANDLE_TOP, CANDLE_BOTTOM = 380, 440
FLAME_CX, FLAME_CY, FLAME_RX, FLAME_RY = 410, 346, 13, 26


def pixel(x, y):
    """Return the (r, g, b) colour at integer pixel (x, y)."""
    # Flame (ellipse, integer arithmetic only).
    dx, dy = x - FLAME_CX, y - FLAME_CY
    if (dx * dx) * (FLAME_RY * FLAME_RY) + (dy * dy) * (FLAME_RX * FLAME_RX) <= (
        FLAME_RX * FLAME_RX * FLAME_RY * FLAME_RY
    ):
        return FLAME
    if CANDLE_LEFT <= x < CANDLE_RIGHT and CANDLE_TOP <= y < CANDLE_BOTTOM:
        return CANDLE
    # Cross carved into the tombstone.
    if STONE_TOP - 30 <= y < STONE_TOP + 110:
        if STONE_CX - 8 <= x < STONE_CX + 8:
            return STONE_CROSS
    if STONE_TOP + 20 <= y < STONE_TOP + 36 and STONE_CX - 40 <= x < STONE_CX + 40:
        return STONE_CROSS
    # Tombstone body.
    if STONE_LEFT <= x < STONE_RIGHT and STONE_TOP <= y < STONE_BOTTOM:
        return STONE
    # Half-disc top.
    if y < STONE_TOP:
        dx, dy = x - STONE_CX, y - STONE_TOP
        if dx * dx + dy * dy <= STONE_R * STONE_R:
            return STONE_CROSS if (
                STONE_TOP - 30 <= y and STONE_CX - 8 <= x < STONE_CX + 8
            ) else STONE
    return BACKGROUND


def chunk(tag, data):
    body = tag + data
    return (
        struct.pack(">I", len(data))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def build_png():
    rows = bytearray()
    for y in range(SIZE):
        rows.append(0)  # filter type 0 (None)
        for x in range(SIZE):
            rows.extend(pixel(x, y))
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_png())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
