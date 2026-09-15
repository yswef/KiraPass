#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KiraPass experimental — live hotspot page dissection + CHAP / hexMD5 diagnosis.

WHAT IT DOES (all from the LIVE page you give it — nothing is assumed):

  1. Fetches the login page you type and saves the raw HTML.
  2. Dissects it: every <form> (name/id/method/action/onSubmit), every field
     (tag/name/id/type/value/placeholder/attributes), buttons, scripts.
  3. Fetches the external scripts (e.g. /md5.js) and saves them, then reports
     what the real MD5 code does: chrsz, charCodeAt & mask, hexcase, and the
     body of hexMD5() if it is defined there.
  4. Extracts the real hash call:  hexMD5('...' + document.X.Y.value + '...')
     and decodes the JS string escapes to real bytes (\\247 = 0xA7, not UTF-8).
  5. Compares everything it found with the facts extracted earlier by hand
     ("رد الذكاء الثاني.txt") and marks each one  CONFIRMED / DIFFERS / MISSING.
  6. Optionally fires LIVE login attempts and records, for each one:
     request shape -> HTTP status -> redirect chain -> body markers -> cookies.
  7. Monitors the network before/after (captive portal check) and can keep
     watching for a number of minutes, so you SEE the network go open.
  8. Writes a text report with ERRORS and WARNINGS plus the raw artifacts.

SAFETY / SCOPE: use it only on a network you own or manage, or one you have
written permission to test. Every "attempt" is one real login request.

Standard library only (no requests, no bs4) -> runs anywhere with Python 3.8+.

    python3 KiraPass_experimental.py                     # interactive
    python3 KiraPass_experimental.py --url http://10.10.10.10/login --all
    python3 KiraPass_experimental.py --url ... --dissect            # read-only
    python3 KiraPass_experimental.py --url ... --probe --watch 5
    python3 KiraPass_experimental.py --url ... --login --user 1234 --pass 1234
"""

import argparse
import hashlib
import http.cookiejar
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

VERSION = '0.1-exp'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(SCRIPT_DIR, 'KiraPass_experimental_out')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'identity',
    'Connection': 'close',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

READ_CAP = 2_000_000
CONNECT_TIMEOUT = 4.0
READ_TIMEOUT = 10.0

FAIL_MARKERS = [
    'invalid username or password', 'wrong username or password',
    'login failed', 'failed to log in', 'access denied', 'incorrect',
    'authentication failed', 'cannot log in', 'try again',
    'radius server is not responding', 'username or password',
]
OK_MARKERS = [
    'logged in', 'you are logged in', 'welcome', 'connected', 'logout',
    'free access', 'session started', 'success',
]
PORTAL_MARKERS = ['login', 'hotspot', 'captive', 'voucher', 'card', 'password']

# What the previous manual extraction ("رد الذكاء الثاني.txt") claims.
# It is only a baseline to CHECK against the live page — never assumed true.
EXPECTED = {
    'form1': {
        'name': 'sendin', 'method': 'post',
        'action': 'http://10.10.10.10/login',
        'fields': ['username', 'password', 'dst', 'popup'],
    },
    'form2': {
        'name': 'login', 'method': 'post',
        'action': 'http://10.10.10.10/login',
        'fields': ['dst', 'popup', 'domain', 'Hspeed', 'username', 'password',
                   'checkbox1'],
    },
    'script_src': '/md5.js',
    'hash_prefix_octal': '043',                       # -> 0x23 '#'
    'hash_salt_octal': ('247 263 106 062 027 142 236 045 046 210 347 103 366 '
                        '145 343 231'),
    'hash_document': 'document.login.password.value',
    'sendin_sets': ['username', 'password', 'speed', 'update', 'facebook'],
}

CHECK_URLS_DEFAULT = [
    'http://connectivitycheck.gstatic.com/generate_204',
    'http://www.msftconnecttest.com/connecttest.txt',
    'http://captive.apple.com/hotspot-detect.html',
]


# ─────────────────────────────────────────────────────────────────────────────
# report
# ─────────────────────────────────────────────────────────────────────────────
class Report:
    """Collects everything; writes a text report; counts errors/warnings."""

    def __init__(self):
        self.lines = []
        self.errors = []
        self.warnings = []
        self.unconfirmed = []

    # -- writing ------------------------------------------------------------
    def add(self, text=''):
        self.lines.append(text)
        print(text)

    def raw(self, text=''):
        """Put a line in the file without printing it (long dumps)."""
        self.lines.append(text)

    def hr(self, title=''):
        self.add('')
        self.add('─' * 74)
        if title:
            self.add(' ' + title)
            self.add('─' * 74)

    def error(self, text):
        self.errors.append(text)
        self.add(' ✗ ERROR   : ' + text)

    def warn(self, text):
        self.warnings.append(text)
        self.add(' ⚠ WARNING : ' + text)

    def note(self, text):
        self.add('   ' + text)

    def check(self, label, ok, detail=''):
        """One baseline fact: CONFIRMED / DIFFERS / MISSING."""
        if ok is True:
            tag, glyph = 'CONFIRMED', '✓'
        elif ok is None:
            tag, glyph = 'MISSING', '✗'
        else:
            tag, glyph = 'DIFFERS', '⚠'
        line = f' {glyph} {tag:<9} {label}'
        if detail:
            line += f'   [{detail}]'
        self.add(line)
        if ok is not True:
            self.unconfirmed.append(f'{label} -> {tag} {detail}')
        return ok

    def snapshot(self):
        return len(self.lines)

    def delta(self, mark):
        return self.lines[mark:]

    # -- saving -------------------------------------------------------------
    def save(self, path, head_lines):
        body = list(head_lines) + self.lines
        body += ['', '─' * 74, ' SUMMARY', '─' * 74]
        body.append(f' errors   : {len(self.errors)}')
        body.append(f' warnings : {len(self.warnings)}')
        body.append(f' facts not confirmed against the live page : '
                    f'{len(self.unconfirmed)}')
        for u in self.unconfirmed:
            body.append('   - ' + u)
        body.append('')
        body.append(' errors detail:')
        body += ['   - ' + e for e in self.errors] or ['   (none)']
        body.append('')
        body.append(' warnings detail:')
        body += ['   - ' + w for w in self.warnings] or ['   (none)']
        body.append('')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(body) + '\n')
        return path


# ─────────────────────────────────────────────────────────────────────────────
# HTTP layer (stdlib, manual redirect handling so the chain is visible)
# ─────────────────────────────────────────────────────────────────────────────
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Session:
    def __init__(self, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)):
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            NoRedirect(),
            urllib.request.HTTPSHandler(context=ctx),
        )

    def cookies(self):
        return '; '.join(f'{c.name}={c.value}' for c in self.jar)

    def send(self, url, data=None, method=None, follow=True, max_hops=8,
             extra_headers=None):
        """Return a dict with the full chain. Never raises for HTTP errors."""
        chain = []
        cur_url = url
        cur_data = data
        cur_method = method
        for hop in range(max_hops + 1):
            if cur_method is None:
                cur_method = 'POST' if cur_data is not None else 'GET'
            req = urllib.request.Request(cur_url, data=cur_data,
                                         method=cur_method)
            for k, v in HEADERS.items():
                req.add_header(k, v)
            for k, v in (extra_headers or {}).items():
                req.add_header(k, v)
            t0 = time.time()
            try:
                resp = self.opener.open(req, timeout=self.timeout[1])
                status, reason, hdrs = resp.status, resp.reason, resp.headers
                body = resp.read(READ_CAP)
                resp.close()
            except urllib.error.HTTPError as e:
                status, reason, hdrs = e.code, e.reason, e.headers
                try:
                    body = e.read(READ_CAP)
                except Exception:
                    body = b''
                try:
                    e.close()
                except Exception:
                    pass
            except Exception as e:
                chain.append({'url': cur_url, 'method': cur_method,
                              'error': f'{type(e).__name__}: {e}',
                              'ms': round((time.time() - t0) * 1000)})
                return {'ok': False, 'error': f'{type(e).__name__}: {e}',
                        'url': cur_url, 'final_url': cur_url, 'status': 0,
                        'headers': {}, 'body': b'', 'text': '', 'chain': chain}
            ms = round((time.time() - t0) * 1000)
            loc = hdrs.get('Location')
            chain.append({'url': cur_url, 'method': cur_method, 'status': status,
                          'reason': reason, 'location': loc,
                          'len': len(body), 'ms': ms,
                          'ct': hdrs.get('Content-Type', '')})
            if not follow or status not in (301, 302, 303, 307, 308) or not loc:
                nxt = urllib.parse.urljoin(cur_url, loc) if loc else None
                return {'ok': True, 'status': status, 'reason': reason,
                        'headers': hdrs, 'body': body, 'text': decode(body),
                        'final_url': cur_url, 'next_url': nxt, 'chain': chain,
                        'ms': ms}
            nxt = urllib.parse.urljoin(cur_url, loc)
            if status in (301, 302, 303) and cur_method != 'GET':
                cur_data, cur_method = None, 'GET'       # what browsers do
            cur_url = nxt
        return {'ok': False, 'error': 'too many redirects', 'url': url,
                'final_url': cur_url, 'status': 0, 'headers': {}, 'body': b'',
                'text': '', 'chain': chain}


def decode(body):
    if isinstance(body, str):
        return body
    for enc in ('utf-8', 'windows-1256', 'latin-1'):
        try:
            return body.decode(enc)
        except Exception:
            continue
    return ''


def fmt_chain(chain):
    out = []
    for i, h in enumerate(chain, 1):
        if 'error' in h:
            out.append(f'   {i}. {h["method"]} {h["url"]}  ->  NETWORK ERROR '
                       f'[{h["error"]}]')
        else:
            loc = f' -> {h["location"]}' if h.get('location') else ''
            out.append(f'   {i}. {h["method"]} {h["url"]}  ->  HTTP {h["status"]}'
                       f' {h.get("reason", "")} ({h["len"]} B, {h["ms"]} ms){loc}')
    return out


# ─────────────────────────────────────────────────────────────────────────────
# HTML dissection
# ─────────────────────────────────────────────────────────────────────────────
class Page(HTMLParser):
    """Collects forms, fields, buttons, scripts and duplicate attributes."""

    FIELD_TAGS = ('input', 'select', 'textarea', 'button')

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.fields = []          # every field, with form index (-1 = outside)
        self.scripts = []         # {'src':..., 'text':..., 'attrs':...}
        self.links = []
        self.title = ''
        self.duplicate_attrs = []
        self._form = None
        self._in_script = False
        self._in_title = False
        self._script = None
        self._select = None

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _get(attrs, key):
        for k, v in attrs:
            if k == key:
                return v if v is not None else ''
        return None

    def _check_dupes(self, tag, attrs):
        seen = {}
        for k, _ in attrs:
            seen[k] = seen.get(k, 0) + 1
        for k, n in seen.items():
            if n > 1:
                self.duplicate_attrs.append((tag, k, n))

    # -- parser callbacks ---------------------------------------------------
    def handle_starttag(self, tag, attrs):
        self._check_dupes(tag, attrs)
        if tag == 'form':
            self._form = {
                'attrs': attrs,
                'name': self._get(attrs, 'name'),
                'id': self._get(attrs, 'id'),
                'method': (self._get(attrs, 'method') or '').lower() or None,
                'action': self._get(attrs, 'action'),
                'onSubmit': self._get(attrs, 'onSubmit')
                if self._get(attrs, 'onSubmit') is not None
                else self._get(attrs, 'onsubmit'),
                'index': len(self.forms),
            }
            self.forms.append(self._form)
        elif tag in self.FIELD_TAGS:
            f = {
                'tag': tag,
                'attrs': attrs,
                'name': self._get(attrs, 'name'),
                'id': self._get(attrs, 'id'),
                'type': (self._get(attrs, 'type') or '').lower(),
                'value': self._get(attrs, 'value'),
                'placeholder': self._get(attrs, 'placeholder'),
                'checked': self._get(attrs, 'checked') is not None,
                'form': self._form['index'] if self._form else -1,
                'options': [],
            }
            if tag == 'button':
                f['type'] = f['type'] or 'submit'
                f['onclick'] = self._get(attrs, 'onclick')
            self.fields.append(f)
            if tag == 'select':
                self._select = f
        elif tag == 'option' and self._select is not None:
            self._select['options'].append(
                {'value': self._get(attrs, 'value'),
                 'text': ''})
        elif tag == 'script':
            self._script = {'src': self._get(attrs, 'src'), 'attrs': attrs,
                            'text': ''}
            self.scripts.append(self._script)
            self._in_script = True
        elif tag == 'link':
            self.links.append(attrs)
        elif tag == 'title':
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == 'form':
            self._form = None
        elif tag == 'script':
            self._in_script = False
            self._script = None
        elif tag == 'title':
            self._in_title = False
        elif tag == 'select':
            self._select = None

    def handle_data(self, data):
        if self._in_script and self._script is not None:
            self._script['text'] += data
        elif self._in_title:
            self.title += data

    # -- queries ------------------------------------------------------------
    def form_by_name(self, name):
        for f in self.forms:
            if (f['name'] or '').lower() == name.lower():
                return f
        return None

    def fields_of(self, form_index):
        return [f for f in self.fields if f['form'] == form_index]

    def inline_js(self):
        return '\n'.join(s['text'] for s in self.scripts if s['text'])

    def script_srcs(self):
        return [s['src'] for s in self.scripts if s['src']]


def describe_field(f):
    bits = [f'{f["tag"]}']
    if f['type']:
        bits.append(f'type={f["type"]}')
    bits.append(f'name={f["name"]!r}')
    if f['id']:
        bits.append(f'id={f["id"]!r}')
    if f['value'] is not None:
        bits.append(f'value={f["value"]!r}')
    if f['placeholder']:
        bits.append(f'placeholder={f["placeholder"]!r}')
    if f['checked']:
        bits.append('checked')
    extra = [(k if v is None else f'{k}={v!r}') for k, v in f['attrs']
             if k not in ('type', 'name', 'id', 'value', 'placeholder',
                          'checked')]
    if extra:
        bits.append('attrs: ' + ', '.join(extra))
    return ' '.join(bits)


# ─────────────────────────────────────────────────────────────────────────────
# JavaScript analysis
# ─────────────────────────────────────────────────────────────────────────────
_SIMPLE_ESC = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f',
               'v': '\v', '0': '\0', '\n': ''}


def js_unescape(s):
    """Decode a JS string body the way a browser does (octal/hex/unicode)."""
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c != '\\':
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= len(s):
            break
        c = s[i]
        if c in '01234567':
            j = i
            while j < len(s) and j < i + 3 and s[j] in '01234567':
                j += 1
            out.append(chr(int(s[i:j], 8) & 0xFF))
            i = j
        elif c == 'x' and len(s) >= i + 3:
            try:
                out.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
            except ValueError:
                out.append(c)
                i += 1
        elif c == 'u' and len(s) >= i + 5:
            try:
                out.append(chr(int(s[i + 1:i + 5], 16)))
                i += 5
            except ValueError:
                out.append(c)
                i += 1
        elif c in _SIMPLE_ESC:
            out.append(_SIMPLE_ESC[c])
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def js_bytes(s):
    """JS string -> bytes the way str2binl(charCodeAt & 0xFF) does it."""
    return bytes(ord(ch) & 0xFF for ch in s)


def find_hash_call(js):
    """Find  hexMD5('<prefix>' + document.F.field.value + '<salt>')  calls."""
    calls = []
    # permissive: any hexMD5(...) with string literals around a .value
    for m in re.finditer(r'hexMD5\s*\(', js):
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth:
            if js[i] == '(':
                depth += 1
            elif js[i] == ')':
                depth -= 1
            i += 1
        calls.append(js[m.start():i])
    out = []
    lit = r"'((?:[^'\\]|\\.)*)'"
    pat = re.compile(
        r'hexMD5\s*\(\s*' + lit + r'\s*\+\s*document\.(\w+)\.(\w+)\.value\s*\+'
        r'\s*' + lit, re.S)
    for m in pat.finditer(js):
        out.append({
            'raw': calls[0] if calls else '',
            'prefix_raw': m.group(1),
            'doc': m.group(2),
            'field': m.group(3),
            'salt_raw': m.group(4),
            'prefix_str': js_unescape(m.group(1)),
            'salt_str': js_unescape(m.group(4)),
        })
        out[-1]['prefix_bytes'] = js_bytes(out[-1]['prefix_str'])
        out[-1]['salt_bytes'] = js_bytes(out[-1]['salt_str'])
    return out, calls


def find_functions(js, names):
    found = {}
    for n in names:
        if re.search(r'function\s+' + re.escape(n) + r'\s*\(', js):
            found[n] = 'defined'
        elif re.search(re.escape(n) + r'\s*=\s*function', js):
            found[n] = 'defined (assigned)'
    body = re.search(r'function\s+hexMD5\s*\(([^)]*)\)\s*\{([^}]*)\}', js)
    if body:
        found['hexMD5 body'] = f'function hexMD5({body.group(1)}) {{{body.group(2)}}}'
    return found


def md5_semantics(js):
    info = {}
    m = re.search(r'chrsz\s*=\s*(\d+)', js)
    info['chrsz'] = m.group(1) if m else None
    m = re.search(r'hexcase\s*=\s*([01])', js)
    info['hexcase'] = m.group(1) if m else None
    info['charCodeAt'] = 'charCodeAt' in js
    info['mask'] = bool(re.search(r'&\s*mask', js)) or 'mask' in js
    info['str2binl'] = bool(re.search(r'function\s+str2binl', js))
    info['library'] = ('Paul Johnston / Mikrotik md5.js style'
                       if info['str2binl'] or info['chrsz'] else 'unknown')
    return info


def hexmd5(prefix, value, salt):
    """hexMD5(prefix + value + salt) with the byte semantics of md5.js."""
    if isinstance(value, str):
        value = value_bytes(value)[0]
    return hashlib.md5(prefix + value + salt).hexdigest()


def value_bytes(s):
    """Return (bytes, note). md5.js uses charCodeAt & 0xFF -> latin-1."""
    try:
        return s.encode('latin-1'), ''
    except UnicodeEncodeError:
        return (s.encode('utf-8'),
                'password has non-latin-1 characters: hashed as UTF-8 bytes, '
                'which may NOT match the page')


# ─────────────────────────────────────────────────────────────────────────────
# steps
# ─────────────────────────────────────────────────────────────────────────────
def save_artifact(out_dir, name, data):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    mode = 'wb' if isinstance(data, bytes) else 'w'
    kwargs = {} if isinstance(data, bytes) else {'encoding': 'utf-8'}
    with open(path, mode, **kwargs) as f:
        f.write(data)
    return path


def step_fetch_page(rep, sess, url, out_dir):
    rep.hr('1. FETCH LOGIN PAGE')
    res = sess.send(url, follow=True)
    for line in fmt_chain(res['chain']):
        rep.add(line)
    if not res['ok']:
        rep.error(f'cannot fetch {url}: {res["error"]}')
        return None
    if res['status'] != 200:
        rep.warn(f'the page answered HTTP {res["status"]} {res["reason"]} '
                 f'(not 200)')
    if res['chain'] and urllib.parse.urlsplit(res['chain'][0]['url']).netloc \
            != urllib.parse.urlsplit(res['final_url']).netloc:
        rep.warn(f'request was redirected to another host '
                 f'({res["final_url"]}) — a captive portal is intercepting')
    if res['body']:
        p = save_artifact(out_dir, 'login_page.html', res['body'])
        rep.note(f'saved raw page  -> {p}')
    else:
        rep.error('the page body is empty')
    rep.note(f'final URL : {res["final_url"]}')
    rep.note(f'cookies   : {sess.cookies() or "(none)"}')
    rep.note(f'size      : {len(res["body"])} bytes')
    return res


def step_dissect(rep, sess, res, base_url, out_dir, fetch_scripts=True):
    rep.hr('2. DISSECT THE HTML')
    page = Page()
    try:
        page.feed(res['text'])
    except Exception as e:
        rep.error(f'HTML parser problem: {type(e).__name__}: {e}')
    rep.note(f'title: {page.title.strip()!r}')
    if not page.forms:
        rep.error('no <form> found in the page — is this really the login page?')
    for form in page.forms:
        rep.add('')
        rep.add(f' FORM #{form["index"] + 1}  name={form["name"]!r} '
                f'id={form["id"]!r} method={form["method"]!r} '
                f'action={form["action"]!r}')
        if form['onSubmit']:
            rep.note(f'onSubmit={form["onSubmit"]!r}')
        else:
            rep.note('onSubmit: (none)  <- the browser would POST the fields as '
                     'they are, no JS hook')
        for f in page.fields_of(form['index']):
            if f['tag'] == 'button':
                rep.note('  (button, not submitted) ' + describe_field(f))
            elif not f['name']:
                rep.note('  (no name -> not submitted by the browser) '
                         + describe_field(f))
            else:
                rep.note('  ' + describe_field(f))
    loose = page.fields_of(-1)
    if loose:
        rep.add('')
        rep.note(f'{len(loose)} field(s) outside any form '
                 f'(runtime-generated elements look like this):')
        for f in loose:
            rep.note('  ' + describe_field(f))
    if page.duplicate_attrs:
        rep.warn('duplicate attributes in the HTML (an id must be unique — '
                 'this is what hand-extraction gets wrong): '
                 + ', '.join(f'<{t} {k}×{n}>' for t, k, n in
                             page.duplicate_attrs))

    # scripts
    rep.add('')
    rep.note(f'scripts: {len(page.scripts)} '
             f'({len(page.script_srcs())} external)')
    inline = page.inline_js()
    ext_texts = {}
    for src in page.script_srcs():
        full = urllib.parse.urljoin(base_url, src)
        rep.note(f'  external: {src}  -> {full}')
        if not fetch_scripts:
            continue
        if urllib.parse.urlsplit(full).netloc != urllib.parse.urlsplit(
                base_url).netloc:
            rep.warn(f'skipping {full}: different host than the login page')
            continue
        r = sess.send(full, follow=True)
        if not r['ok'] or r['status'] != 200 or not r['body']:
            rep.warn(f'could not read {full} '
                     f'({r.get("error") or "HTTP " + str(r["status"])})')
            continue
        name = os.path.basename(urllib.parse.urlsplit(full).path) or 'script.js'
        p = save_artifact(out_dir, name, r['body'])
        ext_texts[src] = {'url': full, 'text': r['text'], 'path': p,
                          'len': len(r['body'])}
        rep.note(f'    saved -> {p}  ({len(r["body"])} bytes)')

    return page, inline, ext_texts


def step_js(rep, page, inline, ext_texts):
    rep.hr('3. JAVASCRIPT ANALYSIS')
    names = ['hexMD5', 'hex_md5', 'md5', 'str2binl', 'core_md5', 'doLogin',
             'userLogin', 'alertmac', 'rem2']
    for label, text in [('inline page script', inline)] + \
            [(f'external {k}', v['text']) for k, v in ext_texts.items()]:
        if not text.strip():
            continue
        rep.add('')
        rep.note(f'--- {label} ({len(text)} chars) ---')
        found = find_functions(text, names)
        for k, v in found.items():
            rep.note(f'  {k:<12} : {v}')
        for n in names:
            if n not in found and re.search(re.escape(n), text):
                rep.note(f'  {n:<12} : used but not defined here')
        sem = md5_semantics(text)
        if any(v for v in sem.values()):
            rep.note('  md5 semantics: ' + ', '.join(
                f'{k}={v}' for k, v in sem.items() if v))

    all_js = inline + '\n' + '\n'.join(v['text'] for v in ext_texts.values())
    calls, every = find_hash_call(all_js)
    rep.add('')
    rep.note(f'hexMD5(...) calls found: {len(every)}')
    for c in every:
        one = ' '.join(c.split())
        if len(one) <= 160:
            rep.note('   call: ' + one)
        else:
            rep.note('   call: ' + one[:157] + '…')
            rep.raw('   call (full): ' + one)
    if not calls:
        rep.warn('no  hexMD5(\'prefix\' + document.F.field.value + \'salt\')  '
                 'call found — the password may be sent unhashed, or the code '
                 'is built at runtime (look at document.write)')
    for c in calls:
        rep.add('')
        rep.add(' HASH CALL DECODED')
        rep.note(f'  source field    : document.{c["doc"]}.{c["field"]}.value')
        rep.note(f'  prefix literal  : {c["prefix_raw"]!r}  -> '
                 f'{c["prefix_bytes"].hex(" ")}  ({c["prefix_bytes"]!r})')
        rep.note(f'  salt literal    : {c["salt_raw"]!r}')
        rep.note(f'  salt bytes      : {c["salt_bytes"].hex(" ")}  '
                 f'({len(c["salt_bytes"])} bytes)')
    # document.write / dynamic elements
    writes = re.findall(r'document\.write\s*\(([^;]{0,200})\)', all_js)
    if writes:
        rep.add('')
        rep.note(f'document.write(...) calls: {len(writes)} — these create '
                 f'elements AFTER the page loads, so they are NOT in the HTML:')
        for w in writes[:12]:
            one = ' '.join(w.split())
            if len(one) <= 150:
                rep.note('   write: ' + one)
            else:
                rep.note('   write: ' + one[:147] + '…')
                rep.raw('   write (full): ' + one)
    return calls


def quick_hash(sess, url, save_dir=None, cap=400_000):
    """Fetch the page again and return the hash call(s) it hands out now.

    Used to answer the one question a single page load cannot: is the salt
    fixed, or does the router rotate it on every load?
    """
    res = sess.send(url, follow=True)
    if not res['ok'] or not res['body']:
        return [], res
    page = Page()
    page.feed(res['text'])
    js = page.inline_js()
    for src in page.script_srcs():
        full = urllib.parse.urljoin(url, src)
        if urllib.parse.urlsplit(full).netloc != urllib.parse.urlsplit(url).netloc:
            continue
        r = sess.send(full, follow=True)
        if r['ok'] and r['body'] and len(r['body']) < cap:
            js += '\n' + r['text']
    calls, _ = find_hash_call(js)
    if save_dir:
        save_artifact(save_dir, 'login_page_2nd_load.html', res['body'])
    return calls, res


def step_salt_stability(rep, sess, url, out_dir, first_calls):
    """Two page loads (and, if we can, three) decide: fixed salt or rotating?"""
    rep.hr('3b. IS THE CHALLENGE FIXED OR ROTATED PER PAGE LOAD?')
    if not first_calls:
        rep.note('no hash call in the first load — nothing to compare')
        return None
    second, res = quick_hash(sess, url, out_dir)
    if not second:
        rep.warn('the second page load handed out no parsable hash call '
                 '(the page may build it at runtime) — cannot tell whether the '
                 'salt rotates; the tool will print the bytes of every load')
        return None
    a, b = first_calls[0], second[0]
    same_prefix = a['prefix_bytes'] == b['prefix_bytes']
    same_salt = a['salt_bytes'] == b['salt_bytes']
    rep.note(f'load 1 salt : {a["salt_bytes"].hex(" ")}')
    rep.note(f'load 2 salt : {b["salt_bytes"].hex(" ")}')
    if same_salt and same_prefix:
        rep.check('the challenge (prefix+salt) is IDENTICAL on both loads',
                  True, 'fixed challenge: one hash is valid for every request')
        return {'rotating': False, 'salt': a['salt_bytes'],
                'prefix': a['prefix_bytes']}
    rep.check('the challenge changes between page loads', False,
              'ROTATING challenge')
    rep.error('The salt rotates on every page load. A hash you compute once is '
              'only valid for the page load that produced it, so a long run '
              'must re-fetch the login page (or at least re-read the salt) '
              'before/while sending. Sending one fixed salt thousands of times '
              'will be rejected exactly like a wrong password — and you would '
              'never be able to tell it apart from an expired card.')
    if not same_prefix:
        rep.error('even the fixed part in front of the password changed '
                  'between loads — re-check the page by hand')
    return {'rotating': True, 'salt': a['salt_bytes'],
            'prefix': a['prefix_bytes']}


def step_fact_check(rep, page, calls, ext_texts, base_url):
    rep.hr('4. FACT CHECK vs the previous manual extraction')
    rep.note('Every line below is decided by what the LIVE page showed, not by '
             'what the old file claimed.')

    def names_of(form):
        # only fields the browser would actually submit: named, not buttons
        if not form:
            return []
        return [f['name'] for f in page.fields_of(form['index'])
                if f['name'] and f['tag'] != 'button']

    exp = EXPECTED
    f1 = page.form_by_name(exp['form1']['name'])
    rep.check(f'form "{exp["form1"]["name"]}" exists', True if f1 else None)
    if f1:
        rep.check(f'{exp["form1"]["name"]}: method is post',
                  (f1['method'] or '') == 'post', f'found {f1["method"]!r}')
        got = urllib.parse.urlsplit(urllib.parse.urljoin(base_url,
                                                         f1['action'] or ''))
        want = urllib.parse.urlsplit(exp['form1']['action'])
        same_path = got.path == want.path
        rep.check(f'{exp["form1"]["name"]}: action path = {want.path}',
                  same_path, f'found {f1["action"]!r} -> path {got.path!r}')
        if same_path and got.netloc != want.netloc:
            rep.note(f'same path, different host ({got.netloc} instead of '
                     f'{want.netloc}) — normal if you opened another '
                     f'deployment of the same portal')
        got_fields = names_of(f1)
        missing = [x for x in exp['form1']['fields'] if x not in got_fields]
        extra = [x for x in got_fields if x not in exp['form1']['fields']]
        rep.check(f'{exp["form1"]["name"]}: fields = '
                  f'{", ".join(exp["form1"]["fields"])}',
                  not missing and not extra,
                  f'found [{", ".join(got_fields)}]'
                  + (f' missing={missing}' if missing else '')
                  + (f' extra={extra}' if extra else ''))
        if extra:
            rep.warn(f'the old extraction said "{exp["form1"]["name"]}" has NO '
                     f'other elements, but the live page has extra field(s): '
                     f'{", ".join(extra)} — the old extraction was INCOMPLETE')

    f2 = page.form_by_name(exp['form2']['name'])
    rep.check(f'form "{exp["form2"]["name"]}" exists', True if f2 else None)
    if f2:
        rep.check(f'{exp["form2"]["name"]}: method is post',
                  (f2['method'] or '') == 'post', f'found {f2["method"]!r}')
        got_fields = names_of(f2)
        missing = [x for x in exp['form2']['fields'] if x not in got_fields]
        extra = [x for x in got_fields if x not in exp['form2']['fields']]
        rep.check(f'{exp["form2"]["name"]}: fields = '
                  f'{", ".join(exp["form2"]["fields"])}',
                  not missing and not extra,
                  f'found [{", ".join(got_fields)}]'
                  + (f' missing={missing}' if missing else '')
                  + (f' extra={extra}' if extra else ''))
        if not f2['onSubmit'] and 'doLogin' in ''.join(
                (s['text'] for s in page.scripts)):
            rep.warn(f'"{exp["form2"]["name"]}" has no onSubmit but doLogin() '
                     f'exists in the page — find what actually calls it '
                     f'(a button onclick or a jQuery handler)')

    srcs = [urllib.parse.urlsplit(s).path for s in page.script_srcs()]
    rep.check(f'external script {exp["script_src"]}', 
              True if exp['script_src'] in srcs else None,
              f'found {srcs or "[]"}')
    key = next((k for k in ext_texts
                if urllib.parse.urlsplit(k).path == exp['script_src']), None)
    if key:
        sem = md5_semantics(ext_texts[key]['text'])
        rep.check(f'{exp["script_src"]}: md5 code readable',
                  bool(sem['chrsz'] or sem['str2binl']),
                  ', '.join(f'{k}={v}' for k, v in sem.items() if v))
        if sem.get('chrsz') and sem['chrsz'] != '8':
            rep.warn(f'chrsz={sem["chrsz"]} — the hash does NOT treat a '
                     f'character as one byte, my byte math may be wrong')
        if sem.get('hexcase') == '1':
            rep.warn('hexcase=1: the hash is UPPERCASE hex, not lowercase')
        if not sem.get('charCodeAt'):
            rep.warn('charCodeAt not found in the md5 code — cannot confirm the '
                     'byte semantics; hashes may not match')
    elif page.script_srcs():
        rep.warn(f'{exp["script_src"]} could not be read — the hash cannot be '
                 f'reproduced without it')

    if calls:
        want_prefix = bytes([int(EXPECTED['hash_prefix_octal'], 8)])
        want_salt = bytes(int(x, 8)
                          for x in EXPECTED['hash_salt_octal'].split())
        c = calls[0]
        rep.check(f'hash prefix = \\{EXPECTED["hash_prefix_octal"]} '
                  f'({want_prefix.hex()})',
                  c['prefix_bytes'] == want_prefix,
                  f'found {c["prefix_bytes"].hex(" ")}')
        rep.check(f'hash salt = {len(want_salt)} bytes '
                  f'{want_salt.hex(" ")}',
                  c['salt_bytes'] == want_salt,
                  f'found {len(c["salt_bytes"])} bytes '
                  f'{c["salt_bytes"].hex(" ")}')
        rep.check(f'hash source = {EXPECTED["hash_document"]}',
                  f'{c["doc"]}.{c["field"]}' ==
                  EXPECTED['hash_document'].split('.')[1] + '.' +
                  EXPECTED['hash_document'].split('.')[2],
                  f'found document.{c["doc"]}.{c["field"]}.value')
        # what doLogin copies into sendin?
        if f1:
            touched = [x for x in EXPECTED['sendin_sets'] if re.search(
                r'document\.' + re.escape(f1['name'] or 'sendin') + r'\.' +
                re.escape(x) + r'\b', page.inline_js())]
            absent = [x for x in touched if x not in names_of(f1)]
            rep.check('doLogin only touches fields that exist in the form',
                      not absent,
                      f'set by JS: [{", ".join(touched) or "none"}], '
                      f'missing from the form: [{", ".join(absent) or "none"}]')
            if absent:
                rep.error('doLogin() assigns document.' + (f1['name'] or '?') +
                          '.' + absent[0] + '.value but that field does not '
                          'exist -> the real page would throw a JS error; '
                          'either the field is created later by script or the '
                          'old copy of doLogin is wrong')
    else:
        rep.check('hash call present in the page', None)


def step_connectivity(rep, sess, urls, label):
    rep.hr(f'NETWORK CHECK — {label}')
    out = []
    if not urls:
        rep.note('skipped (no check URL was given) — if you want the '
                 'before/after internet test, pass --check http://…')
        return out
    for u in urls:
        r = sess.send(u, follow=False)
        if not r['ok']:
            verdict = 'UNREACHABLE'
            detail = r['error']
        else:
            st = r['status']
            loc = r['headers'].get('Location')
            body_low = (r['text'] or '').lower()
            if st in (204, 200) and not loc:
                portal = any(m in body_low for m in
                             ['login', 'hotspot', 'captive', 'password'])
                if st == 204:
                    verdict, detail = 'OPEN', 'HTTP 204 no content (expected)'
                elif 'success' in body_low or 'microsoft connect test' in body_low:
                    verdict, detail = 'OPEN', 'expected body'
                elif portal:
                    verdict, detail = 'CAPTIVE', 'HTTP 200 with portal words'
                else:
                    verdict, detail = 'OPEN?', f'HTTP 200, unusual body ' \
                                               f'({len(r["body"])} B)'
            elif st in (301, 302, 303, 307, 308) and loc:
                verdict = 'CAPTIVE'
                detail = f'redirected to {loc}'
            else:
                verdict, detail = 'CAPTIVE', f'HTTP {st}'
        out.append((u, verdict, detail))
        rep.add(f'   {verdict:<11} {u}')
        rep.note(f'               {detail}')
    if out and all(v == 'UNREACHABLE' for _, v, _ in out):
        rep.note('every check URL was unreachable. That is normal while a '
                 'captive portal blocks the internet (the portal often drops '
                 'these requests instead of answering). Only the login-page '
                 'reachability and the reply of a real attempt matter here.')
    return out


def _verdict_word(rows):
    if not rows:
        return 'UNKNOWN'
    words = [v for _, v, _ in rows]
    if all(w.startswith('OPEN') for w in words):
        return 'OPEN'
    if any(w == 'CAPTIVE' for w in words):
        return 'CAPTIVE'
    return 'UNKNOWN'


def step_attempt(rep, sess, page, calls, base_url, label, user, password,
                 hashed, dst_value=None, extra=None, out_dir=None):
    """One real login request. Returns a dict with everything observed."""
    rep.add('')
    rep.add(f' ATTEMPT — {label}')
    form = page.form_by_name('sendin') or page.form_by_name('login') or \
        (page.forms[0] if page.forms else None)
    if form is None:
        rep.error('no form to send to')
        return None
    action = urllib.parse.urljoin(base_url, form['action'] or base_url)
    method = (form['method'] or 'post').upper()
    fields = page.fields_of(form['index'])
    data = []
    for f in fields:
        n = f['name']
        if not n:
            continue
        if n == 'username':
            data.append((n, user))
        elif n == 'password':
            data.append((n, password))
        elif n == 'dst':
            data.append((n, dst_value if dst_value is not None
                         else (f['value'] or '')))
        elif n == 'popup':
            data.append((n, f['value'] or 'true'))
        elif n == 'checkbox1':
            data.append((n, f['value'] or 'ON'))
        else:
            if extra and n in extra:
                data.append((n, extra[n]))
            else:
                data.append((n, f['value'] if f['value'] is not None else ''))
    if hashed and calls:
        c = calls[0]
        prefix, salt = c['prefix_bytes'], c['salt_bytes']
        vb, note = value_bytes(password)
        data = [(n, hexmd5(prefix, password, salt) if n == 'password' else v)
                for n, v in data]
        if note:
            rep.warn(note)
    rep.note(f'form={form["name"]!r} method={method} action={action}')
    rep.note('fields sent: ' + ', '.join(f'{k}={v!r}' for k, v in data))
    body = urllib.parse.urlencode(data).encode()
    if method == 'GET':
        url = action + ('&' if '?' in action else '?') + body.decode()
        res = sess.send(url, follow=True)
    else:
        res = sess.send(action, data=body, method='POST', follow=True,
                        extra_headers={
                            'Content-Type':
                                'application/x-www-form-urlencoded',
                            'Referer': base_url})
    for line in fmt_chain(res['chain']):
        rep.add(line)
    low = (res['text'] or '').lower()
    fail = next((m for m in FAIL_MARKERS if m in low), None)
    oks = [m for m in OK_MARKERS if m in low]
    status_page = '/status' in (res['final_url'] or '').lower() or any(
        '/status' in (h.get('url') or '').lower() for h in res['chain'])
    size = len(res['body'])
    sha = hashlib.sha1(res['body']).hexdigest()[:16] if res['body'] else '-'
    rep.note(f'final URL   : {res["final_url"]}')
    rep.note(f'body size   : {size} B')
    rep.note(f'body sha1   : {sha}')
    rep.note(f'failure word: {fail!r}')
    rep.note(f'success words: {oks}')
    rep.note(f'cookies now : {sess.cookies() or "(none)"}')
    reply_path = None
    if res['body']:
        # keep the raw reply: with no valid card this IS the rejection baseline
        fname = ('reply_' + re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')
                 + '.html')
        try:
            reply_path = save_artifact(out_dir or os.getcwd(), fname, res['body'])
            rep.note(f'saved reply -> {reply_path}')
        except OSError as e:
            rep.warn(f'could not save the reply body: {e}')
    if status_page:
        rep.add('   >>> looks like a SUCCESS (redirect to /status)')
    elif fail:
        rep.add('   >>> server REJECTED this credential (page said so)')
    else:
        rep.warn('reply is neither a clear success nor a clear rejection — '
                 'compare its size with the login page and read it by hand')
    if not res['ok']:
        rep.error(f'network error during attempt: {res["error"]}')
    return {'label': label, 'hashed': hashed, 'sent': data, 'res': res,
            'fail': fail, 'ok_markers': oks, 'status_page': status_page,
            'size': size, 'sha': sha, 'path': reply_path,
            'status': res.get('status')}


def step_probe_compare(rep, attempts):
    """What two attempts with deliberately wrong data can tell WITHOUT a card."""
    probes = [a for a in attempts
              if a and a['label'].lower().startswith('probe')]
    if len(probes) < 2:
        return
    plain = next((a for a in probes if 'PLAIN' in a['label']), None)
    hashed = next((a for a in probes if 'HASHED' in a['label']), None)
    rep.hr('5b. WHAT THE PROBES SAY (a valid card is NOT needed)')
    for a in (plain, hashed):
        if a is None:
            continue
        rep.note(f'{a["label"].split(":")[-1].strip():<28} HTTP '
                 f'{a["status"]}  {a["size"]} B  sha1 {a["sha"]}  '
                 f'fail={a["fail"]!r}  success={a["status_page"]}')
    if plain and hashed:
        if plain['sha'] == hashed['sha']:
            rep.note('identical replies for a plain and a hashed password: this '
                     'router does not separate the two in the reply, so nothing '
                     'about plain-vs-hashed can be concluded here — the page '
                     'itself sends the hash, so keep sending the hash.')
        else:
            rep.note('the replies DIFFER between a plain and a hashed password '
                     '— the router does not treat clear text the same way, '
                     'which is one more reason to send exactly what the page '
                     'sends (the hash).')
    if any(a and a['status_page'] for a in (plain, hashed)):
        rep.warn('a random card reached /status — that would mean the router '
                 'accepts anything; re-check the URL before trusting anything')
    if any(a and not a['fail'] and not a['status_page'] for a in (plain, hashed)):
        rep.warn('the reply to a wrong card had neither a known failure word '
                 'nor a success redirect. Read the saved reply_*.html by hand: '
                 'that page is the shape of a REJECTION on this router, and '
                 'detection depends on knowing it.')
    rep.note('these probes are still one HTTP page each: they prove the request '
             'SHAPE is accepted (no 4xx/5xx, a normal portal reply, cookies, '
             'redirect chain) but they CANNOT prove which page means success. '
             'Only a real card can teach that.')
    rep.note('saved for later comparison: ' + ', '.join(
        f'{a["path"]} ({a["size"]} B)' for a in (plain, hashed) if a and a['path']))
    # remember the failure fingerprint for the summary
    fails = [a for a in (plain, hashed) if a and a['fail']]
    if fails:
        rep.note('rejection baseline: HTTP ' + ', '.join(
            f'{a["status"]} {a["size"]} B ({a["fail"]!r})' for a in fails))


def step_watch(rep, sess, urls, minutes, total_attempts):
    if minutes <= 0:
        return
    rep.hr(f'MONITORING the network for {minutes} minute(s)')
    end = time.time() + minutes * 60
    last = None
    while time.time() < end:
        rows = step_connectivity(rep, sess, urls[:1], datetime.now()
                                 .strftime('%H:%M:%S'))
        word = _verdict_word(rows)
        if word != last:
            rep.add(f'   *** network is now {word} ***')
            last = word
        time.sleep(10)


def step_summary(rep, page, calls, base_rows, after_rows, attempts):
    rep.hr('WHAT WE KNOW NOW (from this page, not from assumptions)')
    conf = []
    if page.form_by_name('sendin'):
        conf.append('the sendin form exists with the fields listed above')
    if calls:
        conf.append('the password field is sent as hexMD5('
                    + repr(chr(calls[0]['prefix_bytes'][0]))
                    + ' + password + ' + str(len(calls[0]['salt_bytes']))
                    + '-byte salt)')
    ext = [s for s in page.script_srcs()]
    if ext:
        conf.append('external script(s): ' + ', '.join(ext))
    for c in conf:
        rep.add(' CONFIRMED  ' + c)
    rep.add('')
    rep.add(' STILL UNKNOWN (cannot be answered by one page load):')
    rep.add('   - the salt question above is answered by section 3b '
            '(fixed / rotating) unless it was skipped')
    rep.add('   - whether the router keeps the same challenge for your IP '
            'between the page load and the POST')
    rep.add('   - whether domain / Hspeed / checkbox1 are required by the '
            'router (only a real login shows that)')
    rep.add('   - what a SUCCESS page looks like on this router (unless an '
            'attempt redirected to /status just now)')
    rep.add('')
    real = [x for x in attempts if x and x['label'].startswith('REAL')]
    if attempts and not real:
        rep.add(' THIS RUN USED NO VALID CARD (probes only). So:')
        rep.add('   PROVEN   the URL, the form, the field names and the hash '
                'shape are right — the router answered normally instead of '
                'rejecting the request itself.')
        rep.add('   NOT KNOWN what a SUCCESS page looks like on this router, '
                'and therefore no detection can be called correct yet.')
        rep.add('   SAVED    the rejection reply (reply_*.html) as the '
                'baseline to compare every later reply against.')
        if any(x and x['fail'] for x in attempts):
            rep.add('   the router rejects a card with a page containing: '
                    + repr(next(x['fail'] for x in attempts
                                if x and x['fail'])))
        else:
            rep.add('   WARNING: no known failure word appeared at all — '
                    'detection cannot rely on words; read reply_*.html.')
        rep.add('')
    b, a = _verdict_word(base_rows), _verdict_word(after_rows)
    rep.add(f' NETWORK  before attempts: {b}   after attempts: {a}')
    if b == 'CAPTIVE' and a == 'OPEN':
        rep.add('   -> an attempt opened the network: the shape AND the '
                'credentials you gave are correct.')
    elif b == 'OPEN':
        rep.add('   -> the device already had internet; a login attempt was '
                'not needed (and the network was NOT captive).')


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def collect_bundle(out_dir, max_chars=0):
    """Pack every artifact of a run into ONE text block that can be pasted."""
    if not os.path.isdir(out_dir):
        print(f' ✗ no such folder: {out_dir}')
        return 1
    files = []
    reports = sorted(f for f in os.listdir(out_dir)
                     if f.startswith('report_') and f.endswith('.txt'))
    if reports:
        files.append(reports[-1])
    for name in sorted(os.listdir(out_dir)):
        if name in files or name.startswith('bundle_'):
            continue
        if name.endswith(('.html', '.js', '.json', '.txt')):
            files.append(name)
    if not files:
        print(f' ✗ nothing to collect in {out_dir}')
        return 1
    parts = ['╔══════════════ KiraPass experimental — COLLECTED OUTPUT '
             '══════════════╗',
             ' Paste EVERYTHING between the BEGIN and END markers.',
             f' folder : {out_dir}',
             f' files  : {len(files)}',
             '╚══════════════════════════════════════════════════════════════╝']
    for name in files:
        path = os.path.join(out_dir, name)
        try:
            size = os.path.getsize(path)
            with open(path, encoding='utf-8', errors='replace') as f:
                text = f.read()
        except OSError as e:
            parts.append(f'\n── {name}: could not be read ({e}) ──')
            continue
        truncated = ''
        if max_chars and len(text) > max_chars:
            text = text[:max_chars]
            truncated = f' … TRUNCATED at {max_chars} chars (file is {size} B)'
        parts.append('')
        parts.append('╔' + '═' * 68)
        parts.append(f'║ BEGIN FILE: {name}   ({size} bytes){truncated}')
        parts.append('╚' + '═' * 68)
        parts.append(text.rstrip('\n'))
        parts.append('── END FILE: ' + name + ' ' + '─' * max(0, 46 - len(name)))
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    bundle_path = os.path.join(out_dir, f'bundle_{stamp}.txt')
    with open(bundle_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts) + '\n')
    print('\n'.join(parts))
    print('')
    print('=' * 70)
    print(f' the same block is saved in: {bundle_path}')
    print(f' copy from the first ╔ line to the last ═ line above')
    print('=' * 70)
    return 0


def ask(prompt, default=None):
    raw = input(prompt).strip()
    return default if raw == '' and default is not None else raw


def interactive(args):
    print('''
  ┌──────────────── KiraPass experimental ────────────────┐
  │ live page dissection + CHAP/hexMD5 diagnosis          │
  │ use only on a network you own or may test             │
  └───────────────────────────────────────────────────────┘''')
    url = args.url or ask(' → Login page URL (ex: http://10.10.10.10/login) : ')
    if not url:
        print(' no URL, bye')
        return None
    if not re.match(r'^https?://', url, re.I):
        url = 'http://' + url
    args.url = url
    print('''
  1) Dissect only              (read-only: page, scripts, JS, facts)
  2) Dissect + probe           (2 attempts, random wrong data — NO CARD NEEDED)
  3) Dissect + probe + my own card   (needs a card you know is valid)
  4) Watch the network only    (no login attempt)
  0) Exit''')
    c = ask(' → choice (Enter = 2) : ', '2')
    while c not in ('0', '1', '2', '3', '4'):
        c = ask(' → choice (0-4) : ')
    if c == '0':
        return None
    args.dissect = c in ('1', '2', '3')
    args.probe = c in ('2', '3')
    args.login = c == '3'
    args.watch_only = c == '4'
    if args.login:
        args.user = ask(' → Username / card : ')
        pw = ask(' → Password (Enter = same as username, "-" = none) : ')
        args.passwd = args.user if pw == '' else (None if pw == '-' else pw)
    if c in ('1', '2', '3', '4'):
        raw = ask(' → Test URLs for the network check '
                  '(Enter = default, "-" = skip, or type one) : ', '')
        if raw == '-':
            args.check = []
            args.no_net_check = True
        elif raw:
            args.check = [raw]
    return args


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='KiraPass experimental — live hotspot dissection and '
                    'CHAP/hexMD5 diagnosis (stdlib only)')
    ap.add_argument('--url', help='login page URL')
    ap.add_argument('--all', action='store_true',
                    help='dissect + probe (2 attempts) + watch 0 min')
    ap.add_argument('--dissect', action='store_true', help='read-only analysis')
    ap.add_argument('--probe', action='store_true',
                    help='send 2 login attempts with random wrong data')
    ap.add_argument('--login', action='store_true',
                    help='send a real login attempt with --user/--pass')
    ap.add_argument('--user', default=None)
    ap.add_argument('--pass', dest='passwd', default=None,
                    help='password ("" = same as username, "-" = send none)')
    ap.add_argument('--watch', type=float, default=0.0,
                    help='minutes to keep monitoring the network afterwards')
    ap.add_argument('--check', action='append', default=None,
                    help='connectivity URL to test (repeatable)')
    ap.add_argument('--out', default=DEFAULT_OUT, help='output folder')
    ap.add_argument('--collect', action='store_true',
                    help='do not touch the network: pack the last run\'s '
                         'artifacts into one pasteable text block')
    ap.add_argument('--collect-max', type=int, default=0,
                    help='max characters per file inside the bundle '
                         '(0 = no limit)')
    ap.add_argument('--timeout', type=float, default=READ_TIMEOUT)
    ap.add_argument('--no-reload-check', action='store_true',
                    help='do not load the page a second time to test whether '
                         'the challenge rotates')
    ap.add_argument('--no-net-check', dest='no_net_check', action='store_true',
                    help='skip the captive-portal check before/after attempts')
    args = ap.parse_args(argv)

    if args.collect:
        return collect_bundle(args.out, args.collect_max)
    if not args.url:
        args = interactive(args)
        if args is None:
            return 0
    if args.all:
        args.dissect = args.probe = True
    if not (args.dissect or args.probe or args.login or args.watch):
        args.dissect = True

    url = (args.url or '').strip()
    if not url:
        print(' ✗ no URL given. Example:  python3 KiraPass_experimental.py '
              '--url http://10.10.10.10/login')
        return 2
    if not re.match(r'^https?://', url, re.I):
        url = 'http://' + url
    if args.passwd == '':
        args.passwd = args.user
    if args.passwd == '-':
        args.passwd = None

    checks = args.check if args.check is not None else CHECK_URLS_DEFAULT
    if getattr(args, 'no_net_check', False):
        checks = []
    sess = Session(timeout=(CONNECT_TIMEOUT, args.timeout))
    rep = Report()
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    os.makedirs(args.out, exist_ok=True)

    head = [
        '=' * 74,
        f' KiraPass experimental {VERSION} — diagnosis report',
        f' time   : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f' target : {url}',
        f' python : {sys.version.split()[0]} on {sys.platform}',
        '=' * 74,
        ' All facts below come from the live page. The old hand-extraction is',
        ' only used as a checklist to compare against.',
        '',
    ]

    base_rows = after_rows = []
    attempts = []
    page = None
    calls = []
    try:
        if args.watch and not args.dissect:
            pass
        else:
            res = step_fetch_page(rep, sess, url, args.out)
            if res is None:
                rep.add('')
                rep.error('stopping: the login page could not be read')
            else:
                base_rows = step_connectivity(rep, sess, checks,
                                              'BEFORE any login attempt')
                page, inline, ext = step_dissect(rep, sess, res, url, args.out)
                calls = step_js(rep, page, inline, ext)
                if not args.no_reload_check:
                    step_salt_stability(rep, sess, url, args.out, calls)
                step_fact_check(rep, page, calls, ext, url)
                if args.probe or args.login:
                    if args.probe:
                        stamp_rnd = datetime.now().strftime('%H%M%S')
                        attempts.append(step_attempt(
                            rep, sess, page, calls, url,
                            'probe: random wrong card, PLAIN password',
                            'zq9x' + stamp_rnd[-6:], 'zq9x' + stamp_rnd[-6:],
                            False, out_dir=args.out))
                        if calls:
                            attempts.append(step_attempt(
                                rep, sess, page, calls, url,
                                'probe: random wrong card, HASHED password',
                                'zq9x' + stamp_rnd[-6:], 'zq9x' + stamp_rnd[-6:],
                                True, out_dir=args.out))
                        else:
                            rep.warn('no hash call found — skipped the hashed '
                                     'probe')
                        step_probe_compare(rep, attempts)
                    if args.login and args.user:
                        attempts.append(step_attempt(
                            rep, sess, page, calls, url,
                            'REAL attempt, PLAIN password', args.user,
                            args.passwd if args.passwd else '', False,
                            out_dir=args.out))
                        if calls:
                            attempts.append(step_attempt(
                                rep, sess, page, calls, url,
                                'REAL attempt, HASHED password', args.user,
                                args.passwd if args.passwd else '', True,
                                out_dir=args.out))
                after_rows = step_connectivity(rep, sess, checks,
                                               'AFTER the attempts')
                step_summary(rep, page, calls, base_rows, after_rows, attempts)
        if args.watch:
            step_watch(rep, sess, checks, args.watch, len(attempts))
    except KeyboardInterrupt:
        rep.warn('interrupted by the user — the report keeps what was done')
    except Exception as e:
        import traceback
        rep.error(f'unexpected failure: {type(e).__name__}: {e}')
        rep.raw('')
        rep.raw(' TRACEBACK (for the developer):')
        for line in traceback.format_exc().splitlines():
            rep.raw('   ' + line)
        print(traceback.format_exc())

    report_path = os.path.join(args.out, f'report_{stamp}.txt')
    rep.raw('')
    rep.raw('─' * 74)
    rep.raw(f' artifacts in : {args.out}')
    rep.raw(f' report file  : {report_path}')
    rep.save(report_path, head)
    print('')
    print('=' * 74)
    print(f' report : {report_path}')
    if sys.stdin.isatty():
        try:
            if input(' → pack everything into one pasteable block now? y/N : '
                     ).strip().lower() in ('y', 'yes'):
                collect_bundle(args.out, 0)
        except (EOFError, KeyboardInterrupt):
            pass
    print(f' errors : {len(rep.errors)}   warnings : {len(rep.warnings)}   '
          f'facts not confirmed : {len(rep.unconfirmed)}')
    print('=' * 74)
    return 1 if rep.errors else 0


if __name__ == '__main__':
    sys.exit(main())
