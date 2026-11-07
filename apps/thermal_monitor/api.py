"""Authenticated loopback control API; the desktop UI uses the same engine."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import logging
from pathlib import Path
import secrets
import socket
import threading
from urllib.parse import parse_qs, urlsplit

from imaging import png_bytes


class LoopbackServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        # Windows otherwise permits a second process to bind an already-used
        # address; requests could reach the wrong camera session.
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ApiServer:
    def __init__(self, engine, runtime_dir):
        self.engine = engine
        self.token = secrets.token_urlsafe(32)
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = 'BenchMonitor/1.0'

            def log_message(self, fmt, *args):
                logging.debug('API ' + fmt, *args)

            def _send(self, status, body, mime='application/json; charset=utf-8'):
                if not isinstance(body, bytes):
                    body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(body)

            def _auth(self):
                supplied = self.headers.get('Authorization', '')
                if not hmac.compare_digest(supplied, 'Bearer ' + owner.token):
                    self._send(401, {'error': 'Authorization: Bearer token is required.'})
                    return False
                return True

            def do_GET(self):
                url = urlsplit(self.path)
                if url.path == '/health':
                    self._send(200, {'app': 'bench-monitor', 'ok': True})
                    return
                if not self._auth():
                    return
                query = parse_qs(url.query)
                try:
                    if url.path == '/api/state':
                        self._send(200, owner.engine.state())
                    elif url.path == '/api/devices':
                        self._send(200, {'devices': owner.engine.devices(query.get('refresh') == ['1'])})
                    elif url.path == '/api/modes':
                        self._send(200, {'modes': owner.engine.modes(query['device'][0])})
                    elif url.path == '/api/temperature':
                        self._send(200, owner.engine.temperature(float(query['x'][0]), float(query['y'][0])))
                    elif url.path in ('/api/frame/color.png', '/api/frame/thermal.png'):
                        role = url.path.rsplit('/', 1)[1].split('.')[0]
                        image = owner.engine.frame(role, query.get('annotated') != ['0'], query.get('full') == ['1'])
                        self._send(200, png_bytes(image), 'image/png')
                    else:
                        self._send(404, {'error': 'Unknown endpoint'})
                except (ValueError, KeyError, TypeError) as error:
                    self._send(400, {'error': str(error)})
                except Exception as error:
                    logging.exception('API request failed')
                    self._send(500, {'error': str(error)})

            def do_POST(self):
                if not self._auth():
                    return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 <= size <= 65536:
                        self._send(413, {'error': 'Request too large'})
                        return
                    data = json.loads(self.rfile.read(size) or b'{}')
                    if not isinstance(data, dict):
                        raise ValueError('JSON object required')
                    route = urlsplit(self.path).path
                    engine = owner.engine
                    if route == '/api/connect':
                        result = engine.connect(data['role'], data['device'], data.get('mode'))
                    elif route == '/api/disconnect':
                        engine.disconnect(data['role'])
                        result = {'ok': True}
                    elif route == '/api/cursor':
                        result = engine.set_cursor(data['x'], data['y'])
                    elif route == '/api/markers':
                        result = engine.add_marker(data['x'], data['y'], data.get('name'))
                    elif route == '/api/markers/remove':
                        engine.remove_marker(data.get('id'))
                        result = {'ok': True}
                    elif route == '/api/calibration':
                        result = engine.set_calibration(data['pairs'])
                    elif route == '/api/calibration/clear':
                        engine.clear_calibration()
                        result = {'ok': True}
                    elif route == '/api/settings':
                        result = engine.update_settings(data)
                    elif route == '/api/save':
                        result = engine.save_pair()
                    else:
                        self._send(404, {'error': 'Unknown endpoint'})
                        return
                    self._send(200, result)
                except (ValueError, KeyError, TypeError) as error:
                    self._send(400, {'error': str(error)})
                except Exception as error:
                    logging.exception('API command failed')
                    self._send(500, {'error': str(error)})

        for port in range(18765, 18775):
            try:
                self.httpd = LoopbackServer(('127.0.0.1', port), Handler)
                break
            except OSError:
                continue
        else:
            raise RuntimeError('Не удалось открыть локальный интерфейс управления.')
        self.httpd.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.httpd.server_port}'
        self.connection_file = self.runtime_dir / 'api.json'
        self.connection_file.write_text(json.dumps({'url': self.url, 'token': self.token}, indent=2), encoding='utf-8')
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name='bench-api')
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
        self.connection_file.unlink(missing_ok=True)
