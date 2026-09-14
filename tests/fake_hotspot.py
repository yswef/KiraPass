#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fake MikroTik-style hotspot used to TEST KiraPass_experimental.py offline.

It is NOT a source of facts about the user's router — it is only a target that
behaves like the page described in "رد الذكاء الثاني.txt", so the diagnosis
script can be proven to work end to end without touching any real network.

Run it alone:

    python3 tests/fake_hotspot.py --port 8099

Endpoints:
    GET  /login                          the portal page (2 forms + md5.js)
    GET  /md5.js                         md5 code with the real semantics used
    POST /login                          username + password (plain OR hashed)
    GET  /status                         success page
    GET  /connectivitycheck/generate_204 204 when logged in, else 302 -> /login
    GET  /connecttest.txt                200 "Microsoft Connect Test" when open
"""

import argparse
import hashlib
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

# the same material quoted in the previous extraction
PREFIX = b'\043'                                   # '#'
SALT = bytes([0o247, 0o263, 0o106, 0o062, 0o027, 0o142, 0o236, 0o045,
              0o046, 0o210, 0o347, 0o103, 0o366, 0o145, 0o343, 0o231])
VALID_USER = '1234'
VALID_PASS = 'abcd'


def escaper(raw: bytes) -> str:
    """bytes -> JS octal escapes, exactly like the page shows them."""
    return ''.join('\\%03o' % b for b in raw)


def md5_hash(pw: str) -> str:
    return hashlib.md5(PREFIX + pw.encode('latin-1') + SALT).hexdigest()


PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>KiraPass fake hotspot</title>
<script type="text/javascript" src="/md5.js"></script>
</head><body>
<div id="alert-speed" style="display:none">speed choice</div>

<form name="login" action="__ACTION__" method="post">
  <input type="hidden" name="dst" value="http://www.msftconnecttest.com/redirect" />
  <input type="hidden" name="popup" value="true" />
  <input type="hidden" id="domain" name="domain"  value=""  />
  <input type="hidden" id="Hspeed" name="Hspeed"  value=""  />
  <input id='uname' type="text" value="" placeholder="\u0631\u0642\u0645 \u0627\u0644\u0643\u0631\u062a" name="username" autocomplete="off" required improve-input rm-white-spaces to-lower only-alphanumeric to-arabic-numbers />
  <input  id='paswd'  type="hidden"   placeholder="\u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631"  name="password"   improve-input rm-white-spaces to-lower only-alphanumeric to-arabic-numbers />
  <input type="checkbox" name="checkbox1" id="remember" class="ios-toggle" value="ON" checked/>
  <button  id='choosedupdate' onclick="document.getElementById('alert-speed').style.display = ('block')" type="button" class="form-control display-7" id="username-form3-m">update</button>
  <button  id='choosedspeed' onclick="document.getElementById('alert-speed').style.display = ('block')" type="button" class="form-control display-7" id="username-form3-m">speed</button>
  <script type="text/javascript">
    document.write("<div class="+"submit"+" ><button onclick="+"alertmac()"+"  type="+"submit"+"  > \u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644 </button></div>");
    document.write("<div class="+"submit"+" ><button onclick="+"rem2();"+"  type="+"submit"+"  > \u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644 </button></div>");
  </script>
</form>

<form name="sendin" action="__ACTION__" method="post">
  <input type="hidden" name="username" />
  <input type="hidden" name="password" />
  <input type="hidden" name="dst" value="http://www.msftconnecttest.com/redirect" />
  <input type="hidden" name="popup" value="true" />
  <input type="hidden" name="speed" />
  <input type="hidden" name="update" />
  <input type="hidden" name="facebook" />
</form>

<script type="text/javascript">
    function userLogin() { return true; }
    function alertmac() { return true; }
    function rem2() { return true; }
    function doLogin() {
        userLogin();
        document.sendin.username.value = document.login.username.value;
        document.sendin.password.value = hexMD5('__PREFIX__' + document.login.password.value + '__SALT__');
        document.sendin.speed.value = document.login.speed.value;
        document.sendin.update.value = document.login.update.value;
        document.sendin.facebook.value = document.login.facebook.value;
        document.sendin.submit();
        return false;
    }
</script>
</body></html>
"""

MD5_JS = """/*
 * md5.js  (test stub — only the parts the diagnosis script inspects)
 * The real page loads the classic Paul Johnston / Mikrotik library here.
 */
var hexcase = 0;   /* hex output format. 0 - lowercase; 1 - uppercase */
var chrsz   = 8;   /* bits per input character. 8 - ASCII; 16 - Unicode  */

function hex_md5(s){ return binl2hex(core_md5(str2binl(s), s.length * chrsz)); }
function hexMD5(s){ return hex_md5(s); }

function str2binl(str) {
    var bin = Array();
    var mask = (1 << chrsz) - 1;
    for (var i = 0; i < str.length * chrsz; i += chrsz)
        bin[i >> 5] |= (str.charCodeAt(i / chrsz) & mask) << (i % 32);
    return bin;
}
"""

FAIL_PAGE = """<html><body><h1>Hotspot login</h1>
<p>invalid username or password</p>
<form name="login" action="__ACTION__" method="post">
  <input name="username" /><input name="password" type="hidden" />
</form></body></html>"""

STATUS_PAGE = """<html><body><h1>You are logged in</h1>
<p>welcome, session started</p><p><a href="/logout">logout</a></p>
</body></html>"""


VARIANTS = ('normal', 'dynamic_salt', 'no_hash', 'uppercase', 'missing_fields')


class State:
    def __init__(self):
        self.lock = Lock()
        self.logged_in = False
        self.requests = []


ST = State()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'FakeHotspot/1.0'

    @property
    def variant(self):
        return getattr(self.server, 'variant', 'normal')

    # -- helpers ------------------------------------------------------------
    def base(self):
        host = self.headers.get('Host') or f'127.0.0.1:{self.server.server_port}'
        return f'http://{host}'

    def reply(self, code, body, ctype='text/html; charset=utf-8', headers=None):
        raw = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def record(self, note=''):
        with ST.lock:
            ST.requests.append(f'{self.command} {self.path} {note}')
        print(f'  fake-hotspot: {self.command} {self.path} {note}', flush=True)

    # -- routes -------------------------------------------------------------
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        self.record()
        if path == '/login':
            page = (PAGE.replace('__ACTION__', self.base() + '/login')
                        .replace('__PREFIX__', escaper(PREFIX))
                        .replace('__SALT__', escaper(SALT)))
            if self.variant == 'dynamic_salt':
                # a router that rotates the challenge on every page load
                page = page.replace(escaper(SALT), escaper(dynamic_salt()))
            if self.variant == 'no_hash':
                # the password leaves the browser in clear text
                page = re.sub(
                    r"hexMD5\('[^']*'\s*\+\s*document\.login\.password"
                    r"\.value\s*\+\s*'[^']*'\)",
                    "document.login.password.value", page)
            if self.variant == 'missing_fields':
                # doLogin() touches fields the form does not have -> JS error
                page = page.replace(
                    '  <input type="hidden" name="speed" />\n'
                    '  <input type="hidden" name="update" />\n'
                    '  <input type="hidden" name="facebook" />\n', '')
            self.reply(200, page)
        elif path == '/md5.js':
            js = MD5_JS
            if self.variant == 'uppercase':
                js = js.replace('var hexcase = 0;', 'var hexcase = 1;')
            self.reply(200, js, 'application/javascript')
        elif path == '/status':
            self.reply(200, STATUS_PAGE)
        elif path == '/connectivitycheck/generate_204':
            with ST.lock:
                open_now = ST.logged_in
            if open_now:
                self.reply(204, '')
            else:
                self.reply(302, '', headers={'Location': self.base() + '/login'})
        elif path == '/connecttest.txt':
            with ST.lock:
                open_now = ST.logged_in
            if open_now:
                self.reply(200, 'Microsoft Connect Test', 'text/plain')
            else:
                self.reply(302, '', headers={'Location': self.base() + '/login'})
        else:
            self.reply(404, 'not found')

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length).decode('utf-8', 'replace')
        form = dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
        user = form.get('username', '')
        pw = form.get('password', '')
        hashed_ok = (pw == md5_hash(VALID_PASS))
        plain_ok = (pw == VALID_PASS)
        if self.variant == 'dynamic_salt':
            hashed_ok = False        # re-used salt is refused on purpose
        ok = (user == VALID_USER) and (hashed_ok or plain_ok)
        kind = 'hash' if hashed_ok else ('plain' if plain_ok else 'wrong')
        self.record(f'user={user!r} pw={pw[:12]!r}({kind}) fields='
                    f'{sorted(form)} -> {"ACCEPT" if ok else "REJECT"}')
        if ok:
            with ST.lock:
                ST.logged_in = True
            self.reply(302, '', headers={'Location': self.base() + '/status',
                                         'Set-Cookie': 'session=ok; Path=/'})
        else:
            self.reply(200, FAIL_PAGE.replace('__ACTION__', self.base() + '/login'))

    def log_message(self, *a):
        pass


def dynamic_salt():
    import random
    return bytes(random.randrange(256) for _ in range(16))


def serve(port=8099, variant='normal', quiet=False):
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    srv.variant = variant
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8099)
    ap.add_argument('--variant', default='normal', choices=list(VARIANTS))
    a = ap.parse_args()
    srv = serve(a.port, a.variant)
    print(f'fake hotspot on http://127.0.0.1:{a.port}/login '
          f'(valid card: {VALID_USER} / {VALID_PASS})', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nbye')
    finally:
        srv.server_close()


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
