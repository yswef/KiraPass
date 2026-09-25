"""KiraPass test suite.

    python3 -m unittest discover -s tests -v      (all of it)
    python3 KiraPass.py --selftest                (the scenario part, readable)

The scenarios are the same ones the --selftest flag prints: they run against
local mock routers, so no real network is touched.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kirapass import (config, engine, fingerprint, httpclient,  # noqa: E402
                     portals, selftest, store)
from kirapass.mockportal import MockPortal                                     # noqa: E402

# Test data must never land in the real kirapass_data folder: the scenarios
# write reports, review pages and hits.  Everything goes to a temp dir that is
# removed when the suite finishes.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="kirapass_tests_")
config.set_data_dir(_TEST_DATA_DIR)


def tearDownModule():                                  # noqa: N802
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


# ---------------------------------------------------------------------------
# end-to-end scenarios against the mock routers
# ---------------------------------------------------------------------------
def _make_case(fn):
    def test(self):
        result = fn()
        self.assertTrue(result.ok, f"{result.name}: {result.detail}")
    return test


class ScenarioTests(unittest.TestCase):
    maxDiff = None


for _fn in selftest.SCENARIOS:
    setattr(ScenarioTests, "test_" + _fn.__name__[2:], _make_case(_fn))


# ---------------------------------------------------------------------------
# units
# ---------------------------------------------------------------------------
class MaskingTests(unittest.TestCase):
    def test_dynamic_tokens_are_detected_and_masked(self):
        a = "<html>session abc123def456 card 0201242548</html>"
        b = "<html>session zzz999zzz888 card 0201242549</html>"
        # the tool must notice the page changes on its own ...
        self.assertTrue(fingerprint.differing_tokens(a, b))
        # ... and the masked forms must compare equal whatever the values are
        literals = fingerprint.learn_dynamic([a, b])
        self.assertEqual(fingerprint.mask_text(a, literals),
                         fingerprint.mask_text(b, literals))

    def test_submitted_values_do_not_break_comparison(self):
        page = lambda card: f"<html><body>card={card} error: invalid</body></html>"
        fp = fingerprint.Fingerprinter.learn([
            _FakeReply(page("0201242548")), _FakeReply(page("0201242577"))])
        judge = fingerprint.Judge(fp, "http://portal/login")
        v = judge.classify(_FakeReply(page("0201249999")),
                           submitted=["0201249999", ""])
        self.assertEqual(v.code, "REJECTED", v.as_dict())

    def test_ban_page_is_never_reported_as_rejected(self):
        ban = "<html><title>Blocked</title><body>You are blocked</body></html>"
        fp = fingerprint.Fingerprinter.learn([_FakeReply(ban), _FakeReply(ban)])
        judge = fingerprint.Judge(fp, "http://portal/login")
        v = judge.classify(_FakeReply(ban, status=403))
        self.assertIn(v.code, ("BANNED", "RATE_LIMITED"), v.as_dict())

    def test_a_redirect_inside_the_portal_is_not_a_hit(self):
        """Some routers bounce you between their own pages - every bounce
        used to be reported as "the router let us out"."""
        fp = fingerprint.Fingerprinter.learn(
            [_FakeReply("<html>wrong card</html>"), _FakeReply("<html>wrong card</html>")])
        judge = fingerprint.Judge(fp, "http://10.5.50.1/login")
        v = judge.classify(_FakeReply("", status=302, headers={
            "location": "http://10.5.50.2/portal/status?dst=x"}))
        self.assertEqual(v.code, "UNKNOWN", v.as_dict())
        self.assertEqual(v.reason, "redirect_to_another_portal_page")

    def test_different_page_is_not_a_hit(self):
        fp = fingerprint.Fingerprinter.learn([
            _FakeReply("<html>wrong card</html>"), _FakeReply("<html>wrong card</html>")])
        judge = fingerprint.Judge(fp, "http://portal/login")
        v = judge.classify(_FakeReply("<html>something totally else happened</html>"))
        self.assertEqual(v.code, "UNKNOWN")
        self.assertFalse(v.is_hit)

    def test_redirect_out_of_portal_is_a_hit(self):
        fp = fingerprint.Fingerprinter.learn([
            _FakeReply("<html>wrong card</html>"), _FakeReply("<html>wrong card</html>")])
        judge = fingerprint.Judge(fp, "http://portal/login")
        v = judge.classify(_FakeReply("", status=302,
                                      headers={"location":
                                               "http://connectivitycheck.gstatic.com/generate_204"}))
        self.assertEqual(v.code, "ACCEPTED")
        self.assertTrue(v.is_hit)


class PhraseTests(unittest.TestCase):
    def test_builtin_phrases_match_whole_words_only(self):
        # "error" inside "errors" must not make a page look rejected
        self.assertEqual(fingerprint.find_phrase("no errors on this page",
                                                 ["error"]), "")
        self.assertEqual(fingerprint.find_phrase("an error occurred", ["error"]),
                         "error")
        self.assertEqual(fingerprint.find_phrase("You are blocked",
                                                 ["you are blocked"]),
                         "you are blocked")


class FingerprintTests(unittest.TestCase):
    def test_missing_probe_replies_do_not_crash_the_baseline(self):
        fp = fingerprint.Fingerprinter.learn(
            [None, _FakeReply("<html>wrong card</html>")])
        self.assertEqual(fp.samples, 1)
        self.assertEqual(fp.reject_status, 200)


class PortalFormTests(unittest.TestCase):
    def test_the_login_form_wins_over_other_forms(self):
        html = """<html>
        <form action="/search" method="get">
          <input type="text" name="q"><input type="submit" name="go" value="Go">
        </form>
        <form name="login" action="/login" method="post">
          <input type="hidden" name="dst" value="http://x/">
          <input type="text" name="username" value="">
          <input type="password" name="password" value="">
          <input type="submit" name="connect" value="Connect">
        </form></html>"""
        form = portals.parse_form(html, "http://10.5.50.1/")
        self.assertEqual(form.action, "http://10.5.50.1/login")
        self.assertTrue(form.is_post)
        self.assertEqual(form.user_field, "username")
        self.assertEqual(form.pass_field, "password")
        # a named submit button is not data we should replay
        self.assertNotIn("connect", form.extra_fields)
        self.assertNotIn("go", form.extra_fields)

    def test_buttons_are_never_sent_as_fixed_fields(self):
        html = """<html><form action="/login" method="post">
          <input type="text" name="username">
          <input type="password" name="password">
          <input type="submit" name="send" value="ok">
          <input type="button" name="cancel" value="no">
        </form></html>"""
        form = portals.parse_form(html, "http://10.5.50.1/login")
        self.assertEqual(form.extra_fields, {})


class CalibrationTests(unittest.TestCase):
    def test_a_card_space_that_cannot_exist_is_refused(self):
        """A profile with no room to guess in must fail with a reason - it
        used to "calibrate" against an empty baseline and then call every
        reply 'not rejected'."""
        from kirapass import engine
        p = store.new_profile(login_url="http://127.0.0.1:1/login",
                              prefix="02", length=6, charset="0")
        cal = engine.calibrate(p)
        self.assertFalse(cal.ok)
        self.assertTrue(cal.error, "calibration must say why it refused")
        self.assertFalse([s for s in cal.steps if s["id"] == "profile_valid"
                          and s["ok"]])

    def test_a_dead_target_is_reported_as_a_network_problem(self):
        from kirapass import engine
        p = store.new_profile(login_url="http://127.0.0.1:1/login",
                              prefix="02", length=6, charset="0123456789")
        cal = engine.calibrate(p)
        step = next((s for s in cal.steps if s["id"] == "reach_login_page"), None)
        self.assertFalse(cal.ok)
        self.assertTrue(step and step["reason"].startswith("net_"), cal.steps)


class CacheTests(unittest.TestCase):
    def test_bytecode_folders_are_counted_once(self):
        st = store.Store()
        st.clear_cache("temp")
        tmp = tempfile.mkdtemp(prefix="kirapass_base_")
        try:
            folder = os.path.join(tmp, "__pycache__")
            os.makedirs(folder)
            with open(os.path.join(folder, "x.pyc"), "wb") as fh:
                fh.write(b"0" * 64)
            old = config.BASE_DIR
            config.BASE_DIR = tmp
            try:
                info = st.clear_cache("temp")
            finally:
                config.BASE_DIR = old
            self.assertEqual(info["freed_bytes"], 64, info)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RedirectPortalTests(unittest.TestCase):
    """Routers that answer a WRONG card with a redirect, not with a page.

    Both replies are then empty pages, and the old comparison called them
    "identical" - which hid every real hit behind "same as the rejection page".
    """

    @staticmethod
    def _redirect(location):
        return _FakeReply("", status=302, headers={"location": location})

    def _learn(self):
        wrong_a = "http://10.5.50.1/login?error=1&mac=AA:BB:CC:DD:EE:FF"
        wrong_b = "http://10.5.50.1/login?error=1&mac=11:22:33:44:55:66"
        return fingerprint.Fingerprinter.learn(
            [self._redirect(wrong_a), self._redirect(wrong_b)],
            login_reply=_FakeReply("<html><form>login</form></html>"))

    def test_a_card_that_goes_somewhere_else_is_a_hit(self):
        fp = self._learn()
        judge = fingerprint.Judge(fp, "http://10.5.50.1/login")
        v = judge.classify(self._redirect("http://10.5.50.1/status?sid=7"),
                           ["0301", ""])
        self.assertEqual(v.code, "ACCEPTED", v.as_dict())
        self.assertEqual(v.reason, "redirect_differs_from_rejection")

    def test_the_same_redirect_as_a_wrong_card_is_still_rejected(self):
        fp = self._learn()
        judge = fingerprint.Judge(fp, "http://10.5.50.1/login")
        v = judge.classify(
            self._redirect("http://10.5.50.1/login?error=1&mac=99:88:77:66:55:44"),
            ["0302", ""])
        self.assertEqual(v.code, "REJECTED", v.as_dict())


class BlockRecoveryTests(unittest.TestCase):
    """A router that locks a device after N failed logins.

    The learning cards are failed logins too, so three of them can fill the
    counter on their own - the tool must notice that it caused the lockout,
    wait for it to clear, and try again with fewer cards.
    """

    def test_the_lockout_is_waited_out_and_the_run_starts(self):
        from unittest import mock
        # two failures are enough for this router, and three learning cards
        # are three failures - the third one gets the block page
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty",
                        ban_after=2, ban_seconds=2) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020", length=9,
                                      portal_info=info)
            # three learning cards -> the router's counter is full before any
            # real attempt was made
            cal = engine.calibrate(p, checks=selftest.mock_checks(portal))
            self.assertFalse(cal.ok, cal.as_dict())
            self.assertEqual(cal.error, "blocked_already")
            self.assertTrue(
                any(s["reason"] == "blocked_by_our_probes" for s in cal.steps),
                cal.steps)
            self.assertTrue(engine.block_caused_by_probes(cal))

            # and the engine waits the lockout out, then relearns with two
            with mock.patch.object(config, "BLOCK_WAIT_SECONDS", 3), \
                    mock.patch.object(config, "CALIBRATION_PROBES_RETRY", 2):
                eng = engine.Engine(store.Store(), persist=False,
                                  checks=selftest.mock_checks(portal))
                eng.start(p, attempts=20, threads=2, delay_ms=0)
                deadline = time.time() + 60
                while time.time() < deadline and eng.state not in ("running", "done"):
                    time.sleep(0.1)
                eng.stop("test_done")
                while time.time() < deadline and eng.state != "done":
                    time.sleep(0.1)
            self.assertNotEqual(eng.stop_reason, "calibration_failed",
                                eng.calibration)
            self.assertEqual(eng.calibration.get("ok"), True)
            baseline = [s for s in eng.calibration.get("steps", [])
                        if s["id"] == "rejection_baseline"]
            self.assertTrue(baseline, eng.calibration)
            self.assertLessEqual(baseline[0]["detail"]["samples"], 2)

    def test_a_block_that_was_already_there_is_not_our_fault(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty",
                        ban_after=1) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020", length=9,
                                      portal_info=info)
            # one failure is enough here, so the very first learning card is
            # already answered with the block page
            cal = engine.calibrate(p, checks=selftest.mock_checks(portal))
            self.assertFalse(cal.ok)
            # the login page was clean, so this is still a lockout we caused
            self.assertTrue(engine.block_caused_by_probes(cal))
            # ... but with the block page shown on the login page itself it is
            # reported as older than us - and no card is wasted on it
            from unittest import mock
            with mock.patch.object(engine, "new_session") as ns:
                sess = ns.return_value
                sess.get.return_value = _FakeReply(
                    "<html>you are blocked</html>", status=403)
                cal2 = engine.calibrate(p, checks=selftest.mock_checks(portal))
                self.assertEqual(sess.post.call_count, 0)
                self.assertEqual(sess.get.call_count, 1)
            self.assertFalse(engine.block_caused_by_probes(cal2))
            self.assertTrue(any(s["reason"] == "blocked_before_probes"
                                for s in cal2.steps), cal2.steps)


class BlockFalsePositiveTests(unittest.TestCase):
    """A page that MENTIONS blocking is not the same as a block page.

    Real login pages warn ("abuse is banned", "slow down") while still
    offering the form.  The word alone used to stop every run before it
    started - this is what "still blocked" reports were made of.
    """

    LOGIN_PAGE = ("<html><body><form method='post' action='/login'>"
                  "<input name='username'><input name='password' type='password'>"
                  "<input type='submit'></form>"
                  "<p>note: abusing this network is banned</p></body></html>")
    BLOCK_PAGE = ("<html><body><h1>you are blocked</h1>"
                  "<p>too many attempts, try later</p></body></html>")

    @staticmethod
    def _session_with(page, status=200):
        from unittest import mock
        sess = mock.MagicMock()
        sess.get.return_value = _FakeReply(page, status=status)
        sess.request.return_value = _FakeReply(
            "<html>invalid username or password</html>", status=200)
        return mock.patch.object(engine, "new_session", return_value=sess), sess

    def _profile(self):
        p = selftest.make_profile("http://10.5.50.1/login", prefix="030124",
                                  length=9, portal_info=None)
        p["user_field"], p["pass_field"] = "username", "password"
        p["method"] = "post"
        return p

    def test_a_login_page_that_warns_about_blocking_is_still_a_login_page(self):
        patcher, sess = self._session_with(self.LOGIN_PAGE)
        with patcher:
            cal = engine.calibrate(self._profile(), checks=())
        self.assertTrue(cal.ok, cal.as_dict())
        reason = [s["reason"] for s in cal.steps
                  if s["id"] == "reach_login_page"][0]
        self.assertEqual(reason, "http_ok_word_ignored")
        self.assertFalse(engine.block_caused_by_probes(cal))

    def test_a_real_block_page_stops_before_any_card_is_wasted(self):
        patcher, sess = self._session_with(self.BLOCK_PAGE)
        with patcher:
            cal = engine.calibrate(self._profile(), checks=())
        self.assertFalse(cal.ok)
        self.assertEqual(cal.error, "blocked_already")
        self.assertEqual(sess.request.call_count, 0)   # no failed login added
        self.assertTrue(any(s["reason"] == "blocked_before_probes"
                            for s in cal.steps), cal.steps)
        self.assertFalse(engine.block_caused_by_probes(cal))

    def test_a_403_login_page_is_a_block_even_with_a_form(self):
        patcher, sess = self._session_with(self.LOGIN_PAGE, status=403)
        with patcher:
            cal = engine.calibrate(self._profile(), checks=())
        self.assertEqual(cal.error, "blocked_already")
        self.assertEqual(sess.request.call_count, 0)


class InternetWatchdogTests(unittest.TestCase):
    """The nastiest real case: the router logs the guest in and still answers
    with the rejection page, so no verdict ever looks like a hit.  The only
    honest signal left is the internet itself.
    """

    def test_the_watchdog_names_the_cards_that_opened_the_internet(self):
        from unittest import mock
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty",
                        hide_success=True) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="0201240", length=9,
                                      portal_info=info)
            # walk it in order, starting on the working card - deterministic
            # (decode_card fills the free slots least-significant first, so
            # index 24 is the card ...042)
            p["walk_a"], p["walk_b"], p["space_pos"] = 1, 0, 24
            with mock.patch.object(config, "WATCH_EVERY_SECONDS", 0.3):
                eng = engine.Engine(store.Store(), persist=False,
                                    checks=selftest.mock_checks(portal))
                eng.start(p, attempts=100, threads=1, delay_ms=200,
                          verify_after=True)
                deadline = time.time() + 60
                while time.time() < deadline and eng.state != "done":
                    time.sleep(0.1)
            self.assertEqual(eng.stop_reason, "internet_opened", eng.calibration)
            suspects = [s["card"] for s in
                        (eng._internet_opened or {}).get("suspects", [])]
            self.assertIn("020124042", suspects, suspects)
            # and the judge really did miss it - the watchdog is why we know
            self.assertEqual(eng.hits, [])
            self.assertEqual(portal.state.hidden_successes, 1)

    def test_cards_the_router_refused_to_judge_are_not_counted_as_covered(self):
        """A block page is not an answer: that card is still untested."""
        from unittest import mock
        # bans start after five failures, so the learning is clean and the
        # lockout hits in the middle of the run
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty",
                        ban_after=5) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            with mock.patch.object(config, "BLOCK_WAIT_SECONDS", 0):
                eng = engine.Engine(store.Store(), persist=False,
                                    checks=selftest.mock_checks(portal))
                eng.start(p, attempts=20, threads=2, delay_ms=0,
                          verify_after=False)
                deadline = time.time() + 60
                while time.time() < deadline and eng.state != "done":
                    time.sleep(0.1)
            st = eng.status()
            banned = st["counters"].get("BANNED", 0)
            tried = sum(st["counters"].values())
            self.assertGreater(banned, 0, st["counters"])
            covered = st["progress"]["covered"]
            self.assertEqual(covered, tried - banned,
                             "a banned card is not a tested card: %s / %s"
                             % (st["progress"], st["counters"]))


class LockoutProbeTests(unittest.TestCase):
    """Measure the protection instead of fighting it: how many failures does
    this router forgive, and how long does the lockout last?
    """

    def test_it_measures_the_limit_and_the_recovery(self):
        # blocks after 3 failures, clears after 2 seconds
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty",
                        ban_after=3, ban_seconds=2) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            got = engine.probe_lockout(p, checks=selftest.mock_checks(portal),
                                       max_failures=10, wait_limit=30,
                                       step=1.0, pace=0.0)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["ban_after"], 3, got)
        self.assertIsNotNone(got["clears_after"], got)
        self.assertLessEqual(got["clears_after"], 10, got)
        # 3 failures forgiven every couple of seconds -> about a second each
        self.assertGreaterEqual(got["safe_delay_ms"], 1000, got)

    def test_a_router_that_never_forgives_says_so(self):
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty",
                        ban_after=2) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            got = engine.probe_lockout(p, checks=selftest.mock_checks(portal),
                                       max_failures=6, wait_limit=4,
                                       step=1.0, pace=0.0)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["ban_after"], 2, got)
        self.assertIsNone(got["clears_after"], got)   # never cleared
        self.assertIsNone(got["safe_delay_ms"], got)  # so: no safe pace

    def test_a_router_that_never_blocks_is_reported_as_such(self):
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty") as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            got = engine.probe_lockout(p, checks=selftest.mock_checks(portal),
                                       max_failures=6, wait_limit=2,
                                       step=1.0, pace=0.0)
        self.assertTrue(got["ok"], got)
        self.assertIsNone(got["ban_after"], got)
        self.assertEqual(got["tried"], 6, got)


class KnownCardTests(unittest.TestCase):
    """The "I know a card that works" field: it must either prove the card or
    say exactly why it could not.
    """

    @staticmethod
    def _shape_step(cal):
        for s in cal.steps:
            if s["id"] == "shape_tuned":
                return s
        return None

    def test_a_card_that_does_not_fit_the_format_is_named(self):
        p = {"prefix": "0201", "length": 9, "suffix": "", "charset": "0123456789"}
        self.assertEqual(engine.known_card_problem(p, "020124042"), {})
        got = engine.known_card_problem(p, "293466475")   # right length,
        self.assertEqual(got["reason"], "prefix_mismatch")   # wrong prefix
        got = engine.known_card_problem(
            {"prefix": "", "length": 9, "suffix": "", "charset": "0123456789"},
            "2934664754")
        self.assertEqual(got["reason"], "length_mismatch")
        got = engine.known_card_problem(
            {"prefix": "", "length": 10, "suffix": "", "charset": "abc"},
            "2934664754")
        self.assertEqual(got["reason"], "charset_mismatch")

    def test_it_finds_the_right_request_shape_and_says_so(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="same") as portal:
            info = selftest.scan(portal.url)
            # the profile says "no password" - the router wants the card itself
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info, pass_mode="empty")
            cal = engine.calibrate(p, known_card="020124042",
                                   checks=selftest.mock_checks(portal))
        self.assertTrue(cal.ok, cal.as_dict())
        step = self._shape_step(cal)
        self.assertIsNotNone(step, cal.steps)
        self.assertTrue(step["ok"], step)
        self.assertEqual(step["reason"], "known_card_works")
        self.assertEqual(cal.profile["pass_mode"], "same")

    def test_a_card_the_router_refuses_reports_what_came_back(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty") as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info, pass_mode="empty")
            cal = engine.calibrate(p, known_card="020124999",
                                   checks=selftest.mock_checks(portal))
        self.assertTrue(cal.ok, cal.as_dict())     # the run can still go on
        step = self._shape_step(cal)
        self.assertIsNotNone(step, cal.steps)
        self.assertFalse(step["ok"], step)
        self.assertEqual(step["reason"], "known_card_not_proven")
        trials = step["detail"]["trials"]
        self.assertTrue(trials, step["detail"])
        self.assertTrue(all(t["code"] == "REJECTED" for t in trials), trials)
        # and the router's own answer is in there, not just "it failed"
        self.assertTrue(any(t.get("word") for t in trials), trials)


class _FakeReply:
    def __init__(self, text, status=200, headers=None):
        self._text = text
        self.status = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.url = "http://portal/login"
        self.elapsed_ms = 5
        self.history = []

    @property
    def text(self):
        return self._text

    @property
    def length(self):
        return len(self._text)

    def header(self, name, default=""):
        return self.headers.get(name.lower(), default)

    @property
    def location(self):
        return self.header("location")

    def is_redirect(self):
        return self.status in (301, 302, 303, 307, 308) and bool(self.location)

    def as_dict(self):
        return {"status": self.status, "length": self.length, "url": self.url}


class StoreTests(unittest.TestCase):
    def test_migrates_all_old_shapes(self):
        samples = [
            {"name": "a", "login_url": "http://x/login", "method": "2",
             "network_type": "1", "var_len": 4, "prefix": "020124",
             "extras": True, "pass_mode": "empty"},
            {"name": "b", "login_url": "http://x/login", "network_type": "2",
             "charset": "0123456789", "var_len": 6, "prefix": "", "suffix": "",
             "walk": {"pos": 120}, "fixed_fields": {"dst": "http://a/b"}},
            {"name": "c", "login_url": "http://x/login", "network_type": "3",
             "u_charset": "0123456789", "u_len": 4, "u_prefix": "u",
             "p_charset": "0123456789", "p_len": 4, "p_prefix": ""},
        ]
        for raw in samples:
            prof = store.migrate(raw)
            self.assertEqual(store.variable_len(prof) > 0, True, raw["name"])
            self.assertNotIn("length_not_bigger_than_prefix_and_suffix",
                             store.validate(prof))
        prof_b = store.migrate(samples[1])
        self.assertEqual(prof_b["space_pos"], 120)

    def test_validation_catches_bad_format(self):
        p = store.new_profile(prefix="020124", length=3, charset="0123456789")
        self.assertIn("length_not_bigger_than_prefix_and_suffix", store.validate(p))

    def test_space_and_samples(self):
        p = store.new_profile(prefix="020124", length=10, charset="0123456789")
        self.assertEqual(store.space_size(p), 10 ** 4)
        for card in store.sample_cards(p, 3):
            self.assertEqual(len(card), 10)
            self.assertTrue(card.startswith("020124"))

    def test_walk_visits_everything_once(self):
        p = store.new_profile(prefix="", length=3, charset="0123456789",
                              walk_a=7, walk_b=3)
        seen = {store.card_at_walk_pos(p, i) for i in range(store.space_size(p))}
        self.assertEqual(len(seen), 1000)

    def test_review_round_trip(self):
        st = store.Store()
        saved = st.save_review(1, "0201242548",
                               {"code": "UNKNOWN", "reason": "x", "data": {}},
                               "<html>hello</html>")
        self.assertTrue(saved.get("file"))
        self.assertIn("hello", st.read_review(saved["file"]))
        st.clear_cache("temp")


class HttpTests(unittest.TestCase):
    def test_connect_timeout_is_not_a_read_timeout(self):
        """Opening the socket and reading the answer are two different
        failures - "the router never answered the connection" must not be
        reported as "the router answered slowly"."""
        import socket

        class _DeadConn:
            sock = None
            timeout = 1.0

            def connect(self):
                raise socket.timeout("timed out")

        s = httpclient.Session(allow_redirects=False)
        s._conn, s._key = _DeadConn(), ("http", "127.0.0.1", 1)
        try:
            with self.assertRaises(Exception) as ctx:
                s._send_once("GET", "http://127.0.0.1:1/login", None, None, {},
                             (1.0, 1.0))
        finally:
            s.close()
        self.assertEqual(getattr(ctx.exception, "kind", ""), "connect_timeout",
                         repr(ctx.exception))

    def test_cookies_and_redirects(self):
        with MockPortal(valid_cards={"0242"}, pass_mode="empty") as portal:
            s = httpclient.Session(allow_redirects=True)
            r = s.get(portal.url)
            self.assertEqual(r.status, 200)
            r2 = s.get(portal.url)               # keep-alive reuse
            self.assertEqual(r2.status, 200)
            self.assertGreaterEqual(s.stats["requests"], 2)
            s.close()

    def test_http_error_kinds(self):
        s = httpclient.Session()
        with self.assertRaises(Exception) as ctx:
            s.get("http://127.0.0.1:9/nothing", timeout=(1.0, 1.0))
        err = ctx.exception
        self.assertIn(getattr(err, "kind", ""), ("refused", "reset", "stale",
                                                 "connect_timeout", "read_timeout"))
        s.close()


class PortalParsingTests(unittest.TestCase):
    def test_mikrotik_chap_and_fields(self):
        html = """<html><script src="md5.js"></script>
        <script>document.login.password.value = hexMD5('abc123' +
            document.login.password.value + 'def456');</script>
        <form name="login" action="/login?mac=AA:BB:CC:DD:EE:FF" method="post">
        <input type="hidden" name="dst" value="http://www.msftconnecttest.com/redirect">
        <input type="hidden" name="popup" value="true">
        <input type="text" name="username" value="">
        <input type="password" name="password" value="">
        </form></html>"""
        form = portals.parse_form(html, "http://10.5.50.1/login")
        self.assertTrue(form.is_post)
        self.assertEqual(form.user_field, "username")
        self.assertEqual(form.pass_field, "password")
        self.assertEqual(form.dst_value, "http://www.msftconnecttest.com/redirect")
        self.assertIsNotNone(form.chap)
        self.assertEqual(form.chap["id"], "abc123")
        self.assertEqual(form.chap["challenge"], "def456")


if __name__ == "__main__":
    unittest.main(verbosity=2)
