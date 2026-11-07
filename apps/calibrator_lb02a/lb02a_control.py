"""Loopback interface for the viewer that owns the ESP32 serial port."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from threading import Thread


def start_control(port, state, press):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload, kind="application/json"):
            if kind == "application/json":
                payload = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            frame, status = state()
            if self.path == "/state":
                self.respond(200, status)
            elif self.path == "/frame.png" and frame is not None:
                stream = BytesIO()
                frame.save(stream, format="PNG")
                self.respond(200, stream.getvalue(), "image/png")
            else:
                self.respond(404, {"error": "No frame or unknown path"})

        def do_POST(self):
            if self.path != "/key":
                self.respond(404, {"error": "Unknown path"})
                return
            if self.headers.get("Origin") or self.headers.get_content_type() != "application/json":
                self.respond(403, {"error": "Use a local JSON client"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100:
                    raise ValueError
                key = json.loads(self.rfile.read(length))["key"]
                if type(key) is not int or key not in range(1, 17) or key == 13:
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                self.respond(400, {"error": "Invalid key"})
                return
            accepted = press(key)
            self.respond(202 if accepted else 409, {"queued": accepted, "key": key})

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server
