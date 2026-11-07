"""Command-line client used by automation and the assistant; no GUI clicking required."""
import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


def request(route, data=None, output=None):
    connection_file = Path(__file__).resolve().parent / '.runtime' / 'api.json'
    if not connection_file.exists():
        raise RuntimeError('Сначала запустите стендовую программу.')
    connection = json.loads(connection_file.read_text(encoding='utf-8'))
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(connection['url'] + route, data=body,
        headers={'Authorization': 'Bearer ' + connection['token'], 'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=45) as response:
            result = response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode('utf-8')) from error
    if output:
        target = Path(output).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result)
        return {'saved': str(target)}
    return json.loads(result)


def main():
    parser = argparse.ArgumentParser(description='Управление программой «Стенд · Видео и тепло»')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('state', 'devices', 'save', 'clear-markers'):
        sub.add_parser(command)
    for command in ('temperature', 'cursor', 'mark'):
        p = sub.add_parser(command)
        p.add_argument('x', type=float, help='0..1 по ширине термограммы')
        p.add_argument('y', type=float, help='0..1 по высоте термограммы')
        if command == 'mark':
            p.add_argument('--name')
    p = sub.add_parser('frame')
    p.add_argument('role', choices=['color', 'thermal'])
    p.add_argument('output')
    p.add_argument('--full', action='store_true')
    p.add_argument('--raw', action='store_true')
    p = sub.add_parser('connect')
    p.add_argument('role', choices=['color', 'thermal'])
    p.add_argument('device')
    p.add_argument('--mode')
    for command in ('settings', 'calibrate'):
        p = sub.add_parser(command)
        p.add_argument('json_file')
    args = parser.parse_args()
    if args.command in ('state', 'devices'):
        result = request('/api/' + args.command)
    elif args.command == 'save':
        result = request('/api/save', {})
    elif args.command == 'clear-markers':
        result = request('/api/markers/remove', {})
    elif args.command == 'temperature':
        result = request('/api/temperature?' + urllib.parse.urlencode({'x': args.x, 'y': args.y}))
    elif args.command in ('cursor', 'mark'):
        data = {'x': args.x, 'y': args.y}
        if args.command == 'mark' and args.name:
            data['name'] = args.name
        result = request('/api/cursor' if args.command == 'cursor' else '/api/markers', data)
    elif args.command == 'frame':
        result = request(f'/api/frame/{args.role}.png?full={int(args.full)}&annotated={int(not args.raw)}', output=args.output)
    elif args.command == 'connect':
        result = request('/api/connect', {'role': args.role, 'device': args.device, 'mode': args.mode})
    elif args.command == 'settings':
        result = request('/api/settings', json.loads(Path(args.json_file).read_text(encoding='utf-8')))
    else:
        result = request('/api/calibration', {'pairs': json.loads(Path(args.json_file).read_text(encoding='utf-8'))})
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
