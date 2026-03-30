#!/usr/bin/env python3
"""
Generate Tauri app icons for Gilbertus desktop app.
Pure Python — no external dependencies (uses struct, zlib, math, io only).

Design: Dark blue circle background with gold "G" letter.
"""

import struct
import zlib
import math
import io
import os

# Colors
BG_OUTER = (0x1a, 0x1a, 0x2e)  # #1a1a2e
BG_INNER = (0x16, 0x21, 0x3e)  # #16213e
GOLD = (0xd4, 0xaf, 0x37)       # #d4af37
TRANSPARENT = (0, 0, 0, 0)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "apps", "desktop", "src-tauri", "icons"
)


def lerp_color(c1, c2, t):
    """Linear interpolation between two RGB colors."""
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def blend_over(bg_r, bg_g, bg_b, bg_a, fg_r, fg_g, fg_b, fg_a):
    """Alpha composite fg over bg. All values 0-255."""
    fa = fg_a / 255.0
    ba = bg_a / 255.0
    oa = fa + ba * (1 - fa)
    if oa == 0:
        return (0, 0, 0, 0)
    or_ = int((fg_r * fa + bg_r * ba * (1 - fa)) / oa)
    og = int((fg_g * fa + bg_g * ba * (1 - fa)) / oa)
    ob = int((fg_b * fa + bg_b * ba * (1 - fa)) / oa)
    return (or_, og, ob, int(oa * 255))


def render_icon(size):
    """Render icon at given size, return list of (R,G,B,A) tuples."""
    pixels = []
    cx, cy = size / 2.0, size / 2.0
    radius = size / 2.0 - 0.5

    # G glyph parameters (normalized 0-1, relative to icon center)
    # These define the G shape
    g_outer_r = 0.34  # outer radius of G arc
    g_inner_r = 0.22  # inner radius of G arc (thickness = outer - inner)
    g_cx, g_cy = 0.50, 0.52  # G center (slightly below icon center)

    # Gap in the arc: from -40 deg to +40 deg (right side opening)
    gap_start = math.radians(-45)
    gap_end = math.radians(45)

    # Crossbar of G: horizontal bar from center-right inward
    bar_y_center = 0.52  # vertical center of bar (at G center)
    bar_half_height = 0.045
    bar_x_left = 0.50   # bar extends from center
    bar_x_right = 0.50 + g_outer_r  # to right edge of G

    for y in range(size):
        for x in range(size):
            px = (x + 0.5)
            py = (y + 0.5)

            # Normalized coordinates
            nx = px / size
            ny = py / size

            # Distance from icon center
            dist_center = math.sqrt((px - cx) ** 2 + (py - cy) ** 2)

            # Check if inside circle background
            circle_edge = radius - dist_center  # positive = inside
            if circle_edge < -1.0:
                pixels.append(TRANSPARENT)
                continue

            # Background color (radial gradient)
            grad_t = dist_center / radius if radius > 0 else 0
            bg = lerp_color(BG_INNER, BG_OUTER, grad_t)

            # Circle alpha (anti-aliased edge)
            circle_alpha = max(0.0, min(1.0, circle_edge + 0.5))

            # Check if pixel is part of the G glyph
            # Distance from G center
            gdx = nx - g_cx
            gdy = ny - g_cy
            g_dist = math.sqrt(gdx ** 2 + gdy ** 2)
            g_angle = math.atan2(-gdy, gdx)  # note: y inverted for screen coords

            # Anti-aliased ring check
            pixel_size = 1.0 / size  # size of one pixel in normalized coords
            aa_width = pixel_size * 1.2  # anti-aliasing width

            # Outer edge of ring
            outer_edge = g_outer_r - g_dist
            outer_aa = max(0.0, min(1.0, outer_edge / aa_width + 0.5))

            # Inner edge of ring
            inner_edge = g_dist - g_inner_r
            inner_aa = max(0.0, min(1.0, inner_edge / aa_width + 0.5))

            ring_alpha = outer_aa * inner_aa

            # Check if in the gap (right side opening)
            in_gap = False
            if g_angle > gap_start and g_angle < gap_end:
                # In gap region — but only for the top half of the gap
                # The gap is on the right. Check if above the crossbar.
                if ny < bar_y_center - bar_half_height:
                    in_gap = True
                    ring_alpha = 0.0

            # Anti-alias the gap edges
            if not in_gap and ny < bar_y_center - bar_half_height:
                # Near gap boundary — smooth transition
                gap_start_dist = abs(g_angle - gap_start)
                gap_end_dist = abs(g_angle - gap_end)
                angle_pixel = math.atan2(pixel_size, g_dist) if g_dist > 0 else 0.1
                if gap_start_dist < angle_pixel:
                    ring_alpha *= min(1.0, gap_start_dist / angle_pixel)
                if gap_end_dist < angle_pixel:
                    ring_alpha *= min(1.0, gap_end_dist / angle_pixel)

            # Crossbar of G
            bar_alpha = 0.0
            if (bar_x_left <= nx <= bar_x_right and
                    abs(ny - bar_y_center) <= bar_half_height + aa_width):
                # Vertical anti-aliasing
                vert_dist = bar_half_height - abs(ny - bar_y_center)
                vert_aa = max(0.0, min(1.0, vert_dist / aa_width + 0.5))

                # Left edge anti-aliasing
                left_dist = nx - bar_x_left
                left_aa = max(0.0, min(1.0, left_dist / aa_width + 0.5))

                # Right edge anti-aliasing (clip to outer ring)
                right_dist = g_outer_r - math.sqrt((nx - g_cx) ** 2 + (ny - g_cy) ** 2)
                right_aa = max(0.0, min(1.0, right_dist / aa_width + 0.5))

                bar_alpha = vert_aa * left_aa * right_aa

            # Combine G alpha
            g_alpha = max(ring_alpha, bar_alpha)
            g_alpha = max(0.0, min(1.0, g_alpha))

            # Compose final pixel
            # Start with background
            r, g, b = bg
            a = int(circle_alpha * 255)

            # Blend gold G on top
            if g_alpha > 0:
                ga = int(g_alpha * 255)
                r, g, b, a = blend_over(r, g, b, a, GOLD[0], GOLD[1], GOLD[2], ga)

            pixels.append((r, g, b, a))

    return pixels


def make_png(pixels, width, height):
    """Create PNG file bytes from pixel data."""
    # Build raw image data (filter byte + RGBA per row)
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # filter: None
        for x in range(width):
            r, g, b, a = pixels[y * width + x]
            raw_data.extend([r, g, b, a])

    compressed = zlib.compress(bytes(raw_data), 9)

    buf = io.BytesIO()

    # PNG signature
    buf.write(b'\x89PNG\r\n\x1a\n')

    def write_chunk(chunk_type, data):
        buf.write(struct.pack('>I', len(data)))
        buf.write(chunk_type)
        buf.write(data)
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        buf.write(struct.pack('>I', crc))

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    write_chunk(b'IHDR', ihdr_data)

    # IDAT
    write_chunk(b'IDAT', compressed)

    # IEND
    write_chunk(b'IEND', b'')

    return buf.getvalue()


def make_ico(png_data_list):
    """Create ICO file from list of (width, height, png_bytes) tuples."""
    num = len(png_data_list)
    buf = io.BytesIO()

    # ICONDIR header
    buf.write(struct.pack('<HHH', 0, 1, num))

    # Calculate offsets
    header_size = 6 + num * 16
    offset = header_size

    entries = []
    for width, height, png_data in png_data_list:
        w = width if width < 256 else 0
        h = height if height < 256 else 0
        entries.append((w, h, len(png_data), offset))
        offset += len(png_data)

    # ICONDIRENTRY for each image
    for w, h, data_size, data_offset in entries:
        buf.write(struct.pack('<BBBBHHII',
                              w,           # width (0 = 256)
                              h,           # height (0 = 256)
                              0,           # color palette
                              0,           # reserved
                              1,           # color planes
                              32,          # bits per pixel
                              data_size,   # size of image data
                              data_offset  # offset to image data
                              ))

    # Image data
    for _, _, png_data in png_data_list:
        buf.write(png_data)

    return buf.getvalue()


def make_icns(png_256_data):
    """Create minimal valid ICNS file with ic08 (256x256) entry."""
    buf = io.BytesIO()

    # ic08 = 256x256 PNG
    icon_type = b'ic08'
    entry_size = 8 + len(png_256_data)  # type(4) + size(4) + data

    total_size = 8 + entry_size  # header(8) + entry

    # ICNS header
    buf.write(b'icns')
    buf.write(struct.pack('>I', total_size))

    # ic08 entry
    buf.write(icon_type)
    buf.write(struct.pack('>I', entry_size))
    buf.write(png_256_data)

    return buf.getvalue()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sizes_needed = [16, 32, 48, 128, 256]
    rendered = {}
    png_cache = {}

    print("Rendering icons...")
    for s in sizes_needed:
        print(f"  Rendering {s}x{s}...")
        pixels = render_icon(s)
        rendered[s] = pixels
        png_cache[s] = make_png(pixels, s, s)

    # 1. 32x32.png
    path = os.path.join(OUTPUT_DIR, "32x32.png")
    with open(path, 'wb') as f:
        f.write(png_cache[32])
    print(f"  Written: {path} ({len(png_cache[32])} bytes)")

    # 2. 128x128.png
    path = os.path.join(OUTPUT_DIR, "128x128.png")
    with open(path, 'wb') as f:
        f.write(png_cache[128])
    print(f"  Written: {path} ({len(png_cache[128])} bytes)")

    # 3. 128x128@2x.png (256x256)
    path = os.path.join(OUTPUT_DIR, "128x128@2x.png")
    with open(path, 'wb') as f:
        f.write(png_cache[256])
    print(f"  Written: {path} ({len(png_cache[256])} bytes)")

    # 4. icon.ico (16, 32, 48, 256)
    ico_entries = [
        (16, 16, png_cache[16]),
        (32, 32, png_cache[32]),
        (48, 48, png_cache[48]),
        (256, 256, png_cache[256]),
    ]
    ico_data = make_ico(ico_entries)
    path = os.path.join(OUTPUT_DIR, "icon.ico")
    with open(path, 'wb') as f:
        f.write(ico_data)
    print(f"  Written: {path} ({len(ico_data)} bytes)")

    # 5. icon.icns (macOS)
    icns_data = make_icns(png_cache[256])
    path = os.path.join(OUTPUT_DIR, "icon.icns")
    with open(path, 'wb') as f:
        f.write(icns_data)
    print(f"  Written: {path} ({len(icns_data)} bytes)")

    print("\nAll icons generated successfully!")


if __name__ == "__main__":
    main()
