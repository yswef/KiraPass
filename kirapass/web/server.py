# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""The local web server: one page, four steps, all the answers as JSON.

The tool is a *backend only*. It prints a link like
`http://127.0.0.1:8770/` and everything happens in the browser - which is why
it works the same on Windows, Linux, Android (Termux/Pydroid) and macOS, and
why you can answer the questions with taps instead of typing in a terminal.

Security of the UI itself: it only ever answers on the machine it runs on
unless the user explicitly opens it to the LAN (`--host 0.0.0.0`), and in that
case a one-time token is required for every request.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import hmac  # استيراد الوحدة hmac من المكتبة
import json  # استيراد الوحدة json من المكتبة
import os  # استيراد الوحدة os من المكتبة
import threading  # استيراد الوحدة threading من المكتبة
import time  # استيراد الوحدة time من المكتبة
import uuid  # استيراد الوحدة uuid من المكتبة
from concurrent.futures import ThreadPoolExecutor  # استيراد ThreadPoolExecutor من الوحدة concurrent.futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # استيراد BaseHTTPRequestHandler, ThreadingHTTPServer من الوحدة http.server
from urllib.parse import parse_qs, urlsplit  # استيراد parse_qs, urlsplit من الوحدة urllib.parse

from .. import capture, config, engine, portals, store, verify  # استيراد capture, config, engine, portals, store, verify من الوحدة .
from ..httpclient import Session  # استيراد Session من الوحدة httpclient
from ..version_helpers import package_dir  # استيراد package_dir من الوحدة version_helpers

STATIC = package_dir("web")  # إسناد نتيجة استدعاء package_dir (معامل واحد) إلى STATIC


# تنقيح تقرير المعايرة: حذف card_hint وsample_cards وكل مفتاح يحوي سرّاً.
def _safe_calibration_report(value, profile, key=""):  # تعريف الدالة _safe_calibration_report(value, profile, key)
    """Redact card hints and sensitive URL/query material from report text."""  # نص توثيقي (docstring) يشرح ما يليه
    sensitive_names = {"card_hint", "sample_cards", "cookie", "cookies",  # إسناد مجموعة فريدة إلى sensitive_names
                       "token", "csrf", "challenge", "password", "pass_fixed",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                       "extra_fields"}  # تكملة قيمة المفتاح/العنصر السابق
    if isinstance(value, dict):  # شرط: نتيجة isinstance(value, dict)
        out = {}  # إسناد قاموس إلى out
        for name, item in value.items():  # دورة على value.items() باسم مجموعة
            low = str(name).lower()  # إسناد نتيجة استدعاء str(name).lower إلى low
            if low in sensitive_names or any(secret in low for secret in  # شرط مركّب (أو)
                                             ("cookie", "csrf", "token", "challenge")):  # تكملة تعريف متعدد الأسطر
                out[name] = "[REDACTED]"  # إسناد القيمة الثابتة out[name]
            else:  # مفتاح else في القاموس
                out[name] = _safe_calibration_report(item, profile, low)  # إسناد نتيجة استدعاء _safe_calibration_report (3 معاملات) إلى out[name]
        return out  # إرجاع out
    if isinstance(value, list):  # شرط: نتيجة isinstance(value, list)
        return [_safe_calibration_report(item, profile, key) for item in value]  # إرجاع اشتقاق قائمة
    if isinstance(value, str):  # شرط: نتيجة isinstance(value, str)
        if key in {"url", "login_url", "final_url", "location", "dst",  # شرط: key ضمن مجموعة فريدة
                   "dst_value"}:  # تكملة تعريف متعدد الأسطر
            return engine._safe_url_shape(value, profile)  # إرجاع engine._safe_url_shape(value, profile)
        if key == "text":  # شرط: key يساوي 'text'
            return "[REDACTED]"  # إرجاع '[REDACTED]'
    return value  # إرجاع value


def _json_bytes(obj) -> bytes:  # تعريف الدالة _json_bytes(obj) ترجع bytes
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")  # إرجاع json.dumps(obj, ensure_ascii=False).encode('utf-8')


class Job:  # تعريف الصنف Job
    def __init__(self, kind: str, fn):  # تعريف الدالة __init__(self, kind, fn)
        self.id = uuid.uuid4().hex[:12]  # إسناد uuid.uuid4().hex[] إلى self.id
        self.kind = kind  # إسناد kind إلى self.kind
        self.state = "running"  # إسناد القيمة الثابتة self.state
        self.result = None  # إسناد القيمة الثابتة self.result
        self.error = ""  # إسناد القيمة الثابتة self.error
        self.started = time.time()  # إسناد نتيجة استدعاء time.time إلى self.started
        self.finished = 0.0  # إسناد القيمة الثابتة self.finished
        self._fn = fn  # إسناد fn إلى self._fn

    def run(self):  # تعريف الدالة run(self)
        try:  # بدايةtry محمية (يليها except/finally)
            self.result = self._fn()  # إسناد نتيجة استدعاء self._fn إلى self.result
            self.state = "done"  # إسناد القيمة الثابتة self.state
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                          # noqa: BLE001
            import traceback  # استيراد الوحدة traceback من المكتبة
            self.error = f"{type(exc).__name__}: {exc}"  # بناء نص منسّق وإسناده إلى self.error
            self.state = "error"  # إسناد القيمة الثابتة self.state
            self.result = {"trace": traceback.format_exc()[-1200:]}  # إسناد قاموس إلى self.result
        finally:  # مفتاح finally في القاموس
            self.finished = time.time()  # إسناد نتيجة استدعاء time.time إلى self.finished

    def as_dict(self) -> dict:  # تعريف الدالة as_dict(self) ترجع dict
        return {"id": self.id, "kind": self.kind, "state": self.state,  # إرجاع قاموس
                "result": self.result, "error": self.error,  # مفتاح result في القاموس
                "elapsed": round((self.finished or time.time()) - self.started, 1)}  # مفتاح elapsed في القاموس


class KiraServer(ThreadingHTTPServer):  # تعريف الصنف KiraServer يرث من ThreadingHTTPServer
    daemon_threads = True  # إسناد القيمة الثابتة daemon_threads
    allow_reuse_address = True  # إسناد القيمة الثابتة allow_reuse_address

    def server_bind(self):  # تعريف الدالة server_bind(self)
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Bind without socket.getfqdn(): that lookup can hang for seconds on
        a machine with a slow resolver, and we do not need the name at all."""  # نهاية النص متعدد الأسطر
        import socketserver  # استيراد الوحدة socketserver من المكتبة
        socketserver.TCPServer.server_bind(self)  # استدعاء socketserver.TCPServer.server_bind (معامل واحد)
        host, port = self.server_address[:2]  # إسناد self.server_address[] إلى مجموعة
        self.server_name = host  # إسناد host إلى self.server_name
        self.server_port = port  # إسناد port إلى self.server_port

    def __init__(self, address, handler, token: str = ""):  # تعريف الدالة __init__(self, address, handler, token)
        super().__init__(address, handler)  # استدعاء super().__init__ (2 معاملات)
        self.token = token or ""  # دمج منطقي (أو) وإسناده إلى self.token
        self.store = store.Store()  # إسناد نتيجة استدعاء store.Store إلى self.store
        self.engine = engine.Engine(self.store)  # إسناد نتيجة استدعاء engine.Engine (معامل واحد) إلى self.engine
        self.jobs = {}  # إسناد قاموس إلى self.jobs
        self.jobs_lock = threading.Lock()  # إسناد نتيجة استدعاء threading.Lock إلى self.jobs_lock
        self.captures = capture.HUB  # إسناد capture.HUB إلى self.captures
        self.pool = ThreadPoolExecutor(max_workers=2,  # إسناد نتيجة استدعاء ThreadPoolExecutor (max_workers=…، thread_name_prefix=…) إلى self.pool
                                       thread_name_prefix="kirapass-job")  # المعامل المسمّى thread_name_prefix
        self.started = time.time()  # إسناد نتيجة استدعاء time.time إلى self.started

    # -- المهام ------------------------------------------------------------
    def submit(self, kind: str, fn) -> Job:  # تعريف الدالة submit(self, kind, fn) ترجع Job
        job = Job(kind, fn)  # إسناد نتيجة استدعاء Job (2 معاملات) إلى job
        with self.jobs_lock:  # سياق مُدار: self.jobs_lock
            self.jobs[job.id] = job  # إسناد job إلى self.jobs[job.id]
            stale = sorted(self.jobs.values(), key=lambda j: j.started)[:-20]  # إسناد sorted(self.jobs.values(), key=دالة مجهولة)[] إلى stale
            for old in stale:  # دورة على stale باسم old
                self.jobs.pop(old.id, None)  # استدعاء self.jobs.pop (2 معاملات)
        self.pool.submit(job.run)  # استدعاء self.pool.submit (معامل واحد)
        return job  # إرجاع job

    def job(self, job_id: str):  # تعريف الدالة job(self, job_id)
        with self.jobs_lock:  # سياق مُدار: self.jobs_lock
            return self.jobs.get(job_id)  # إرجاع self.jobs.get(job_id)


class Handler(BaseHTTPRequestHandler):  # تعريف الصنف Handler يرث من BaseHTTPRequestHandler
    server_version = f"{config.APP_NAME}/{config.VERSION}"  # بناء نص منسّق وإسناده إلى server_version
    protocol_version = "HTTP/1.1"  # إسناد القيمة الثابتة protocol_version

    # -- الأنابيب --------------------------------------------------------
    def log_message(self, fmt, *args):        # أبقِ الطرفية نظيفة
        if os.environ.get("KIRAPASS_DEBUG"):  # شرط: نتيجة os.environ.get('KIRAPASS_DEBUG')
            super().log_message(fmt, *args)  # استدعاء super().log_message (2 معاملات)

    def _send(self, body: bytes, code=200, ctype="application/json; charset=utf-8",  # تعريف الدالة _send(self, body, code, ctype, extra)
              extra=None):  # المعامل المسمّى extra
        self.send_response(code)  # استدعاء self.send_response (معامل واحد)
        self.send_header("Content-Type", ctype)  # استدعاء self.send_header (2 معاملات)
        self.send_header("Content-Length", str(len(body)))  # استدعاء self.send_header (2 معاملات)
        self.send_header("Cache-Control", "no-store")  # استدعاء self.send_header (2 معاملات)
        self.send_header("X-Content-Type-Options", "nosniff")  # استدعاء self.send_header (2 معاملات)
        self.send_header("Referrer-Policy", "no-referrer")  # استدعاء self.send_header (2 معاملات)
        for key, value in (extra or {}).items():  # دورة على extra أو قاموس.items() باسم مجموعة
            self.send_header(key, value)  # استدعاء self.send_header (2 معاملات)
        self.end_headers()  # استدعاء self.end_headers
        try:  # بدايةtry محمية (يليها except/finally)
            self.wfile.write(body)  # استدعاء self.wfile.write (معامل واحد)
        except (BrokenPipeError, ConnectionResetError):  # تكملة السطر السابق داخل القوس
            pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً

    def _json(self, obj, code=200):  # تعريف الدالة _json(self, obj, code)
        self._send(_json_bytes(obj), code)  # استدعاء self._send (2 معاملات)

    def _error(self, message, code=400, **extra):  # تعريف الدالة _error(self, message, code, **extra)
        self._json({"ok": False, "error": message, **extra}, code)  # استدعاء self._json (2 معاملات)

    def _body(self) -> dict:  # تعريف الدالة _body(self) ترجع dict
        try:  # بدايةtry محمية (يليها except/finally)
            length = int(self.headers.get("Content-Length") or 0)  # إسناد نتيجة استدعاء int (معامل واحد) إلى length
        except ValueError:  # تكملة السطر السابق داخل القوس
            return {}  # إرجاع قاموس
        if not length:  # شرط معكوس: ليس length
            return {}  # إرجاع قاموس
        raw = self.rfile.read(length)  # إسناد نتيجة استدعاء self.rfile.read (معامل واحد) إلى raw
        try:  # بدايةtry محمية (يليها except/finally)
            data = json.loads(raw.decode("utf-8"))  # إسناد نتيجة استدعاء json.loads (معامل واحد) إلى data
            return data if isinstance(data, dict) else {}  # إرجاع data إن isinstance(data, dict) وإلا قاموس
        except Exception:  # تكملة السطر السابق داخل القوس
            return {}  # إرجاع قاموس

    # العميل المحلي مسموح دائماً؛ وغيره يلزمه الرمز.
    # المقارنة بـhmac.compare_digest (زمن ثابت) حتى لا يُستعاد الرمز من زمن الرد.
    def _authorized(self) -> bool:  # تعريف الدالة _authorized(self) ترجع bool
        host = self.client_address[0]  # إسناد self.client_address[0] إلى host
        if host in ("127.0.0.1", "::1", "localhost"):  # شرط: host ضمن مجموعة
            return True  # إرجاع True
        if not self.server.token:  # شرط معكوس: ليس self.server.token
            return True  # إرجاع True
        query = parse_qs(urlsplit(self.path).query)  # إسناد نتيجة استدعاء parse_qs (معامل واحد) إلى query
        given = (self.headers.get("X-KiraPass-Token")  # دمج منطقي (أو) وإسناده إلى given
                 or (query.get("token") or [""])[0])  # تكملة السطر السابق داخل القوس
        # زمن ثابت: رمز يُقارن بـ== يمكن استعادته بايتاً
        # بايتاً من زمن الاستجابة
        return hmac.compare_digest(given or "", self.server.token)  # إرجاع hmac.compare_digest(given أو '', self.server.token)

    # -- التوجيه ---------------------------------------------------------
    # المسارات الثابتة (/ و/ui.js و/ui.css و/favicon.ico) تُخدم قبل التفويض عمداً
    # حتى تستطيع الصفحة أن تطلب الرمز. /capture/view يأتي بعد الفحص.
    def do_GET(self):  # تعريف الدالة do_GET(self)
        route = urlsplit(self.path).path  # إسناد urlsplit(self.path).path إلى route
        if route in ("/", "/index.html"):  # شرط: route ضمن مجموعة
            return self._static("ui.html", "text/html; charset=utf-8")  # إرجاع self._static('ui.html', 'text/html; charset=utf-8')
        if route == "/ui.js":  # شرط: route يساوي '/ui.js'
            return self._static("ui.js", "application/javascript; charset=utf-8")  # إرجاع self._static('ui.js', 'application/javascript; charset=utf-8')
        if route == "/ui.css":  # شرط: route يساوي '/ui.css'
            return self._static("ui.css", "text/css; charset=utf-8")  # إرجاع self._static('ui.css', 'text/css; charset=utf-8')
        if route == "/favicon.ico":  # شرط: route يساوي '/favicon.ico'
            return self._send(b"", 204, "image/x-icon")  # إرجاع self._send(b'', 204, 'image/x-icon')
        if not self._authorized():  # شرط معكوس: ليس self._authorized()
            return self._error("unauthorized", 401)  # إرجاع self._error('unauthorized', 401)
        if route == "/capture/view":  # شرط: route يساوي '/capture/view'
            return self._capture_view(parse_qs(urlsplit(self.path).query))  # إرجاع self._capture_view(parse_qs(urlsplit(self.path).query))
        try:  # بدايةtry محمية (يليها except/finally)
            return self._api_get(route, parse_qs(urlsplit(self.path).query))  # إرجاع self._api_get(route, parse_qs(urlsplit(self.path).query))
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                          # noqa: BLE001
            return self._error(f"{type(exc).__name__}: {exc}", 500)  # إرجاع self._error(نص منسّق (f-string), 500)

    def do_POST(self):  # تعريف الدالة do_POST(self)
        if not self._authorized():  # شرط معكوس: ليس self._authorized()
            return self._error("unauthorized", 401)  # إرجاع self._error('unauthorized', 401)
        route = urlsplit(self.path).path  # إسناد urlsplit(self.path).path إلى route
        try:  # بدايةtry محمية (يليها except/finally)
            return self._api_post(route, self._body())  # إرجاع self._api_post(route, self._body())
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                          # noqa: BLE001
            return self._error(f"{type(exc).__name__}: {exc}", 500)  # إرجاع self._error(نص منسّق (f-string), 500)

    def _static(self, name: str, ctype: str):  # تعريف الدالة _static(self, name, ctype)
        path = os.path.join(STATIC, name)  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى path
        try:  # بدايةtry محمية (يليها except/finally)
            with open(path, "rb") as fh:  # سياق مُدار: open(path, 'rb') باسم fh
                return self._send(fh.read(), 200, ctype)  # إرجاع self._send(fh.read(), 200, ctype)
        except OSError:  # تكملة السطر السابق داخل القوس
            return self._send(b"missing asset", 404, "text/plain; charset=utf-8")  # إرجاع self._send(b'missing asset', 404, 'text/plain; charset=utf-8')

    # -- نقاط GET ---------------------------------------------------
    def _api_get(self, route, query):  # تعريف الدالة _api_get(self, route, query)
        srv = self.server  # إسناد self.server إلى srv
        if route == "/api/meta":  # شرط: route يساوي '/api/meta'
            return self._json({  # إرجاع self._json(قاموس)
                "ok": True, "app": config.APP_NAME, "version": config.VERSION,  # مفتاح ok في القاموس
                "lang": srv.store.get_setting("lang", "ar"),  # مفتاح lang في القاموس
                "steps": ["start", "saved", "profile-review", "scan", "format", "run", "results"],  # مفتاح steps في القاموس
                "charsets": store.CHARSETS,  # مفتاح charsets في القاموس
                "pass_modes": list(store.PASS_MODES),  # مفتاح pass_modes في القاموس
                "defaults": {  # مفتاح defaults في القاموس
                    "threads": config.DEFAULT_THREADS,  # مفتاح threads في القاموس
                    "attempts": config.DEFAULT_ATTEMPTS,  # مفتاح attempts في القاموس
                    "delay_ms": config.DEFAULT_DELAY_MS,  # مفتاح delay_ms في القاموس
                    "connect_timeout": config.CONNECT_TIMEOUT,  # مفتاح connect_timeout في القاموس
                    "read_timeout": config.READ_TIMEOUT,  # مفتاح read_timeout في القاموس
                    "warn_space": config.WARN_SPACE,  # مفتاح warn_space في القاموس
                    "warn_threads": config.WARN_THREADS,  # مفتاح warn_threads في القاموس
                },  # إغلاق القوس المفتوح في السطر السابق
                "presets": [  # مفتاح presets في القاموس
                    {"id": "safe", "threads": 4, "attempts": 500, "delay_ms": 60},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                    {"id": "normal", "threads": 12, "attempts": 2000, "delay_ms": 0},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                    {"id": "fast", "threads": 40, "attempts": 10000, "delay_ms": 0},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                ],  # إغلاق القوس المفتوح في السطر السابق
                "settings": dict(srv.store.settings or {}),  # مفتاح settings في القاموس
                "cache": srv.store.cache_info(),  # مفتاح cache في القاموس
                "data_dir": config.DATA_DIR,  # مفتاح data_dir في القاموس
                "profiles": [_profile_brief(p) for p in srv.store.all()],  # مفتاح profiles في القاموس
                "license": "authorized_use_only",  # مفتاح license في القاموس
                "lan_open": self.server.server_address[0] not in (  # مفتاح lan_open في القاموس
                    "127.0.0.1", "localhost", "::1"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            })  # إغلاق القوس المفتوح في السطر السابق
        if route == "/api/profiles":  # شرط: route يساوي '/api/profiles'
            return self._json({"ok": True,  # إرجاع self._json(قاموس)
                               "profiles": [_profile_brief(p) for p in srv.store.all()]})  # مفتاح profiles في القاموس
        if route == "/api/profiles/get":  # شرط: route يساوي '/api/profiles/get'
            name = (query.get("name") or [""])[0]  # إسناد query.get('name') أو قائمة[0] إلى name
            prof = srv.store.get(name)  # إسناد نتيجة استدعاء srv.store.get (معامل واحد) إلى prof
            if not prof:  # شرط معكوس: ليس prof
                return self._error("profile_not_found", 404)  # إرجاع self._error('profile_not_found', 404)
            return self._json({"ok": True, "profile": prof,  # إرجاع self._json(قاموس)
                               "preview": store.sample_cards(prof, 3),  # مفتاح preview في القاموس
                               "space": store.space_size(prof),  # مفتاح space في القاموس
                               "problems": store.validate(prof)})  # مفتاح problems في القاموس
        if route == "/api/run/status":  # شرط: route يساوي '/api/run/status'
            since = int((query.get("since") or ["0"])[0] or 0)  # إسناد نتيجة استدعاء int (معامل واحد) إلى since
            status = srv.engine.status()  # إسناد نتيجة استدعاء srv.engine.status إلى status
            events = srv.engine.events_since(since)  # إسناد نتيجة استدعاء srv.engine.events_since (معامل واحد) إلى events
            return self._json({"ok": True, "status": status, "events": events})  # إرجاع self._json(قاموس)
        if route == "/api/job":  # شرط: route يساوي '/api/job'
            job = srv.job((query.get("id") or [""])[0])  # إسناد نتيجة استدعاء srv.job (معامل واحد) إلى job
            if not job:  # شرط معكوس: ليس job
                return self._error("job_not_found", 404)  # إرجاع self._error('job_not_found', 404)
            return self._json({"ok": True, "job": job.as_dict()})  # إرجاع self._json(قاموس)
        if route == "/api/review":  # شرط: route يساوي '/api/review'
            return self._json({"ok": True, "items": srv.store.list_review()})  # إرجاع self._json(قاموس)
        if route == "/api/review/file":  # شرط: route يساوي '/api/review/file'
            name = (query.get("name") or [""])[0]  # إسناد query.get('name') أو قائمة[0] إلى name
            content = srv.store.read_review(name)  # إسناد نتيجة استدعاء srv.store.read_review (معامل واحد) إلى content
            if not content:  # شرط معكوس: ليس content
                return self._error("review_file_not_found", 404)  # إرجاع self._error('review_file_not_found', 404)
            return self._send(content.encode("utf-8", "replace"), 200,  # إرجاع self._send(content.encode('utf-8', 'replace'), 200, 'text/html; charset=utf-8')
                              "text/html; charset=utf-8")  # تكملة السطر السابق داخل القوس
        if route == "/api/cache":  # شرط: route يساوي '/api/cache'
            return self._json({"ok": True, "cache": srv.store.cache_info()})  # إرجاع self._json(قاموس)
        if route == "/api/report":  # شرط: route يساوي '/api/report'
            name = (query.get("name") or [""])[0]  # إسناد query.get('name') أو قائمة[0] إلى name
            path = os.path.join(config.RUN_DIR, os.path.basename(name))  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى path
            try:  # بدايةtry محمية (يليها except/finally)
                with open(path, "r", encoding="utf-8") as fh:  # سياق مُدار: open(path, 'r', encoding='utf-8') باسم fh
                    return self._send(fh.read().encode("utf-8"), 200,  # إرجاع self._send(fh.read().encode('utf-8'), 200, 'application/json; charset=utf-8')
                                      "application/json; charset=utf-8")  # تكملة السطر السابق داخل القوس
            except OSError:  # تكملة السطر السابق داخل القوس
                return self._error("report_not_found", 404)  # إرجاع self._error('report_not_found', 404)
        if route == "/api/reports":  # شرط: route يساوي '/api/reports'
            try:  # بدايةtry محمية (يليها except/finally)
                names = sorted(os.listdir(config.RUN_DIR), reverse=True)[:50]  # إسناد sorted(os.listdir(config.RUN_DIR), reverse=True)[] إلى names
            except OSError:  # تكملة السطر السابق داخل القوس
                names = []  # إسناد قائمة إلى names
            return self._json({"ok": True, "reports": names})  # إرجاع self._json(قاموس)
        if route == "/api/capture/status":  # شرط: route يساوي '/api/capture/status'
            return self._capture_status((query.get("id") or [""])[0])  # إرجاع self._capture_status(query.get('id') أو قائمة[0])
        if route == "/api/capture/report":  # شرط: route يساوي '/api/capture/report'
            return self._capture_report((query.get("id") or [""])[0],  # إرجاع self._capture_report(query.get('id') أو قائمة[0], download=bool(query.get('download') أو قائمة[0]))
                                        download=bool((query.get("download") or [""])[0]))  # المعامل المسمّى download
        return self._error("not_found", 404)  # إرجاع self._error('not_found', 404)

    # -- نقاط POST --------------------------------------------------
    def _api_post(self, route, data):  # تعريف الدالة _api_post(self, route, data)
        srv = self.server  # إسناد self.server إلى srv
        if route == "/api/scan":  # شرط: route يساوي '/api/scan'
            return self._scan(data)  # إرجاع self._scan(data)
        if route == "/api/format/preview":  # شرط: route يساوي '/api/format/preview'
            return self._preview(data)  # إرجاع self._preview(data)
        if route == "/api/profiles/save":  # شرط: route يساوي '/api/profiles/save'
            prof = store.migrate(data.get("profile") or {})  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى prof
            problems = store.validate(prof)  # إسناد نتيجة استدعاء store.validate (معامل واحد) إلى problems
            hard = [p for p in problems if p not in  # بناء اشتقاق قائمة وإسناده إلى hard
                    ("space_is_astronomically_big", "needs_browser_js")]  # تكملة السطر السابق داخل القوس
            if hard:  # شرط: hard
                return self._json({"ok": False, "problems": problems}, 400)  # إرجاع self._json(قاموس, 400)
            saved = srv.store.put(prof)  # إسناد نتيجة استدعاء srv.store.put (معامل واحد) إلى saved
            return self._json({"ok": True, "profile": saved,  # إرجاع self._json(قاموس)
                               "profiles": [_profile_brief(p) for p in srv.store.all()]})  # مفتاح profiles في القاموس
        if route == "/api/profiles/delete":  # شرط: route يساوي '/api/profiles/delete'
            ok = srv.store.delete(data.get("name", ""))  # إسناد نتيجة استدعاء srv.store.delete (معامل واحد) إلى ok
            return self._json({"ok": ok,  # إرجاع self._json(قاموس)
                               "profiles": [_profile_brief(p) for p in srv.store.all()]})  # مفتاح profiles في القاموس
        if route == "/api/diagnose":  # شرط: route يساوي '/api/diagnose'
            prof = store.migrate(data.get("profile") or {})  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى prof
            threads = int(data.get("threads") or 0)  # إسناد نتيجة استدعاء int (معامل واحد) إلى threads
            checks = self._internet_checks()  # إسناد نتيجة استدعاء self._internet_checks إلى checks
            job = srv.submit("diagnose",  # إسناد نتيجة استدعاء srv.submit (2 معاملات) إلى job
                             lambda: engine.diagnose(prof, threads=threads,  # مفتاح lambda في القاموس
                                                     checks=checks))  # المعامل المسمّى checks
            return self._json({"ok": True, "job": job.as_dict()})  # إرجاع self._json(قاموس)
        if route == "/api/calibrate":  # شرط: route يساوي '/api/calibrate'
            prof = store.migrate(data.get("profile") or {})  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى prof
            known = (data.get("known_card") or "").strip()  # إسناد نتيجة استدعاء data.get('known_card') أو ''.strip إلى known
            keyword = (data.get("keyword") or "").strip()  # إسناد نتيجة استدعاء data.get('keyword') أو ''.strip إلى keyword
            checks = self._internet_checks()  # إسناد نتيجة استدعاء self._internet_checks إلى checks

            def run_calibration():  # تعريف الدالة run_calibration()
                result = engine.calibrate(prof, known_card=known,  # إسناد نتيجة استدعاء engine.calibrate(prof, known_card=known, keyword=keyword, checks=checks).as_dict إلى result
                                          keyword=keyword,  # المعامل المسمّى keyword
                                          checks=checks).as_dict()  # المعامل المسمّى checks
                report = {  # إسناد قاموس إلى report
                    "tool": config.APP_NAME, "version": config.VERSION,  # مفتاح tool في القاموس
                    "finished": time.strftime("%Y-%m-%d %H:%M:%S"),  # مفتاح finished في القاموس
                    "kind": "calibration", "profile": prof.get("name", ""),  # مفتاح kind في القاموس
                    "calibration": _safe_calibration_report(result, prof),  # مفتاح calibration في القاموس
                }  # إغلاق القوس المفتوح في السطر السابق
                try:  # بدايةtry محمية (يليها except/finally)
                    result["report_file"] = os.path.basename(srv.store.save_run(report))  # إسناد نتيجة استدعاء os.path.basename (معامل واحد) إلى result['report_file']
                except OSError:  # تكملة السطر السابق داخل القوس
                    result["report_file"] = ""  # إسناد القيمة الثابتة result['report_file']
                return result  # إرجاع result

            job = srv.submit("calibrate", run_calibration)  # إسناد نتيجة استدعاء srv.submit (2 معاملات) إلى job
            return self._json({"ok": True, "job": job.as_dict()})  # إرجاع self._json(قاموس)
        if route == "/api/lockout":  # شرط: route يساوي '/api/lockout'
            # فحص مُختار صراحةً ومحدود؛ المحرك يتوقف عند أول
            # رد حجب ولا ينتظر زواله ولا يعيد بعده أبداً.
            prof = store.migrate(data.get("profile") or {})  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى prof
            checks = self._internet_checks()  # إسناد نتيجة استدعاء self._internet_checks إلى checks
            job = srv.submit("lockout",  # إسناد نتيجة استدعاء srv.submit (2 معاملات) إلى job
                             lambda: engine.probe_lockout(  # مفتاح lambda في القاموس
                                 prof,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                 max_failures=int(data.get("max_failures") or 8),  # المعامل المسمّى max_failures
                                 checks=checks))  # المعامل المسمّى checks
            return self._json({"ok": True, "job": job.as_dict()})  # إرجاع self._json(قاموس)
        if route == "/api/run/start":  # شرط: route يساوي '/api/run/start'
            prof = store.migrate(data.get("profile") or {})  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى prof
            # طبّق رابط فحص الإنترنت المخصص من المسؤول لهذا التشغيل.
            srv.engine.checks = self._internet_checks()  # إسناد نتيجة استدعاء self._internet_checks إلى srv.engine.checks
            # احترم مهلة الاتصال المتقدمة من الإعدادات إن وُجدت.
            ct = srv.store.get_setting("connect_timeout")  # إسناد نتيجة استدعاء srv.store.get_setting (معامل واحد) إلى ct
            if ct:  # شرط: ct
                try:  # بدايةtry محمية (يليها except/finally)
                    config.CONNECT_TIMEOUT = float(ct)  # إسناد نتيجة استدعاء float (معامل واحد) إلى config.CONNECT_TIMEOUT
                except (TypeError, ValueError):  # تكملة السطر السابق داخل القوس
                    pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
            rt = srv.store.get_setting("read_timeout")  # إسناد نتيجة استدعاء srv.store.get_setting (معامل واحد) إلى rt
            if rt:  # شرط: rt
                try:  # بدايةtry محمية (يليها except/finally)
                    config.READ_TIMEOUT = float(rt)  # إسناد نتيجة استدعاء float (معامل واحد) إلى config.READ_TIMEOUT
                except (TypeError, ValueError):  # تكملة السطر السابق داخل القوس
                    pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
            result = srv.engine.start(  # إسناد نتيجة استدعاء srv.engine.start (معامل واحد، attempts=…، threads=…، delay_ms=…، keyword=…، known_card=…، preflight_only=…، verify_after=…، auto_stop=…، resume=…) إلى result
                prof,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                attempts=int(data.get("attempts") or config.DEFAULT_ATTEMPTS),  # المعامل المسمّى attempts
                threads=int(data.get("threads") or config.DEFAULT_THREADS),  # المعامل المسمّى threads
                delay_ms=int(data.get("delay_ms") or 0),  # المعامل المسمّى delay_ms
                keyword=(data.get("keyword") or "").strip(),  # المعامل المسمّى keyword
                known_card=(data.get("known_card") or "").strip(),  # المعامل المسمّى known_card
                preflight_only=bool(data.get("preflight_only", False)),  # المعامل المسمّى preflight_only
                verify_after=bool(data.get("verify", True)),  # المعامل المسمّى verify_after
                auto_stop=bool(data.get("auto_stop", True)),  # المعامل المسمّى auto_stop
                resume=data.get("resume", True) is not False)  # المعامل المسمّى resume
            return self._json(result, 200 if result.get("ok") else 400)  # إرجاع self._json(result, 200 إن result.get('ok') وإلا 400)
        if route == "/api/run/stop":  # شرط: route يساوي '/api/run/stop'
            srv.engine.stop("user_stop")  # استدعاء srv.engine.stop (معامل واحد)
            return self._json({"ok": True})  # إرجاع self._json(قاموس)
        if route == "/api/cache/clear":  # شرط: route يساوي '/api/cache/clear'
            scope = data.get("scope", "temp")  # إسناد نتيجة استدعاء data.get (2 معاملات) إلى scope
            if scope not in ("temp", "results", "profiles", "all"):  # شرط: scope ليس ضمن مجموعة
                return self._error("bad_scope", 400)  # إرجاع self._error('bad_scope', 400)
            freed = srv.store.clear_cache(scope)  # إسناد نتيجة استدعاء srv.store.clear_cache (معامل واحد) إلى freed
            if scope in ("profiles", "all"):  # شرط: scope ضمن مجموعة
                srv.store = store.Store()  # إسناد نتيجة استدعاء store.Store إلى srv.store
                srv.engine.store = srv.store  # إسناد srv.store إلى srv.engine.store
            return self._json({"ok": True, "cleared": freed,  # إرجاع self._json(قاموس)
                               "cache": srv.store.cache_info()})  # مفتاح cache في القاموس
        if route == "/api/settings":  # شرط: route يساوي '/api/settings'
            if "lang" in data:  # شرط: 'lang' ضمن data
                srv.store.set_setting("lang", str(data["lang"])[:5])  # استدعاء srv.store.set_setting (2 معاملات)
            if "internet_check_url" in data:  # شرط: 'internet_check_url' ضمن data
                raw = str(data.get("internet_check_url") or "").strip()[:400]  # إسناد str(data.get('internet_check_url') أو '').strip()[] إلى raw
                srv.store.set_setting("internet_check_url", raw)  # استدعاء srv.store.set_setting (2 معاملات)
            if "connect_timeout" in data:  # شرط: 'connect_timeout' ضمن data
                try:  # بدايةtry محمية (يليها except/finally)
                    value = float(data.get("connect_timeout") or 0)  # إسناد نتيجة استدعاء float (معامل واحد) إلى value
                    if 0.5 <= value <= 120:  # شرط: 0.5 أصغر أو يساوي value
                        srv.store.set_setting("connect_timeout", value)  # استدعاء srv.store.set_setting (2 معاملات)
                        config.CONNECT_TIMEOUT = value  # إسناد value إلى config.CONNECT_TIMEOUT
                except (TypeError, ValueError):  # تكملة السطر السابق داخل القوس
                    pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
            if "read_timeout" in data:  # شرط: 'read_timeout' ضمن data
                try:  # بدايةtry محمية (يليها except/finally)
                    value = float(data.get("read_timeout") or 0)  # إسناد نتيجة استدعاء float (معامل واحد) إلى value
                    if 0.5 <= value <= 120:  # شرط: 0.5 أصغر أو يساوي value
                        srv.store.set_setting("read_timeout", value)  # استدعاء srv.store.set_setting (2 معاملات)
                        config.READ_TIMEOUT = value  # إسناد value إلى config.READ_TIMEOUT
                except (TypeError, ValueError):  # تكملة السطر السابق داخل القوس
                    pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
            return self._json({"ok": True, "settings": srv.store.settings})  # إرجاع self._json(قاموس)
        if route == "/api/probe-link":  # شرط: route يساوي '/api/probe-link'
            return self._probe_link(data)  # إرجاع self._probe_link(data)
        if route == "/api/profiles/export":  # شرط: route يساوي '/api/profiles/export'
            name = (data.get("name") or "").strip()  # إسناد نتيجة استدعاء data.get('name') أو ''.strip إلى name
            prof = srv.store.get(name) if name else None  # إسناد srv.store.get(name) إن name وإلا None إلى prof
            if not prof:  # شرط معكوس: ليس prof
                return self._error("profile_not_found", 404)  # إرجاع self._error('profile_not_found', 404)
            safe = engine.safe_profile_snapshot(prof)  # إسناد نتيجة استدعاء engine.safe_profile_snapshot (معامل واحد) إلى safe
            return self._json({"ok": True, "profile": safe})  # إرجاع self._json(قاموس)
        if route == "/api/profiles/import":  # شرط: route يساوي '/api/profiles/import'
            raw = data.get("profile") or {}  # دمج منطقي (أو) وإسناده إلى raw
            if not isinstance(raw, dict):  # شرط معكوس: ليس isinstance(raw, dict)
                return self._error("bad_profile", 400)  # إرجاع self._error('bad_profile', 400)
            prof = store.migrate(raw)  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى prof
            # لا تستورد أبداً أسراراً حيّة من ملف عُدّل يدوياً.
            if prof.get("pass_fixed"):  # شرط: نتيجة prof.get('pass_fixed')
                prof["pass_fixed"] = ""  # إسناد القيمة الثابتة prof['pass_fixed']
            problems = store.validate(prof)  # إسناد نتيجة استدعاء store.validate (معامل واحد) إلى problems
            hard = [p for p in problems if p not in  # بناء اشتقاق قائمة وإسناده إلى hard
                    ("space_is_astronomically_big", "needs_browser_js")]  # تكملة السطر السابق داخل القوس
            if hard and not data.get("force"):  # شرط مركّب (و)
                return self._json({"ok": False, "problems": problems}, 400)  # إرجاع self._json(قاموس, 400)
            saved = srv.store.put(prof)  # إسناد نتيجة استدعاء srv.store.put (معامل واحد) إلى saved
            return self._json({"ok": True, "profile": saved,  # إرجاع self._json(قاموس)
                               "profiles": [_profile_brief(p)  # مفتاح profiles في القاموس
                                            for p in srv.store.all()]})  # تكملة السطر السابق داخل القوس
        if route == "/api/cache/cleanup-old":  # شرط: route يساوي '/api/cache/cleanup-old'
            days = data.get("days")  # إسناد نتيجة استدعاء data.get (معامل واحد) إلى days
            try:  # بدايةtry محمية (يليها except/finally)
                days = int(days) if days is not None else None  # إسناد int(days) إن مقارنة وإلا None إلى days
            except (TypeError, ValueError):  # تكملة السطر السابق داخل القوس
                days = None  # إسناد القيمة الثابتة days
            result = srv.store.cleanup_old_reports(days=days)  # إسناد نتيجة استدعاء srv.store.cleanup_old_reports (days=…) إلى result
            return self._json({"ok": True, "cleanup": result,  # إرجاع self._json(قاموس)
                               "cache": srv.store.cache_info()})  # مفتاح cache في القاموس
        if route == "/api/capture/start":  # شرط: route يساوي '/api/capture/start'
            return self._capture_start(data)  # إرجاع self._capture_start(data)
        if route == "/api/capture/step":  # شرط: route يساوي '/api/capture/step'
            return self._capture_step(data)  # إرجاع self._capture_step(data)
        if route == "/api/capture/mark":  # شرط: route يساوي '/api/capture/mark'
            return self._capture_mark(data)  # إرجاع self._capture_mark(data)
        if route == "/api/capture/finish":  # شرط: route يساوي '/api/capture/finish'
            return self._capture_finish(data)  # إرجاع self._capture_finish(data)
        if route == "/api/quit":  # شرط: route يساوي '/api/quit'
            # مستخدمو الهاتف (Termux/Pydroid) بلا Ctrl+C: دع الصفحة توقف
            # الأداة. الإيقاف يعمل من خيطه الخاص — واستدعاؤه
            # من داخل serve_forever سيسبب تعليقاً متبادلاً (deadlock).
            threading.Timer(0.4, srv.shutdown).start()  # استدعاء threading.Timer(0.4, srv.shutdown).start
            return self._json({"ok": True, "shutting_down": True})  # إرجاع self._json(قاموس)
        return self._error("not_found", 404)  # إرجاع self._error('not_found', 404)

    # -- مساعدات ---------------------------------------------------------
    def _internet_checks(self):  # تعريف الدالة _internet_checks(self)
        custom = (self.server.store.get_setting("internet_check_url", "")  # إسناد نتيجة استدعاء self.server.store.get_setting('internet_check_url', '') أو ''.strip إلى custom
                  or "").strip()  # تكملة السطر السابق داخل القوس
        return verify.resolve_internet_checks(custom or None)  # إرجاع verify.resolve_internet_checks(custom أو None)

    def _probe_link(self, data) -> None:  # تعريف الدالة _probe_link(self, data) ترجع None
        """Single GET to the login URL — connectivity check, no guessing."""  # نص توثيقي (docstring) يشرح ما يليه
        url = (data.get("url") or "").strip()  # إسناد نتيجة استدعاء data.get('url') أو ''.strip إلى url
        if not url:  # شرط معكوس: ليس url
            return self._error("url_required", 400)  # إرجاع self._error('url_required', 400)
        if not url.startswith(("http://", "https://")):  # شرط معكوس: ليس url.startswith(مجموعة)
            url = "http://" + url.lstrip("/")  # حساب جمع بين 'http://' وurl.lstrip('/') وإسناده إلى url
        session = Session(allow_redirects=True)  # إسناد نتيجة استدعاء Session (allow_redirects=…) إلى session
        t0 = time.time()  # إسناد نتيجة استدعاء time.time إلى t0
        try:  # بدايةtry محمية (يليها except/finally)
            resp = session.get(url, allow_redirects=True)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…) إلى resp
            ms = round((time.time() - t0) * 1000)  # إسناد نتيجة استدعاء round (معامل واحد) إلى ms
            form = portals.parse_form(resp.text or "", resp.url or url)  # إسناد نتيجة استدعاء portals.parse_form (2 معاملات) إلى form
            return self._json({  # إرجاع self._json(قاموس)
                "ok": True,  # مفتاح ok في القاموس
                "reachable": True,  # مفتاح reachable في القاموس
                "status": resp.status,  # مفتاح status في القاموس
                "ms": ms,  # مفتاح ms في القاموس
                "final_url": resp.url or url,  # مفتاح final_url في القاموس
                "has_login_form": bool(form and form.inputs),  # مفتاح has_login_form في القاموس
                "length": resp.length,  # مفتاح length في القاموس
                "hint": "reachable",  # مفتاح hint في القاموس
            })  # إغلاق القوس المفتوح في السطر السابق
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                              # noqa: BLE001
            from ..errors import classify  # استيراد classify من الوحدة errors
            err = classify(exc, url)  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
            return self._json({  # إرجاع self._json(قاموس)
                "ok": False,  # مفتاح ok في القاموس
                "reachable": False,  # مفتاح reachable في القاموس
                "error": err.kind,  # مفتاح error في القاموس
                "detail": err.text[:200],  # مفتاح detail في القاموس
                "hint": err.kind,  # مفتاح hint في القاموس
                "ms": round((time.time() - t0) * 1000),  # مفتاح ms في القاموس
            })  # إغلاق القوس المفتوح في السطر السابق
        finally:  # مفتاح finally في القاموس
            session.close()  # استدعاء session.close

    def _scan(self, data) -> None:  # تعريف الدالة _scan(self, data) ترجع None
        url = (data.get("url") or "").strip()  # إسناد نتيجة استدعاء data.get('url') أو ''.strip إلى url
        if not url.startswith(("http://", "https://")):  # شرط معكوس: ليس url.startswith(مجموعة)
            url = "http://" + url.lstrip("/")  # حساب جمع بين 'http://' وurl.lstrip('/') وإسناده إلى url
        session = Session(allow_redirects=True)  # إسناد نتيجة استدعاء Session (allow_redirects=…) إلى session
        t0 = time.time()  # إسناد نتيجة استدعاء time.time إلى t0
        try:  # بدايةtry محمية (يليها except/finally)
            try:  # بدايةtry محمية (يليها except/finally)
                portal = portals.discover(session, url)  # إسناد نتيجة استدعاء portals.discover (2 معاملات) إلى portal
            # تكملة السطر السابق داخل القوس
            except Exception as exc:                      # noqa: BLE001
                from ..errors import classify  # استيراد classify من الوحدة errors
                err = classify(exc, url)  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
                return self._json({"ok": False, "error": f"net_{err.kind}",  # إرجاع self._json(قاموس, 200)
                                   "detail": err.text[:200],  # مفتاح detail في القاموس
                                   "hint": err.short}, 200)  # مفتاح hint في القاموس
            internet = verify.probe_internet(session,  # إسناد نتيجة استدعاء verify.probe_internet (معامل واحد، checks=…) إلى internet
                                             checks=self._internet_checks())  # المعامل المسمّى checks
            return self._json({"ok": True, "portal": portal.as_dict(),  # إرجاع self._json(قاموس)
                               "internet": internet,  # مفتاح internet في القاموس
                               "ms": round((time.time() - t0) * 1000)})  # مفتاح ms في القاموس
        finally:  # مفتاح finally في القاموس
            session.close()  # استدعاء session.close

    def _preview(self, data) -> None:  # تعريف الدالة _preview(self, data) ترجع None
        prof = store.migrate(data.get("profile") or {})  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى prof
        request_shape = None  # إسناد القيمة الثابتة request_shape
        if prof.get("login_url"):  # شرط: نتيجة prof.get('login_url')
            try:  # بدايةtry محمية (يليها except/finally)
                request_shape = engine.safe_request_shape(prof, "CARD")  # إسناد نتيجة استدعاء engine.safe_request_shape (2 معاملات) إلى request_shape
            # تكملة السطر السابق داخل القوس
            except Exception:                               # noqa: BLE001
                request_shape = None  # إسناد القيمة الثابتة request_shape
        return self._json({"ok": True,  # إرجاع self._json(قاموس)
                           "space": store.space_size(prof),  # مفتاح space في القاموس
                           "variable_len": store.variable_len(prof),  # مفتاح variable_len في القاموس
                           "samples": store.sample_cards(prof, 4),  # مفتاح samples في القاموس
                           "problems": store.validate(prof),  # مفتاح problems في القاموس
                           "request_shape": request_shape,  # مفتاح request_shape في القاموس
                           "charset_size": len(set(prof.get("charset") or ""))})  # مفتاح charset_size في القاموس

    def _guard(self) -> str:  # تعريف الدالة _guard(self) ترجع str
        host = self.headers.get("Host") or "127.0.0.1"  # دمج منطقي (أو) وإسناده إلى host
        scheme = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"  # إسناد 'https' إن مقارنة وإلا 'http' إلى scheme
        return f"{scheme}://{host}"  # إرجاع نص منسّق (f-string)

    def _capture_start(self, data) -> None:  # تعريف الدالة _capture_start(self, data) ترجع None
        url = (data.get("url") or "").strip()  # إسناد نتيجة استدعاء data.get('url') أو ''.strip إلى url
        if not url:  # شرط معكوس: ليس url
            return self._error("url_missing")  # إرجاع self._error('url_missing')
        try:  # بدايةtry محمية (يليها except/finally)
            cap = self.server.captures.start(url, guard=self._guard())  # إسناد نتيجة استدعاء self.server.captures.start (معامل واحد، guard=…) إلى cap
        except ValueError as exc:  # تكملة السطر السابق داخل القوس
            return self._error(str(exc))  # إرجاع self._error(str(exc))
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                          # noqa: BLE001
            from ..errors import classify  # استيراد classify من الوحدة errors
            err = classify(exc, url)  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
            return self._json({"ok": False, "error": f"net_{err.kind}",  # إرجاع self._json(قاموس, 200)
                               "detail": err.text[:200], "hint": err.short}, 200)  # مفتاح detail في القاموس
        public = cap.as_public()  # إسناد نتيجة استدعاء cap.as_public إلى public
        public["view"] = "/capture/view?id=" + cap.id  # حساب جمع بين '/capture/view?id=' وcap.id وإسناده إلى public['view']
        return self._json(public)  # إرجاع self._json(public)

    def _capture_step(self, data) -> None:  # تعريف الدالة _capture_step(self, data) ترجع None
        try:  # بدايةtry محمية (يليها except/finally)
            result = self.server.captures.step(  # إسناد نتيجة استدعاء self.server.captures.step (2 معاملات، guard=…) إلى result
                data.get("id") or "", data, guard=self._guard())  # تكملة السطر السابق داخل القوس
        except KeyError:  # تكملة السطر السابق داخل القوس
            return self._error("capture_not_found", 404)  # إرجاع self._error('capture_not_found', 404)
        except ValueError as exc:  # تكملة السطر السابق داخل القوس
            return self._error(str(exc))  # إرجاع self._error(str(exc))
        return self._json(result, 200 if result.get("ok") else 400)  # إرجاع self._json(result, 200 إن result.get('ok') وإلا 400)

    def _capture_mark(self, data) -> None:  # تعريف الدالة _capture_mark(self, data) ترجع None
        try:  # بدايةtry محمية (يليها except/finally)
            result = self.server.captures.mark(data.get("id") or "",  # إسناد نتيجة استدعاء self.server.captures.mark (2 معاملات) إلى result
                                               data.get("mark") or "")  # تكملة السطر السابق داخل القوس
        except KeyError:  # تكملة السطر السابق داخل القوس
            return self._error("capture_not_found", 404)  # إرجاع self._error('capture_not_found', 404)
        return self._json(result, 200 if result.get("ok") else 400)  # إرجاع self._json(result, 200 إن result.get('ok') وإلا 400)

    def _capture_finish(self, data) -> None:  # تعريف الدالة _capture_finish(self, data) ترجع None
        try:  # بدايةtry محمية (يليها except/finally)
            result = self.server.captures.finish(  # إسناد نتيجة استدعاء self.server.captures.finish (2 معاملات، hints=…) إلى result
                data.get("id") or "", self.server.store,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                hints=data.get("profile") or {})  # المعامل المسمّى hints
        except KeyError:  # تكملة السطر السابق داخل القوس
            return self._error("capture_not_found", 404)  # إرجاع self._error('capture_not_found', 404)
        return self._json(result)  # إرجاع self._json(result)

    def _capture_status(self, capture_id: str) -> None:  # تعريف الدالة _capture_status(self, capture_id) ترجع None
        try:  # بدايةtry محمية (يليها except/finally)
            return self._json(self.server.captures.status(capture_id))  # إرجاع self._json(self.server.captures.status(capture_id))
        except KeyError:  # تكملة السطر السابق داخل القوس
            return self._error("capture_not_found", 404)  # إرجاع self._error('capture_not_found', 404)

    def _capture_report(self, capture_id: str, download: bool = False) -> None:  # تعريف الدالة _capture_report(self, capture_id, download) ترجع None
        try:  # بدايةtry محمية (يليها except/finally)
            report = self.server.captures.report_of(capture_id)  # إسناد نتيجة استدعاء self.server.captures.report_of (معامل واحد) إلى report
        except KeyError:  # تكملة السطر السابق داخل القوس
            return self._error("capture_not_found", 404)  # إرجاع self._error('capture_not_found', 404)
        body = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")  # إسناد نتيجة استدعاء json.dumps(report, ensure_ascii=False, indent=2).encode (معامل واحد) إلى body
        extra = {}  # إسناد قاموس إلى extra
        if download:  # شرط: download
            extra["Content-Disposition"] = (  # إسناد القيمة الثابتة extra['Content-Disposition']
                'attachment; filename="kirapass-capture.json"')  # تكملة السطر السابق داخل القوس
        return self._send(body, 200, "application/json; charset=utf-8", extra)  # إرجاع self._send(body, 200, 'application/json; charset=utf-8', …)

    def _capture_view(self, query) -> None:  # تعريف الدالة _capture_view(self, query) ترجع None
        capture_id = (query.get("id") or [""])[0]  # إسناد query.get('id') أو قائمة[0] إلى capture_id
        try:  # بدايةtry محمية (يليها except/finally)
            self.server.captures.get(capture_id)  # استدعاء self.server.captures.get (معامل واحد)
        except KeyError:  # تكملة السطر السابق داخل القوس
            return self._error("capture_not_found", 404)  # إرجاع self._error('capture_not_found', 404)
        token = (self.headers.get("X-KiraPass-Token")  # دمج منطقي (أو) وإسناده إلى token
                 or (query.get("token") or [""])[0]  # تكملة السطر السابق داخل القوس
                 or self.server.token)  # تكملة السطر السابق داخل القوس
        return self._send(capture.view_page(capture_id, token),  # إرجاع self._send(capture.view_page(capture_id, token), 200, 'text/html; charset=utf-8')
                          200, "text/html; charset=utf-8")  # تكملة السطر السابق داخل القوس


def _profile_brief(p: dict) -> dict:  # تعريف الدالة _profile_brief(p) ترجع dict
    return {"name": p.get("name", ""), "login_url": p.get("login_url", ""),  # إرجاع قاموس
            "method": p.get("method", "post"),  # مفتاح method في القاموس
            "cards": f"{p.get('prefix','')}[{store.variable_len(p)} with "  # مفتاح cards في القاموس
                     f"{len(set(p.get('charset') or ''))} symbols]"  # تكملة السطر السابق داخل القوس
                     f"{p.get('suffix','')}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            "space": store.space_size(p),  # مفتاح space في القاموس
            "covered": p.get("space_pos", 0),  # مفتاح covered في القاموس
            "pass_mode": p.get("pass_mode", ""),  # مفتاح pass_mode في القاموس
            "dst_value": p.get("dst_value", ""),  # مفتاح dst_value في القاموس
            "success_words": p.get("success_words", [])[:6]}  # مفتاح success_words في القاموس


def serve(host: str = "127.0.0.1", port: int = 8770, token: str = "",  # تعريف الدالة serve(host, port, token, on_ready) ترجع None
          on_ready=None) -> None:  # المعامل المسمّى on_ready
    httpd = KiraServer((host, port), Handler, token=token)  # إسناد نتيجة استدعاء KiraServer (2 معاملات، token=…) إلى httpd
    real_port = httpd.server_address[1]  # إسناد httpd.server_address[1] إلى real_port
    if on_ready:  # شرط: on_ready
        on_ready(real_port, httpd.token)  # استدعاء on_ready (2 معاملات)
    try:  # بدايةtry محمية (يليها except/finally)
        httpd.serve_forever(poll_interval=0.4)  # استدعاء httpd.serve_forever (poll_interval=…)
    except KeyboardInterrupt:  # تكملة السطر السابق داخل القوس
        pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
    finally:  # مفتاح finally في القاموس
        httpd.pool.shutdown(wait=False)  # استدعاء httpd.pool.shutdown (wait=…)
        httpd.server_close()  # استدعاء httpd.server_close
