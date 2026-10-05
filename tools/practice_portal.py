#!/usr/bin/env python3
"""A local practice hotspot - a fake captive portal for safe training.

    python3 tools/practice_portal.py                 # defaults below
    python3 tools/practice_portal.py --card 0201242548 --port 8899
    python3 tools/practice_portal.py --chap          # md5.js (chap) scheme
    python3 tools/practice_portal.py --method get    # GET form
    python3 tools/practice_portal.py --ban-after 25  # block after 25 failures
    python3 tools/practice_portal.py --rate-limit 20 # answer 429 after 20
    python3 tools/practice_portal.py --drop-every 3  # cut one connection in 3
    python3 tools/practice_portal.py --session  # only a browser gets in (400)
    python3 tools/practice_portal.py --success-page  # welcome + statistics pages

It answers on 127.0.0.1 only, so it can never be reached from outside your
machine. Point KiraPass at the printed URL and watch every verdict - this is
the exact same portal the self-test uses.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kirapass.mockportal import MockPortal   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--card", default="0201242548", help="the one valid card")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--method", choices=["post", "get"], default="post")
    ap.add_argument("--pass-mode", choices=["same", "empty", "chap"],
                    default="same", help="what the portal expects as password")
    ap.add_argument("--chap", action="store_true", help="enable md5.js (chap)")
    ap.add_argument("--ban-after", type=int, default=0, help="0 = never")
    ap.add_argument("--rate-limit", type=int, default=0, help="0 = never")
    ap.add_argument("--drop-every", type=int, default=0, help="0 = never")
    ap.add_argument("--static-page", action="store_true",
                    help="same token on every page (tests the easy case)")
    ap.add_argument("--session", action="store_true",
                    help="like a real portal: hand out a session cookie plus a "
                         "hidden token on the page, and answer 400 'bad "
                         "request' to anything that does not carry them - a "
                         "browser asks for the page first, a bare script does "
                         "not, and that is the whole difference")
    ap.add_argument("--success-page", action="store_true",
                    help="after a valid card, show /success (You are logged in) "
                         "and keep /status as the statistics page - for the "
                         "browser recorder training journey")
    args = ap.parse_args()

    pass_mode = "chap" if args.chap else args.pass_mode
    portal = MockPortal(port=args.port, valid_cards={args.card},
                        method=args.method, pass_mode=pass_mode, chap=args.chap,
                        ban_after=args.ban_after,
                        rate_limit_after=args.rate_limit,
                        drop_every=args.drop_every,
                        require_session=args.session,
                        success_page=args.success_page,
                        dynamic=not args.static_page).start()

    print(f"""
  practice portal is up  ·  بوابة تدريب محلية

    login page : http://127.0.0.1:{args.port}/login
    valid card : {args.card}
    scheme     : {args.method.upper()} form, password = {pass_mode}
    page       : {'static' if args.static_page else 'a new session token every request'}
    ban after  : {args.ban_after or 'never'} failures
    rate limit : {args.rate_limit or 'never'}
    dropped    : every {args.drop_every or '-'} connection
    session    : {'required - a cookie + token from the page, or 400 "bad request"'
                  if args.session else 'not required (any script may post)'}
    success    : {'/success welcome page + /status statistics'
                  if args.success_page else '302 to a connectivity-check URL'}

  Point KiraPass at the login page above and start.
  Ctrl+C to stop.   (this server listens on 127.0.0.1 only)
""", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    print("  stopped.")
    portal.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
