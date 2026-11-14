"""Generate FINN's PWA icons as PNG files, using only the Python standard library.

Run from the repo root:  py scripts/make_icons.py
Writes frontend/public/icons/: icon-192.png, icon-512.png, maskable-512.png, apple-touch-icon.png
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "icons"

INK = (17, 24, 39)
WHITE = (255, 255, 255)
UP_GREEN = (74, 222, 128)

# Shapes in a unit square. Later shapes paint over earlier ones.
RECT, TRI = "rect", "tri"
SHAPES = [
    (RECT, (0.24, 0.24, 0.36, 0.78), WHITE),  # F: stem
    (RECT, (0.24, 0.24, 0.56, 0.36), WHITE),  # F: top bar
    (RECT, (0.24, 0.46, 0.50, 0.57), WHITE),  # F: middle bar
    (TRI, ((0.68, 0.22), (0.60, 0.36), (0.76, 0.36)), UP_GREEN),  # an "up" marker
]


def _in_tri(p, a, b, c) -> bool:
    def side(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1, d2, d3 = side(p, a, b), side(p, b, c), side(p, c, a)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def _colour_at(u: float, v: float):
    colour = INK
    for kind, geom, fill in SHAPES:
        if kind == RECT:
            x0, y0, x1, y1 = geom
            if x0 <= u <= x1 and y0 <= v <= y1:
                colour = fill
        elif _in_tri((u, v), *geom):
            colour = fill
    return colour


def render(size: int, scale: float = 1.0, samples: int = 3) -> bytes:
    """Return PNG bytes. `scale` shrinks the artwork towards the centre (for the maskable safe zone)."""
    rows = []
    for py in range(size):
        row = bytearray([0])  # PNG filter type 0 (none)
        for px in range(size):
            r = g = b = 0
            for sy in range(samples):
                for sx in range(samples):
                    x = (px + (sx + 0.5) / samples) / size
                    y = (py + (sy + 0.5) / samples) / size
                    cr, cg, cb = _colour_at(0.5 + (x - 0.5) / scale, 0.5 + (y - 0.5) / scale)
                    r, g, b = r + cr, g + cg, b + cb
            n = samples * samples
            row += bytes((r // n, g // n, b // n))
        rows.append(bytes(row))
    return _png(size, size, b"".join(rows))


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "icon-192.png": (192, 1.0),
        "icon-512.png": (512, 1.0),
        "maskable-512.png": (512, 0.8),  # artwork inside the 80% safe zone
        "apple-touch-icon.png": (180, 1.0),
    }
    for name, (size, scale) in files.items():
        (OUT / name).write_bytes(render(size, scale))
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
