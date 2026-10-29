"""Loopback dashboard with a genuine Python simulator and allowlisted downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .evidence import ROOT, build_evidence, read_json

WEB = Path(__file__).parent / 'web'


class Application:
    def __init__(self):
        self.evidence = build_evidence()
        self.allowed = {r['path'] for r in self.evidence['artifacts']}
        self.fingerprints = {r['path']: r['sha256'] for r in self.evidence['artifacts']}
        self.jobs = {}
        self.lock = threading.Lock()
        self.worker = threading.Lock()

    def run(self, identifier, request):
        from .simulation import simulate
        with self.worker:
            try:
                spec = next(r for r in self.evidence['evaluation_manifest'] if r['id'] == request['episode_id'])
                for controller in request['controllers']:
                    def update(elapsed, duration, trace):
                        with self.lock:
                            self.jobs[identifier].update(current_controller=controller,
                                                        elapsed_s=elapsed, duration_s=duration,
                                                        preview=trace[-1])
                    with self.lock:
                        self.jobs[identifier].update(current_controller=controller, elapsed_s=0, preview=None)
                    result = simulate(spec, controller, request['shield'], request['training_seed'], update)
                    with self.lock:
                        self.jobs[identifier]['results'].append(result)
                with self.lock:
                    self.jobs[identifier]['status'] = 'complete'
                    serialized = json.dumps(self.jobs[identifier], indent=2, allow_nan=False)
                directory = ROOT / 'report/dashboard/runs'
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f'{identifier}.json').write_text(serialized, encoding='utf-8')
            except Exception as exc:
                with self.lock:
                    self.jobs[identifier].update(status='failed', error=f'{type(exc).__name__}: {exc}')


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, data, content_type, code=200, filename=None):
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, value, code=200):
            self.send_bytes(json.dumps(value, allow_nan=False).encode(), 'application/json; charset=utf-8', code)

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.valid_host():
                return self.send_json({'error': 'Invalid host'}, 403)
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == '/api/health':
                return self.send_json(dict(backend='python', simulation='existing BTMSEnv',
                                           persistence='local report/dashboard/runs', training=False))
            if parsed.path == '/api/evidence':
                return self.send_json(app.evidence)
            if parsed.path == '/api/run':
                with app.lock:
                    job = app.jobs.get(query.get('id', [''])[0])
                    return self.send_json(job if job else {'error': 'Unknown run'}, 200 if job else 404)
            if parsed.path == '/api/artifact':
                name = query.get('path', [''])[0]
                if name not in app.allowed:
                    return self.send_json({'error': 'Artifact is not in the evidence catalog'}, 404)
                path = ROOT / name
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != app.fingerprints[name]:
                    return self.send_json({'error': 'Artifact changed since inspection. Restart the dashboard to rebuild its evidence snapshot.'}, 409)
                return self.send_bytes(data, mimetypes.guess_type(path.name)[0] or 'application/octet-stream',
                                       filename=path.name)
            names = {'/': 'index.html', '/index.html': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js'}
            if parsed.path in names:
                path = WEB / names[parsed.path]
                return self.send_bytes(path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'text/plain')
            self.send_json({'error': 'Not found'}, 404)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('Origin') not in (None, f'http://{self.headers.get("Host")}'):
                return self.send_json({'error': 'Same-origin requests only'}, 403)
            if urlparse(self.path).path != '/api/runs':
                return self.send_json({'error': 'Not found'}, 404)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                controllers = data.get('controllers')
                if not isinstance(controllers, list) or not 1 <= len(controllers) <= 2 or len(set(controllers)) != len(controllers):
                    raise ValueError('Choose one or two different controllers')
                if any(c not in ('pid', 'null', 'bangbang', 'mpc', 'ppo', 'sac', 'td3') for c in controllers):
                    raise ValueError('Unknown controller')
                if data.get('episode_id') not in {r['id'] for r in app.evidence['evaluation_manifest']}:
                    raise ValueError('Unknown evaluation episode')
                if type(data.get('shield')) is not bool or type(data.get('training_seed')) is not int or data['training_seed'] not in range(5):
                    raise ValueError('Invalid shield or training seed')
                with app.lock:
                    if any(job['status'] == 'running' for job in app.jobs.values()):
                        return self.send_json({'error': 'A simulation is already running'}, 409)
                    identifier = uuid.uuid4().hex
                    app.jobs[identifier] = dict(id=identifier, status='running', request=data, results=[])
                threading.Thread(target=app.run, args=(identifier, data), daemon=True).start()
                self.send_json({'id': identifier}, 202)
            except (ValueError, TypeError, KeyError) as exc:
                self.send_json({'error': str(exc)}, 400)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    app = Application()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(app))
    print(f'RL Battery Lab: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
