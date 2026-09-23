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
"""

from __future__ import annotations

import hashlib
import http.server
import random
import socket
import socketserver
import string
import threading
import time
import urllib.parse

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
<input type="hidden" name="popup" value="true">
<input type="text" name="username" value="{echo_user}">
<input type="password" name="password" value="">
<input type="submit" value="Connect">
</form>
<div id="session">session: {nonce}</div>
<script>var nonce = "{nonce}";</script>
</div></div></body></html>"""

BAN_PAGE = """<html><head><title>Blocked</title></head><body>
<h1>You are blocked</h1><p>Too many login attempts from your address.</p>
</body></html>"""

RATE_PAGE = """<html><head><title>Slow down</title></head><body>
<p>rate limit exceeded, please slow down</p></body></html>"""


class PortalState:
    def __init__(self, valid_cards, pass_mode="same", method="post",
                 dynamic=True, ban_after=0, rate_limit_after=0, drop_every=0,
                 drop_after=0, chap=False, prefix="02", length=6,
                 error_text=None):
        self.valid_cards = set(valid_cards)
        self.pass_mode = pass_mode          # same | empty | chap
        self.method = method
        self.dynamic = dynamic
        self.ban_after = ban_after          # 0 = never
        self.rate_limit_after = rate_limit_after
        self.drop_every = drop_every
        self.drop_after = drop_after      # drop EVERY request after this many
        self.chap = chap
        self.chap_id = "a1b2c3d4"
        self.chap_challenge = "9f8e7d6c"
        self.error_text = error_text or "invalid username or password"
        self.use_prefix_free = True
        self.lock = threading.Lock()
        self.requests = 0
        self.logins = 0
        self.failures = 0
        self.bans = 0
        self.rate_hits = 0
        self.online_ips = set()
        self.asked_cards = []
        self.started = time.time()

    # -- counters ---------------------------------------------------------
    def bump(self, field, n=1):
        with self.lock:
            setattr(self, field, getattr(self, field) + n)

    def snapshot(self) -> dict:
        with self.lock:
            return {"requests": self.requests, "logins": self.logins,
                    "failures": self.failures, "bans": self.bans,
                    "rate_hits": self.rate_hits,
                    "online_ips": len(self.online_ips)}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "MockHotspot/1.0"

    def log_message(self, *args):
        if self.server.verbose:
            super().log_message(*args)

    # -- plumbing ---------------------------------------------------------
    def _reply(self, code, body: str, headers=None):
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if payload:
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        st = self.server.state
        st.bump("requests")
        with st.lock:
            n = st.requests
        # simulate a router that drops connections (under load, or dead)
        drop = bool((st.drop_every and n % st.drop_every == 0)
                    or (st.drop_after and n > st.drop_after))
        if drop:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.connection.close()
            except OSError:
                pass
            self.close_connection = True
            return

        # always drain the body, otherwise keep-alive desynchronises
        body = b""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length:
            body = self.rfile.read(length)

        parts = urllib.parse.urlsplit(self.path)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}
        form = {k: v[0] for k, v in
                urllib.parse.parse_qs(body.decode("utf-8", "replace")).items()}
        fields = dict(query)
        fields.update(form)
        base = f"http://{self.headers.get('Host', '127.0.0.1')}"

        if parts.path in ("/generate_204", "/connecttest.txt",
                          "/hotspot-detect.html"):
            return self._internet_check(parts.path, base)

        if parts.path.startswith("/logout"):
            with st.lock:
                st.online_ips = set()
            return self._reply(200, "<html><title>Logged out</title>bye</html>")

        if parts.path.startswith("/status"):
            online = self.client_address[0] in st.online_ips
            if not online:
                return self._reply(302, "", {"Location": base + "/login"})
            return self._reply(200, "<html><title>Status</title>You are logged in"
                                    ", session uptime 0:01:20 remaining 3h 59m"
                                    " <a href='/logout'>logout</a></html>")

        if not parts.path.startswith("/login"):
            return self._reply(404, "<html>not found</html>")

        # --- the login page (GET with no card = just show the form) ----
        if method == "GET" and not query.get("username"):
            return self._login_page(base, fields)

        # --- ban / rate-limit behaviour ------------------------------
        if st.ban_after and st.failures >= st.ban_after:
            st.bump("bans")
            return self._reply(403, BAN_PAGE,
                               {"Retry-After": "30"} if st.ban_after else None)
        if st.rate_limit_after and st.failures >= st.rate_limit_after:
            st.bump("rate_hits")
            return self._reply(429, RATE_PAGE, {"Retry-After": "1"})

        card = fields.get("username", "")
        password = fields.get("password", "")
        with st.lock:
            st.logins += 1
            st.asked_cards.append(card)

        if self._is_valid(card, password):
            with st.lock:
                st.online_ips.add(self.client_address[0])
            st.bump("logins")
            return self._reply(302, "", {
                "Location": "http://connectivitycheck.gstatic.com/generate_204"})

        st.bump("failures")
        return self._login_page(base, fields, error=True)

    # -- helpers ---------------------------------------------------------
    def _internet_check(self, path, base):
        st = self.server.state
        online = self.client_address[0] in st.online_ips
        if path == "/generate_204":
            if online:
                return self._reply(204, "")
        elif path == "/connecttest.txt":
            if online:
                return self._reply(200, "Microsoft Connect Test")
        elif path == "/hotspot-detect.html":
            if online:
                return self._reply(200, "<HTML><HEAD><TITLE>Success</TITLE></HEAD>"
                                        "<BODY>Success</BODY></HTML>")
        # a captive portal hijacks the request instead
        return self._reply(302, "", {"Location": base + "/login?dst=" +
                                     urllib.parse.quote(path, safe="")})

    def _is_valid(self, card, password) -> bool:
        st = self.server.state
        if card not in st.valid_cards:
            return False
        if st.pass_mode == "empty":
            return password == ""
        if st.pass_mode == "same":
            if password == card:
                return True
            if st.chap:
                return password == self._chap(card)
            return False
        if st.pass_mode == "chap":
            return password == self._chap(card)
        return False

    def _chap(self, raw: str) -> str:
        st = self.server.state
        return hashlib.md5(f"{st.chap_id}{raw}{st.chap_challenge}".encode()).hexdigest()

    def _login_page(self, base, fields, error=False):
        st = self.server.state
        nonce = "".join(random.choices(string.hexdigits.lower()[:16], k=8)) \
            if st.dynamic else "fixednonce"
        message = st.error_text if error else ""
        html = CARD_PAGE.format(
            action=base + "/login", method=st.method,
            dst=fields.get("dst", ""), echo_user=fields.get("username", ""),
            nonce=nonce, message=message,
            chap_id=st.chap_id, chap_challenge=st.chap_challenge,
            mac_tail="33:44")
        return self._reply(200, html)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name, self.server_port = host, port


class MockPortal:
    """Start/stop wrapper around the handler."""

    def __init__(self, port: int = 0, **kwargs):
        self.state = PortalState(**kwargs)
        self.httpd = _Server(("127.0.0.1", port), Handler)
        self.httpd.daemon_threads = True
        self.httpd.state = self.state
        self.httpd.verbose = False
        self.port = self.httpd.server_address[1]
        self.thread = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/login"

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       kwargs={"poll_interval": 0.1}, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False
