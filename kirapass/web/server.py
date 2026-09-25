"""The local web server: one page, four steps, all the answers as JSON.

The tool is a *backend only*. It prints a link like
`http://127.0.0.1:8770/` and everything happens in the browser - which is why
it works the same on Windows, Linux, Android (Termux/Pydroid) and macOS, and
why you can answer the questions with taps instead of typing in a terminal.

Security of the UI itself: it only ever answers on the machine it runs on
unless the user explicitly opens it to the LAN (`--host 0.0.0.0`), and in that
case a one-time token is required for every request.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .. import config, engine, portals, store, verify
from ..httpclient import Session
from ..version_helpers import package_dir

STATIC = package_dir("web")


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class Job:
    def __init__(self, kind: str, fn):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.state = "running"
        self.result = None
        self.error = ""
        self.started = time.time()
        self.finished = 0.0
        self._fn = fn

    def run(self):
        try:
            self.result = self._fn()
            self.state = "done"
        except Exception as exc:                          # noqa: BLE001
            import traceback
            self.error = f"{type(exc).__name__}: {exc}"
            self.state = "error"
            self.result = {"trace": traceback.format_exc()[-1200:]}
        finally:
            self.finished = time.time()

    def as_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "state": self.state,
                "result": self.result, "error": self.error,
                "elapsed": round((self.finished or time.time()) - self.started, 1)}


class KiraServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        """Bind without socket.getfqdn(): that lookup can hang for seconds on
        a machine with a slow resolver, and we do not need the name at all."""
        import socketserver
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port

    def __init__(self, address, handler, token: str = ""):
        super().__init__(address, handler)
        self.token = token or ""
        self.store = store.Store()
        self.engine = engine.Engine(self.store)
        self.jobs = {}
        self.jobs_lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=2,
                                       thread_name_prefix="kirapass-job")
        self.started = time.time()

    # -- jobs ------------------------------------------------------------
    def submit(self, kind: str, fn) -> Job:
        job = Job(kind, fn)
        with self.jobs_lock:
            self.jobs[job.id] = job
            stale = sorted(self.jobs.values(), key=lambda j: j.started)[:-20]
            for old in stale:
                self.jobs.pop(old.id, None)
        self.pool.submit(job.run)
        return job

    def job(self, job_id: str):
        with self.jobs_lock:
            return self.jobs.get(job_id)


class Handler(BaseHTTPRequestHandler):
    server_version = f"{config.APP_NAME}/{config.VERSION}"
    protocol_version = "HTTP/1.1"

    # -- plumbing --------------------------------------------------------
    def log_message(self, fmt, *args):        # keep the console clean
        if os.environ.get("KIRAPASS_DEBUG"):
            super().log_message(fmt, *args)

    def _send(self, body: bytes, code=200, ctype="application/json; charset=utf-8",
              extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        self._send(_json_bytes(obj), code)

    def _error(self, message, code=400, **extra):
        self._json({"ok": False, "error": message, **extra}, code)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _authorized(self) -> bool:
        host = self.client_address[0]
        if host in ("127.0.0.1", "::1", "localhost"):
            return True
        if not self.server.token:
            return True
        query = parse_qs(urlsplit(self.path).query)
        given = (self.headers.get("X-KiraPass-Token")
                 or (query.get("token") or [""])[0])
        # constant time: a token compared with == can be recovered byte by
        # byte from the response time
        return hmac.compare_digest(given or "", self.server.token)

    # -- routing ---------------------------------------------------------
    def do_GET(self):
        route = urlsplit(self.path).path
        if route in ("/", "/index.html"):
            return self._static("ui.html", "text/html; charset=utf-8")
        if route == "/ui.js":
            return self._static("ui.js", "application/javascript; charset=utf-8")
        if route == "/ui.css":
            return self._static("ui.css", "text/css; charset=utf-8")
        if route == "/favicon.ico":
            return self._send(b"", 204, "image/x-icon")
        if not self._authorized():
            return self._error("unauthorized", 401)
        try:
            return self._api_get(route, parse_qs(urlsplit(self.path).query))
        except Exception as exc:                          # noqa: BLE001
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def do_POST(self):
        if not self._authorized():
            return self._error("unauthorized", 401)
        route = urlsplit(self.path).path
        try:
            return self._api_post(route, self._body())
        except Exception as exc:                          # noqa: BLE001
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def _static(self, name: str, ctype: str):
        path = os.path.join(STATIC, name)
        try:
            with open(path, "rb") as fh:
                return self._send(fh.read(), 200, ctype)
        except OSError:
            return self._send(b"missing asset", 404, "text/plain; charset=utf-8")

    # -- GET endpoints ---------------------------------------------------
    def _api_get(self, route, query):
        srv = self.server
        if route == "/api/meta":
            return self._json({
                "ok": True, "app": config.APP_NAME, "version": config.VERSION,
                "lang": srv.store.get_setting("lang", "ar"),
                "steps": ["scan", "format", "run", "results"],
                "charsets": store.CHARSETS,
                "pass_modes": list(store.PASS_MODES),
                "defaults": {
                    "threads": config.DEFAULT_THREADS,
                    "attempts": config.DEFAULT_ATTEMPTS,
                    "delay_ms": config.DEFAULT_DELAY_MS,
                },
                "presets": [
                    {"id": "safe", "threads": 4, "attempts": 500, "delay_ms": 60},
                    {"id": "normal", "threads": 12, "attempts": 2000, "delay_ms": 0},
                    {"id": "fast", "threads": 40, "attempts": 10000, "delay_ms": 0},
                ],
                "cache": srv.store.cache_info(),
                "data_dir": config.DATA_DIR,
                "profiles": [_profile_brief(p) for p in srv.store.all()],
                "license": "authorized_use_only",
            })
        if route == "/api/profiles":
            return self._json({"ok": True,
                               "profiles": [_profile_brief(p) for p in srv.store.all()]})
        if route == "/api/profiles/get":
            name = (query.get("name") or [""])[0]
            prof = srv.store.get(name)
            if not prof:
                return self._error("profile_not_found", 404)
            return self._json({"ok": True, "profile": prof,
                               "preview": store.sample_cards(prof, 3),
                               "space": store.space_size(prof),
                               "problems": store.validate(prof)})
        if route == "/api/run/status":
            since = int((query.get("since") or ["0"])[0] or 0)
            status = srv.engine.status()
            events = srv.engine.events_since(since)
            return self._json({"ok": True, "status": status, "events": events})
        if route == "/api/job":
            job = srv.job((query.get("id") or [""])[0])
            if not job:
                return self._error("job_not_found", 404)
            return self._json({"ok": True, "job": job.as_dict()})
        if route == "/api/review":
            return self._json({"ok": True, "items": srv.store.list_review()})
        if route == "/api/review/file":
            name = (query.get("name") or [""])[0]
            content = srv.store.read_review(name)
            if not content:
                return self._error("review_file_not_found", 404)
            return self._send(content.encode("utf-8", "replace"), 200,
                              "text/html; charset=utf-8")
        if route == "/api/cache":
            return self._json({"ok": True, "cache": srv.store.cache_info()})
        if route == "/api/report":
            name = (query.get("name") or [""])[0]
            path = os.path.join(config.RUN_DIR, os.path.basename(name))
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return self._send(fh.read().encode("utf-8"), 200,
                                      "application/json; charset=utf-8")
            except OSError:
                return self._error("report_not_found", 404)
        if route == "/api/reports":
            try:
                names = sorted(os.listdir(config.RUN_DIR), reverse=True)[:50]
            except OSError:
                names = []
            return self._json({"ok": True, "reports": names})
        return self._error("not_found", 404)

    # -- POST endpoints --------------------------------------------------
    def _api_post(self, route, data):
        srv = self.server
        if route == "/api/scan":
            return self._scan(data)
        if route == "/api/format/preview":
            return self._preview(data)
        if route == "/api/profiles/save":
            prof = store.migrate(data.get("profile") or {})
            problems = store.validate(prof)
            hard = [p for p in problems if p != "space_is_astronomically_big"]
            if hard:
                return self._json({"ok": False, "problems": problems}, 400)
            saved = srv.store.put(prof)
            return self._json({"ok": True, "profile": saved,
                               "profiles": [_profile_brief(p) for p in srv.store.all()]})
        if route == "/api/profiles/delete":
            ok = srv.store.delete(data.get("name", ""))
            return self._json({"ok": ok,
                               "profiles": [_profile_brief(p) for p in srv.store.all()]})
        if route == "/api/diagnose":
            prof = store.migrate(data.get("profile") or {})
            threads = int(data.get("threads") or 0)
            job = srv.submit("diagnose",
                             lambda: engine.diagnose(prof, threads=threads))
            return self._json({"ok": True, "job": job.as_dict()})
        if route == "/api/calibrate":
            prof = store.migrate(data.get("profile") or {})
            known = (data.get("known_card") or "").strip()
            keyword = (data.get("keyword") or "").strip()
            job = srv.submit("calibrate",
                             lambda: engine.calibrate(prof, known_card=known,
                                                      keyword=keyword).as_dict())
            return self._json({"ok": True, "job": job.as_dict()})
        if route == "/api/run/start":
            prof = store.migrate(data.get("profile") or {})
            result = srv.engine.start(
                prof,
                attempts=int(data.get("attempts") or config.DEFAULT_ATTEMPTS),
                threads=int(data.get("threads") or config.DEFAULT_THREADS),
                delay_ms=int(data.get("delay_ms") or 0),
                keyword=(data.get("keyword") or "").strip(),
                known_card=(data.get("known_card") or "").strip(),
                verify_after=bool(data.get("verify", True)),
                auto_stop=bool(data.get("auto_stop", True)),
                resume=data.get("resume", True) is not False)
            return self._json(result, 200 if result.get("ok") else 400)
        if route == "/api/run/stop":
            srv.engine.stop("user_stop")
            return self._json({"ok": True})
        if route == "/api/cache/clear":
            scope = data.get("scope", "temp")
            if scope not in ("temp", "results", "profiles", "all"):
                return self._error("bad_scope", 400)
            freed = srv.store.clear_cache(scope)
            if scope in ("profiles", "all"):
                srv.store = store.Store()
                srv.engine.store = srv.store
            return self._json({"ok": True, "cleared": freed,
                               "cache": srv.store.cache_info()})
        if route == "/api/settings":
            if "lang" in data:
                srv.store.set_setting("lang", str(data["lang"])[:5])
            return self._json({"ok": True, "settings": srv.store.settings})
        if route == "/api/quit":
            # phone users (Termux/Pydroid) have no Ctrl+C: let the page stop
            # the tool.  The shutdown runs from its own thread - calling it
            # from inside serve_forever would deadlock.
            threading.Timer(0.4, srv.shutdown).start()
            return self._json({"ok": True, "shutting_down": True})
        return self._error("not_found", 404)

    # -- helpers ---------------------------------------------------------
    def _scan(self, data) -> None:
        url = (data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            url = "http://" + url.lstrip("/")
        session = Session(allow_redirects=True)
        t0 = time.time()
        try:
            try:
                portal = portals.discover(session, url)
            except Exception as exc:                      # noqa: BLE001
                from ..errors import classify
                err = classify(exc, url)
                return self._json({"ok": False, "error": f"net_{err.kind}",
                                   "detail": err.text[:200],
                                   "hint": err.short}, 200)
            internet = verify.probe_internet(session)
            return self._json({"ok": True, "portal": portal.as_dict(),
                               "internet": internet,
                               "ms": round((time.time() - t0) * 1000)})
        finally:
            session.close()

    def _preview(self, data) -> None:
        prof = store.migrate(data.get("profile") or {})
        return self._json({"ok": True,
                           "space": store.space_size(prof),
                           "variable_len": store.variable_len(prof),
                           "samples": store.sample_cards(prof, 4),
                           "problems": store.validate(prof),
                           "charset_size": len(set(prof.get("charset") or ""))})


def _profile_brief(p: dict) -> dict:
    return {"name": p.get("name", ""), "login_url": p.get("login_url", ""),
            "method": p.get("method", "post"),
            "cards": f"{p.get('prefix','')}[{store.variable_len(p)} with "
                     f"{len(set(p.get('charset') or ''))} symbols]"
                     f"{p.get('suffix','')}",
            "space": store.space_size(p),
            "covered": p.get("space_pos", 0),
            "pass_mode": p.get("pass_mode", ""),
            "dst_value": p.get("dst_value", ""),
            "success_words": p.get("success_words", [])[:6]}


def serve(host: str = "127.0.0.1", port: int = 8770, token: str = "",
          on_ready=None) -> None:
    httpd = KiraServer((host, port), Handler, token=token)
    real_port = httpd.server_address[1]
    if on_ready:
        on_ready(real_port, httpd.token)
    try:
        httpd.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.pool.shutdown(wait=False)
        httpd.server_close()
