#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Offline test for KiraPass_experimental.py.

Starts tests/fake_hotspot.py, runs the diagnosis script against it and checks
that every claim it prints is really backed by what the fake page returned.

    python3 tests/test_offline.py

Exit code 0 = all checks passed. No real network is touched.
"""

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from fake_hotspot import ST, VALID_PASS, VALID_USER, serve  # noqa: E402

RESULTS = []


def check(label, ok, detail=''):
    RESULTS.append((label, bool(ok), detail))
    print(('  ✓ ' if ok else '  ✗ ') + label + (f'   [{detail}]' if detail else ''))


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_tool(args, timeout=120):
    cmd = [sys.executable, os.path.join(ROOT, 'KiraPass_experimental.py')] + args
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=timeout)
    return p


def read_report(out_dir):
    names = [n for n in os.listdir(out_dir) if n.startswith('report_')]
    assert names, 'no report file was written'
    with open(os.path.join(out_dir, names[0]), encoding='utf-8') as f:
        return f.read(), os.path.join(out_dir, names[0])


def main():
    port = free_port()
    srv = serve(port)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.3)
    url = f'http://127.0.0.1:{port}/login'
    out = tempfile.mkdtemp(prefix='kirapass_test_')
    print(f'fake hotspot: {url}\noutput dir  : {out}\n')

    # ── run 1: full diagnosis with a real, valid credential ────────────────
    p = run_tool(['--url', url, '--dissect', '--probe',
                  '--login', '--user', VALID_USER, '--pass', VALID_PASS,
                  '--out', out,
                  '--check', f'http://127.0.0.1:{port}/connectivitycheck/generate_204',
                  '--check', f'http://127.0.0.1:{port}/connecttest.txt'])
    rep, rep_path = read_report(out)
    print(f'--- report: {rep_path} (exit {p.returncode}) ---')

    # ── checks ─────────────────────────────────────────────────────────────
    print('\n[1] live dissection')
    check('two forms found', rep.count(' FORM #') == 2,
          f'count={rep.count(" FORM #")}')
    check('form "sendin" listed', "'sendin'" in rep)
    check('form "login" listed', "'login'" in rep)
    check('sendin extra fields detected (speed/update/facebook)',
          all(f'name={n!r}' in rep for n in ('speed', 'update', 'facebook')))
    check('duplicate id warning raised', 'duplicate attributes' in rep)

    print('\n[2] external md5.js read and understood')
    check('md5.js fetched and saved',
          os.path.exists(os.path.join(out, 'md5.js')))
    check('md5 semantics reported (chrsz/charCodeAt)',
          'chrsz=8' in rep and 'charCodeAt' in rep)
    check('hexMD5 body quoted', 'function hexMD5' in rep)

    print('\n[3] hash call decoded correctly')
    m = re.search(r'salt bytes      : ([0-9a-f ]+)\s+\((\d+) bytes\)', rep)
    check('salt found', m is not None)
    if m:
        got = bytes.fromhex(m.group(1).strip())
        want = bytes([0o247, 0o263, 0o106, 0o062, 0o027, 0o142, 0o236, 0o045,
                      0o046, 0o210, 0o347, 0o103, 0o366, 0o145, 0o343, 0o231])
        check('salt bytes == the quoted material', got == want,
              f'{got.hex(" ")}')
        check('salt length is 16', len(got) == 16, str(len(got)))
    check('prefix decoded to 0x23 (#)',
          'prefix literal' in rep and '23  (b' in rep)

    print('\n[4] baseline fact-check ran')
    check('fact-check section present', 'FACT CHECK vs the previous' in rep)
    confirmed = rep.count('✓ CONFIRMED')
    check('the sample page confirms most baseline facts', confirmed >= 8,
          f'CONFIRMED={confirmed}')
    # the fake page deliberately adds speed/update/facebook to "sendin", so the
    # tool MUST notice that the old extraction was incomplete
    check('extra sendin fields reported as DIFFERS',
          'speed, update, facebook' in rep and 'DIFFERS' in rep)
    check('incompleteness of the old extraction flagged',
          'the old extraction was INCOMPLETE' in rep)

    print('\n[5] real login attempts and redirect chain')
    check('redirect to /status seen', 'SUCCESS (redirect to /status)' in rep)
    # the fake server itself validated the hash, so this proves the tool
    # computed hexMD5('#password'+salt) byte-for-byte correctly
    log = '\n'.join(ST.requests)
    check('the SERVER accepted the HASHED (hexMD5) password',
          'user=' + repr(VALID_USER) in log and '(hash)' in log + '\n' and
          "(hash) fields=" in log, [l for l in ST.requests if 'hash' in l][:1])
    check('the server rejected the random probe card', '(wrong)' in log,
          [l for l in ST.requests if '(wrong)' in l][:1])
    check('report records the exact fields that were sent',
          "password=" in rep and "dst=" in rep and "popup=" in rep)
    check('network went CAPTIVE -> OPEN after the valid login',
          'CAPTIVE' in rep and 'after attempts: OPEN' in rep)
    check('attempt summary printed', 'ATTEMPT —' in rep)
    check('probe comparison section present',
          'WHAT THE PROBES SAY (a valid card is NOT needed)' in rep)
    check('rejection reply saved to disk',
          any(n.startswith('reply_') for n in os.listdir(out)),
          [n for n in os.listdir(out) if n.startswith('reply_')][:2])
    check('reply fingerprint (sha1) printed', 'body sha1' in rep)

    print('\n[6] errors and report quality')
    check('no ERROR lines in the report', '✗ ERROR' not in rep,
          [l for l in rep.splitlines() if '✗ ERROR' in l][:3])
    check('report file written and non trivial', len(rep) > 4000,
          f'{len(rep)} chars')
    check('tool exit code is 0', p.returncode == 0, f'exit={p.returncode}')

    # ── run 2: salt stability (is it per page load or fixed?) ─────────────
    print('\n[7] second page load — salt stability')
    out2 = tempfile.mkdtemp(prefix='kirapass_test2_')
    run_tool(['--url', url, '--out', out2,
              '--check', f'http://127.0.0.1:{port}/connecttest.txt'])
    rep2, _ = read_report(out2)
    m2 = re.search(r'salt bytes      : ([0-9a-f ]+)\s+\((\d+) bytes\)', rep2)
    check('same salt on the second load (fixed challenge)',
          bool(m and m2 and m.group(1) == m2.group(1)),
          'the tool prints a warning when it differs, which is the useful '
          'signal on a real router')

    # ── run 2b: NO CARD AT ALL (exactly what the user asked for) ──────────
    print('\n[7b] probe-only run: no valid card, no --login')
    outn = tempfile.mkdtemp(prefix='kirapass_nocard_')
    pn = run_tool(['--url', url, '--probe', '--out', outn,
                   '--check',
                   f'http://127.0.0.1:{port}/connectivitycheck/generate_204'])
    repn, _ = read_report(outn)
    check('no-card run exits 0', pn.returncode == 0, f'exit={pn.returncode}')
    check('probe comparison section present without a card',
          'WHAT THE PROBES SAY (a valid card is NOT needed)' in repn)
    check('the report states plainly what is NOT known',
          'THIS RUN USED NO VALID CARD' in repn and
          'NOT KNOWN what a SUCCESS page looks like' in repn)
    check('rejection baseline saved for later comparison',
          'rejection baseline' in repn and
          sum(1 for n in os.listdir(outn) if n.startswith('reply_')) == 2,
          [n for n in os.listdir(outn) if n.startswith('reply_')])
    check('no invented success claim without a card',
          'SUCCESS — FOUND' not in repn and
          'looks like a SUCCESS' not in repn)

    # ── run 3: interactive menu must not crash ────────────────────────────
    print('\n[8] interactive menu (piped answers)')
    out3 = tempfile.mkdtemp(prefix='kirapass_test3_')
    p3 = subprocess.run(
        [sys.executable, os.path.join(ROOT, 'KiraPass_experimental.py'),
         '--out', out3],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
        input=f'{url}\n1\n-\n')
    check('interactive run exits 0', p3.returncode == 0,
          f'exit={p3.returncode}')
    check('interactive run had no traceback', 'Traceback' not in p3.stderr,
          p3.stderr.strip().splitlines()[-1:] or '')
    check('interactive run wrote a report',
          any(n.startswith('report_') for n in os.listdir(out3)))

    # ── run 4: --collect packs everything into one block ─────────────────
    print('\n[9] --collect bundle')
    before = len(ST.requests)
    p4 = subprocess.run([sys.executable,
                         os.path.join(ROOT, 'KiraPass_experimental.py'),
                         '--collect', '--out', out],
                        cwd=ROOT, capture_output=True, text=True, timeout=120)
    after = len(ST.requests)
    check('bundle printed', 'BEGIN FILE: login_page.html' in p4.stdout and
          'BEGIN FILE: md5.js' in p4.stdout, f'exit={p4.returncode}')
    check('bundle saved to a file',
          any(n.startswith('bundle_') for n in os.listdir(out)))
    check('collect mode did not touch the network', before == after,
          f'requests before={before} after={after}')

    # ── summary ───────────────────────────────────────────────────────────
    failed = [r for r in RESULTS if not r[1]]
    print('\n' + '=' * 66)
    print(f' {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed')
    for label, _, detail in failed:
        print(f'   FAILED: {label}  [{detail}]')
    print('=' * 66)
    srv.shutdown()
    srv.server_close()
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
