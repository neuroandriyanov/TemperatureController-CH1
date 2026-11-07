"""DirectShow device discovery and bounded, independent camera readers."""
from dataclasses import dataclass
from collections import deque
import re
import subprocess
import threading
import time

import imageio_ffmpeg
import numpy as np

HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def _probe(arguments):
    result = subprocess.run([ffmpeg(), '-hide_banner', *arguments], capture_output=True,
                            timeout=12, creationflags=HIDDEN)
    return result.stderr.decode('utf-8', errors='replace')


def list_devices():
    log = _probe(['-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'])
    found = []
    for line in log.splitlines():
        match = re.search(r'"(.*)" \((video|audio, video)\)', line)
        if match:
            found.append({'name': match[1], 'id': match[1]})
        elif found and 'Alternative name' in line:
            match = re.search(r'Alternative name "(.*)"', line)
            if match:
                found[-1]['id'] = match[1]
    return found


def list_modes(device):
    log = _probe(['-list_options', 'true', '-f', 'dshow', '-i', 'video=' + device])
    modes = {}
    for line in log.splitlines():
        match = re.search(r'(pixel_format|vcodec)=(\w+).*?min s=(\d+)x(\d+) fps=([\d.]+).*?max s=(\d+)x(\d+) fps=([\d.]+)', line)
        if not match:
            continue
        kind, fmt, w, h, lo, _, _, hi = match.groups()
        if fmt not in ('yuyv422', 'nv12', 'mjpeg', 'bgr0', 'rgb24', 'bgr24'):
            continue
        rate = min(float(hi), 25.0)
        if rate < float(lo):
            rate = float(lo)
        mode = {'width': int(w), 'height': int(h), 'fps': round(rate, 4),
                'format': fmt, 'codec': kind == 'vcodec'}
        mode['key'] = f'{w}x{h}|{mode["fps"]}|{fmt}'
        modes[mode['key']] = mode
    return sorted(modes.values(), key=lambda m: (m['width'] * m['height'],
                  m['format'] == 'yuyv422', m['format'] == 'nv12'), reverse=True)


def default_mode(modes, thermal=False):
    if not modes:
        raise ValueError('Устройство не сообщило поддерживаемые видеорежимы.')
    if thermal:
        for mode in modes:
            if (mode['width'], mode['height'], mode['format']) == (240, 321, 'yuyv422'):
                return mode
    for mode in modes:
        if mode['width'] <= 3840 and mode['format'] == 'yuyv422':
            return mode
    return modes[0]


@dataclass(frozen=True)
class Packet:
    image: np.ndarray
    sequence: int
    wall_time: float
    monotonic: float


class CameraReader:
    def __init__(self, device, name, mode, preview_fps=10):
        self.device, self.name, self.mode = device, name, dict(mode)
        self.latest = None
        self.status = 'starting'
        self.error = ''
        self.log = deque(maxlen=20)
        self._stop = threading.Event()
        self._process = None
        self._thread = None
        self.preview_fps = preview_fps

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name='capture-' + self.name)
        self._thread.start()

    def _stderr(self, stream):
        for line in iter(stream.readline, b''):
            self.log.append(line.decode('utf-8', errors='replace').strip())

    def _run(self):
        m = self.mode
        command = [ffmpeg(), '-hide_banner', '-loglevel', 'warning', '-f', 'dshow',
                   '-rtbufsize', '256M', '-video_size', f'{m["width"]}x{m["height"]}',
                   '-framerate', str(m['fps'])]
        command += ['-vcodec' if m.get('codec') else '-pixel_format', m['format']]
        command += ['-i', 'video=' + self.device, '-an', '-vf',
                    f'fps={min(self.preview_fps, m["fps"])}', '-pix_fmt', 'bgr24',
                    '-threads', '2', '-f', 'rawvideo', 'pipe:1']
        process = None
        try:
            process = self._process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, creationflags=HIDDEN)
            threading.Thread(target=self._stderr, args=(process.stderr,), daemon=True).start()
            size = m['width'] * m['height'] * 3
            sequence = 0
            while not self._stop.is_set():
                data = bytearray(size)
                view = memoryview(data)
                pos = 0
                while pos < size and not self._stop.is_set():
                    count = process.stdout.readinto(view[pos:])
                    if not count:
                        raise RuntimeError('Поток камеры завершился. ' + ' '.join(self.log)[-900:])
                    pos += count
                if pos != size:
                    break
                image = np.frombuffer(data, dtype=np.uint8).reshape(m['height'], m['width'], 3)
                image.setflags(write=False)
                sequence += 1
                self.latest = Packet(image, sequence, time.time(), time.monotonic())
                self.status = 'live'
        except Exception as error:
            if not self._stop.is_set():
                self.status, self.error = 'error', str(error)
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                for stream in (process.stdout, process.stderr):
                    if stream:
                        stream.close()
            if self._stop.is_set():
                self.status = 'stopped'

    def stop(self):
        self._stop.set()
        p = self._process
        if p is not None and p.poll() is None:
            p.kill()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=6)

    def state(self):
        packet = self.latest
        age = time.monotonic() - packet.monotonic if packet else None
        return {'name': self.name, 'device': self.device, 'mode': self.mode,
                'status': 'stale' if self.status == 'live' and age is not None and age > 2 else self.status,
                'error': self.error, 'age_seconds': age, 'sequence': packet.sequence if packet else 0}
