"""Run Python inside this project's environment without activating it."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RECORD = ROOT / '.runtime/environment.json'


def default_environment():
    if os.name == 'nt':
        # Qt wheels have deep resource paths. Keep venv short without changing
        # Windows registry settings or requiring administrator privileges.
        local = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
        identity = hashlib.sha256(str(ROOT).casefold().encode('utf-8')).hexdigest()[:12]
        return local / 'CH1' / identity
    return ROOT / '.venv'


def environment_python():
    environment = default_environment()
    if RECORD.is_file():
        try:
            environment = Path(json.loads(RECORD.read_text(encoding='utf-8'))['environment'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise SystemExit('Invalid local environment record; rerun python setup.py') from error
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        raise SystemExit('Environment is missing. Run: python setup.py')
    return python


def main():
    if len(sys.argv) < 2:
        print('Usage: python env.py SCRIPT [ARGS] or python env.py -m MODULE [ARGS]')
        return 0
    return subprocess.call([str(environment_python()), *sys.argv[1:]])


if __name__ == '__main__':
    raise SystemExit(main())
