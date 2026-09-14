#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Negative tests: a page that is NOT the "happy" one must produce warnings/errors,
never a confident statement the data does not support.

    python3 tests/test_negatives.py

Variants served by tests/fake_hotspot.py:
    dynamic_salt    the salt rotates on every page load
    no_hash         the password is posted in clear text (no hexMD5)
    uppercase       the md5 code returns UPPERCASE hex (hexcase = 1)
    missing_fields  doLogin() touches fields the form does not have
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

from fake_hotspot import serve  # noqa: E402

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


def run_case(variant, extra_args=()):
    port = free_port()
    srv = serve(port, variant)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.25)
    out = tempfile.mkdtemp(prefix=f'kira_{variant}_')
    url = f'http://127.0.0.1:{port}/login'
    cmd = [sys.executable, os.path.join(ROOT, 'KiraPass_experimental.py'),
           '--url', url, '--out', out,
           '--check', f'http://127.0.0.1:{port}/connecttest.txt'] + list(extra_args)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
    names = [n for n in os.listdir(out) if n.startswith('report_')]
    rep = open(os.path.join(out, names[0]), encoding='utf-8').read() if names else ''
    srv.shutdown()
    srv.server_close()
    return rep, p


def main():
    print('negative tests — the tool must warn, not guess\n')

    print('[A] rotating salt (dynamic_salt)')
    rep, p = run_case('dynamic_salt', ['--probe'])
    check('rotating challenge reported as an ERROR',
          'The salt rotates on every page load' in rep)
    check('the tool explains why a fixed hash cannot work',
          'only valid for the page load' in rep)
    check('the DIFFERS line marks the challenge as changed',
          'the challenge changes between page loads' in rep)
    check('run still finishes and writes a report', len(rep) > 3000,
          f'{len(rep)} chars, exit={p.returncode}')

    print('\n[B] plain-text password, no hexMD5 (no_hash)')
    rep, p = run_case('no_hash')
    check('missing hash call is a WARNING',
          'no  hexMD5(' in rep and 'may be sent unhashed' in rep)
    check('hash fact-check line says MISSING',
          'MISSING' in rep and 'hash call present in the page' in rep)
    check('no invented salt is printed',
          'salt bytes      :' not in rep)

    print('\n[C] uppercase md5 output (hexcase = 1)')
    rep, p = run_case('uppercase')
    check('uppercase hash warned about', 'hexcase=1' in rep)
    check('uppercase warning says the hashes would not match',
          'UPPERCASE hex' in rep)
    check('the salt is still decoded correctly',
          'a7 b3 46 32 17 62 9e 25 26 88 e7 43 f6 65 e3 99' in rep)

    print('\n[D] doLogin() touches fields the form does not have')
    rep, p = run_case('missing_fields')
    check('missing form fields make doLogin() a hard ERROR',
          'but that field does not exist' in rep or
          'does not exist -> the real page would throw' in rep)
    check('the fact-check marks sendin fields as MISSING/DIFFERS',
          'MISSING' in rep or 'DIFFERS' in rep)
    check('the tool still dissects the rest of the page',
          'FORM #2' in rep and 'document.write' in rep)

    failed = [r for r in RESULTS if not r[1]]
    print('\n' + '=' * 66)
    print(f' {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed')
    for label, _, detail in failed:
        print(f'   FAILED: {label}  [{detail}]')
    print('=' * 66)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
