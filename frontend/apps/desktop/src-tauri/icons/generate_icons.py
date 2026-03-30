#!/usr/bin/env python3
"""Generate Gilbertus Albans icon files using only stdlib (struct + zlib)."""

import struct
import zlib
import os

# Colors
BG = (0x1a, 0x27, 0x44)  # dark navy
FG = (0xc9, 0xa8, 0x4c)  # gold

# Letter G bitmap (16x16 grid, scaled up for each size)
G_BITMAP = [
    "..XXXXXXXXXXXX..",
    ".XXXXXXXXXXXXXXX",
    "XXXX........XXXX",
    "XXX..........XXX",
    "XXX..........XXX",
    "XXX..............",
    "XXX..............",
    "XXX..............",
    "XXX.......XXXXXXX",
    "XXX.......XXXXXXX",
    "XXX..........XXX",
    "XXX..........XXX",
    "XXX..........XXX",
    "XXXX........XXXX",
    ".XXXXXXXXXXXXXXX",
    "..XXXXXXXXXXXX..",
]


def make_png(width: int, height: int) -> bytes:
    """Generate a PNG with letter G on navy background."""
    width / 16
    height / 16

    # Margin: 15% on each side
    margin_x = int(width * 0.15)
    margin_y = int(height * 0.15)
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y
    glyph_scale_x = inner_w / 16
    glyph_scale_y = inner_h / 16

    rows = []
    for y in range(height):
        row = bytearray()
        row.append(0)  # PNG filter: None
        for x in range(width):
            # Check if pixel is in the glyph area
            gx = x - margin_x
            gy = y - margin_y
            if 0 <= gx < inner_w and 0 <= gy < inner_h:
                bx = int(gx / glyph_scale_x)
                by = int(gy / glyph_scale_y)
                bx = min(bx, 15)
                by = min(by, 15)
                if by < len(G_BITMAP) and bx < len(G_BITMAP[by]) and G_BITMAP[by][bx] == 'X':
                    row.extend(FG)
                    row.append(255)
                else:
                    row.extend(BG)
                    row.append(255)
            else:
                row.extend(BG)
                row.append(255)
        rows.append(bytes(row))

    raw = b''.join(rows)

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + c + crc

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8bit RGBA

    compressed = zlib.compress(raw, 9)

    return sig + png_chunk(b'IHDR', ihdr) + png_chunk(b'IDAT', compressed) + png_chunk(b'IEND', b'')


def make_ico(sizes=(16, 32, 48, 64, 256)) -> bytes:
    """Generate ICO file with multiple PNG sizes."""
    images = []
    for s in sizes:
        images.append(make_png(s, s))

    # ICO header: reserved(2) + type(2) + count(2)
    header = struct.pack('<HHH', 0, 1, len(sizes))

    # Directory entries + image data
    offset = 6 + 16 * len(sizes)  # header + all directory entries
    entries = []
    for i, s in enumerate(sizes):
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        entry = struct.pack('<BBBBHHII',
                            w, h, 0, 0,  # width, height, palette, reserved
                            1, 32,  # planes, bpp
                            len(images[i]),  # size
                            offset)  # offset
        entries.append(entry)
        offset += len(images[i])

    return header + b''.join(entries) + b''.join(images)


def main():
    outdir = os.path.dirname(os.path.abspath(__file__))

    # Only generate icon.png (512x512) - others already exist and are valid
    files = {
        'icon.png': make_png(512, 512),
    }

    for name, data in files.items():
        path = os.path.join(outdir, name)
        with open(path, 'wb') as f:
            f.write(data)
        print(f"  {name}: {len(data)} bytes")

    print("Done!")


if __name__ == '__main__':
    main()
