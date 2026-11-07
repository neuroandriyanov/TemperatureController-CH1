"""Read LB02A framebuffer glyphs captured from the physical display bus."""

from hashlib import blake2s
from itertools import groupby
import re


def frame_is_fresh(*, pixels, now, ready_after, requested_at,
                   updated_at, instrument_seen, gaps, baseline):
    """Require a post-request frame, settling time, live bus and no packet gaps.

    A fast redraw can finish before the next key is allowed. It is still a
    post-request frame; comparing its time to the key throttle deadline would
    reject a stable source screen forever until another redraw.
    """
    return bool(pixels and now >= ready_after and gaps == baseline
                and now - max(updated_at, instrument_seen) <= 2
                and updated_at >= requested_at)


# Exact masks of glyphs from the captured LB02A framebuffer.
DIGITS = {
    "ea0e76527750": "0", "4b23cc42cb9c": "1", "0fdaa414fb1d": "2",
    "eaa0a3b73b4c": "3", "0848005ed697": "4", "bd4139c37ff1": "5",
    "85de7a4d091a": "6", "a2ad71e21ae0": "7", "d8ec33956e9d": "8",
    "249243e570c2": "9", "a325af67e0ac": ".", "7709f15a22f9": "L",
    "b49b68add6e9": "-",
}
SMALL = {
    "affdcf55294c": "0", "b468067a4170": "1", "81628243077f": "2",
    "95732bce9d67": "3", "f0f7e8b3a8bd": "4", "050c48b5c0e2": "5",
    "4d7480134ff1": "6", "df9dfa1213dd": "7", "7ab175896589": "8",
    "0c939bbb8c12": "9", "e6de2ff83482": ".", "0acf859b26bc": "-",
    "b9ac88ffc794": "L",
}
MEDIUM = {
    "478998c5b384": "0", "290a72fac1da": "1", "c44588c11d8d": "2",
    "af0b957ae15a": "3", "3091cd728902": "4", "74e25d8ec4c3": "5",
    "45888321fe47": "6", "d2013811dcd6": "7", "6f7b928f8020": "8",
    "5df505536ac3": "9", "e980a98f1b8a": ".", "4541c8489689": "-",
    "d08fb1042f80": "L",
}
TC = {
    "81ae845a1ddc": "S", "35cbb5742c26": "B", "ff5f62ec82ff": "R",
    "3d92143dff3b": "J", "6fe4b8e17485": "T", "294cbb1dd4d0": "N",
    "309437ccdfa0": "E", "6cd6d10a62ad": "K",
}
RTD = {"dde8a8cdac6f": "Pt100", "5ee35a2801fb": "Cu50", "ae9b5225a308": "Pt1000"}
UNITS = {
    "bd05755a9035": "V", "c22ff4bed49a": "24V", "3aac1fb163f6": "mA",
    "e5ec133f52ce": "kHz", "49665222c45d": "mV", "bfec48f5da35": "Ω",
}
DIRECTIONS = {"062a33354028": "output", "64265dc39097": "input"}


def signature(mask):
    box = mask.getbbox()
    if box:
        return blake2s(mask.crop(box).tobytes(), digest_size=6).hexdigest()
    return None


def read_text(mask, box, glyphs):
    region = mask.crop(box)
    occupied, _ = region.getprojection()
    digits = []
    for present, columns in groupby(range(region.width), key=occupied.__getitem__):
        if present:
            first, *rest = columns
            last = rest[-1] if rest else first
            digit = glyphs.get(signature(region.crop((first, 0, last + 1, region.height))))
            if digit is None:
                return None
            digits.append(digit)
    return "".join(digits)


def number(display):
    if display and re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", display):
        return float(display)
    return None


def reading(display, unit, direction):
    value = number(display)
    if unit is None or (value is None and display != "0.L"):
        return None
    return {"value": value, "text": display, "unit": unit, "direction": direction,
            "status": "overload" if value is None else "ok"}


def read_display(frame):
    if frame.size != (320, 240):
        return None
    mask = frame.convert("L").point([255] * 80 + [0] * 176)
    direction = DIRECTIONS.get(signature(mask.crop((255, 15, 315, 58))))
    if direction is None:
        return None
    framed = bool(mask.getpixel((10, 58)))
    unit_box = (240, 69, 305, 113) if framed else (256, 70, 305, 113)
    unit_mark = signature(mask.crop(unit_box))
    top = (65, 26, 195, 55)
    top_unit = UNITS.get(signature(mask.crop((195, 25, 251, 56))))
    if framed and signature(mask.crop((227, 69, 305, 97))) == "81bb9652ce38":
        count = reading(read_text(mask, (20, 62, 227, 113), MEDIUM), "CNT", direction)
        if count is None:
            return None
        fields = {"C-H": (65, 149, 154, 174), "C-L": (213, 149, 305, 174)}
        if top_unit == "Ω":
            fields.update({"SP": (158, 118, 255, 143), "R-H": (65, 175, 154, 201),
                           "R-L": (213, 175, 305, 201)})
        else:
            fields["SP"] = (158, 118, 255, 143) if top_unit == "mV" else (64, 117, 149, 143)
            if top_unit == "kHz":
                fields.update({"Hz-V": (218, 118, 305, 143), "Hz-H": (72, 175, 154, 201),
                               "Hz-L": (218, 175, 305, 201)})
            if top_unit in ("V", "mV", "mA"):
                fields.update({f"{top_unit}-H": (72, 175, 154, 201),
                               f"{top_unit}-L": (218, 175, 305, 201)})
                if top_unit != "mV":
                    fields["Sqrt"] = (218, 118, 305, 143)
        count.update(mode="CNT", source=reading(read_text(mask, top, SMALL), top_unit, direction),
                     fields={key: number(read_text(mask, box, SMALL)) for key, box in fields.items()})
        return count

    thermocouple = TC.get(signature(mask.crop((265, 69, 306, 96))))
    resistance_sensor = RTD.get(signature(mask.crop((225, 69, 306, 96))))
    sensor = thermocouple or resistance_sensor
    degrees = signature(mask.crop((265, 101, 306, 140))) == "434c5966d54a"
    if sensor and degrees:
        mode = "TC" if thermocouple else "RTD"
        right = 256 if thermocouple else 225
        box, glyphs = ((20, 64, right, 141), MEDIUM) if framed else ((0, 65, right, 155), DIGITS)
        result = reading(read_text(mask, box, glyphs), "°C", direction)
        if result is None:
            return None
        result.update(mode=mode, sensor=sensor)
        if framed:
            result["source"] = reading(read_text(mask, top, SMALL), top_unit, direction)
            fields = {"SP": (172, 150, 303, 194)}
            if mode == "TC":
                fields = {"SP": (51, 150, 154, 170), "CJ_M": (96, 174, 150, 201),
                          "CJ_A": (245, 174, 303, 201)}
                if direction == "output":
                    fields["OUT"] = (208, 150, 303, 171)
            elif direction == "input":
                fields = {"SP": (51, 150, 154, 170), "WR_M": (101, 174, 150, 201),
                          "WR_A": (245, 174, 303, 201)}
            result["fields"] = {key: number(read_text(mask, region, SMALL))
                                for key, region in fields.items()}
        return result

    unit = UNITS.get(unit_mark)
    if unit is None:
        return None
    box, glyphs = ((20, 64, 240, 141), MEDIUM) if framed else ((0, 65, 256, 155), DIGITS)
    result = reading(read_text(mask, box, glyphs), unit, direction)
    if result and framed:
        result["fields"] = {"SP": number(read_text(mask, (172, 150, 303, 194), SMALL))}
    return result
