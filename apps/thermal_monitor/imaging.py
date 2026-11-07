"""Display processing, calibrated geometry, and labels shared by UI and API."""
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def resized(image, max_width):
    h, w = image.shape[:2]
    if w <= max_width:
        return image.copy()
    return cv2.resize(image, (max_width, round(h * max_width / w)), interpolation=cv2.INTER_AREA)


def enhance(image, settings):
    """Compress highlights and apply restrained unsharp masking, without invented detail."""
    if not settings.get('enabled', True):
        return image.copy()
    glare = settings.get('glare', 25) / 100.0
    sharp = settings.get('sharpness', 18) / 100.0
    result = image.copy()
    if glare > 0:
        values = np.arange(256, dtype=np.float32)
        highlights = np.maximum(0, (values - 155) / 100)
        curve = values - glare * 55 * highlights ** 1.6
        result = cv2.LUT(result, np.clip(curve, 0, 255).astype(np.uint8))
    if sharp > 0:
        blur = cv2.GaussianBlur(result, (0, 0), 0.9)
        result = cv2.addWeighted(result, 1 + sharp * 0.8, blur, -sharp * 0.8, 0)
    return result


def solve_alignment(pairs):
    if not isinstance(pairs, list) or not 4 <= len(pairs) <= 30:
        raise ValueError('Нужно от 4 до 30 пар общих точек.')
    src, dst = [], []
    for pair in pairs:
        for key in ('thermal', 'color'):
            coords = pair.get(key)
            if not isinstance(coords, (list, tuple)) or len(coords) != 2:
                raise ValueError('Каждая пара должна содержать thermal и color: [x, y].')
            # A rotated or stretched overlay may extend beyond the color frame.
            # Thermal coordinates remain within its original image; destination
            # coordinates outside [0, 1] are clipped only when displaying marks.
            low, high = (0, 1) if key == 'thermal' else (-4, 5)
            if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not low <= v <= high for v in coords):
                raise ValueError(f'Координаты {key} должны быть от {low} до {high}.')
        src.append(pair['thermal'])
        dst.append(pair['color'])
    src, dst = np.asarray(src, np.float32), np.asarray(dst, np.float32)
    for points in (src, dst):
        if cv2.contourArea(cv2.convexHull(points)) < 0.015:
            raise ValueError('Точки расположены слишком близко или на одной линии. Разнесите их по стенду.')
        for i in range(len(points)):
            if np.any(np.linalg.norm(points[i + 1:] - points[i], axis=1) < 0.008):
                raise ValueError('Есть совпадающие точки совмещения.')
    matrix, _ = cv2.findHomography(src, dst, 0)
    if matrix is None or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-8:
        raise ValueError('Не удалось вычислить совмещение. Проверьте порядок точек.')
    hull = cv2.convexHull(src).reshape(-1, 2)
    denominators = np.c_[hull, np.ones(len(hull))] @ matrix[2]
    if not (np.all(denominators > 1e-8) or np.all(denominators < -1e-8)):
        raise ValueError('Контур совмещения пересекается. Измените положение углов.')
    projected = cv2.perspectiveTransform(src[None], matrix)[0]
    rms = float(np.sqrt(np.mean(np.sum((projected - dst) ** 2, axis=1))))
    if rms > 0.04:
        raise ValueError('Пары точек не согласуются. Проверьте одинаковый порядок в двух изображениях.')
    return matrix.tolist(), rms


def map_point(matrix, x, y):
    if matrix is None:
        return None
    p = np.asarray(matrix, float) @ np.array([x, y, 1.0])
    if not np.isfinite(p).all() or abs(p[2]) < 1e-8:
        return None
    xx, yy = p[:2] / p[2]
    if not 0 <= xx <= 1 or not 0 <= yy <= 1:
        return None
    return [float(xx), float(yy)]


def label_text(marker):
    temperature = marker.get('temperature')
    value = f'≈ {temperature:.1f} °{marker.get("unit", "C")}' if temperature is not None else 'нет данных'
    return f'{marker["name"]}  {value}'


def annotate(image, markers, kind, footer=None):
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil)
    w, h = pil.size
    scale = max(1.0, w / 1440)
    font_size = max(12, round(17 * scale))
    font_path = Path('C:/Windows/Fonts/segoeui.ttf')
    font = ImageFont.truetype(str(font_path), font_size) if font_path.exists() else ImageFont.load_default()
    for marker in markers:
        point = marker.get(kind)
        if point is None:
            continue
        x, y = round(point[0] * (w - 1)), round(point[1] * (h - 1))
        radius = round(8 * scale)
        color = '#ffb857' if marker.get('active') else '#65e5df'
        for width, ink in ((max(3, round(5 * scale)), '#101723'), (max(1, round(2 * scale)), color)):
            draw.line((x-radius, y, x+radius, y), fill=ink, width=width)
            draw.line((x, y-radius, x, y+radius), fill=ink, width=width)
        text = label_text(marker)
        box = draw.textbbox((0, 0), text, font=font)
        tw, th = box[2] - box[0] + 14, box[3] - box[1] + 12
        tx = min(max(0, x + radius + 4), max(0, w - tw))
        ty = min(max(0, y - th - 5), max(0, h - th))
        draw.rounded_rectangle((tx, ty, tx+tw, ty+th), radius=4, fill='#111c2b', outline=color, width=1)
        draw.text((tx+7, ty+4-box[1]), text, font=font, fill=color)
    if footer:
        small = ImageFont.truetype(str(font_path), max(11, round(13 * scale))) if font_path.exists() else font
        box = draw.textbbox((0, 0), footer, font=small)
        th = box[3] - box[1] + 14
        draw.rectangle((0, h-th, w, h), fill='#101723')
        draw.text((8, h-th+5-box[1]), footer, font=small, fill='#d1d9e6')
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def png_bytes(image):
    ok, result = cv2.imencode('.png', image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise RuntimeError('Не удалось сохранить PNG.')
    return result.tobytes()
