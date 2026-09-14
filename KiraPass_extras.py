#!/usr/bin/env python3
"""
KiraPass extras — flows that live OUTSIDE the main menu.

`KiraPass.py` never imports this file. These two flows were taken out of the
main tool to keep it small; they still work and can be run on their own:

    python3 KiraPass_extras.py

    1) Verify with a known-good card — sends one card you KNOW is valid in
       every request shape (GET/POST, with/without dst+popup, with/without a
       password) and tells you whether the problem is the shape, the success
       detection, or the card itself.
    2) Diagnostics — read-only link test: 30 sequential requests against a
       parallel burst, with error kinds, latency and a verdict. Guesses
       nothing and consumes no attempts.

Everything they need is imported from KiraPass.py, so there is no duplicated
logic to keep in sync.
"""
import os
import sys
import time
from random import choices
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from KiraPass import (  # noqa: E402
    CONNECT_TIMEOUT,
    ERROR_HINTS,
    FAILURE_SIGNS,
    READ_TIMEOUT,
    _probe,
    ask_int,
    ask_yn,
    choose_profile,
    classify_error,
    extract_signature,
    load_db,
    same_path,
    save_db,
    send_login,
    test_connection,
    cyan,
    gray,
    green,
    red,
    white,
    yellow,
)


def _shape_send(p, method, user, pw, extras):
    """Send one request in a given shape without touching the saved profile."""
    q = dict(p)
    q['method'] = method
    q['extras'] = extras
    return send_login(q, user, pw, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))


def _describe_resp(resp, base):
    """Details of one request compared with the original login page."""
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
 ┌─ Verify with a known-good card ─────────────┐
 │ {gray}Know a valid card? this screen tests it{white}     │
 │ {gray}across 8 different request shapes and{white}       │
 │ {gray}tells you exactly where the problem is{white}      │
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
        print(f''' {green}✓ Correct request shape: {w["label"].strip()}
   The router accepted the card and sent you to /status, so success detection
   works. That means the earlier failures were only incomplete number coverage
   (repeated cards) — which version 3.2 fixed.{white}''')
    elif differs:
        d = differs[0]
        print(f''' {yellow}▲ No redirect to /status, but the reply for the valid card
   really is different from the login page ({d["len"]} bytes instead of
   {base["len"]}). So the request succeeded and the router returned a different
   success page (JS/Popup) that your detector does not know — that is why no
   MATCH FOUND was shown.{white}''')
        print(f' {gray}   final URL: {d["url"]}{white}')
    elif rejected_all:
        print(f''' {red}✗ All eight shapes rejected the valid card itself.
   So the problem is neither the tool nor the request shape, but one of:
     1) The card is expired, or was never created / activated on the router
     2) Your device is blocked (ip-binding), or the router refuses a new login
     3) The URL is not the real hotspot login page
   {gray}   Open the login page in a browser and log in with the card by hand:
   if it is rejected there too, the problem is the card/network, not the tool.{white}''')
    else:
        print(f''' {yellow}▲ The replies show neither clear success nor clear rejection.
   Double-check that the valid card is typed correctly and that the URL really
   is the login page.{white}''')
    learn_src = winners[0] if winners else (differs[0] if differs else None)
    if learn_src and idx is not None:
        print(f'''\n {cyan}You can now teach the tool the success page from this reply
   (instead of relying on /status alone — much more accurate).{white}''')
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

def diagnose_flow():
    db = load_db()
    p = choose_profile(db)
    if p is None:
        return

    print(f'''{cyan}
 ┌─ Diagnostics (read-only, no guessing) ──────┐
 │ {gray}Sends requests with wrong data on purpose{white}   │
 │ {gray}to measure the link only: latency,{white}          │
 │ {gray}errors, HTTP codes. Guesses no card.{white}        │
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
        print(f'{yellow}   Guessing is useless until the URL is reachable again.{white}')
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
   So any error you see while attacking is not from the network — check the
   URL and the method.{white}''')
    elif r2 > r1 * 2 and r2 > 3:
        rec = max(4, min(t // 2, 40))
        print(f''' {yellow}▲ Errors grow with the thread count ({r1:.1f}% → {r2:.1f}%).
   That is pressure on the router/device, not a ban and not expired cards.
   {t} → try {rec} threads: real speed usually will not drop, because the router
   is the bottleneck, and the errors will fall a lot.{white}''')
    elif r1 > 3 and s1['err'] >= 3:
        print(f''' {yellow}▲ Errors appear even with a single thread
   ({r1:.1f}% = {s1["err"]} of {s1["n"]} requests).
   The suspect here is the path itself: weak Wi-Fi, a middle AP, or the router
   under pressure / a slow RADIUS. Lowering threads will not fix it.{white}''')
    elif r1 > 3:
        print(f''' {green}✓ One or two errors on a single thread
   ({s1["err"]} of {s1["n"]}) = ordinary noise, no conclusion from it.
   Errors show up with parallelism ({r2:.1f}%) → router pressure, not a ban.{white}''')
    else:
        print(f' {green}✓ The difference is normal: {r1:.1f}% → {r2:.1f}%.{white}')

    if s2['kinds'].get('stale_keepalive'):
        print(f' {gray}Note: {s2["kinds"]["stale_keepalive"]} of the errors were stale '
              f'keep-alive connections (auto-retried) — zero impact.{white}')
    input(f'{gray} Enter to continue...{white}')


def main():
    print(f'\n {cyan}── KiraPass extras (not part of the main menu) ──{white}\n')
    while True:
        print(f"""{cyan}
  ┌─────────────── Extras Menu ───────────────┐{white}
   1) Verify with a known-good card
   2) Diagnostics (read-only)
   0) Back
{cyan}  └───────────────────────────────────────────┘{white}""")
        c = input(f'{white} → choice : ').strip()
        if c == '1':
            verify_flow()
        elif c == '2':
            diagnose_flow()
        elif c in ('0', 'q', 'exit'):
            break
        else:
            print(f'{red} ✗ Invalid choice.{white}')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n {yellow}Interrupted.{white}')
