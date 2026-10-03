# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""A small, honest captive-portal simulator used by the self-test.

It behaves like the real thing in the ways that matter for this tool:

* POST / GET login form with hidden dst/popup fields
* a per-request session token in the page (so naive byte comparison fails)
* the error text re-rendered into the same page for a wrong card
* 302 redirect to the internet for a good card
* optional MikroTik chap (md5.js) password scheme
* optional ban page, 429 rate limiting and dropped connections

The self-test is how a user can *see* the tool working without touching any
real network.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import hashlib  # استيراد الوحدة hashlib من المكتبة
import http.server  # استيراد الوحدة http.server من المكتبة
import random  # استيراد الوحدة random من المكتبة
import socket  # استيراد الوحدة socket من المكتبة
import socketserver  # استيراد الوحدة socketserver من المكتبة
import string  # استيراد الوحدة string من المكتبة
import threading  # استيراد الوحدة threading من المكتبة
import time  # استيراد الوحدة time من المكتبة
import urllib.parse  # استيراد الوحدة urllib.parse من المكتبة
import uuid  # استيراد الوحدة uuid من المكتبة

# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
CARD_PAGE = """<!DOCTYPE html><html><head><title>Hotspot Login</title>
<script type="text/javascript" src="md5.js"></script>
<script>
var mac = "4C:5E:0C:11:22:{mac_tail}";
function doLogin() {{
  document.login.password.value = hexMD5('{chap_id}' +
      document.login.password.value + '{chap_challenge}');
  return true;
}}
</script></head><body>
<div id="wrapper"><div id="main">
<p id="message">{message}</p>
<form name="login" action="{action}" method="{method}" onSubmit="return doLogin()">
<input type="hidden" name="dst" value="{dst}">
<input type="hidden" name="popup" value="true">{tok_field}
<input type="text" name="username" value="{echo_user}">
<input type="password" name="password" value="">
<input type="submit" value="Connect">
</form>
<div id="session">session: {nonce}</div>
<script>var nonce = "{nonce}";</script>
</div></div></body></html>"""  # نهاية النص متعدد الأسطر

# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
BAN_PAGE = """<html><head><title>Blocked</title></head><body>
<h1>You are blocked</h1><p>Too many login attempts from your address.</p>
</body></html>"""  # نهاية النص متعدد الأسطر

# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
RATE_PAGE = """<html><head><title>Slow down</title></head><body>
<p>rate limit exceeded, please slow down</p></body></html>"""  # نهاية النص متعدد الأسطر

# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
SUCCESS_PAGE = """<!DOCTYPE html><html><head><title>Welcome</title></head>
<body><h1>You are logged in</h1>
<p>Welcome to the network. Remaining time 3h 59m.</p>
<p><a href="/status">statistics</a></p>
</body></html>"""  # نهاية النص متعدد الأسطر


class PortalState:  # تعريف الصنف PortalState
    def __init__(self, valid_cards, pass_mode="same", method="post",  # تعريف الدالة __init__(self, valid_cards, pass_mode, method, dynamic, ban_after, ban_seconds, rate_limit_after, drop_every, drop_after, chap, prefix, length, error_text, hide_success, require_session, reject_shape, success_page, unknown_success_page, global_online_login_page, login_page_extra)
                 dynamic=True, ban_after=0, ban_seconds=0,  # المعامل المسمّى dynamic
                 rate_limit_after=0, drop_every=0,  # المعامل المسمّى rate_limit_after
                 drop_after=0, chap=False, prefix="02", length=6,  # المعامل المسمّى drop_after
                 error_text=None, hide_success=False, require_session=False,  # المعامل المسمّى error_text
                 reject_shape=False, success_page=False,  # المعامل المسمّى reject_shape
                 unknown_success_page=False, global_online_login_page=False,  # المعامل المسمّى unknown_success_page
                 login_page_extra=""):  # المعامل المسمّى login_page_extra
        self.valid_cards = set(valid_cards)  # إسناد نتيجة استدعاء set (معامل واحد) إلى self.valid_cards
        self.pass_mode = pass_mode          # same | empty | chap
        self.method = method  # إسناد method إلى self.method
        self.dynamic = dynamic  # إسناد dynamic إلى self.dynamic
        self.ban_after = ban_after          # 0 = لا يحجب أبداً
        self.ban_seconds = ban_seconds      # 0 = الحجب لا يزول أبداً
        self.banned_at = 0.0  # إسناد القيمة الثابتة self.banned_at
        # hide_success: البطاقة تُدخل الضيف فعلاً، لكن الراوتر ما يزال
        # يردّ بصفحة الرفض — أخبث حالة حقيقية، والوحيدة
        # التي لا يكشفها إلا مراقب «هل فتح الإنترنت؟»
        self.hide_success = hide_success  # إسناد hide_success إلى self.hide_success
        # require_session: بوابة حقيقية توزع كوكي جلسة ورمزاً
        # في صفحة الدخول وترفض الإرسال بدونهما (هذا ما يفعله
        # المتصفح تلقائياً ولا يفعله سكربت عارٍ)
        self.require_session = require_session  # إسناد require_session إلى self.require_session
        self.reject_shape = reject_shape  # إسناد reject_shape إلى self.reject_shape
        self.success_page = success_page  # إسناد success_page إلى self.success_page
        # البوابة تقبل البطاقة وتفتح الشبكة لكن تردّ بصفحة
        # HTTP 200 مختلفة غير موسومة. هذا يحاكي نجاحاً لا يستطيع
        # مصنف يعتمد على الرد وحده إثباته بلا فحص إنترنت.
        self.unknown_success_page = unknown_success_page  # إسناد unknown_success_page إلى self.unknown_success_page
        # بعض البوابات ترجع صفحة المصادقة/الحالة لكل طلب دخول
        # لاحق من نفس الجهاز بمجرد فتح جلسة بوابته.
        # هذا يحاكي تحققات كاذبة لكل بطاقة في التشغيلات المتوازية.
        self.global_online_login_page = global_online_login_page  # إسناد global_online_login_page إلى self.global_online_login_page
        # ترميز خام يُضاف إلى كل صفحة دخول تقدّمها هذه البوابة. يُستخدم
        # لمحاكاة البوابات الحقيقية التي تذكر سكربتها صفحة حجب
        # (window.location = "blocked.html" خلف عدّاد في المتصفح):
        # فتكون كلمة الحجب في كل رد، حجباً كان أم لا.
        self.login_page_extra = login_page_extra  # إسناد login_page_extra إلى self.login_page_extra
        self.tokens = {}  # إسناد قاموس إلى self.tokens
        self.bad_requests = 0  # إسناد القيمة الثابتة self.bad_requests
        self.rate_limit_after = rate_limit_after  # إسناد rate_limit_after إلى self.rate_limit_after
        self.drop_every = drop_every  # إسناد drop_every إلى self.drop_every
        self.drop_after = drop_after      # اقطع كل طلب بعد هذا العدد
        self.chap = chap  # إسناد chap إلى self.chap
        self.chap_id = "a1b2c3d4"  # إسناد القيمة الثابتة self.chap_id
        self.chap_challenge = "9f8e7d6c"  # إسناد القيمة الثابتة self.chap_challenge
        self.error_text = error_text or "invalid username or password"  # دمج منطقي (أو) وإسناده إلى self.error_text
        self.use_prefix_free = True  # إسناد القيمة الثابتة self.use_prefix_free
        self.lock = threading.Lock()  # إسناد نتيجة استدعاء threading.Lock إلى self.lock
        self.requests = 0  # إسناد القيمة الثابتة self.requests
        self.logins = 0  # إسناد القيمة الثابتة self.logins
        self.failures = 0  # إسناد القيمة الثابتة self.failures
        self.bans = 0  # إسناد القيمة الثابتة self.bans
        self.hidden_successes = 0  # إسناد القيمة الثابتة self.hidden_successes
        self.rate_hits = 0  # إسناد القيمة الثابتة self.rate_hits
        self.online_ips = set()  # إسناد نتيجة استدعاء set إلى self.online_ips
        self.asked_cards = []  # إسناد قائمة إلى self.asked_cards
        self.started = time.time()  # إسناد نتيجة استدعاء time.time إلى self.started

    # -- العدّادات ---------------------------------------------------------
    def bump(self, field, n=1):  # تعريف الدالة bump(self, field, n)
        with self.lock:  # سياق مُدار: self.lock
            setattr(self, field, getattr(self, field) + n)  # استدعاء setattr (3 معاملات)

    def snapshot(self) -> dict:  # تعريف الدالة snapshot(self) ترجع dict
        with self.lock:  # سياق مُدار: self.lock
            return {"requests": self.requests, "logins": self.logins,  # إرجاع قاموس
                    "failures": self.failures, "bans": self.bans,  # مفتاح failures في القاموس
                    "rate_hits": self.rate_hits,  # مفتاح rate_hits في القاموس
                    "online_ips": len(self.online_ips)}  # مفتاح online_ips في القاموس


class Handler(http.server.BaseHTTPRequestHandler):  # تعريف الصنف Handler يرث من http.server.BaseHTTPRequestHandler
    protocol_version = "HTTP/1.1"  # إسناد القيمة الثابتة protocol_version
    server_version = "MockHotspot/1.0"  # إسناد القيمة الثابتة server_version

    def log_message(self, *args):  # تعريف الدالة log_message(self, *args)
        if self.server.verbose:  # شرط: self.server.verbose
            super().log_message(*args)  # استدعاء super().log_message (معامل واحد)

    # -- الأنابيب ---------------------------------------------------------
    def _reply(self, code, body, headers=None):  # تعريف الدالة _reply(self, code, body, headers)
        # بوابة حقيقية تضبط كوكي جلستها مع الصفحة
        sid = getattr(self, "_new_cookie", None)  # إسناد نتيجة استدعاء getattr (3 معاملات) إلى sid
        if sid:  # شرط: sid
            self._new_cookie = None  # إسناد القيمة الثابتة self._new_cookie
            headers = dict(headers or {})  # إسناد نتيجة استدعاء dict (معامل واحد) إلى headers
            headers["Set-Cookie"] = "portal_sid=%s; Path=/" % sid  # حساب باقي القسمة بين 'portal_sid=%s; Path=/' وsid وإسناده إلى headers['Set-Cookie']
        return self._raw_reply(code, body, headers)  # إرجاع self._raw_reply(code, body, headers)

    def _raw_reply(self, code, body: str, headers=None):  # تعريف الدالة _raw_reply(self, code, body, headers)
        payload = body.encode("utf-8")  # إسناد نتيجة استدعاء body.encode (معامل واحد) إلى payload
        self.send_response(code)  # استدعاء self.send_response (معامل واحد)
        self.send_header("Content-Type", "text/html; charset=utf-8")  # استدعاء self.send_header (2 معاملات)
        self.send_header("Content-Length", str(len(payload)))  # استدعاء self.send_header (2 معاملات)
        for key, value in (headers or {}).items():  # دورة على headers أو قاموس.items() باسم مجموعة
            self.send_header(key, value)  # استدعاء self.send_header (2 معاملات)
        self.end_headers()  # استدعاء self.end_headers
        if payload:  # شرط: payload
            try:  # بدايةtry محمية (يليها except/finally)
                self.wfile.write(payload)  # استدعاء self.wfile.write (معامل واحد)
            except (BrokenPipeError, ConnectionResetError):  # تكملة السطر السابق داخل القوس
                pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً

    def do_GET(self):  # تعريف الدالة do_GET(self)
        self._handle("GET")  # استدعاء self._handle (معامل واحد)

    def do_POST(self):  # تعريف الدالة do_POST(self)
        self._handle("POST")  # استدعاء self._handle (معامل واحد)

    def _handle(self, method):  # تعريف الدالة _handle(self, method)
        st = self.server.state  # إسناد self.server.state إلى st
        st.bump("requests")  # استدعاء st.bump (معامل واحد)
        with st.lock:  # سياق مُدار: st.lock
            n = st.requests  # إسناد st.requests إلى n
        # يحاكي راوتراً يقطع الاتصالات (تحت ضغط، أو ميت)
        drop = bool((st.drop_every and n % st.drop_every == 0)  # إسناد نتيجة استدعاء bool (معامل واحد) إلى drop
                    or (st.drop_after and n > st.drop_after))  # تكملة السطر السابق داخل القوس
        if drop:  # شرط: drop
            try:  # بدايةtry محمية (يليها except/finally)
                self.connection.shutdown(socket.SHUT_RDWR)  # استدعاء self.connection.shutdown (معامل واحد)
            except OSError:  # تكملة السطر السابق داخل القوس
                pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
            try:  # بدايةtry محمية (يليها except/finally)
                self.connection.close()  # استدعاء self.connection.close
            except OSError:  # تكملة السطر السابق داخل القوس
                pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
            self.close_connection = True  # إسناد القيمة الثابتة self.close_connection
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)

        # فرّغ الجسم دائماً، وإلا اختل تزامن keep-alive
        body = b""  # إسناد القيمة الثابتة body
        try:  # بدايةtry محمية (يليها except/finally)
            length = int(self.headers.get("Content-Length") or 0)  # إسناد نتيجة استدعاء int (معامل واحد) إلى length
        except ValueError:  # تكملة السطر السابق داخل القوس
            length = 0  # إسناد القيمة الثابتة length
        if length:  # شرط: length
            body = self.rfile.read(length)  # إسناد نتيجة استدعاء self.rfile.read (معامل واحد) إلى body

        parts = urllib.parse.urlsplit(self.path)  # إسناد نتيجة استدعاء urllib.parse.urlsplit (معامل واحد) إلى parts
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}  # بناء قاموس بالاشتقاق وإسناده إلى query
        form = {k: v[0] for k, v in  # بناء قاموس بالاشتقاق وإسناده إلى form
                urllib.parse.parse_qs(body.decode("utf-8", "replace")).items()}  # تكملة السطر السابق داخل القوس
        fields = dict(query)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى fields
        fields.update(form)  # استدعاء fields.update (معامل واحد)
        base = f"http://{self.headers.get('Host', '127.0.0.1')}"  # بناء نص منسّق وإسناده إلى base

        if parts.path in ("/generate_204", "/connecttest.txt",  # شرط: parts.path ضمن مجموعة
                          "/hotspot-detect.html"):  # تكملة تعريف متعدد الأسطر
            return self._internet_check(parts.path, base)  # إرجاع self._internet_check(parts.path, base)

        if parts.path.startswith("/logout"):  # شرط: نتيجة parts.path.startswith('/logout')
            with st.lock:  # سياق مُدار: st.lock
                st.online_ips = set()  # إسناد نتيجة استدعاء set إلى st.online_ips
            return self._reply(200, "<html><title>Logged out</title>bye</html>")  # إرجاع self._reply(200, '<html><title>Logged out</title>bye</html>')

        if parts.path.startswith("/success"):  # شرط: نتيجة parts.path.startswith('/success')
            online = self.client_address[0] in st.online_ips  # مقارنة (ضمن) وإسناد النتيجة المنطقية إلى online
            if not online:  # شرط معكوس: ليس online
                return self._reply(302, "", {"Location": base + "/login"})  # إرجاع self._reply(302, '', قاموس)
            return self._reply(200, SUCCESS_PAGE)  # إرجاع self._reply(200, SUCCESS_PAGE)

        if parts.path.startswith("/status"):  # شرط: نتيجة parts.path.startswith('/status')
            online = self.client_address[0] in st.online_ips  # مقارنة (ضمن) وإسناد النتيجة المنطقية إلى online
            if not online:  # شرط معكوس: ليس online
                return self._reply(302, "", {"Location": base + "/login"})  # إرجاع self._reply(302, '', قاموس)
            return self._reply(200, "<html><head><title>Status</title></head><body>"  # إرجاع self._reply(200, "<html><head><title>Status</title></head><body>You are logged in, session uptime 0:01:20 remaining 3h 59m <a href='/logout'>logout</a><form action='/status'><input type='hidden' name='erase-cookie' value='1'></form></body></html>")
                                    "You are logged in, session uptime 0:01:20 "  # تكملة السطر السابق داخل القوس
                                    "remaining 3h 59m <a href='/logout'>logout</a>"  # تكملة السطر السابق داخل القوس
                                    "<form action='/status'><input type='hidden' "  # تكملة السطر السابق داخل القوس
                                    "name='erase-cookie' value='1'></form></body></html>")  # تكملة السطر السابق داخل القوس

        if not parts.path.startswith("/login"):  # شرط معكوس: ليس parts.path.startswith('/login')
            return self._reply(404, "<html>not found</html>")  # إرجاع self._reply(404, '<html>not found</html>')

        # --- صفحة الدخول (GET بلا بطاقة = اعرض النموذج فقط) ----
        if method == "GET" and not query.get("username"):  # شرط مركّب (و)
            return self._login_page(base, fields)  # إرجاع self._login_page(base, fields)

        # --- سلوك الحجب / تقييد الطلبات ------------------------------
        # راوتر حقيقي يسامح بعد حين: مع ban_seconds يزول
        # القفل وحده ويبدأ عدّاد الفشل من جديد (هذا ما يعتمد عليه
        # «انتظر زواله وجرّب مجدداً»).
        if (st.ban_after and st.banned_at and st.ban_seconds and  # شرط مركّب (و)
                time.time() - st.banned_at > st.ban_seconds):  # تكملة تعريف متعدد الأسطر
            with st.lock:  # سياق مُدار: st.lock
                st.failures = 0  # إسناد القيمة الثابتة st.failures
                st.banned_at = 0.0  # إسناد القيمة الثابتة st.banned_at
        if st.ban_after and st.failures >= st.ban_after:  # شرط مركّب (و)
            st.bump("bans")  # استدعاء st.bump (معامل واحد)
            if not st.banned_at:  # شرط معكوس: ليس st.banned_at
                st.banned_at = time.time()  # إسناد نتيجة استدعاء time.time إلى st.banned_at
            return self._reply(403, BAN_PAGE,  # إرجاع self._reply(403, BAN_PAGE, قاموس)
                               {"Retry-After": str(st.ban_seconds or 30)})  # تكملة السطر السابق داخل القوس
        if st.rate_limit_after and st.failures >= st.rate_limit_after:  # شرط مركّب (و)
            st.bump("rate_hits")  # استدعاء st.bump (معامل واحد)
            return self._reply(429, RATE_PAGE, {"Retry-After": "1"})  # إرجاع self._reply(429, RATE_PAGE, قاموس)

        if st.require_session:  # شرط: st.require_session
            sid = ""  # إسناد القيمة الثابتة sid
            for part in (self.headers.get("Cookie") or "").split(";"):  # دورة على self.headers.get('Cookie') أو ''.split(';') باسم part
                if part.strip().startswith("portal_sid="):  # شرط: نتيجة part.strip().startswith('portal_sid=')
                    sid = part.strip().split("=", 1)[1]  # إسناد part.strip().split('=', 1)[1] إلى sid
            if not sid or fields.get("tok") != st.tokens.get(sid):  # شرط مركّب (أو)
                return self._bad_request()  # إرجاع self._bad_request()
            # رمز CSRF الصارم أحادي الاستخدام: صفحة الدخول الراجعة تعطي
            # المتصفح الرمز التالي. هذا يمسك السكربتات التي تجلب
            # الصفحة مرة واحدة ثم تعيد استخدام قيمتها المخفية الأولى للأبد.
            st.tokens[sid] = uuid.uuid4().hex[:16]  # إسناد uuid.uuid4().hex[] إلى st.tokens[sid]

        if st.reject_shape:  # شرط: st.reject_shape
            return self._bad_request("bad request: request shape rejected")  # إرجاع self._bad_request('bad request: request shape rejected')

        card = fields.get("username", "")  # إسناد نتيجة استدعاء fields.get (2 معاملات) إلى card
        password = fields.get("password", "")  # إسناد نتيجة استدعاء fields.get (2 معاملات) إلى password
        with st.lock:  # سياق مُدار: st.lock
            st.logins += 1  # تحديث st.logins بعملية جمع
            st.asked_cards.append(card)  # استدعاء st.asked_cards.append (معامل واحد)
            already_online = self.client_address[0] in st.online_ips  # مقارنة (ضمن) وإسناد النتيجة المنطقية إلى already_online
        if st.global_online_login_page and already_online:  # شرط مركّب (و)
            return self._reply(200, SUCCESS_PAGE)  # إرجاع self._reply(200, SUCCESS_PAGE)

        if self._is_valid(card, password):  # شرط: نتيجة self._is_valid(card, password)
            with st.lock:  # سياق مُدار: st.lock
                st.online_ips.add(self.client_address[0])  # استدعاء st.online_ips.add (معامل واحد)
            if st.hide_success:  # شرط: st.hide_success
                # دخل، لكن الردّ حرفياً صفحة رفض
                st.bump("hidden_successes")  # استدعاء st.bump (معامل واحد)
                return self._login_page(base, fields, error=True)  # إرجاع self._login_page(base, fields, error=True)
            if st.unknown_success_page:  # شرط: st.unknown_success_page
                return self._reply(  # إرجاع self._reply(200, '<html><body><h1>Portal session updated</h1><p>Account settings were refreshed.</p></body></html>')
                    200, "<html><body><h1>Portal session updated</h1>"  # تكملة السطر السابق داخل القوس
                         "<p>Account settings were refreshed.</p></body></html>")  # تكملة السطر السابق داخل القوس
            if st.success_page:  # شرط: st.success_page
                return self._reply(302, "", {"Location": base + "/success"})  # إرجاع self._reply(302, '', قاموس)
            return self._reply(302, "", {  # إرجاع self._reply(302, '', قاموس)
                "Location": "http://connectivitycheck.gstatic.com/generate_204"})  # مفتاح Location في القاموس

        st.bump("failures")  # استدعاء st.bump (معامل واحد)
        return self._login_page(base, fields, error=True)  # إرجاع self._login_page(base, fields, error=True)

    # -- مساعدات ---------------------------------------------------------
    def _internet_check(self, path, base):  # تعريف الدالة _internet_check(self, path, base)
        st = self.server.state  # إسناد self.server.state إلى st
        online = self.client_address[0] in st.online_ips  # مقارنة (ضمن) وإسناد النتيجة المنطقية إلى online
        if path == "/generate_204":  # شرط: path يساوي '/generate_204'
            if online:  # شرط: online
                return self._reply(204, "")  # إرجاع self._reply(204, '')
        elif path == "/connecttest.txt":  # شرط: path يساوي '/connecttest.txt'
            if online:  # شرط: online
                return self._reply(200, "Microsoft Connect Test")  # إرجاع self._reply(200, 'Microsoft Connect Test')
        elif path == "/hotspot-detect.html":  # شرط: path يساوي '/hotspot-detect.html'
            if online:  # شرط: online
                return self._reply(200, "<HTML><HEAD><TITLE>Success</TITLE></HEAD>"  # إرجاع self._reply(200, '<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>')
                                        "<BODY>Success</BODY></HTML>")  # تكملة السطر السابق داخل القوس
        # بوابة أسر تعترض الطلب بدلاً من ذلك
        return self._reply(302, "", {"Location": base + "/login?dst=" +  # إرجاع self._reply(302, '', قاموس)
                                     urllib.parse.quote(path, safe="")})  # تكملة السطر السابق داخل القوس

    def _session_id(self) -> str:  # تعريف الدالة _session_id(self) ترجع str
        """The portal's session cookie: created on the first page view."""  # نص توثيقي (docstring) يشرح ما يليه
        st = self.server.state  # إسناد self.server.state إلى st
        raw = self.headers.get("Cookie") or ""  # دمج منطقي (أو) وإسناده إلى raw
        sid = ""  # إسناد القيمة الثابتة sid
        for part in raw.split(";"):  # دورة على raw.split(';') باسم part
            if part.strip().startswith("portal_sid="):  # شرط: نتيجة part.strip().startswith('portal_sid=')
                sid = part.strip().split("=", 1)[1]  # إسناد part.strip().split('=', 1)[1] إلى sid
        if not sid or sid not in st.tokens:  # شرط مركّب (أو)
            sid = uuid.uuid4().hex[:12]  # إسناد uuid.uuid4().hex[] إلى sid
            st.tokens[sid] = uuid.uuid4().hex[:16]  # إسناد uuid.uuid4().hex[] إلى st.tokens[sid]
            self._new_cookie = sid  # إسناد sid إلى self._new_cookie
        return sid  # إرجاع sid

    def _bad_request(self, why="bad request: the form token is missing or old"):  # تعريف الدالة _bad_request(self, why)
        st = self.server.state  # إسناد self.server.state إلى st
        st.bump("bad_requests")  # استدعاء st.bump (معامل واحد)
        return self._reply(400, "<html><body>%s</body></html>" % why)  # إرجاع self._reply(400, باقي القسمة)

    def _is_valid(self, card, password) -> bool:  # تعريف الدالة _is_valid(self, card, password) ترجع bool
        st = self.server.state  # إسناد self.server.state إلى st
        if card not in st.valid_cards:  # شرط: card ليس ضمن st.valid_cards
            return False  # إرجاع False
        if st.pass_mode == "empty":  # شرط: st.pass_mode يساوي 'empty'
            return password == ""  # إرجاع مقارنة
        if st.pass_mode == "same":  # شرط: st.pass_mode يساوي 'same'
            if password == card:  # شرط: password يساوي card
                return True  # إرجاع True
            if st.chap:  # شرط: st.chap
                return password == self._chap(card)  # إرجاع مقارنة
            return False  # إرجاع False
        if st.pass_mode == "chap":  # شرط: st.pass_mode يساوي 'chap'
            return password == self._chap(card)  # إرجاع مقارنة
        return False  # إرجاع False

    def _chap(self, raw: str) -> str:  # تعريف الدالة _chap(self, raw) ترجع str
        st = self.server.state  # إسناد self.server.state إلى st
        return hashlib.md5(f"{st.chap_id}{raw}{st.chap_challenge}".encode()).hexdigest()  # إرجاع hashlib.md5(نص منسّق (f-string).encode()).hexdigest()

    def _login_page(self, base, fields, error=False):  # تعريف الدالة _login_page(self, base, fields, error)
        st = self.server.state  # إسناد self.server.state إلى st
        tok_field = ""  # إسناد القيمة الثابتة tok_field
        if st.require_session:  # شرط: st.require_session
            sid = self._session_id()  # إسناد نتيجة استدعاء self._session_id إلى sid
            tok_field = ('<input type="hidden" name="tok" value="%s">'  # حساب باقي القسمة بين '<input type="hidden" name="tok" value="%s">' وst.tokens.get(sid, '') وإسناده إلى tok_field
                         % st.tokens.get(sid, ""))  # تكملة السطر السابق داخل القوس
        # إسناد ''.join(random.choices(string.hexdigits.lower()[], k=8)) إن st.dynamic وإلا 'fixednonce' إلى nonce
        nonce = "".join(random.choices(string.hexdigits.lower()[:16], k=8)) \
            if st.dynamic else "fixednonce"  # تكملة السطر السابق داخل القوس
        message = st.error_text if error else ""  # إسناد st.error_text إن error وإلا '' إلى message
        html = CARD_PAGE.format(  # إسناد نتيجة استدعاء CARD_PAGE.format (action=…، method=…، dst=…، echo_user=…، nonce=…، message=…، tok_field=…، chap_id=…، chap_challenge=…، mac_tail=…) إلى html
            action=base + "/login", method=st.method,  # المعامل المسمّى action
            dst=fields.get("dst", ""), echo_user=fields.get("username", ""),  # المعامل المسمّى dst
            nonce=nonce, message=message, tok_field=tok_field,  # المعامل المسمّى nonce
            chap_id=st.chap_id, chap_challenge=st.chap_challenge,  # المعامل المسمّى chap_id
            mac_tail="33:44")  # المعامل المسمّى mac_tail
        if st.login_page_extra:  # شرط: إن طلبت البوابة ترميزاً إضافياً في صفحة الدخول
            html = html.replace("</body>", st.login_page_extra + "</body>")  # إدراج الترميز الإضافي قبل إغلاق body
        return self._reply(200, html)  # إرجاع self._reply(200, html)


class _Server(socketserver.ThreadingTCPServer):  # تعريف الصنف _Server يرث من socketserver.ThreadingTCPServer
    allow_reuse_address = True  # إسناد القيمة الثابتة allow_reuse_address

    def server_bind(self):  # تعريف الدالة server_bind(self)
        socketserver.TCPServer.server_bind(self)  # استدعاء socketserver.TCPServer.server_bind (معامل واحد)
        host, port = self.server_address[:2]  # إسناد self.server_address[] إلى مجموعة
        self.server_name, self.server_port = host, port  # إسناد مجموعة إلى مجموعة


class MockPortal:  # تعريف الصنف MockPortal
    """Start/stop wrapper around the handler."""  # نص توثيقي (docstring) يشرح ما يليه

    def __init__(self, port: int = 0, **kwargs):  # تعريف الدالة __init__(self, port, **kwargs)
        self.state = PortalState(**kwargs)  # إسناد نتيجة استدعاء PortalState (**=…) إلى self.state
        self.httpd = _Server(("127.0.0.1", port), Handler)  # إسناد نتيجة استدعاء _Server (2 معاملات) إلى self.httpd
        self.httpd.daemon_threads = True  # إسناد القيمة الثابتة self.httpd.daemon_threads
        self.httpd.state = self.state  # إسناد self.state إلى self.httpd.state
        self.httpd.verbose = False  # إسناد القيمة الثابتة self.httpd.verbose
        self.port = self.httpd.server_address[1]  # إسناد self.httpd.server_address[1] إلى self.port
        self.thread = None  # إسناد القيمة الثابتة self.thread

    @property  # مُزخرف (decorator) بـproperty
    def url(self) -> str:  # تعريف الدالة url(self) ترجع str
        return f"http://127.0.0.1:{self.port}/login"  # إرجاع نص منسّق (f-string)

    @property  # مُزخرف (decorator) بـproperty
    def base(self) -> str:  # تعريف الدالة base(self) ترجع str
        return f"http://127.0.0.1:{self.port}"  # إرجاع نص منسّق (f-string)

    def start(self):  # تعريف الدالة start(self)
        self.thread = threading.Thread(target=self.httpd.serve_forever,  # إسناد نتيجة استدعاء threading.Thread (target=…، kwargs=…، daemon=…) إلى self.thread
                                       kwargs={"poll_interval": 0.1}, daemon=True)  # المعامل المسمّى kwargs
        self.thread.start()  # استدعاء self.thread.start
        return self  # إرجاع self

    def stop(self):  # تعريف الدالة stop(self)
        try:  # بدايةtry محمية (يليها except/finally)
            self.httpd.shutdown()  # استدعاء self.httpd.shutdown
            self.httpd.server_close()  # استدعاء self.httpd.server_close
        except Exception:  # تكملة السطر السابق داخل القوس
            pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً

    def __enter__(self):  # تعريف الدالة __enter__(self)
        return self.start()  # إرجاع self.start()

    def __exit__(self, *exc):  # تعريف الدالة __exit__(self, *exc)
        self.stop()  # استدعاء self.stop
        return False  # إرجاع False
