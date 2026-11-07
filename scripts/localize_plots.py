"""Render English plot companions by translating SVG text only.

Geometry, paths, numeric tick labels, and source measurement files are untouched.
Requires Pillow and either Inkscape or CairoSVG for PNG rendering;
--svg-only needs standard Python.
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    'Температура, °C': 'Temperature, °C',
    'период 2 с': 'period 2 s',
    'Термопара K': 'Type K thermocouple',
    'Уставка 60 °C': 'Setpoint 60 °C',
    'Допуск реле ±10 °C': 'Relay band ±10 °C',
    'Команда, %': 'Command, %',
    'Команда PID': 'PID command',
    'Время после AUTO, мин': 'Time after AUTO, min',
    'Корпус ≈ °C': 'Enclosure ≈ °C',
    'Корпус A ≈': 'Case A ≈',
    'Корпус B ≈': 'Case B ≈',
    'Удержание после достижения уставки': 'Holding after reaching the setpoint',
    'Показание термопары K': 'Type K reading',
    'После первого попадания в 59,8…60,2 °C, мин': 'Time after first entering 59.8…60.2 °C, min',
    'Задание калибратора, °C': 'Calibrator setting, °C',
    'Среднее отклонение CH1, °C': 'CH1 mean deviation, °C',
    'Термопары · 35 точек · внутренняя компенсация': 'Thermocouples · 35 points · internal compensation',
    'Задание Pt100, °C (последняя точка — повтор)': 'Pt100 setting, °C (last point repeated)',
    'Отклонение от задания, °C': 'Deviation from setting, °C',
    'Pt100 → НПТ → CH1 · порядок реальной серии': 'Pt100 → transmitter → CH1 · actual series order',
    'CH1, среднее': 'CH1, mean',
    'НПТ, экран': 'NPT display',
    'Источник, мА': 'Source, mA',
    'CH1 − источник, мА': 'CH1 − source, mA',
    'Прямой вход 4–20 мА после калибровки': 'Direct 4–20 mA input after calibration',
    'Среднее и min…max отсчётов': 'Mean and sample min…max',
}

def translate_text(match):
    text = match.group(2)
    for source, target in sorted(LABELS.items(), key=lambda p: len(p[0]), reverse=True):
        text = text.replace(source, target)
    if re.search('[А-Яа-яЁё]', text):
        raise ValueError(f'Untranslated plot label: {text}')
    return match.group(1) + text + match.group(3)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--svg-only', action='store_true')
    args = parser.parse_args()
    for source in sorted((ROOT/'measurements').rglob('*.svg')):
        if '.en.' in source.name:
            continue
        original = source.read_text(encoding='utf-8')
        result = re.sub(r'(<text\b[^>]*>)(.*?)(</text>)', translate_text, original, flags=re.S)
        before = ET.fromstring(original)
        after = ET.fromstring(result)
        # Only text content may differ; all drawing coordinates remain exact.
        for a, b in zip(before.iter(), after.iter()):
            if a.tag != b.tag or a.attrib != b.attrib:
                raise ValueError(f'Plot geometry changed: {source}')
            if not a.tag.endswith('text') and a.text != b.text:
                raise ValueError(f'Non-label content changed: {source}')
        target = source.with_name(source.stem+'.en.svg')
        target.write_text(result, encoding='utf-8')
        if not args.svg_only:
            from PIL import Image
            with Image.open(source.with_suffix('.png')) as png:
                width, height = png.size
            if shutil.which('inkscape'):
                subprocess.run(['inkscape', str(target), '--export-type=png',
                    '--export-filename='+str(target.with_suffix('.png')),
                    '--export-width='+str(width), '--export-height='+str(height)], check=True,
                    stdout=subprocess.DEVNULL)
            else:
                import cairosvg
                cairosvg.svg2png(bytestring=result.encode(), write_to=str(target.with_suffix('.png')),
                                output_width=width, output_height=height)
        print(target.relative_to(ROOT))

if __name__ == '__main__':
    main()
