# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Command line entry point.

The command line is intentionally tiny now: it only starts the local web UI,
clears the cache, or runs the self-test.  Every question is asked in the
browser, which is what makes the tool usable on a phone as well.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import argparse  # استيراد الوحدة argparse من المكتبة
import os  # استيراد الوحدة os من المكتبة
import secrets  # استيراد الوحدة secrets من المكتبة
import socket  # استيراد الوحدة socket من المكتبة
import sys  # استيراد الوحدة sys من المكتبة
import webbrowser  # استيراد الوحدة webbrowser من المكتبة

from . import config, store  # استيراد config, store من الوحدة .
from .httpclient import local_ip  # استيراد local_ip من الوحدة httpclient


def build_parser() -> argparse.ArgumentParser:  # تعريف الدالة build_parser() ترجع argparse.ArgumentParser
    p = argparse.ArgumentParser(  # إسناد نتيجة استدعاء argparse.ArgumentParser (prog=…، description=…، epilog=…) إلى p
        prog="KiraPass",  # المعامل المسمّى prog
        description="Authorized hotspot/captive-portal security testing tool. "  # المعامل المسمّى description
                    "Runs a small local web page - open it and answer there.",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        epilog="Use only on networks you own or have written permission to test.")  # المعامل المسمّى epilog
    p.add_argument("--host", default=os.environ.get("KIRAPASS_HOST", "127.0.0.1"),  # استدعاء p.add_argument (معامل واحد، default=…، help=…)
                   help="127.0.0.1 (default, this machine only) or 0.0.0.0 "  # المعامل المسمّى help
                        "(also reachable from your phone on the same wifi - "  # تكملة السطر السابق داخل القوس
                        "a token is then required)")  # تكملة السطر السابق داخل القوس
    p.add_argument("--port", type=int, default=int(os.environ.get("KIRAPASS_PORT",  # استدعاء p.add_argument (معامل واحد، type=…، default=…، help=…)
                                                                  8770)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                   help="port for the local page (default 8770)")  # المعامل المسمّى help
    p.add_argument("--token", default="auto",  # استدعاء p.add_argument (معامل واحد، default=…، help=…)
                   help="auto (default) | off | your-own-secret")  # المعامل المسمّى help
    p.add_argument("--no-browser", action="store_true",  # استدعاء p.add_argument (معامل واحد، action=…، help=…)
                   help="do not open the browser automatically")  # المعامل المسمّى help
    p.add_argument("--lang", choices=["ar", "en"], help="UI language")  # استدعاء p.add_argument (معامل واحد، choices=…، help=…)
    p.add_argument("--clear-cache", nargs="?", const="temp",  # استدعاء p.add_argument (معامل واحد، nargs=…، const=…، choices=…، help=…)
                   choices=["temp", "results", "profiles", "all"],  # المعامل المسمّى choices
                   help="delete tool data and exit (temp=review+cache, "  # المعامل المسمّى help
                        "results=reports+logs+hits, profiles, all)")  # تكملة السطر السابق داخل القوس
    p.add_argument("--selftest", action="store_true",  # استدعاء p.add_argument (معامل واحد، action=…، help=…)
                   help="run the built-in test against local mock routers")  # المعامل المسمّى help
    p.add_argument("--check", action="store_true",  # استدعاء p.add_argument (معامل واحد، action=…، help=…)
                   help="check python version, folders and write permissions")  # المعامل المسمّى help
    p.add_argument("--version", action="store_true", help="print the version")  # استدعاء p.add_argument (معامل واحد، action=…، help=…)
    return p  # إرجاع p


def banner(url: str, lan: str, token: str) -> str:  # تعريف الدالة banner(url, lan, token) ترجع str
    bar = "─" * 62  # حساب ضرب بين '─' و62 وإسناده إلى bar
    lines = [  # إسناد قائمة إلى lines
        "",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        f"  {config.APP_NAME} v{config.VERSION}  ·  authorized testing only",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        f"  {bar}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        f"  Open this link / افتح هذا الرابط:",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        f"      {url}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    ]  # إغلاق القوس المفتوح في السطر السابق
    if lan and token:  # شرط مركّب (و)
        lines += [  # تحديث lines بعملية جمع
            f"  From your phone (same wifi) / من الهاتف على نفس الشبكة:",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            f"      {lan}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            f"  token: {token}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        ]  # إغلاق القوس المفتوح في السطر السابق
    lines += [  # تحديث lines بعملية جمع
        f"  {bar}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        "  Stop the tool with Ctrl+C  ·  لإيقاف الأداة اضغط Ctrl+C",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        "",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    ]  # إغلاق القوس المفتوح في السطر السابق
    return "\n".join(lines)  # إرجاع '\n'.join(lines)


def free_port(host: str, wanted: int, tries: int = 25) -> int:  # تعريف الدالة free_port(host, wanted, tries) ترجع int
    for candidate in range(wanted, wanted + tries):  # دورة على range(wanted, جمع) باسم candidate
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:  # سياق مُدار: socket.socket(socket.AF_INET, socket.SOCK_STREAM) باسم s
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # استدعاء s.setsockopt (3 معاملات)
            try:  # بدايةtry محمية (يليها except/finally)
                s.bind((host, candidate))  # استدعاء s.bind (معامل واحد)
                return candidate  # إرجاع candidate
            except OSError:  # تكملة السطر السابق داخل القوس
                continue  # الانتقال إلى الدورة التالية
    return wanted  # إرجاع wanted


def cmd_clear_cache(scope: str) -> int:  # تعريف الدالة cmd_clear_cache(scope) ترجع int
    st = store.Store()  # إسناد نتيجة استدعاء store.Store إلى st
    info = st.cache_info()  # إسناد نتيجة استدعاء st.cache_info إلى info
    print(f"  cache before: {info['total_bytes'] / 1024:.1f} KB")  # استدعاء print (معامل واحد)
    result = st.clear_cache(scope)  # إسناد نتيجة استدعاء st.clear_cache (معامل واحد) إلى result
    print(f"  scope       : {result['scope']}")  # استدعاء print (معامل واحد)
    print(f"  removed     : {', '.join(result['removed']) or 'nothing'}")  # استدعاء print (معامل واحد)
    print(f"  freed       : {result['freed_human']}")  # استدعاء print (معامل واحد)
    print("  done.")  # استدعاء print (معامل واحد)
    return 0  # إرجاع 0


def cmd_check() -> int:  # تعريف الدالة cmd_check() ترجع int
    print(f"  python      : {sys.version.split()[0]} ({sys.executable})")  # استدعاء print (معامل واحد)
    print(f"  platform    : {sys.platform} / {os.name}")  # استدعاء print (معامل واحد)
    try:  # بدايةtry محمية (يليها except/finally)
        store.ensure_dirs()  # استدعاء store.ensure_dirs
        probe = os.path.join(config.DATA_DIR, ".write-test")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى probe
        with open(probe, "w", encoding="utf-8") as fh:  # سياق مُدار: open(probe, 'w', encoding='utf-8') باسم fh
            fh.write("ok")  # استدعاء fh.write (معامل واحد)
        os.remove(probe)  # استدعاء os.remove (معامل واحد)
        print(f"  data folder : {config.DATA_DIR} (writable)")  # استدعاء print (معامل واحد)
    except OSError as exc:  # تكملة السطر السابق داخل القوس
        print(f"  data folder : NOT writable -> {exc}")  # استدعاء print (معامل واحد)
        return 1  # إرجاع 1
    print("  dependencies: none needed (standard library only)")  # استدعاء print (معامل واحد)
    try:  # بدايةtry محمية (يليها except/finally)
        # استيراد engine, fingerprint, httpclient, portals, verify من الوحدة .
        from . import engine, fingerprint, httpclient, portals, verify  # noqa: F401
        print("  modules     : import OK")  # استدعاء print (معامل واحد)
    # تكملة السطر السابق داخل القوس
    except Exception as exc:                              # noqa: BLE001
        print(f"  modules     : IMPORT FAILED -> {exc}")  # استدعاء print (معامل واحد)
        return 1  # إرجاع 1
    return 0  # إرجاع 0


def cmd_selftest() -> int:  # تعريف الدالة cmd_selftest() ترجع int
    from . import selftest  # استيراد selftest من الوحدة .
    print("  KiraPass self-test - local mock routers only, no real network\n")  # استدعاء print (معامل واحد)
    summary = selftest.run_all(verbose=True)  # إسناد نتيجة استدعاء selftest.run_all (verbose=…) إلى summary
    return 0 if summary["ok"] else 1  # إرجاع 0 إن summary['ok'] وإلا 1


# يحلّل سطر الأوامر ثم يشغّل السيرفر ويطبع الرابط والرمز.
# --host 0.0.0.0 يطبع تحذيراً: الرمز يُرسل بلا TLS على شبكة محلية.
def main(argv=None) -> int:  # تعريف الدالة main(argv) ترجع int
    args = build_parser().parse_args(argv)  # إسناد نتيجة استدعاء build_parser().parse_args (معامل واحد) إلى args

    if args.version:  # شرط: args.version
        print(f"{config.APP_NAME} {config.VERSION}")  # استدعاء print (معامل واحد)
        return 0  # إرجاع 0
    if args.check:  # شرط: args.check
        return cmd_check()  # إرجاع cmd_check()
    if args.clear_cache:  # شرط: args.clear_cache
        return cmd_clear_cache(args.clear_cache)  # إرجاع cmd_clear_cache(args.clear_cache)
    if args.selftest:  # شرط: args.selftest
        return cmd_selftest()  # إرجاع cmd_selftest()

    st = store.Store()  # إسناد نتيجة استدعاء store.Store إلى st
    if args.lang:  # شرط: args.lang
        st.set_setting("lang", args.lang)  # استدعاء st.set_setting (2 معاملات)

    host = args.host  # إسناد args.host إلى host
    port = free_port(host, args.port)  # إسناد نتيجة استدعاء free_port (2 معاملات) إلى port
    token = ""  # إسناد القيمة الثابتة token
    if host not in ("127.0.0.1", "localhost"):  # شرط: host ليس ضمن مجموعة
        # إسناد secrets.token_urlsafe(9) إن مقارنة وإلا '' إن مقارنة وإلا args.token إلى token
        token = secrets.token_urlsafe(9) if args.token == "auto" else \
            ("" if args.token == "off" else args.token)  # تكملة السطر السابق داخل القوس
        print(  # استدعاء print (معامل واحد، flush=…)
            "\n  ⚠  WARNING / تحذير:\n"  # تكملة السطر السابق داخل القوس
            "  --host 0.0.0.0 opens the UI on the LAN over plain HTTP.\n"  # تكملة السطر السابق داخل القوس
            "  The access token is sent without TLS — use only on a network\n"  # تكملة السطر السابق داخل القوس
            "  you trust. Prefer 127.0.0.1 when possible.\n"  # تكملة السطر السابق داخل القوس
            "  فتح الواجهة على 0.0.0.0 يرسل الرمز بدون تشفير؛ استخدمه فقط\n"  # تكملة السطر السابق داخل القوس
            "  على شبكة تثق بها.\n",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            flush=True,  # المعامل المسمّى flush
        )  # إغلاق القوس المفتوح في السطر السابق
    elif args.token not in ("auto", "off"):  # شرط: args.token ليس ضمن مجموعة
        token = args.token  # إسناد args.token إلى token

    from .web.server import serve  # استيراد serve من الوحدة web.server

    shown = {"url": "", "lan": ""}  # إسناد قاموس إلى shown

    def on_ready(real_port, real_token):  # تعريف الدالة on_ready(real_port, real_token)
        base_local = f"http://127.0.0.1:{real_port}/"  # بناء نص منسّق وإسناده إلى base_local
        query = f"?token={real_token}" if real_token else ""  # إسناد نص منسّق (f-string) إن real_token وإلا '' إلى query
        shown["url"] = base_local + query  # حساب جمع بين base_local وquery وإسناده إلى shown['url']
        shown["lan"] = ""  # إسناد القيمة الثابتة shown['lan']
        if host not in ("127.0.0.1", "localhost"):  # شرط: host ليس ضمن مجموعة
            shown["lan"] = f"http://{local_ip()}:{real_port}/{query}"  # بناء نص منسّق وإسناده إلى shown['lan']
        print(banner(shown["url"], shown["lan"], real_token), flush=True)  # استدعاء print (معامل واحد، flush=…)
        if not args.no_browser and not os.environ.get("KIRAPASS_NO_BROWSER"):  # شرط مركّب (و)
            try:  # بدايةtry محمية (يليها except/finally)
                webbrowser.open(shown["url"])  # استدعاء webbrowser.open (معامل واحد)
            except Exception:  # تكملة السطر السابق داخل القوس
                pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً

    try:  # بدايةtry محمية (يليها except/finally)
        serve(host=host, port=port, token=token, on_ready=on_ready)  # استدعاء serve (host=…، port=…، token=…، on_ready=…)
    except OSError as exc:  # تكملة السطر السابق داخل القوس
        print(f"  could not start the server on {host}:{port} -> {exc}")  # استدعاء print (معامل واحد)
        return 1  # إرجاع 1
    except KeyboardInterrupt:  # تكملة السطر السابق داخل القوس
        pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
    print("\n  stopped.")  # استدعاء print (معامل واحد)
    return 0  # إرجاع 0
