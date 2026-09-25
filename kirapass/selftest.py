"""Self-test: prove the tool works without touching any real network.

    python3 KiraPass.py --selftest

It spins up local mock routers (see mockportal.py), including the exact
situations that broke the old version:

    * a page whose session token changes on every request
    * wrong cards that must NEVER be reported as a hit
    * a router that bans you, one that rate limits you, one that drops
      connections, a chap/md5.js portal, a GET portal, an old saved profile
"""

from __future__ import annotations

import os
import shutil
import sys
import time

from . import config, engine, portals, store
from .httpclient import Session
from .mockportal import MockPortal


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def make_profile(url: str, prefix="02", length=4, charset="0123456789",
                 portal_info=None, **kw) -> dict:
    p = store.new_profile(login_url=url, prefix=prefix, length=length,
                          charset=charset, name="selftest", pass_mode="empty")
    if portal_info:
        form = portal_info.get("form") or {}
        p.update({
            "login_url": form.get("action") or url,
            "method": (form.get("method") or "post").lower(),
            "user_field": form.get("user_field") or "username",
            "pass_field": form.get("pass_field") or "password",
            "extra_fields": form.get("extra_fields") or {},
            "dst_field": form.get("dst_field") or "dst",
            "dst_value": form.get("dst_value") or "",
            "chap": form.get("chap") or None,
        })
    p.update(kw)
    return p


def mock_checks(portal) -> tuple:
    """The mock router's own internet endpoints - keeps tests off the internet."""
    base = f"http://127.0.0.1:{portal.port}"
    return ((base + "/generate_204", 204, None, "mock204"),
            (base + "/connecttest.txt", 200, "Microsoft Connect Test", "mocktxt"),
            (base + "/hotspot-detect.html", 200, "Success", "mockapple"))


def scan(url: str) -> dict:
    session = Session(allow_redirects=True)
    try:
        return portals.discover(session, url).as_dict()
    finally:
        session.close()


_RUN_ID = [0]


def run_engine(profile: dict, attempts: int, threads: int = 3,
               timeout: float = 90.0, checks=None, reset: bool = True, **kw):
    """Fresh, throw-away run: no resume state, nothing saved on disk.

    `reset=False` keeps `space_pos`/`walk_*` - that is how the "continue where
    you stopped" path is tested (the UI sends them back with the profile).
    """
    _RUN_ID[0] += 1
    profile = dict(profile)
    profile.update({"name": f"selftest-{_RUN_ID[0]}"})
    if reset:
        profile.update({"space_pos": 0, "walk_a": 0, "walk_b": 0})
    eng = engine.Engine(store.Store(), persist=False, checks=checks)
    res = eng.start(profile, attempts=attempts, threads=threads, **kw)
    if not res.get("ok"):
        return {"state": "rejected", "error": res.get("error"),
                "problems": res.get("problems", [])}, eng
    deadline = time.time() + timeout
    while eng.state in ("calibrating", "running", "stopping"):
        if time.time() > deadline:
            eng.stop("timeout")
            break
        time.sleep(0.05)
    if eng.thread is not None:
        eng.thread.join(timeout=5)
    return eng.status(), eng


class Result:
    def __init__(self, name, ok, detail=""):
        self.name = name
        self.ok = ok
        self.detail = detail

    def __str__(self):
        mark = "PASS" if self.ok else "FAIL"
        return f"[{mark}] {self.name}: {self.detail}"


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------
def t_calibration():
    """The rejection baseline must be learned even with a changing token."""
    with MockPortal(valid_cards={"0299"}, dynamic=True,
                    pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, portal_info=info)
        cal = engine.calibrate(p)
        fp = cal.fingerprint
        ok = (cal.ok and fp is not None and fp.samples == 3
              and (fp.exact or len(fp.literals) >= 0))
        detail = (f"baseline {'exact' if fp and fp.exact else 'shaped'}, "
                  f"dynamic tokens={len(fp.literals) if fp else 0}, "
                  f"status={fp.reject_status if fp else '-'}, "
                  f"bytes={fp.reject_len if fp else '-'}")
        return Result("calibration_learns_rejection_page", bool(ok), detail)


def t_no_false_hits():
    """50 wrong cards: zero accepted. This is the old bug, in a test."""
    with MockPortal(valid_cards={"0299"}, pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info,
                         pass_mode="empty")
        st, _eng = run_engine(p, attempts=50, threads=3,
                              checks=mock_checks(portal))
        c = st.get("counters", {})
        accepted = sum(v for k, v in c.items() if k.startswith("ACCEPTED"))
        ok = accepted == 0 and c.get("REJECTED", 0) >= 40
        return Result("wrong_cards_are_never_reported_as_hits", ok,
                      f"counters={dict(c)} accepted={accepted} "
                      f"stop={st.get('stop_reason')} "
                      f"progress={st.get('progress')}")


def t_find_card():
    """The card that exists gets found AND verified against the internet."""
    with MockPortal(valid_cards={"0242"}) as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, portal_info=info, pass_mode="empty")
        st, eng = run_engine(p, attempts=200, threads=4,
                             checks=mock_checks(portal), known_card="0242")
        hits = st.get("hits", [])
        ok = (bool(hits) and hits[0]["card"] == "0242"
              and hits[0]["code"] == "ACCEPTED_VERIFIED"
              and st.get("stop_reason") == "found_verified")
        return Result("finds_the_working_card_and_proves_internet", ok,
                      f"hits={hits} stop={st.get('stop_reason')} "
                      f"counters={st.get('counters')}")


def t_ban_is_reported():
    """A ban must be named as a ban - never as a hit or as 'tested'."""
    with MockPortal(valid_cards={"0299"}, ban_after=5, pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)
        st, _eng = run_engine(p, attempts=60, threads=2,
                              checks=mock_checks(portal))
        c = st.get("counters", {})
        accepted = sum(v for k, v in c.items() if k.startswith("ACCEPTED"))
        ok = (c.get("BANNED", 0) >= 1 and accepted == 0
              and st.get("stop_reason") == "banned_by_router")
        return Result("ban_from_router_is_named_and_stops_the_run", ok,
                      f"banned={c.get('BANNED', 0)} accepted={accepted} "
                      f"stop={st.get('stop_reason')}")


def t_rate_limit_slows_down():
    with MockPortal(valid_cards={"0299"}, rate_limit_after=4,
                    pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)
        eng = engine.Engine(store.Store(), persist=False,
                            checks=mock_checks(portal))
        eng.start(dict(p, name="selftest-rate", space_pos=0, walk_a=0, walk_b=0),
                  attempts=40, threads=2)
        deadline = time.time() + 60
        while eng.state in ("calibrating", "running") and time.time() < deadline:
            time.sleep(0.05)
        st = eng.status()
        c = st.get("counters", {})
        delay = (st.get("throttle") or {}).get("delay_ms", 0)
        ok = c.get("RATE_LIMITED", 0) >= 1 and delay > 0
        return Result("rate_limit_is_reported_and_slows_down", ok,
                      f"rate_limited={c.get('RATE_LIMITED', 0)} delay={delay}ms "
                      f"reason={(st.get('throttle') or {}).get('reason')}")


def t_dropped_connections():
    """Half the sockets are cut: retries must save the card, and nothing may
    be reported as tested when it never got an answer."""
    with MockPortal(valid_cards={"0299"}, drop_every=2,
                    pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)
        st, _eng = run_engine(p, attempts=30, threads=3,
                              checks=mock_checks(portal))
        c = st.get("counters", {})
        accepted = sum(v for k, v in c.items() if k.startswith("ACCEPTED"))
        pr = st.get("progress", {})
        accounted = pr.get("attempts", 0) == pr.get("queued", -1)
        ok = accepted == 0 and accounted and pr.get("dropped", 0) == 0
        return Result("dropped_connections_are_counted_not_hidden", ok,
                      f"counters={dict(c)} progress={pr} accepted={accepted}")


def t_dead_target_stops():
    """The router stops answering entirely: stop with that reason, honestly."""
    with MockPortal(valid_cards={"0299"}, pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)
        portal.state.drop_after = 12          # everything is cut from here on
        st, _eng = run_engine(p, attempts=400, threads=3,
                              checks=mock_checks(portal), timeout=60)
        c = st.get("counters", {})
        ok = (st.get("stop_reason") == "target_unreachable"
              and c.get("NET_ERROR", 0) >= 10
              and not any(k.startswith("ACCEPTED") for k in c))
        return Result("dead_target_is_detected_and_stops_the_run", ok,
                      f"stop={st.get('stop_reason')} counters={dict(c)} "
                      f"kinds={st.get('net_kinds')}")


def t_chap_portal():
    """MikroTik md5.js (chap) portal - the tool must find the right formula."""
    with MockPortal(valid_cards={"0242"}, chap=True, pass_mode="chap") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, portal_info=info, pass_mode="empty")
        cal = engine.calibrate(p, known_card="0242", checks=mock_checks(portal))
        tuned = cal.tuned or {}
        ok = bool(tuned) and tuned.get("mode", "").startswith("chap")
        if not ok:
            return Result("chap_md5_portal_shape_is_discovered", False,
                          f"tuned={tuned} steps={[s['id'] + ':' + s['reason'] for s in cal.steps]}")
        # now a full run with the discovered shape
        p2 = dict(cal.profile)
        st, _eng = run_engine(p2, attempts=200, threads=4,
                              checks=mock_checks(portal))
        hits = st.get("hits", [])
        ok = bool(hits) and hits[0]["code"] == "ACCEPTED_VERIFIED"
        return Result("chap_md5_portal_shape_is_discovered", ok,
                      f"mode={tuned.get('mode')} verified={tuned.get('verified')} "
                      f"hits={hits}")


def t_get_portal():
    with MockPortal(valid_cards={"0242"}, method="get",
                    pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, portal_info=info)
        st, _eng = run_engine(p, attempts=200, threads=4,
                              checks=mock_checks(portal))
        hits = st.get("hits", [])
        ok = bool(hits) and hits[0]["card"] == "0242"
        return Result("get_style_portal_is_supported", ok,
                      f"method={(info.get('form') or {}).get('method')} hits={hits} "
                      f"stop={st.get('stop_reason')} counters={st.get('counters')} "
                      f"net={st.get('net_kinds')}")


def t_legacy_profile():
    """A profile saved by the OLD version must not crash the new one."""
    old = {"name": "old-network", "login_url": "http://127.0.0.1:1/login",
           "method": "2", "network_type": "1", "var_len": 2, "prefix": "02",
           "extras": True, "dst_value": "", "pass_mode": "empty"}
    p = store.migrate(old)
    problems = store.validate(p)
    with MockPortal(valid_cards={"0242"}, pass_mode="empty") as portal:
        info = scan(portal.url)
        p["login_url"] = (info.get("form") or {}).get("action") or portal.url
        st, _eng = run_engine(p, attempts=200, threads=3,
                              checks=mock_checks(portal), known_card="0242")
        hits = st.get("hits", [])
        ok = bool(hits) and not [x for x in problems if x != "space_is_astronomically_big"]
        return Result("old_profile_is_migrated_without_crashing", ok,
                      f"migrated='{p.get('prefix')}' len={p.get('length')} "
                      f"problems={problems} hits={len(hits)}")


def t_diagnose_dead_target():
    r = engine.diagnose({"login_url": "http://127.0.0.1:9/login", "prefix": "02",
                         "length": 4, "charset": "0123456789", "name": "dead"})
    step = next((s for s in r.get("steps", []) if s["id"] == "reach"), None)
    ok = bool(step) and not step["ok"] and step["reason"].startswith("net_")
    return Result("diagnose_explains_a_dead_target", ok,
                  f"reason={step['reason'] if step else '-'}")


def t_resume_continues():
    """A second run must continue - not repeat the cards of the first one.

    The run position lives in the profile (`space_pos` + the shuffled walk).
    The page sends it back with the profile, so the next run starts where the
    previous one stopped; this scenario is that promise, tested.
    """
    with MockPortal(valid_cards={"9999"}, pass_mode="empty") as portal:
        info = scan(portal.url)
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)
        _st1, eng1 = run_engine(p, attempts=20, threads=2,
                                checks=mock_checks(portal))
        resumed = dict(eng1.profile)      # exactly what the page sends back
        st2, eng2 = run_engine(resumed, attempts=20, threads=2,
                               checks=mock_checks(portal), reset=False)
        pos1 = int(eng1.profile.get("space_pos", 0))
        pos2 = int(eng2.profile.get("space_pos", 0))
        same_walk = (eng1.profile.get("walk_a") == eng2.profile.get("walk_a")
                     and eng1.profile.get("walk_b") == eng2.profile.get("walk_b"))
        ok = pos1 == 20 and pos2 == 40 and same_walk
        return Result("a_second_run_continues_where_the_first_stopped", ok,
                      f"first_run_ended_at={pos1} second_run_ended_at={pos2} "
                      f"same_walk={same_walk} counters={st2.get('counters')}")


def t_cache_clear():
    """Clearing the cache must not eat the results.

    `temp` removes review pages and cache folders but MUST leave the hits log
    alone; only `results`/`all` are allowed to delete it.
    """
    st = store.Store()
    saved = st.save_review(1, "0201242548",
                           {"code": "UNKNOWN", "reason": "reply_differs_not_proven",
                            "data": {}}, "<html>interesting</html>")
    st.append_hit("selftest card=0242 code=ACCEPTED_VERIFIED")
    before = len(st.list_review())
    temp = st.clear_cache("temp")
    review_gone = before >= 1 and not st.list_review()
    hits_kept = os.path.exists(config.HITS_FILE)
    results = st.clear_cache("results")
    hits_gone = not os.path.exists(config.HITS_FILE)
    ok = review_gone and hits_kept and hits_gone
    return Result("clear_cache_scope_keeps_results_safe", ok,
                  f"saved={saved.get('file')} before={before} "
                  f"temp_removed={temp.get('removed')} hits_after_temp={hits_kept} "
                  f"results_removed={results.get('removed')} "
                  f"freed={temp.get('freed_human')}")


def t_format_preview():
    p = store.new_profile(prefix="020124", length=10, charset="0123456789")
    ok = (store.variable_len(p) == 4 and store.space_size(p) == 10 ** 4
          and all(len(c) == 10 and c.startswith("020124")
                  for c in store.sample_cards(p, 3)))
    bad = store.validate(store.new_profile(prefix="020124", length=3))
    return Result("card_format_math_and_validation", ok and
                  "length_not_bigger_than_prefix_and_suffix" in bad,
                  f"samples={store.sample_cards(p, 3)} space={store.space_size(p)} "
                  f"problems={bad}")


SCENARIOS = (
    t_format_preview,
    t_legacy_profile,
    t_calibration,
    t_no_false_hits,
    t_find_card,
    t_ban_is_reported,
    t_rate_limit_slows_down,
    t_dropped_connections,
    t_dead_target_stops,
    t_chap_portal,
    t_get_portal,
    t_diagnose_dead_target,
    t_resume_continues,
    t_cache_clear,
)


def run_all(verbose: bool = True, keep_files: bool = False) -> dict:
    """Run every scenario inside a throw-away data folder.

    The self-test writes real reports and review pages; they must never land in
    the user's kirapass_data.  `keep_files=True` leaves them behind for
    debugging and prints where they are.
    """
    import tempfile
    tmp = tempfile.mkdtemp(prefix="kirapass_selftest_")
    config.set_data_dir(tmp)
    results = []
    t_start = time.time()
    for fn in SCENARIOS:
        t0 = time.time()
        try:
            res = fn()
        except Exception as exc:                          # noqa: BLE001
            import traceback
            res = Result(fn.__name__, False,
                         f"{type(exc).__name__}: {exc} "
                         f"{traceback.format_exc().splitlines()[-1]}")
        res.detail = f"{res.detail} ({time.time() - t0:.1f}s)"
        results.append(res)
        if verbose:
            print(("  " + str(res)).ljust(110), flush=True)
    passed = sum(1 for r in results if r.ok)
    summary = {"ok": passed == len(results), "passed": passed,
               "total": len(results), "seconds": round(time.time() - t_start, 1),
               "results": [{"name": r.name, "ok": r.ok, "detail": r.detail}
                           for r in results]}
    summary["data_dir"] = tmp
    if keep_files:
        if verbose:
            print(f"\n  test files kept in: {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    if verbose:
        print(f"\n  {passed}/{len(results)} passed in {summary['seconds']}s"
              f"  ->  {'ALL GOOD' if summary['ok'] else 'SOMETHING FAILED'}")
    return summary


if __name__ == "__main__":
    print("KiraPass self-test (local mock routers only, no real network used)\n")
    run_all(keep_files="--keep" in sys.argv)
