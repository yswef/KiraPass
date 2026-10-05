# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""A small HTTP client built only on the python standard library.

Why not `requests`?  Because the old version died with
`ModuleNotFoundError: No module named requests` on any machine where the
package was not installed (phones, fresh Windows, locked lab PCs).  This
client needs nothing but python itself, and it gives exact control over the
three things this tool lives on:

* keep-alive connection reuse  -> real speed on a router
* connect timeout vs read timeout -> we can tell "unreachable" from "busy"
* reading the real reply body   -> we need the bytes, not a convenience layer
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import gzip  # استيراد الوحدة gzip من المكتبة
import http.client  # استيراد الوحدة http.client من المكتبة
import http.cookies  # استيراد الوحدة http.cookies من المكتبة
import json  # استيراد الوحدة json من المكتبة
import socket  # استيراد الوحدة socket من المكتبة
import ssl  # استيراد الوحدة ssl من المكتبة
import time  # استيراد الوحدة time من المكتبة
import urllib.parse  # استيراد الوحدة urllib.parse من المكتبة
import zlib  # استيراد الوحدة zlib من المكتبة

from . import config  # استيراد config من الوحدة .
from .errors import NetError, classify  # استيراد NetError, classify من الوحدة errors

MAX_REDIRECTS = 8  # إسناد القيمة الثابتة MAX_REDIRECTS


class Response:  # تعريف الصنف Response
    """One HTTP reply, decoded but otherwise untouched."""  # نص توثيقي (docstring) يشرح ما يليه

    __slots__ = ("status", "headers", "_body", "url", "elapsed_ms",  # إسناد مجموعة إلى __slots__
                 "history", "method", "request_headers", "reason")  # تكملة السطر السابق داخل القوس

    def __init__(self, status, headers, body, url, elapsed_ms, history,  # تعريف الدالة __init__(self, status, headers, body, url, elapsed_ms, history, method, request_headers, reason)
                 method="GET", request_headers=None, reason=""):  # المعامل المسمّى method
        self.status = status  # إسناد status إلى self.status
        self.headers = headers            # قاموس، مفاتيحه بأحرف صغيرة
        self._body = body  # إسناد body إلى self._body
        self.url = url  # إسناد url إلى self.url
        self.elapsed_ms = elapsed_ms  # إسناد elapsed_ms إلى self.elapsed_ms
        self.history = history            # قائمة الروابط التي مرّت
        self.method = method  # إسناد method إلى self.method
        self.request_headers = request_headers or {}  # دمج منطقي (أو) وإسناده إلى self.request_headers
        self.reason = reason  # إسناد reason إلى self.reason

    # -- الجسم -------------------------------------------------------------
    @property  # مُزخرف (decorator) بـproperty
    def body(self) -> bytes:  # تعريف الدالة body(self) ترجع bytes
        return self._body  # إرجاع self._body

    @property  # مُزخرف (decorator) بـproperty
    def text(self) -> str:  # تعريف الدالة text(self) ترجع str
        return self.decode()  # إرجاع self.decode()

    def decode(self, limit: int = 0) -> str:  # تعريف الدالة decode(self, limit) ترجع str
        raw = self._body  # إسناد self._body إلى raw
        if limit:  # شرط: limit
            raw = raw[:limit]  # إسناد raw[] إلى raw
        charset = "utf-8"  # إسناد القيمة الثابتة charset
        ctype = self.header("content-type")  # إسناد نتيجة استدعاء self.header (معامل واحد) إلى ctype
        if "charset=" in ctype:  # شرط: 'charset=' ضمن ctype
            charset = ctype.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"  # دمج منطقي (أو) وإسناده إلى charset
        try:  # بدايةtry محمية (يليها except/finally)
            return raw.decode(charset, "replace")  # إرجاع raw.decode(charset, 'replace')
        except LookupError:  # تكملة السطر السابق داخل القوس
            return raw.decode("utf-8", "replace")  # إرجاع raw.decode('utf-8', 'replace')

    def header(self, name: str, default: str = "") -> str:  # تعريف الدالة header(self, name, default) ترجع str
        return self.headers.get(name.lower(), default)  # إرجاع self.headers.get(name.lower(), default)

    @property  # مُزخرف (decorator) بـproperty
    def location(self) -> str:  # تعريف الدالة location(self) ترجع str
        return self.header("location")  # إرجاع self.header('location')

    @property  # مُزخرف (decorator) بـproperty
    def length(self) -> int:  # تعريف الدالة length(self) ترجع int
        return len(self._body)  # إرجاع len(self._body)

    def is_redirect(self) -> bool:  # تعريف الدالة is_redirect(self) ترجع bool
        return self.status in (301, 302, 303, 307, 308) and bool(self.location)  # إرجاع مقارنة و bool(self.location)

    def as_dict(self) -> dict:  # تعريف الدالة as_dict(self) ترجع dict
        return {  # إرجاع قاموس
            "status": self.status,  # مفتاح status في القاموس
            "length": self.length,  # مفتاح length في القاموس
            "url": self.url,  # مفتاح url في القاموس
            "location": self.location,  # مفتاح location في القاموس
            "ms": round(self.elapsed_ms),  # مفتاح ms في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق


class CookieStore:  # تعريف الصنف CookieStore
    """Minimal cookie jar (name/domain/path), enough for captive portals."""  # نص توثيقي (docstring) يشرح ما يليه

    def __init__(self):  # تعريف الدالة __init__(self)
        self._jar = {}  # إسناد قاموس إلى self._jar

    # يحفظ Set-Cookie مع النطاق والمسار وsecure حتى لا يُرسل كوكي في غير مكانه.
    def update(self, url: str, set_cookie_headers) -> None:  # تعريف الدالة update(self, url, set_cookie_headers) ترجع None
        host = urllib.parse.urlsplit(url).hostname or ""  # دمج منطقي (أو) وإسناده إلى host
        for raw in set_cookie_headers:  # دورة على set_cookie_headers باسم raw
            try:  # بدايةtry محمية (يليها except/finally)
                parsed = http.cookies.SimpleCookie()  # إسناد نتيجة استدعاء http.cookies.SimpleCookie إلى parsed
                parsed.load(raw)  # استدعاء parsed.load (معامل واحد)
            except Exception:  # تكملة السطر السابق داخل القوس
                continue  # الانتقال إلى الدورة التالية
            for name, morsel in parsed.items():  # دورة على parsed.items() باسم مجموعة
                domain = (morsel["domain"] or host).lstrip(".").lower()  # إسناد نتيجة استدعاء morsel['domain'] أو host.lstrip('.').lower إلى domain
                path = morsel["path"] or "/"  # دمج منطقي (أو) وإسناده إلى path
                self._jar[name] = {  # إسناد قاموس إلى self._jar[name]
                    "value": morsel.value,  # مفتاح value في القاموس
                    "domain": domain,  # مفتاح domain في القاموس
                    "path": path,  # مفتاح path في القاموس
                    "secure": bool(morsel["secure"]),  # مفتاح secure في القاموس
                }  # إغلاق القوس المفتوح في السطر السابق

    def header(self, url: str) -> str:  # تعريف الدالة header(self, url) ترجع str
        parts = urllib.parse.urlsplit(url)  # إسناد نتيجة استدعاء urllib.parse.urlsplit (معامل واحد) إلى parts
        host = (parts.hostname or "").lower()  # إسناد نتيجة استدعاء parts.hostname أو ''.lower إلى host
        path = parts.path or "/"  # دمج منطقي (أو) وإسناده إلى path
        out = []  # إسناد قائمة إلى out
        for name, c in self._jar.items():  # دورة على self._jar.items() باسم مجموعة
            dom = c["domain"]  # إسناد c['domain'] إلى dom
            if dom and not (host == dom or host.endswith("." + dom)):  # شرط مركّب (و)
                continue  # الانتقال إلى الدورة التالية
            if not path.startswith(c["path"]):  # شرط معكوس: ليس path.startswith(c['path'])
                continue  # الانتقال إلى الدورة التالية
            if c["secure"] and parts.scheme != "https":  # شرط مركّب (و)
                continue  # الانتقال إلى الدورة التالية
            out.append(f"{name}={c['value']}")  # استدعاء out.append (معامل واحد)
        return "; ".join(out)  # إرجاع '; '.join(out)

    def clear(self) -> None:  # تعريف الدالة clear(self) ترجع None
        self._jar.clear()  # استدعاء self._jar.clear

    # أسماء الكوكيز فقط ولا القيم أبداً — القيم أسرار جلسات.
    def names(self) -> list:  # تعريف الدالة names(self) ترجع list
        """Cookie names only - never the values."""  # نص توثيقي (docstring) يشرح ما يليه
        return sorted(self._jar.keys())  # إرجاع sorted(self._jar.keys())

    def __len__(self) -> int:  # تعريف الدالة __len__(self) ترجع int
        return len(self._jar)  # إرجاع len(self._jar)


class Session:  # تعريف الصنف Session
    """One connection + cookie store. Use one Session per worker thread."""  # نص توثيقي (docstring) يشرح ما يليه

    def __init__(self, headers=None, connect_timeout=config.CONNECT_TIMEOUT,  # تعريف الدالة __init__(self, headers, connect_timeout, read_timeout, verify_tls, allow_redirects)
                 read_timeout=config.READ_TIMEOUT, verify_tls=config.VERIFY_TLS,  # المعامل المسمّى read_timeout
                 allow_redirects=False):  # المعامل المسمّى allow_redirects
        self.headers = dict(config.BASE_HEADERS)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى self.headers
        if headers:  # شرط: headers
            self.headers.update(headers)  # استدعاء self.headers.update (معامل واحد)
        self.connect_timeout = connect_timeout  # إسناد connect_timeout إلى self.connect_timeout
        self.read_timeout = read_timeout  # إسناد read_timeout إلى self.read_timeout
        self.verify_tls = verify_tls  # إسناد verify_tls إلى self.verify_tls
        self.allow_redirects = allow_redirects  # إسناد allow_redirects إلى self.allow_redirects
        self.cookies = CookieStore()  # إسناد نتيجة استدعاء CookieStore إلى self.cookies
        self._conn = None  # إسناد القيمة الثابتة self._conn
        self._key = None  # إسناد القيمة الثابتة self._key
        self.stats = {"requests": 0, "retries": 0, "bytes": 0}  # إسناد قاموس إلى self.stats
        self._ssl_ctx = None  # إسناد القيمة الثابتة self._ssl_ctx

    def __enter__(self) -> "Session":  # تعريف الدالة __enter__(self) ترجع 'Session'
        return self  # إرجاع self

    def __exit__(self, *exc) -> bool:  # تعريف الدالة __exit__(self, *exc) ترجع bool
        self.close()  # استدعاء self.close
        return False  # إرجاع False

    # -- الاتصال -------------------------------------------------------
    def _ssl_context(self):  # تعريف الدالة _ssl_context(self)
        if self._ssl_ctx is None:  # شرط: self._ssl_ctx هو نفسه None
            if self.verify_tls:  # شرط: self.verify_tls
                self._ssl_ctx = ssl.create_default_context()  # إسناد نتيجة استدعاء ssl.create_default_context إلى self._ssl_ctx
            else:  # مفتاح else في القاموس
                self._ssl_ctx = ssl._create_unverified_context()  # إسناد نتيجة استدعاء ssl._create_unverified_context إلى self._ssl_ctx
        return self._ssl_ctx  # إرجاع self._ssl_ctx

    def _connection(self, scheme, host, port):  # تعريف الدالة _connection(self, scheme, host, port)
        key = (scheme, host, port)  # إسناد مجموعة إلى key
        if self._conn is not None and self._key == key:  # شرط مركّب (و)
            return self._conn  # إرجاع self._conn
        self.close()  # استدعاء self.close
        if scheme == "https":  # شرط: scheme يساوي 'https'
            conn = http.client.HTTPSConnection(  # إسناد نتيجة استدعاء http.client.HTTPSConnection (2 معاملات، timeout=…، context=…) إلى conn
                host, port, timeout=self.connect_timeout,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                context=self._ssl_context())  # المعامل المسمّى context
        else:  # مفتاح else في القاموس
            conn = http.client.HTTPConnection(  # إسناد نتيجة استدعاء http.client.HTTPConnection (2 معاملات، timeout=…) إلى conn
                host, port, timeout=self.connect_timeout)  # تكملة السطر السابق داخل القوس
        self._conn, self._key = conn, key  # إسناد مجموعة إلى مجموعة
        return conn  # إرجاع conn

    def close(self):  # تعريف الدالة close(self)
        if self._conn is not None:  # شرط: self._conn ليس نفسه None
            try:  # بدايةtry محمية (يليها except/finally)
                self._conn.close()  # استدعاء self._conn.close
            except Exception:  # تكملة السطر السابق داخل القوس
                pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
        self._conn = None  # إسناد القيمة الثابتة self._conn
        self._key = None  # إسناد القيمة الثابتة self._key

    # -- الطلبات ---------------------------------------------------------
    # الواجهة العامة: إعادة محاولة صامتة واحدة على stale، ثم تصنيف الخطأ.
    def request(self, method, url, params=None, data=None, headers=None,  # تعريف الدالة request(self, method, url, params, data, headers, allow_redirects, timeout) ترجع Response
                allow_redirects=None, timeout=None) -> Response:  # المعامل المسمّى allow_redirects
        method = method.upper()  # إسناد نتيجة استدعاء method.upper إلى method
        if params:  # شرط: params
            sep = "&" if urllib.parse.urlsplit(url).query else "?"  # إسناد '&' إن urllib.parse.urlsplit(url).query وإلا '?' إلى sep
            url = url + sep + urllib.parse.urlencode(params, doseq=True)  # حساب جمع بين جمع وurllib.parse.urlencode(params, doseq=True) وإسناده إلى url
        hdr_ct = ""  # إسناد القيمة الثابتة hdr_ct
        if headers:  # شرط: headers
            for key, value in headers.items():  # دورة على headers.items() باسم مجموعة
                if str(key).lower() == "content-type":  # شرط: str(key).lower() يساوي 'content-type'
                    hdr_ct = value or ""  # دمج منطقي (أو) وإسناده إلى hdr_ct
                    break  # قطع الحلقة فوراً
        if isinstance(data, dict):  # شرط: نتيجة isinstance(data, dict)
            if "json" in hdr_ct.lower():  # شرط: 'json' ضمن hdr_ct.lower()
                body = json.dumps(data).encode("utf-8")  # إسناد نتيجة استدعاء json.dumps(data).encode (معامل واحد) إلى body
                post_headers = {"Content-Type": hdr_ct or "application/json"}  # إسناد قاموس إلى post_headers
            else:  # مفتاح else في القاموس
                body = urllib.parse.urlencode(data, doseq=True).encode()  # إسناد نتيجة استدعاء urllib.parse.urlencode(data, doseq=True).encode إلى body
                post_headers = {"Content-Type": "application/x-www-form-urlencoded"}  # إسناد قاموس إلى post_headers
        elif isinstance(data, str):  # شرط: نتيجة isinstance(data, str)
            body = data.encode()  # إسناد نتيجة استدعاء data.encode إلى body
            post_headers = {"Content-Type": hdr_ct or "application/x-www-form-urlencoded"}  # إسناد قاموس إلى post_headers
        elif isinstance(data, bytes):  # شرط: نتيجة isinstance(data, bytes)
            body = data  # إسناد data إلى body
            post_headers = {"Content-Type": "application/octet-stream"}  # إسناد قاموس إلى post_headers
        else:  # مفتاح else في القاموس
            body = None  # إسناد القيمة الثابتة body
            post_headers = {}  # إسناد قاموس إلى post_headers

        follow = self.allow_redirects if allow_redirects is None else allow_redirects  # إسناد self.allow_redirects إن مقارنة وإلا allow_redirects إلى follow
        history = []  # إسناد قائمة إلى history
        started = time.time()  # إسناد نتيجة استدعاء time.time إلى started

        for _ in range(MAX_REDIRECTS + 1):  # دورة على range(جمع) باسم _
            resp = self._send_once(method, url, body, headers, post_headers,  # إسناد نتيجة استدعاء self._send_once (6 معاملات) إلى resp
                                   timeout)  # تكملة السطر السابق داخل القوس
            resp.history = list(history)  # إسناد نتيجة استدعاء list (معامل واحد) إلى resp.history
            if not (follow and resp.is_redirect()):  # شرط معكوس: ليس follow و resp.is_redirect()
                resp.elapsed_ms = (time.time() - started) * 1000  # حساب ضرب بين طرح و1000 وإسناده إلى resp.elapsed_ms
                return resp  # إرجاع resp
            history.append(url)  # استدعاء history.append (معامل واحد)
            target = urllib.parse.urljoin(url, resp.location)  # إسناد نتيجة استدعاء urllib.parse.urljoin (2 معاملات) إلى target
            if resp.status == 303 or (resp.status in (301, 302) and method == "POST"):  # شرط مركّب (أو)
                method, body, post_headers = "GET", None, {}  # إسناد مجموعة إلى مجموعة
            url = target  # إسناد target إلى url
        raise NetError("too_many_redirects", f"redirect loop at {url}", url)  # رفع NetError('too_many_redirects', نص منسّق (f-string), url)

    def get(self, url, **kw) -> Response:  # تعريف الدالة get(self, url, **kw) ترجع Response
        return self.request("GET", url, **kw)  # إرجاع self.request('GET', url, **=kw)

    def post(self, url, **kw) -> Response:  # تعريف الدالة post(self, url, **kw) ترجع Response
        return self.request("POST", url, **kw)  # إرجاع self.request('POST', url, **=kw)

    # -- رحلة الذهاب والإياب الخام الواحدة -------------------------------
    # إرسال طلب واحد على اتصال موجود أو جديد.
    # فصل مهلة الاتصال عن مهلة القراءة مقصود: بدونه يدمج بايثون المرحلتين
    # في TimeoutError واحد فيبدو الراوتر الميت «بطيئاً» بدل «غير قابل للوصول».
    def _send_once(self, method, url, body, extra_headers, post_headers,  # تعريف الدالة _send_once(self, method, url, body, extra_headers, post_headers, timeout) ترجع Response
                   timeout) -> Response:  # تكملة تعريف متعدد الأسطر
        parts = urllib.parse.urlsplit(url)  # إسناد نتيجة استدعاء urllib.parse.urlsplit (معامل واحد) إلى parts
        if parts.scheme not in ("http", "https"):  # شرط: parts.scheme ليس ضمن مجموعة
            raise NetError("proto", f"unsupported scheme: {parts.scheme!r}", url)  # رفع NetError('proto', نص منسّق (f-string), url)
        host = parts.hostname or ""  # دمج منطقي (أو) وإسناده إلى host
        if not host:  # شرط معكوس: ليس host
            raise NetError("proto", f"no host in url: {url}", url)  # رفع NetError('proto', نص منسّق (f-string), url)
        scheme = parts.scheme  # إسناد parts.scheme إلى scheme
        port = parts.port or (443 if scheme == "https" else 80)  # دمج منطقي (أو) وإسناده إلى port
        path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))  # إسناد نتيجة استدعاء urllib.parse.urlunsplit (معامل واحد) إلى path

        headers = dict(self.headers)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى headers
        headers.update(post_headers)  # استدعاء headers.update (معامل واحد)
        headers["Host"] = host if port in (80, 443) else f"{host}:{port}"  # إسناد host إن مقارنة وإلا نص منسّق (f-string) إلى headers['Host']
        headers["Accept-Encoding"] = "gzip, deflate"  # إسناد القيمة الثابتة headers['Accept-Encoding']
        cookie = self.cookies.header(url)  # إسناد نتيجة استدعاء self.cookies.header (معامل واحد) إلى cookie
        if cookie:  # شرط: cookie
            headers["Cookie"] = cookie  # إسناد cookie إلى headers['Cookie']
        if extra_headers:  # شرط: extra_headers
            headers.update(extra_headers)  # استدعاء headers.update (معامل واحد)

        read_to = (timeout[1] if isinstance(timeout, (tuple, list))  # إسناد timeout[1] إن isinstance(timeout, مجموعة) وإلا timeout أو self.read_timeout إلى read_to
                   else (timeout or self.read_timeout))  # تكملة السطر السابق داخل القوس
        connect_to = (timeout[0] if isinstance(timeout, (tuple, list))  # إسناد timeout[0] إن isinstance(timeout, مجموعة) وإلا self.connect_timeout إلى connect_to
                      else self.connect_timeout)  # تكملة السطر السابق داخل القوس

        last_exc = None  # إسناد القيمة الثابتة last_exc
        for attempt in range(2):          # إعادة صامتة واحدة لاتصال keep-alive ميت
            try:  # بدايةtry محمية (يليها except/finally)
                conn = self._connection(scheme, host, port)  # إسناد نتيجة استدعاء self._connection (3 معاملات) إلى conn
                if conn.sock is None:  # شرط: conn.sock هو نفسه None
                    conn.timeout = connect_to  # إسناد connect_to إلى conn.timeout
                    # فتح المقبس مرحلة قائمة بذاتها: إن انتهت مهلتها يجب
                    # أن نقول «الراوتر لم يردّ على الاتصال»،
                    # لا «الراوتر لم يردّ على الطلب». (بدون
                    # هذا، يطوي بايثون المرحلتين في TimeoutError واحد فيبدو كل
                    # راوتر ميت راوتراً بطيئاً.)
                    try:  # بدايةtry محمية (يليها except/finally)
                        conn.connect()  # استدعاء conn.connect
                    except (socket.timeout, TimeoutError) as exc:  # تكملة السطر السابق داخل القوس
                        self.close()  # استدعاء self.close
                        raise NetError("connect_timeout",  # رفع NetError('connect_timeout', نص منسّق (f-string), url)
                                       f"{type(exc).__name__}: {exc}", url)  # تكملة السطر السابق داخل القوس
                conn.sock.settimeout(read_to)  # استدعاء conn.sock.settimeout (معامل واحد)
                start = time.time()  # إسناد نتيجة استدعاء time.time إلى start
                conn.request(method, path, body=body, headers=headers)  # استدعاء conn.request (2 معاملات، body=…، headers=…)
                raw = conn.getresponse()  # إسناد نتيجة استدعاء conn.getresponse إلى raw
                payload = raw.read()  # إسناد نتيجة استدعاء raw.read إلى payload
                elapsed = (time.time() - start) * 1000  # حساب ضرب بين طرح و1000 وإسناده إلى elapsed
                payload = self._decompress(payload, raw.getheader("Content-Encoding"))  # إسناد نتيجة استدعاء self._decompress (2 معاملات) إلى payload
                hdrs = {k.lower(): v for k, v in raw.getheaders()}  # بناء قاموس بالاشتقاق وإسناده إلى hdrs
                self.stats["requests"] += 1  # تحديث self.stats['requests'] بعملية جمع
                self.stats["bytes"] += len(payload)  # تحديث self.stats['bytes'] بعملية جمع
                if raw.will_close:  # شرط: raw.will_close
                    self.close()  # استدعاء self.close
                self.cookies.update(url, raw.headers.get_all("Set-Cookie") or [])  # استدعاء self.cookies.update (2 معاملات)
                return Response(raw.status, hdrs, payload, url, elapsed, [],  # إرجاع Response(raw.status, hdrs, payload, …)
                                method, headers, raw.reason)  # تكملة السطر السابق داخل القوس
            except NetError:  # تكملة السطر السابق داخل القوس
                raise  # إعادة رفع الاستثناء الحالي
            except Exception as exc:  # تكملة السطر السابق داخل القوس
                err = classify(exc, url)  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
                last_exc = err  # إسناد err إلى last_exc
                self.close()  # استدعاء self.close
                if attempt == 0 and err.retryable:  # شرط مركّب (و)
                    self.stats["retries"] += 1  # تحديث self.stats['retries'] بعملية جمع
                    time.sleep(0.05)  # استدعاء time.sleep (معامل واحد)
                    continue  # الانتقال إلى الدورة التالية
                raise err  # رفع err
        raise last_exc or NetError("unknown", "request failed", url)  # رفع last_exc أو NetError('unknown', 'request failed', url)

    @staticmethod  # مُزخرف (decorator) بـstaticmethod
    def _decompress(payload: bytes, encoding: str) -> bytes:  # تعريف الدالة _decompress(payload, encoding) ترجع bytes
        enc = (encoding or "").lower()  # إسناد نتيجة استدعاء encoding أو ''.lower إلى enc
        if "gzip" in enc:  # شرط: 'gzip' ضمن enc
            try:  # بدايةtry محمية (يليها except/finally)
                return gzip.decompress(payload)  # إرجاع gzip.decompress(payload)
            except Exception:  # تكملة السطر السابق داخل القوس
                return payload  # إرجاع payload
        if "deflate" in enc:  # شرط: 'deflate' ضمن enc
            try:  # بدايةtry محمية (يليها except/finally)
                return zlib.decompress(payload)  # إرجاع zlib.decompress(payload)
            except Exception:  # تكملة السطر السابق داخل القوس
                try:  # بدايةtry محمية (يليها except/finally)
                    return zlib.decompress(payload, -zlib.MAX_WBITS)  # إرجاع zlib.decompress(payload, نفي/سالب)
                except Exception:  # تكملة السطر السابق داخل القوس
                    return payload  # إرجاع payload
        return payload  # إرجاع payload


def open_url(url: str, timeout=None, headers=None) -> Response:  # تعريف الدالة open_url(url, timeout, headers) ترجع Response
    """One-shot GET with a throw-away session (used for quick checks)."""  # نص توثيقي (docstring) يشرح ما يليه
    s = Session(headers=headers)  # إسناد نتيجة استدعاء Session (headers=…) إلى s
    try:  # بدايةtry محمية (يليها except/finally)
        return s.get(url, timeout=timeout)  # إرجاع s.get(url, timeout=timeout)
    finally:  # مفتاح finally في القاموس
        s.close()  # استدعاء s.close


def local_ip() -> str:  # تعريف الدالة local_ip() ترجع str
    """Best-effort local IP, used to print the LAN link of the web UI."""  # نص توثيقي (docstring) يشرح ما يليه
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # إسناد نتيجة استدعاء socket.socket (2 معاملات) إلى s
    try:  # بدايةtry محمية (يليها except/finally)
        s.connect(("10.255.255.255", 1))  # استدعاء s.connect (معامل واحد)
        return s.getsockname()[0]  # إرجاع s.getsockname()[0]
    except Exception:  # تكملة السطر السابق داخل القوس
        return "127.0.0.1"  # إرجاع '127.0.0.1'
    finally:  # مفتاح finally في القاموس
        s.close()  # استدعاء s.close
