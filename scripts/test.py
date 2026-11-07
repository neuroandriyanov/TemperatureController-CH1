"""Offline validation; never opens a serial port or enables a heater."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true', help='also compile and run the C core tests')
    args = parser.parse_args()
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1')
    suites = [('firmware', 'tests'), ('apps/controller', 'tests'),
              ('apps/thermal_monitor', '.'), ('apps/stm32_programmer', '.'),
              ('apps/calibrator_lb02a', '.')]
    for folder, tests in suites:
        print(f'\nTesting {folder}', flush=True)
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', tests, '-v'],
                       cwd=ROOT / folder, env=env, check=True)
    subprocess.run([sys.executable, str(ROOT / 'firmware/scripts/register_map.py'), '--check'], check=True)
    if (ROOT / 'firmware/docs/registers.json').read_bytes() != (ROOT / 'apps/controller/registers.json').read_bytes():
        raise SystemExit('Controller register map differs from firmware; regenerate and copy it.')
    if args.native:
        subprocess.run([sys.executable, str(ROOT / 'firmware/tests/run.py')], env=env, check=True)
    print('\nOffline checks passed.')


if __name__ == '__main__':
    main()
