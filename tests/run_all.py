#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run every offline test of the experimental tool.

    python3 tests/run_all.py

Both suites start their own fake hotspot on 127.0.0.1 — no real network is used.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ['test_offline.py', 'test_negatives.py']


def main():
    failed = []
    for suite in SUITES:
        print('\n' + '█' * 70)
        print(f'█ {suite}')
        print('█' * 70)
        p = subprocess.run([sys.executable, os.path.join(HERE, suite)],
                           cwd=os.path.dirname(HERE))
        if p.returncode != 0:
            failed.append(suite)
    print('\n' + '=' * 70)
    if failed:
        print(' FAILED suites: ' + ', '.join(failed))
    else:
        print(' all suites passed')
    print('=' * 70)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
