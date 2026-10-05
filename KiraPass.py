#!/usr/bin/env python3
# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""KiraPass v5 — authorized hotspot / captive-portal security testing.

    python3 KiraPass.py                  # start the local page and open it
    python3 KiraPass.py --selftest       # prove it works, no real network used
    python3 KiraPass.py --clear-cache    # delete tool cache / review pages
    python3 KiraPass.py --host 0.0.0.0   # also open it to your phone (token)

Everything else (the target, the card format, the load, the results) is
answered in the browser page - see docs/README_AR.md or docs/README_EN.md.

Use only on networks you own or have written permission to test.
"""  # نهاية النص متعدد الأسطر

import os  # استيراد الوحدة os من المكتبة
import sys  # استيراد الوحدة sys من المكتبة

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # استدعاء sys.path.insert (2 معاملات)

# استيراد main من الوحدة kirapass.cli
from kirapass.cli import main   # noqa: E402

if __name__ == "__main__":  # شرط: __name__ يساوي '__main__'
    try:  # بدايةtry محمية (يليها except/finally)
        sys.exit(main())  # استدعاء sys.exit (معامل واحد)
    except KeyboardInterrupt:  # تكملة السطر السابق داخل القوس
        print("\n  stopped.")  # استدعاء print (معامل واحد)
        sys.exit(0)  # استدعاء sys.exit (معامل واحد)
