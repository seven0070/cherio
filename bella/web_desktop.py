"""Local-only desktop bridge for the user's Grok Mirror frontend.

The browser UI never receives a tool-capable agent. It calls a random loopback port
with a per-launch session token; every effect is checked here. No cloud chat store.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import uuid
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .core import Store, local_ollama
from .desktop import VoiceCapture, local_models
from .actions import approve

MAX_BODY = 8_192


def assets_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'bella_frontend'
    return Path(__file__).resolve().parents[1] / 'frontend' / 'dist'


class Bridge:
    def __init__(self, *, data=None, checkout=None, asset_dir=None, model=None):
        self.data = Path(data or os.environ.get('BELLA_DB', '~/.cheerio/bella.sqlite3')).expanduser()
        self.checkout = Path(checkout or Path(__file__).resolve().parents[1])
        self.assets = Path(asset_dir or assets_path()).resolve()
        self.token = secrets.token_urlsafe(32)
        self.model = model or ''
        self.voice = None
        self.voice_lock = threading.Lock()
        with Store(self.data) as _startup_store:
            pass # Recover abandoned running tasks once, not on every API request.
        self.task_lock = threading.Lock()
        self.chat_lock = threading.Lock()

    def store(self):
        return Store(self.data, recover=False)

    def chat_db(self):
        self.data.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.data)
        db.execute('CREATE TABLE IF NOT EXISTS local_chats (id TEXT PRIMARY KEY, title TEXT NOT NULL, messages TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        return db

    def state(self):
        names = local_models()
        with self.store() as store:
            tasks = store.list_tasks()
        if self.model not in names:
            self.model = names[0] if len(names) == 1 else ''
        return {'tasks': tasks, 'models': names, 'selected_model': self.model,
                'status': 'Local preview · no external tools enabled', 'handoff_available': not getattr(sys, 'frozen', False)}

    def action(self, name, data):
        if name == 'state':
            try:
                return self.state()
            except Exception:
                with self.store() as store:
                    tasks = store.list_tasks()
                return {'tasks': tasks, 'models': [], 'selected_model': '',
                        'status': 'Ollama is offline. Start it and refresh models.', 'handoff_available': not getattr(sys, 'frozen', False)}
        if name == 'model/select':
            candidate = data.get('model', '')
            names = local_models()
            if candidate not in names:
                raise ValueError('Choose an installed local model')
            self.model = candidate
            return self.state()
        if name == 'cheerio/answer':
            text, model = data.get('text', ''), data.get('model', '')
            mode = data.get('mode')
            if mode not in ('Fast', 'Think'):
                raise ValueError('Unknown reasoning mode')
            if not isinstance(text, str) or not 0 < len(text.strip()) <= 4000:
                raise ValueError('Question must contain 1-4000 characters')
            if model not in local_models():
                raise ValueError('Choose an installed local Ollama model')
            prompt = ("You are Cheerio, a local reasoning assistant with no tools. Sanath is your owner and boss. Bella is the primary assistant, and you are her assistant; Sanath can direct you directly. Answer directly and concisely. "
                      if mode == 'Fast' else
                      "You are Cheerio, a local reasoning assistant with no tools. Sanath is your owner and boss. Bella is the primary assistant, and you are her assistant; Sanath can direct you directly. Think carefully, consider possible mistakes, then answer clearly. ")
            answer = local_ollama(prompt + text, [], model=model)
            return {'answer': answer}
        if name == 'chat':
            text = data.get('text', '')
            model = data.get('model', '')
            if not isinstance(text, str) or not 0 < len(text.strip()) <= 4000:
                raise ValueError('Message must contain 1-4000 characters')
            if model not in local_models():
                raise ValueError('Choose an installed local Ollama model')
            with self.store() as store:
                notes = store.notes()
            answer = local_ollama(text, notes, model=model)
            if data.get('speak') is True:
                from .voice import say
                def safe_say():
                    try: say(answer)
                    except Exception: pass
                threading.Thread(target=safe_say, daemon=True).start()
            return {'answer': answer}
        if name == 'chats/list':
            with self.chat_db() as db:
                rows = db.execute('SELECT id,title,messages,pinned FROM local_chats ORDER BY created_at DESC').fetchall()
            return {'chats': [dict(id=r[0], title=r[1], messages=json.loads(r[2]), pinned=bool(r[3])) for r in rows]}
        if name == 'chats/save':
            ident, title, messages = data.get('id'), data.get('title'), data.get('messages')
            if not isinstance(title, str) or not 0 < len(title) <= 100 or not isinstance(messages, list) or len(messages) > 500:
                raise ValueError('Invalid chat')
            if any(not isinstance(m, dict) or m.get('role') not in ('user','assistant') or not isinstance(m.get('content'), str) or len(m['content']) > 8000 for m in messages):
                raise ValueError('Invalid chat message')
            payload = json.dumps(messages)
            if len(payload) > 250_000:
                raise ValueError('Chat too large')
            with self.chat_lock, self.chat_db() as db:
                if ident:
                    result = db.execute('UPDATE local_chats SET title=?,messages=? WHERE id=?', (title, payload, ident))
                    if not result.rowcount:
                        raise ValueError('Unknown chat')
                else:
                    ident = uuid.uuid4().hex
                    db.execute('INSERT INTO local_chats(id,title,messages,pinned) VALUES (?,?,?,0)', (ident,title,payload))
            return {'id': ident}
        if name in ('chats/delete','chats/pin','chats/rename'):
            ident = data.get('id')
            if not isinstance(ident, str) or len(ident) > 64:
                raise ValueError('Invalid chat ID')
            with self.chat_lock, self.chat_db() as db:
                if name == 'chats/delete':
                    result = db.execute('DELETE FROM local_chats WHERE id=?', (ident,))
                elif name == 'chats/pin':
                    result = db.execute('UPDATE local_chats SET pinned=? WHERE id=?', (int(data.get('pinned') is True), ident))
                else:
                    title = data.get('title')
                    if not isinstance(title, str) or not 0 < len(title.strip()) <= 100:
                        raise ValueError('Invalid chat title')
                    result = db.execute('UPDATE local_chats SET title=? WHERE id=?', (title.strip(), ident))
                if not result.rowcount:
                    raise ValueError('Unknown chat')
            return {'ok': True}
        if name == 'task/propose':
            if getattr(sys, 'frozen', False):
                raise ValueError('Cheerio task handoff requires a Python source install; this packaged app cannot propose tasks')
            goal = data.get('goal', '')
            if not isinstance(goal, str):
                raise ValueError('Invalid task goal')
            with self.store() as store:
                task = store.task(store.propose(goal))
            return {'task': task}
        if name == 'task/reject':
            with self.store() as store:
                store.transition(data.get('id', ''), 'pending', 'cancelled')
            return {'ok': True}
        if name == 'task/approve':
            if getattr(sys, 'frozen', False):
                raise ValueError('Cheerio task handoff requires a Python source install; the packaged app cannot run it yet')
            # Serializes approval against concurrent clicks. The store transition is atomic.
            with self.task_lock:
                with self.store() as store:
                    return {'result': approve(store, data.get('id', ''), self.checkout)}
        if name == 'mic/start':
            with self.voice_lock:
                if self.voice is not None:
                    raise ValueError('Microphone is already recording')
                capture = VoiceCapture()
                capture.start()
                self.voice = capture
            return {'ok': True}
        if name == 'mic/stop':
            with self.voice_lock:
                if self.voice is None:
                    raise ValueError('Microphone is not recording')
                capture, self.voice = self.voice, None
            return {'text': capture.stop()} # only staged in composer, never submitted
        raise ValueError('Unknown local action')


def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                self.send_error(403); return
            path = unquote(urlsplit(self.path).path)
            if path == '/':
                path = '/index.html'
            target = (bridge.assets / path.lstrip('/')).resolve()
            if not target.is_relative_to(bridge.assets) or not target.is_file():
                self.send_error(404)
                return
            content_type = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                            '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
                            '.woff2': 'font/woff2'}.get(target.suffix, 'application/octet-stream')
            content = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            if not self.path.startswith('/api/') or '?' in self.path:
                self.send_error(404); return
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                self.send_error(403); return
            origin = self.headers.get('Origin')
            expected = f'http://127.0.0.1:{self.server.server_port}'
            if origin not in (None, expected) or self.headers.get('X-Bella-Session') != bridge.token:
                self.send_error(403); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= (300_000 if self.path == '/api/chats/save' else MAX_BODY):
                    raise ValueError('Request too large')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Invalid request')
                result = bridge.action(self.path[5:], data)
                status = 200
            except (ValueError, KeyError, RuntimeError, OSError) as exc:
                status, result = 400, {'error': str(exc)[:250]}
            except Exception:
                status, result = 500, {'error': 'Local action failed; inspect task state before retrying'}
            body = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bella + Cheerio local desktop (Grok Mirror frontend)')
    parser.add_argument('--model', default='')
    args = parser.parse_args(argv)
    bridge = Bridge(model=args.model)
    if not (bridge.assets / 'index.html').is_file():
        print('Frontend not built. In frontend/, run npm ci then npm run build.', file=sys.stderr)
        return 1
    try:
        import webview
    except ImportError:
        print('Install pywebview for the desktop window (pip install pywebview).', file=sys.stderr)
        return 1
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        webview.create_window('Bella + Cheerio', f'http://127.0.0.1:{server.server_port}/?session={bridge.token}', width=1200, height=800, min_size=(900, 650))
        webview.start()
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
