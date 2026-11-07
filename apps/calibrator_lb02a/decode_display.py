"""Reconstruct an ILI9341 display image from a Saleae digital.csv capture."""

import argparse
import csv
from pathlib import Path

from PIL import Image


def spi_bytes(path, clock, mosi, dc, cs):
    """Yield (data/command flag, byte) on rising SCL edges, MSB first."""
    with path.open(newline="", encoding="utf-8-sig") as source:
        rows = csv.reader(source)
        channels = [clock, mosi, dc] + ([] if cs is None else [cs])
        columns = [f"Channel {channel}" for channel in channels]
        header = next(rows, [])
        if not set(columns).issubset(header):
            raise ValueError(f"Capture must contain {', '.join(columns)}")
        clock_index, mosi_index, dc_index, *select = [header.index(col) for col in columns]
        select_index = select[0] if select else None
        previous_clock = None
        previous_dc = None
        value = bits = 0
        for row in rows:
            clock_level, data_mode = row[clock_index], row[dc_index]
            selected = select_index is None or row[select_index] == "0"
            if not selected or data_mode != previous_dc:
                value = bits = 0
            if selected and previous_clock == "0" and clock_level == "1":
                value = (value << 1) | (row[mosi_index] == "1")
                bits += 1
                if bits == 8:
                    yield data_mode == "1", value
                    value = bits = 0
            previous_clock, previous_dc = clock_level, data_mode


def reconstruct(stream, default_landscape=False, base=None):
    """Replay LCD address windows and pixel writes in logical screen coordinates."""
    def with_snapshot():
        yield from stream
        yield None

    image, written = next(replay_frames(with_snapshot(), default_landscape, base))
    if not written:
        raise ValueError("No pixels decoded. Check the channel mapping, SPI rate, and capture a screen redraw.")
    return image, written


def replay_frames(stream, default_landscape=False, base=None):
    """Keep LCD state across snapshots (None) and resync after transport gaps."""
    image = Image.new("RGB", (320, 320))
    if base is not None:
        if base.size not in ((240, 320), (320, 240)):
            raise ValueError("Base image must be 240x320 or 320x240")
        image.paste(base, (0, 0))
        default_landscape = base.width > base.height
    pixels = image.load()
    landscape = default_landscape
    x0 = y0 = x = y = 0
    x1, y1 = (319, 239) if landscape else (239, 319)
    bytes_per_pixel = 2
    command = None
    payload = bytearray()
    written = 0
    for item in stream:
        if item is None:
            width, height = (320, 240) if landscape else (240, 320)
            yield image.crop((0, 0, width, height)), written
            continue
        is_data, value = item
        if is_data is None:
            command = None
            payload.clear()
            x1 = y1 = -1
            continue
        if not is_data:
            command = value
            payload.clear()
            if command == 0x2C:
                x, y = x0, y0
            continue
        if command not in (0x2A, 0x2B, 0x2C, 0x36, 0x3A, 0x3C):
            continue
        payload.append(value)
        if command in (0x2A, 0x2B) and len(payload) == 4:
            start = int.from_bytes(payload[:2], "big")
            end = int.from_bytes(payload[2:], "big")
            if command == 0x2A:
                x0, x1 = start, end
            else:
                y0, y1 = start, end
            command = None
        elif command == 0x36:
            landscape = bool(value & 0x20)
            command = None
        elif command == 0x3A:
            bytes_per_pixel = {5: 2, 6: 3}.get(value & 0x07)
            if bytes_per_pixel is None:
                raise ValueError(f"Unsupported LCD pixel format 0x{value:02X}")
            command = None
        elif command in (0x2C, 0x3C) and len(payload) == bytes_per_pixel:
            if 0 <= x < 320 and 0 <= y < 320 and x0 <= x <= x1 and y0 <= y <= y1:
                if bytes_per_pixel == 2:
                    color = int.from_bytes(payload, "big")
                    rgb = (color >> 11, (color >> 5) & 63, color & 31)
                    pixels[x, y] = tuple(v * 255 // maximum for v, maximum in zip(rgb, (31, 63, 31)))
                else:
                    pixels[x, y] = tuple((v >> 2) * 255 // 63 for v in payload)
                written += 1
            payload.clear()
            x += 1
            if x > x1:
                x, y = x0, y + 1
            if y > y1:
                x, y = x0, y0


def reconstruct_complete_windows(stream, base=None, *, ended_in_idle=False):
    """Replay complete windows from a capture that may start or end mid-transfer."""
    landscape = base is None or base.width > base.height
    image = Image.new("RGB", (320, 320))
    coverage = Image.new("1", image.size)
    if base is not None:
        image.paste(base, (0, 0))
    columns = rows = command = None
    payload = bytearray()
    window = None
    written = 0
    rgb565 = True

    def commit_window():
        x0, y0, x1, _ = window
        line_width = x1 - x0
        complete_rows, remainder = divmod(len(payload) // 2, line_width)
        offset = 0
        for tile_width, tile_height in ((line_width, complete_rows), (remainder, 1)):
            if not tile_width or not tile_height:
                continue
            length = tile_width * tile_height * 2
            little_endian = bytearray(length)
            little_endian[::2] = payload[offset + 1:offset + length:2]
            little_endian[1::2] = payload[offset:offset + length:2]
            tile = Image.frombytes("RGB", (tile_width, tile_height), bytes(little_endian), "raw", "BGR;16")
            box = (x0, y0, x0 + tile_width, y0 + tile_height)
            image.paste(tile, box)
            coverage.paste(1, box)
            y0 += tile_height
            offset += length
        return offset // 2

    for is_data, value in stream:
        if not is_data:
            if window is not None and len(payload) % 2 == 0:
                written += commit_window()
            command = value
            payload.clear()
            window = None
            if command == 0x2C and rgb565 and columns is not None and rows is not None:
                x0, x1 = columns
                y0, y1 = rows
                width, height = (320, 240) if landscape else (240, 320)
                if 0 <= x0 <= x1 < width and 0 <= y0 <= y1 < height:
                    window = (x0, y0, x1 + 1, y1 + 1)
                    size = (x1 - x0 + 1, y1 - y0 + 1)
                    expected = size[0] * size[1] * 2
            continue
        if command in (0x2A, 0x2B):
            payload.append(value)
            if len(payload) == 4:
                bounds = (int.from_bytes(payload[:2], "big"), int.from_bytes(payload[2:], "big"))
                if command == 0x2A:
                    columns = bounds
                else:
                    rows = bounds
                command = None
        elif command == 0x36:
            landscape = bool(value & 0x20)
            command = None
        elif command == 0x3A:
            rgb565 = (value & 0x07) == 5
            command = None
        elif window is not None:
            payload.append(value)
            if len(payload) == expected:
                written += commit_window()
                window = None
    if ended_in_idle and window is not None and len(payload) % 2 == 0:
        written += commit_window()
    width, height = (320, 240) if landscape else (240, 320)
    frame = (0, 0, width, height)
    image = image.crop(frame)
    coverage = coverage.crop(frame)
    full = coverage.getextrema() == (1, 1)
    if base is not None and image.size == (320, 240) and not full:
        # The LB02A's standard O.L Ω screen has no static footer. Recognize
        # it from freshly written glyph pixels, never from the previous frame.
        black = ((128, 113), (204, 108), (267, 85), (276, 85))
        white = ((140, 113), (213, 108), (272, 85))
        if all(coverage.getpixel(p) and max(image.getpixel(p)) < 64 for p in black) and all(
            coverage.getpixel(p) and min(image.getpixel(p)) > 240 for p in white
        ):
            clean = Image.new("RGB", image.size, "white")
            # Keep only the status icons outside the measurement area.
            clean.paste(image.crop((16, 24, 60, 56)), (16, 24))
            clean.paste(image.crop((260, 24, 310, 56)), (260, 24))
            image = Image.composite(image, clean, coverage)
    return image, written, full


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--clock", type=int, default=3)
    parser.add_argument("--mosi", type=int, default=2)
    parser.add_argument("--dc", type=int, default=4)
    parser.add_argument("--cs", type=int, help="include only bytes with this channel low")
    parser.add_argument("--landscape", action="store_true", help="initial orientation if MADCTL is absent")
    parser.add_argument("--base", type=Path, help="previous PNG for applying partial screen updates")
    args = parser.parse_args()
    try:
        base = None
        if args.base is not None:
            with Image.open(args.base) as previous:
                base = previous.convert("RGB")
        stream = spi_bytes(args.capture, args.clock, args.mosi, args.dc, args.cs)
        image, written = reconstruct(stream, args.landscape, base)
        image.save(args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{image.width}x{image.height}, {written} pixel writes: {args.output}")


if __name__ == "__main__":
    main()
