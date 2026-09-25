"""Decide what a router's answer means - without guessing.

The old version had two ways to judge a reply:

    1. byte-compare after masking  -> failed as soon as the page carried a
       session token / echoed card / timestamp the mask did not know about
    2. "if the length differs from the failure page by more than 40 bytes,
       call it a DIFFERENT page and stop as a suspected match"

Rule 2 is why wrong cards were reported as hits (see kirapass_hits.txt in the
history: eight wrong cards, all "DIFFERENT page len=8575"), and why the tool
could not recognise a *real* success that redirected to the internet.

This module does it the way a network engineer would:

    * send two deliberately-wrong probes and learn WHICH parts of the page
      change on their own (tokens, mac echo, timestamps ...) -> mask them
    * a reply identical to that masked rejection page = REJECTED
    * a reply is only ACCEPTED on positive evidence (redirect out of the
      portal, learned success words, or a real internet check)
    * anything else = UNKNOWN, reported honestly instead of being called a hit
"""

from __future__ import annotations

import difflib
import hashlib
import html
import re

from . import config

TOKEN_RE = re.compile(r"[A-Za-z0-9_@.\-]+|[^\sA-Za-z0-9_]")
SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t\r\n]+")

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
LONGHEX_RE = re.compile(r"\b[0-9a-fA-F]{12,}\b")
LONGNUM_RE = re.compile(r"\b\d{4,}\b")
MAC_RE = re.compile(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b")
# session/nonce looking tokens: 6+ chars of hex/alnum that mix letters and digits
# ("faded" or "0201242548" are NOT masked, "5f30507b" is).
TOKENLIKE_RE = re.compile(r"[0-9A-Za-z]{6,}")
HEXLIKE_RE = re.compile(r"^[0-9a-fA-F]+$")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------
def visible_text(body: str) -> str:
    """What the guest actually sees: no <script>/<style>, no tags."""
    if not body:
        return ""
    text = SCRIPT_RE.sub(" ", body)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return WS_RE.sub(" ", text).strip()


def tokens(text: str) -> list:
    return TOKEN_RE.findall(text or "")


def _nonce_like(tok: str) -> bool:
    if len(tok) < 6:
        return False
    has_digit = any(c.isdigit() for c in tok)
    has_alpha = any(c.isalpha() for c in tok)
    return has_digit and has_alpha


def mask_text(text: str, literals=(), generic: bool = True, patterns=()) -> str:
    """Replace values that legitimately change between two identical requests."""
    out = text or ""
    for lit in literals:
        if lit and len(str(lit)) >= 3:
            out = out.replace(str(lit), "#")
    for pattern in patterns:
        try:
            out = re.sub(pattern, "#", out)
        except re.error:
            continue
    if generic:
        out = TOKENLIKE_RE.sub(lambda m: "#" if _nonce_like(m.group(0))
                               else m.group(0), out)
        out = UUID_RE.sub("#", out)
        out = LONGHEX_RE.sub("#", out)
        out = MAC_RE.sub("#", out)
        out = IP_RE.sub("#", out)
        out = LONGNUM_RE.sub("#", out)
    return out


def struct_tokens(text: str, literals=(), generic: bool = True, patterns=()) -> list:
    """A shape-only view of the page, used when exact compare is impossible."""
    masked = mask_text(text, literals, generic, patterns)
    out = []
    for tok in tokens(masked):
        if tok.isdigit():
            out.append("#")
        else:
            out.append(tok.lower())
    return out


def ratio(a, b) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def diff_words(page: str, reference: str, limit: int = 12) -> dict:
    """Words that appear in `page` but not in `reference`, and vice-versa."""
    def words(t):
        return set(re.findall(r"[A-Za-z\u0600-\u06FF]{3,}", visible_text(t).lower()))

    pw, rw = words(page), words(reference)
    return {
        "new_words": sorted(pw - rw, key=len, reverse=True)[:limit],
        "missing_words": sorted(rw - pw, key=len, reverse=True)[:limit],
    }


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# phrase matching
# ---------------------------------------------------------------------------
# A phrase from the word lists must match a whole word, not just any substring:
# "error" must not fire on "no errors found in the terminal", otherwise every
# status page would look like a rejection.  Short learned phrases (the ones the
# user typed) are still matched loosely - they are his own words.
_PHRASE_CACHE = {}


def _phrase_re(phrase: str):
    pat = _PHRASE_CACHE.get(phrase)
    if pat is None:
        pat = re.compile(r"(?<![\w\-])" + re.escape(phrase) + r"(?![\w\-])",
                         re.I)
        _PHRASE_CACHE[phrase] = pat
    return pat


def find_phrase(haystack: str, phrases) -> str:
    """-> the first whole-word phrase found in `haystack`, else ''."""
    for phrase in phrases or ():
        if not phrase:
            continue
        if _phrase_re(phrase).search(haystack or ""):
            return phrase
    return ""


# ---------------------------------------------------------------------------
# learning the dynamic parts of a page
# ---------------------------------------------------------------------------
def differing_tokens(a: str, b: str, limit: int = 40) -> list:
    """Raw list of the values that change between two same-shape replies.

    Reported to the user ("this page changes by itself in N places"); the
    masking engine below is what actually neutralises them.
    """
    if not a or not b:
        return []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out, seen = [], set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for piece in (a[i1:i2], b[j1:j2]):
            for tok in tokens(piece):
                if len(tok) >= 3 and tok not in seen:
                    seen.add(tok)
                    out.append(tok)
                    if len(out) >= limit:
                        return out
    return out


def learn_patterns(samples, max_patterns: int = 6) -> list:
    """Turn "this span changes" into "a token like this changes".

    A session token of 8 hex characters is different on every reply, so
    remembering the value is useless.  Seeing that the value LOOKED like
    `[0-9a-fA-F]{8}` is what lets us ignore it forever.
    """
    samples = [x for x in samples if x]
    if len(samples) < 2:
        return []
    out, seen = [], set()
    base = samples[0]
    for other in samples[1:]:
        sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            for piece in (base[i1:i2], other[j1:j2]):
                for tok in tokens(piece):
                    if not _nonce_like(tok) or len(tok) > 64:
                        continue
                    if HEXLIKE_RE.match(tok):
                        pattern = r"\b[0-9a-fA-F]{%d}\b" % len(tok)
                    else:
                        pattern = r"\b[0-9A-Za-z]{%d}\b" % len(tok)
                    if pattern not in seen:
                        seen.add(pattern)
                        out.append(pattern)
                        if len(out) >= max_patterns:
                            return out
    return out


def learn_dynamic(samples, rounds: int = 4) -> set:
    """Return the literal values that differ between two same-shape replies.

    Two wrong cards sent in a row normally produce the same page, except for
    the session token, the echoed card, timestamps... Those are exactly the
    values we must ignore, and we learn them instead of listing them by hand.
    """
    literals = set()
    samples = [s for s in samples if s]
    if len(samples) < 2:
        return literals

    for _ in range(rounds):
        masked = [mask_text(s, literals) for s in samples]
        if all(m == masked[0] for m in masked):
            break
        base = masked[0]
        gained = False
        for other in samples[1:]:
            sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                for piece in (base[i1:i2], other[j1:j2]):
                    for tok in tokens(piece):
                        if len(tok) >= 3 and not tok.isdigit() or \
                                (tok.isdigit() and len(tok) >= 5):
                            if tok not in literals:
                                literals.add(tok)
                                gained = True
        if not gained:
            break
    return literals


# ---------------------------------------------------------------------------
# verdicts
# ---------------------------------------------------------------------------
class Verdict:
    """One answer about one reply."""

    __slots__ = ("code", "confidence", "reason", "data", "evidence")

    def __init__(self, code, reason, confidence=0.0, data=None, evidence=None):
        self.code = code
        self.reason = reason
        self.confidence = confidence
        self.data = data or {}
        self.evidence = evidence or {}

    @property
    def is_hit(self) -> bool:
        return self.code.startswith("ACCEPTED")

    @property
    def is_final(self) -> bool:
        """High-confidence hits stop the run; UNKNOWN never does."""
        return self.code == "ACCEPTED_VERIFIED" or (
            self.code == "ACCEPTED" and self.confidence >= 0.85)

    def as_dict(self) -> dict:
        return {"code": self.code, "reason": self.reason,
                "confidence": round(self.confidence, 2),
                "data": self.data, "evidence": self.evidence}


class Fingerprinter:
    """Knows what the *rejection* page looks like, and how to compare."""

    def __init__(self):
        self.literals = set()
        self.patterns = []
        self.exact = False
        self.reject_masked_sha = ""
        self.reject_tokens = []
        self.reject_status = 0
        self.reject_len = 0
        self.reject_text = ""
        self.login_text = ""
        self.samples = 0
        self.note = ""
        self.dynamic_count = 0      # values that change on their own

    # -- learning ---------------------------------------------------------
    @classmethod
    def learn(cls, reject_replies, login_reply=None) -> "Fingerprinter":
        """`reject_replies` = list of Replies to wrong-but-well-formed cards."""
        fp = cls()
        # a probe that failed with a network error arrives as None - it is not
        # a page we can learn from, and it must not crash the run either
        replies = [r for r in (reject_replies or []) if r is not None]
        bodies = [r.text for r in replies]
        if login_reply is not None:
            fp.login_text = login_reply.text[:40000]
        if not bodies:
            fp.note = "no rejection baseline"
            return fp

        fp.samples = len(bodies)
        fp.reject_status = replies[0].status
        fp.reject_len = len(bodies[0])
        fp.reject_text = bodies[0][:40000]
        fp.literals = learn_dynamic(bodies)
        fp.patterns = learn_patterns(bodies)
        fp.dynamic_count = len(differing_tokens(bodies[0], bodies[1])) \
            if len(bodies) > 1 else 0

        masked = [mask_text(b, fp.literals, patterns=fp.patterns)
                  for b in bodies]
        fp.exact = all(m == masked[0] for m in masked)
        if fp.exact:
            fp.reject_masked_sha = sha(masked[0])
            fp.note = "exact comparison ready"
        else:
            fp.reject_tokens = struct_tokens(bodies[0], fp.literals,
                                             patterns=fp.patterns)
            fp.note = "page changes on its own - comparing by shape"
        return fp

    # -- comparison -------------------------------------------------------
    def same_as_reject(self, resp, extra_literals=()) -> tuple:
        """-> (is_rejected, how, similarity)

        `extra_literals` are the values we just sent (card, password, dst):
        a portal that echoes them back must not look like a different page.
        """
        body = resp.text or ""
        literals = tuple(self.literals) + tuple(extra_literals or ())
        if not body and not self.reject_text:
            return True, "empty", 1.0

        masked = mask_text(body, literals, patterns=self.patterns)
        if self.exact:
            if sha(masked) == self.reject_masked_sha:
                return True, "exact", 1.0
        if self.reject_tokens:
            sim = ratio(struct_tokens(body, literals, patterns=self.patterns),
                        self.reject_tokens)
            if sim >= 0.995:
                return True, "shape", sim
            return False, "shape", sim

        # no exact baseline: fall back to status + similarity of the shape
        sim = ratio(struct_tokens(body, literals, patterns=self.patterns),
                    struct_tokens(self.reject_text, literals,
                                  patterns=self.patterns))
        if resp.status == self.reject_status and sim >= 0.97:
            return True, "similar", sim
        return False, "similar", sim


class Judge:
    """Turns one reply into one Verdict with a reason a human can read."""

    def __init__(self, fingerprint: Fingerprinter, login_url: str,
                 success_words=(), success_url_contains="",
                 exit_host_markers=config.EXIT_HOST_MARKERS):
        self.fp = fingerprint
        self.login_url = login_url
        self.success_words = [w.lower() for w in (success_words or []) if w]
        self.success_url_contains = (success_url_contains or "").lower()
        self.exit_markers = tuple(exit_host_markers)
        self.portal_host = _host(login_url)

        from urllib.parse import urlsplit
        self.portal_host = urlsplit(login_url).hostname or ""

        reject_text = (fingerprint.reject_text or "").lower()
        login_text = (fingerprint.login_text or "").lower()

        # Words only count when they are NOT already on the rejection/login
        # page - otherwise every page would look like a failure.
        self.reject_phrases = [w for w in config.REJECT_WORDS
                               if w in reject_text or w not in login_text]
        self.accept_phrases = [w for w in config.ACCEPT_WORDS
                               if w not in reject_text and w not in login_text]

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _has_any(haystack: str, needles) -> str:
        """Loose (substring) match - for words the user gave us himself."""
        for n in needles:
            if n and n in haystack:
                return n
        return ""

    @staticmethod
    def _has_phrase(haystack: str, needles) -> str:
        """Whole-word match - for the built-in reject/accept/ban phrases."""
        return find_phrase(haystack, needles)

    # -- the decision ----------------------------------------------------
    def classify(self, resp, submitted=None) -> Verdict:
        body = resp.text or ""
        text = visible_text(body)
        low = text.lower()
        raw_low = body.lower()
        loc = resp.location
        sub = [str(s) for s in (submitted or []) if s]

        # --- the router is blocking us (checked FIRST: if the baseline was
        #     learned while already blocked, a ban page could otherwise look
        #     like an ordinary rejection) ----------------------------------
        ban = self._has_phrase(raw_low, config.BAN_WORDS) or \
            self._has_phrase(low, config.BAN_WORDS)
        if ban or resp.status in (403, 429, 503):
            if resp.status == 429 or (ban and ("rate limit" in ban
                                               or "slow down" in ban)):
                return Verdict("RATE_LIMITED", "ban_page" if ban else "http_429",
                               0.9, data={"word": ban, "status": resp.status},
                               evidence=resp.as_dict())
            if resp.status == 503 and not ban:
                # "service unavailable" is a router/RADIUS that is drowning -
                # telling the user he is blocked would send him to restart the
                # router for nothing.  It is handled like a rate limit: slow
                # down, and stop if it keeps happening.
                return Verdict("RATE_LIMITED", "http_503", 0.9,
                               data={"status": resp.status},
                               evidence=resp.as_dict())
            return Verdict("BANNED", "ban_page" if ban else f"http_{resp.status}",
                           0.9, data={"word": ban, "status": resp.status},
                           evidence=resp.as_dict())

        rejected, how, sim = self.fp.same_as_reject(resp, extra_literals=sub)
        if rejected:
            seen_ok = [w for w in self.success_words if w in low or w in raw_low]
            if seen_ok and how != "exact":
                # the page matches the rejection shape, but words we learned
                # from a working card are present -> let a human look at it
                return Verdict("UNKNOWN", "looks_rejected_but_success_words_found",
                               0.0, data={"words": seen_ok[:6]},
                               evidence=resp.as_dict())
            return Verdict("REJECTED", f"same_as_rejection_page_{how}", 1.0,
                           data={"similarity": round(sim, 3)},
                           evidence=resp.as_dict())

        # --- a captcha / challenge was added ---------------------------
        if any(w in raw_low for w in ("captcha", "g-recaptcha", "hcaptcha")):
            return Verdict("CHALLENGE", "captcha_present", 0.6,
                           evidence=resp.as_dict())

        # --- positive proof: the portal let us OUT ---------------------
        if resp.is_redirect():
            host = _host(loc)
            if host and host != self.portal_host:
                marker = self._has_any(loc.lower(), self.exit_markers)
                if not marker and self._has_any(loc.lower(),
                                                config.PORTAL_URL_WORDS):
                    # another page of the same portal - not an exit, and not
                    # something we may call a working card either
                    return Verdict("UNKNOWN", "redirect_to_another_portal_page",
                                   0.0, data={"location": loc[:200]},
                                   evidence=resp.as_dict())
                confident = 0.95 if marker else 0.85
                return Verdict("ACCEPTED", "redirect_out_of_portal", confident,
                               data={"location": loc[:200]},
                               evidence=resp.as_dict())
            if self.success_url_contains and self.success_url_contains in loc.lower():
                return Verdict("ACCEPTED", "success_url_contains", 0.9,
                               data={"location": loc[:200]},
                               evidence=resp.as_dict())

        # --- positive proof: learned success words ---------------------
        seen = [w for w in self.success_words if w in low or w in raw_low]
        if len(seen) >= 1 and not self._has_phrase(low, self.reject_phrases):
            return Verdict("ACCEPTED", "learned_success_words",
                           min(0.9, 0.6 + 0.1 * len(seen)),
                           data={"words": seen[:6]}, evidence=resp.as_dict())

        if self.success_url_contains and self.success_url_contains in resp.url.lower():
            return Verdict("ACCEPTED", "success_url_contains", 0.9,
                           data={"url": resp.url[:200]}, evidence=resp.as_dict())

        # --- positive words that are unique to a *good* page -----------
        accept_hit = self._has_phrase(low, self.accept_phrases)
        reject_hit = self._has_phrase(low, self.reject_phrases)
        if accept_hit and not reject_hit:
            return Verdict("ACCEPTED", "welcome_words", 0.7,
                           data={"word": accept_hit}, evidence=resp.as_dict())

        # --- not the rejection page, not a proven success --------------
        diff = diff_words(body, self.fp.reject_text)
        if reject_hit:
            # dynamic rejection page that we cannot compare exactly
            return Verdict("REJECTED", "rejection_wording", 0.75,
                           data={"word": reject_hit}, evidence=resp.as_dict())

        return Verdict("UNKNOWN", "reply_differs_not_proven", 0.0,
                       data={"diff": diff, "similarity": round(sim, 3),
                             "status": resp.status, "length": resp.length},
                       evidence=resp.as_dict())


def _host(url: str) -> str:
    from urllib.parse import urlsplit
    try:
        return (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""
