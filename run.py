"""Launch one application using the environment installed by setup.py."""
import argparse
from pathlib import Path
import subprocess
import sys
from env import environment_python

ROOT = Path(__file__).resolve().parent
APPS = {
    'controller': 'apps/controller/app.py',
    'thermal': 'apps/thermal_monitor/app.py',
    'calibrator': 'apps/calibrator_lb02a/esp32_display_viewer.py',
    'programmer': 'apps/stm32_programmer/app.py',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', choices=APPS)
    args, extra = parser.parse_known_args()
    python = environment_python()
    entry = ROOT / APPS[args.application]
    if extra[:1] == ['--']:
        extra = extra[1:]
    return subprocess.call([str(python), str(entry), *extra], cwd=entry.parent)


if __name__ == '__main__':
    raise SystemExit(main())
