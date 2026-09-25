#!/usr/bin/env python3
"""KiraPass v5 — authorized hotspot / captive-portal security testing.

    python3 KiraPass.py                  # start the local page and open it
    python3 KiraPass.py --selftest       # prove it works, no real network used
    python3 KiraPass.py --clear-cache    # delete tool cache / review pages
    python3 KiraPass.py --host 0.0.0.0   # also open it to your phone (token)

Everything else (the target, the card format, the load, the results) is
answered in the browser page - see docs/README_AR.md or docs/README_EN.md.

Use only on networks you own or have written permission to test.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kirapass.cli import main   # noqa: E402

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  stopped.")
        sys.exit(0)
