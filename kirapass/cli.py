"""Command line entry point.

The command line is intentionally tiny now: it only starts the local web UI,
clears the cache, or runs the self-test.  Every question is asked in the
browser, which is what makes the tool usable on a phone as well.
"""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import sys
import webbrowser

from . import config, store
from .httpclient import local_ip


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="KiraPass",
        description="Authorized hotspot/captive-portal security testing tool. "
                    "Runs a small local web page - open it and answer there.",
        epilog="Use only on networks you own or have written permission to test.")
    p.add_argument("--host", default=os.environ.get("KIRAPASS_HOST", "127.0.0.1"),
                   help="127.0.0.1 (default, this machine only) or 0.0.0.0 "
                        "(also reachable from your phone on the same wifi - "
                        "a token is then required)")
    p.add_argument("--port", type=int, default=int(os.environ.get("KIRAPASS_PORT",
                                                                  8770)),
                   help="port for the local page (default 8770)")
    p.add_argument("--token", default="auto",
                   help="auto (default) | off | your-own-secret")
    p.add_argument("--no-browser", action="store_true",
                   help="do not open the browser automatically")
    p.add_argument("--lang", choices=["ar", "en"], help="UI language")
    p.add_argument("--clear-cache", nargs="?", const="temp",
                   choices=["temp", "results", "profiles", "all"],
                   help="delete tool data and exit (temp=review+cache, "
                        "results=reports+logs+hits, profiles, all)")
    p.add_argument("--selftest", action="store_true",
                   help="run the built-in test against local mock routers")
    p.add_argument("--check", action="store_true",
                   help="check python version, folders and write permissions")
    p.add_argument("--version", action="store_true", help="print the version")
    return p


def banner(url: str, lan: str, token: str) -> str:
    bar = "─" * 62
    lines = [
        "",
        f"  {config.APP_NAME} v{config.VERSION}  ·  authorized testing only",
        f"  {bar}",
        f"  Open this link / افتح هذا الرابط:",
        f"      {url}",
    ]
    if lan and token:
        lines += [
            f"  From your phone (same wifi) / من الهاتف على نفس الشبكة:",
            f"      {lan}",
            f"  token: {token}",
        ]
    lines += [
        f"  {bar}",
        "  Stop the tool with Ctrl+C  ·  لإيقاف الأداة اضغط Ctrl+C",
        "",
    ]
    return "\n".join(lines)


def free_port(host: str, wanted: int, tries: int = 25) -> int:
    for candidate in range(wanted, wanted + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, candidate))
                return candidate
            except OSError:
                continue
    return wanted


def cmd_clear_cache(scope: str) -> int:
    st = store.Store()
    info = st.cache_info()
    print(f"  cache before: {info['total_bytes'] / 1024:.1f} KB")
    result = st.clear_cache(scope)
    print(f"  scope       : {result['scope']}")
    print(f"  removed     : {', '.join(result['removed']) or 'nothing'}")
    print(f"  freed       : {result['freed_human']}")
    print("  done.")
    return 0


def cmd_check() -> int:
    print(f"  python      : {sys.version.split()[0]} ({sys.executable})")
    print(f"  platform    : {sys.platform} / {os.name}")
    try:
        store.ensure_dirs()
        probe = os.path.join(config.DATA_DIR, ".write-test")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        print(f"  data folder : {config.DATA_DIR} (writable)")
    except OSError as exc:
        print(f"  data folder : NOT writable -> {exc}")
        return 1
    print("  dependencies: none needed (standard library only)")
    try:
        from . import engine, fingerprint, httpclient, portals, verify  # noqa: F401
        print("  modules     : import OK")
    except Exception as exc:                              # noqa: BLE001
        print(f"  modules     : IMPORT FAILED -> {exc}")
        return 1
    return 0


def cmd_selftest() -> int:
    from . import selftest
    print("  KiraPass self-test - local mock routers only, no real network\n")
    summary = selftest.run_all(verbose=True)
    return 0 if summary["ok"] else 1


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        print(f"{config.APP_NAME} {config.VERSION}")
        return 0
    if args.check:
        return cmd_check()
    if args.clear_cache:
        return cmd_clear_cache(args.clear_cache)
    if args.selftest:
        return cmd_selftest()

    st = store.Store()
    if args.lang:
        st.set_setting("lang", args.lang)

    host = args.host
    port = free_port(host, args.port)
    token = ""
    if host not in ("127.0.0.1", "localhost"):
        token = secrets.token_urlsafe(9) if args.token == "auto" else \
            ("" if args.token == "off" else args.token)
    elif args.token not in ("auto", "off"):
        token = args.token

    from .web.server import serve

    shown = {"url": "", "lan": ""}

    def on_ready(real_port, real_token):
        base_local = f"http://127.0.0.1:{real_port}/"
        query = f"?token={real_token}" if real_token else ""
        shown["url"] = base_local + query
        shown["lan"] = ""
        if host not in ("127.0.0.1", "localhost"):
            shown["lan"] = f"http://{local_ip()}:{real_port}/{query}"
        print(banner(shown["url"], shown["lan"], real_token), flush=True)
        if not args.no_browser and not os.environ.get("KIRAPASS_NO_BROWSER"):
            try:
                webbrowser.open(shown["url"])
            except Exception:
                pass

    try:
        serve(host=host, port=port, token=token, on_ready=on_ready)
    except OSError as exc:
        print(f"  could not start the server on {host}:{port} -> {exc}")
        return 1
    except KeyboardInterrupt:
        pass
    print("\n  stopped.")
    return 0
