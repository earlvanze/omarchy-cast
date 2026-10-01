"""Serve only the selected video to the selected LAN receiver."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re
import threading

STATE = Path('@HOME@/.local/state/video-cast')
HOST = '@LAN_IP@'
PORT = 18794

def byte_range(value, size):
    if size <= 0:
        raise ValueError('Empty file')
    if value is None:
        return 0, size - 1
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
    if not match or not any(match.groups()):
        raise ValueError('Invalid byte range')
    first, last = match.groups()
    if not first:
        if int(last) <= 0:
            raise ValueError('Invalid suffix')
        return max(0, size - int(last)), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise ValueError('Unsatisfiable range')
    return start, end

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_file(False)

    def do_GET(self):
        self.send_file(True)

    def send_file(self, body):
        try:
            target = json.loads((STATE/'target.json').read_text())['ip']
        except (OSError, ValueError, KeyError):
            self.send_error(503)
            return
        if self.client_address[0] not in (target, HOST) or self.path != '/tv.mp4':
            self.send_error(404)
            return
        try:
            media = (STATE/'active.mp4').open('rb')
        except OSError:
            self.send_error(404)
            return
        with media:
            media.seek(0, 2)
            size = media.tell()
            requested = self.headers.get('Range')
            try:
                start, end = byte_range(requested, size)
            except ValueError:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            self.send_response(206 if requested else 200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end - start + 1))
            if requested:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('transferMode.dlna.org', 'Streaming')
            self.end_headers()
            if body:
                try:
                    media.seek(start)
                    left = end - start + 1
                    while left:
                        data = media.read(min(left, 1024 * 1024))
                        if not data:
                            break
                        self.wfile.write(data)
                        left -= len(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

if __name__ == '__main__':
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    timer = threading.Timer(14400, server.shutdown)
    timer.daemon = True
    timer.start()
    try:
        server.serve_forever()
    finally:
        timer.cancel()
        server.server_close()
