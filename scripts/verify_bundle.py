"""Check every file of the prepared source snapshot against MANIFEST.sha256."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
count = 0
for line in (ROOT / 'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
    expected, relative = line.split('  ', 1)
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise SystemExit('Missing or invalid file: ' + relative)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('Changed file: ' + relative)
    count += 1
print(f'Snapshot OK: {count} files. Generated local files are not part of this manifest.')
