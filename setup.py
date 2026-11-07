"""Install the desktop applications into an isolated virtual environment."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv
import json
import struct
from env import default_environment, RECORD

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev', action='store_true', help='also install plotting and ESP32 build tools')
    parser.add_argument('--venv', type=Path, default=default_environment(), help='optional custom environment directory')
    args = parser.parse_args()
    if not (3, 12) <= sys.version_info[:2] < (3, 16):
        parser.error('Use Python 3.12–3.15, 64 bit.')
    if struct.calcsize('P') != 8:
        parser.error('Use 64-bit Python for the Qt/OpenCV dependencies.')
    target = args.venv.resolve()
    venv.EnvBuilder(with_pip=True).create(target)
    python = target / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    requirement = ROOT / ('requirements-dev.txt' if args.dev else 'requirements.txt')
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirement)], check=True)
    RECORD.parent.mkdir(exist_ok=True)
    RECORD.write_text(json.dumps({'environment': str(target)}, indent=2)+'\n', encoding='utf-8')
    print('Installed. Start an application with: python run.py controller')
    print('Developer commands: python env.py scripts/test.py')
    print('No instrument was connected, programmed or switched on.')


if __name__ == '__main__':
    main()
