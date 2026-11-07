"""Validate the local evidence catalog and, explicitly, refresh source hashes."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'knowledge/index.json'
STATUSES = {'document_confirmed', 'needs_verification', 'unknown'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    index = json.loads(INDEX.read_text(encoding='utf-8'))
    sources = {s['id']: s for s in index['sources']}
    if len(sources) != len(index['sources']):
        raise SystemExit('Duplicate source ID')
    for source in sources.values():
        path = (ROOT / source['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise SystemExit('Missing or external source: ' + source['path'])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if args.refresh:
            source['sha256'] = digest
        elif source['sha256'] != digest:
            raise SystemExit('Changed source (review dependent facts): ' + source['path'])
    facts = json.loads((ROOT / index['facts']).read_text(encoding='utf-8'))
    rows = facts + index['hardware_versions'] + index['components'] + index['connections']
    ids = set()
    for row in rows:
        if row['id'] in ids or row['status'] not in STATUSES:
            raise SystemExit('Duplicate ID or unsupported status: ' + row['id'])
        ids.add(row['id'])
        if row['status'] == 'document_confirmed' and not row.get('evidence'):
            raise SystemExit('Missing evidence: ' + row['id'])
        for evidence in row.get('evidence', []):
            if evidence['source_id'] not in sources or not evidence.get('locator'):
                raise SystemExit('Invalid evidence: ' + row['id'])
            path = ROOT / sources[evidence['source_id']]['path']
            if path.suffix in ('.md', '.txt', '.json', '.c', '.h', '.def', '.py'):
                if evidence['locator'] not in path.read_text(encoding='utf-8'):
                    raise SystemExit('Locator no longer exists: ' + row['id'])
    if args.refresh:
        INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Knowledge OK: {len(sources)} sources, {len(rows)} evidence records.')


if __name__ == '__main__':
    main()
