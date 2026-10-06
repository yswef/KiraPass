"""KiraPass test suite.

    python3 -m unittest discover -s tests -v      (all of it)
    python3 KiraPass.py --selftest                (the scenario part, readable)

The scenarios are the same ones the --selftest flag prints: they run against
local mock routers, so no real network is touched.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kirapass import (capture, config, engine, fingerprint, httpclient,  # noqa: E402
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
class UIIntegrityTests(unittest.TestCase):
    def test_ui_ids_are_unique_and_static_translations_exist(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "kirapass" / "web" / "ui.html").read_text(encoding="utf-8")
        js = (root / "kirapass" / "web" / "ui.js").read_text(encoding="utf-8")

        class Markup(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.keys = [], []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get("id"):
                    self.ids.append(attrs["id"])
                if attrs.get("data-i18n"):
                    self.keys.append(attrs["data-i18n"])

        markup = Markup()
        markup.feed(html)
        duplicates = sorted({item for item in markup.ids
                             if markup.ids.count(item) > 1})
        self.assertEqual(duplicates, [], "duplicate DOM ids break UI wiring")
        missing = [key for key in set(markup.keys)
                   if len(re.findall(r"\b" + re.escape(key) + r"\s*:", js)) < 2]
        self.assertEqual(sorted(missing), [],
                         "every static label needs Arabic and English text")
        scan_panel = html.index('id="panel-scan"')
        format_panel = html.index('id="panel-format"')
        self.assertLess(html.index('id="calibrateBtn"'), format_panel)
        self.assertGreater(html.index('id="calibrateBtn"'), scan_panel)
        self.assertIn("S.calibrationReady", js)
        self.assertIn("preflight_only: true", js)
        results_start = html.index('id="panel-results"')
        results_end = html.index("</section>", results_start)
        stop_button = html.index('id="stopBtn"')
        self.assertLess(results_start, stop_button)
        self.assertLess(stop_button, results_end,
                        "the stop control must stay on the visible results panel")
        add_row = js[js.index("function addRow"):js.index("function renderHits")]
        self.assertIn("body.prepend(tr)", add_row)
        self.assertIn("body.lastElementChild", add_row)


class RunStopControlTests(unittest.TestCase):
    def test_stop_marks_the_run_stopping_and_rejects_a_second_start(self):
        eng = engine.Engine(store.Store(), persist=False)
        eng.state = "running"

        eng.stop()

        self.assertTrue(eng.stop_event.is_set())
        self.assertEqual(eng.status()["state"], "stopping")
        self.assertEqual(eng.start({}, attempts=1, threads=1),
                         {"ok": False, "error": "already_running"})

    def test_calibration_honors_stop_before_opening_a_session(self):
        from unittest import mock

        profile = selftest.make_profile("http://portal.test/login")
        stop_event = threading.Event()
        stop_event.set()
        with mock.patch.object(engine, "new_session") as new_session:
            cal = engine.calibrate(profile, stop_event=stop_event)
        self.assertEqual(cal.error, "user_stop")
        new_session.assert_not_called()

    def test_stop_during_calibration_does_not_enter_running_state(self):
        from unittest import mock

        entered = threading.Event()
        release = threading.Event()

        def paused_calibration(*args, **kwargs):
            entered.set()
            release.wait(2)
            return engine.Calibration()

        eng = engine.Engine(store.Store(), persist=False)
        profile = selftest.make_profile("http://portal.test/login")
        with mock.patch.object(engine, "calibrate", side_effect=paused_calibration):
            self.assertTrue(eng.start(profile, attempts=1, threads=1)["ok"])
            self.assertTrue(entered.wait(2), "calibration did not start")
            eng.stop()
            release.set()
            eng.thread.join(3)
        self.assertFalse(eng.thread.is_alive())
        self.assertEqual(eng.state, "done")
        self.assertEqual(eng.stop_reason, "user_stop")
        states = [event["data"].get("state") for event in eng.events
                  if event["kind"] == "state"]
        self.assertNotIn("running", states)

    def test_stop_during_request_delay_prevents_the_next_login_request(self):
        from unittest import mock

        waiting = threading.Event()

        class StopAwareEvent(threading.Event):
            def wait(self, timeout=None):
                waiting.set()
                return super().wait(timeout)

        eng = engine.Engine(store.Store(), persist=False)
        eng.state = "running"
        eng.stop_event = StopAwareEvent()
        eng.throttle["delay_ms"] = 2000
        session = type("Session", (), {})()
        profile = {"login_url": "http://portal.test/login"}
        with mock.patch.object(engine, "send_login") as send_login:
            worker = threading.Thread(target=eng._attempt,
                                      args=(session, None, "CARD", 1, profile))
            worker.start()
            self.assertTrue(waiting.wait(2), "attempt did not enter its delay")
            eng.stop()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        send_login.assert_not_called()
        self.assertEqual(eng._unevaluated, 1)


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

    def test_arabic_ban_phrase_is_detected(self):
        from kirapass import config
        page = "<html><body><h1>تم حظرك</h1><p>جهازك محظور مؤقتا</p></body></html>"
        self.assertTrue(fingerprint.find_phrase(page.lower(), config.BAN_WORDS))
        # French phrase too
        fr = "<html><body>trop de tentatives de connexion</body></html>"
        self.assertTrue(fingerprint.find_phrase(fr.lower(), config.BAN_WORDS))

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

    def test_a_copied_get_submission_is_recognised_without_a_form(self):
        url = "http://a.com/login?username=2934664754&password=&dst=%2F"
        form = portals.parse_form("<html>please wait</html>", url)
        self.assertEqual(form.method, "get")
        self.assertEqual(form.user_field, "username")
        self.assertEqual(form.pass_field, "password")
        self.assertEqual(form.dst_field, "dst")
        self.assertEqual(form.dst_value, "/")

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
    """Explicit router lockouts stop calibration and runs without retries."""

    def test_calibration_lockout_stops_without_waiting_or_retrying(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty",
                        ban_after=2, ban_seconds=2) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020", length=9,
                                      portal_info=info)
            eng = engine.Engine(store.Store(), persist=False,
                               checks=selftest.mock_checks(portal))
            eng.start(p, attempts=20, threads=2, delay_ms=0)
            deadline = time.time() + 10
            while time.time() < deadline and eng.state != "done":
                time.sleep(0.05)

            self.assertEqual(eng.state, "done")
            self.assertEqual(eng.stop_reason, "calibration_failed")
            self.assertEqual(eng.calibration.get("error"), "blocked_already",
                             eng.calibration)
            self.assertEqual(eng.calibration.get("ok"), False)
            self.assertTrue(any(step.get("reason") == "blocked_by_our_probes"
                                for step in eng.calibration.get("steps", [])))
            self.assertEqual(eng.progress.get("attempts", 0), 0)
            # It stops on the second request that returns the block page;
            # there is no third probe and no second calibration cycle.
            self.assertEqual(portal.state.logins, 2)

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


class NetworkFailureGuardTests(unittest.TestCase):
    def test_transport_error_burst_stops_promptly_without_reconnect(self):
        eng = engine.Engine(store.Store(), persist=False)
        for _ in range(config.CONSECUTIVE_TRANSPORT_FAILURE_LIMIT - 1):
            eng._record_transport_health("connect_timeout")
        self.assertFalse(eng.stop_event.is_set())

        # A real HTTP response proves the route is reachable and breaks the
        # consecutive-failure streak; the tool must not infer a MAC/IP ban.
        eng._record_transport_health()
        self.assertFalse(eng.stop_event.is_set())
        for _ in range(config.CONSECUTIVE_TRANSPORT_FAILURE_LIMIT):
            eng._record_transport_health("connect_timeout")
        self.assertTrue(eng.stop_event.is_set())
        self.assertEqual(eng.stop_reason, "target_unreachable")


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
        # bans start after five failures, so the learning is clean and the
        # lockout hits in the middle of the run
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty",
                        ban_after=5) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
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
    """The opt-in check is bounded and stops at the first explicit block."""

    def test_it_stops_at_the_first_block_without_waiting_or_reprobing(self):
        # Three rejected requests increment the counter; the fourth is blocked.
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty",
                        ban_after=3, ban_seconds=2) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            got = engine.probe_lockout(p, checks=selftest.mock_checks(portal),
                                       max_failures=30, wait_limit=30,
                                       step=1.0, pace=0.0)
            login_count = portal.state.logins
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["max_failures"], config.LOCKOUT_PROBE_MAX_FAILURES)
        self.assertEqual(got["ban_after"], 3, got)
        self.assertEqual(got["tried"], 4, got)
        self.assertEqual(login_count, 3)
        self.assertEqual(portal.state.bans, 1,
                         "a second request after the lockout would add another ban")
        self.assertIsNone(got["clears_after"], got)
        self.assertIsNone(got["safe_delay_ms"], got)
        recovery = next(s for s in got["steps"] if s["id"] == "recovery")
        self.assertEqual(recovery["reason"], "not_probed_after_lockout")

    def test_a_router_that_blocks_is_not_polled_for_expiry(self):
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty",
                        ban_after=2, ban_seconds=15) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            got = engine.probe_lockout(p, checks=selftest.mock_checks(portal),
                                       max_failures=6, wait_limit=20,
                                       step=10.0, pace=0.0)
            login_count = portal.state.logins
        self.assertEqual(got["ban_after"], 2, got)
        self.assertEqual(login_count, 2)
        self.assertEqual(portal.state.bans, 1)
        self.assertEqual(got["waited"], 0.0)
        self.assertIsNone(got["clears_after"], got)
        self.assertIsNone(got["safe_delay_ms"], got)

    def test_a_router_that_never_blocks_is_reported_as_such(self):
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty") as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            got = engine.probe_lockout(p, checks=selftest.mock_checks(portal),
                                       max_failures=30, wait_limit=2,
                                       step=1.0, pace=0.0)
            login_count = portal.state.logins
        self.assertTrue(got["ok"], got)
        self.assertIsNone(got["ban_after"], got)
        self.assertEqual(got["tried"], config.LOCKOUT_PROBE_MAX_FAILURES, got)
        self.assertEqual(login_count, config.LOCKOUT_PROBE_MAX_FAILURES)

    def test_network_diagnosis_stops_sampling_after_a_block(self):
        with MockPortal(valid_cards={"020124999"}, pass_mode="empty",
                        ban_after=3) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="030124", length=9,
                                      portal_info=info)
            result = engine.diagnose(p, threads=4,
                                     checks=selftest.mock_checks(portal))
            login_count = portal.state.logins
        seq = result["latency"]["sequential"]
        parallel = result["latency"]["parallel"]
        self.assertGreaterEqual(seq["banned"], 1, result)
        self.assertTrue(parallel["skipped_after_block"], result)
        self.assertEqual(login_count, 3)
        self.assertEqual(portal.state.bans, 1,
                         "diagnosis must not send another request after the block")


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

    def test_run_preflight_only_verifies_exact_request_once_before_baseline(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty",
                        unknown_success_page=True) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info, pass_mode="empty")
            cal = engine.calibrate(p, known_card="020124042", preflight_only=True,
                                   checks=selftest.mock_checks(portal))
            self.assertTrue(cal.ok and cal.tuned and cal.tuned.get("verified"),
                            cal.as_dict())
            self.assertEqual(portal.state.asked_cards.count("020124042"), 1)
            self.assertEqual(cal.tuned["logout"]["internet_after"], "WALLED")

    def test_run_preflight_only_stops_before_probes_when_known_card_fails(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty") as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info, pass_mode="empty")
            cal = engine.calibrate(p, known_card="020124000", preflight_only=True,
                                   checks=selftest.mock_checks(portal))
            self.assertFalse(cal.ok, cal.as_dict())
            self.assertEqual(cal.error, "known_card_not_proven")
            self.assertEqual(portal.state.asked_cards, ["020124000"])

    def test_pretested_known_card_is_excluded_without_being_resubmitted(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty") as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info, pass_mode="empty")
            cal = engine.calibrate(p, known_card="020124042", learn_known=False,
                                   checks=selftest.mock_checks(portal))
            self.assertTrue(cal.ok, cal.as_dict())
            self.assertNotIn("020124042", portal.state.asked_cards)

    def test_rejection_baseline_never_uses_the_known_card(self):
        p = store.new_profile(prefix="02", length=4, charset="0123456789")
        cards = engine.bench_cards(p, count=4, seed=3, exclude=("0200",))
        self.assertEqual(len(cards), 4)
        self.assertNotIn("0200", cards)

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

    def test_http_200_unknown_page_is_verified_against_internet_state(self):
        """A valid card may open the network without a clear success page."""
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty",
                        unknown_success_page=True) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info, pass_mode="empty")
            cal = engine.calibrate(p, known_card="020124042",
                                   checks=selftest.mock_checks(portal))
        step = self._shape_step(cal)
        self.assertTrue(step and step["ok"], cal.as_dict())
        self.assertEqual(step["reason"], "known_card_works")
        self.assertTrue(cal.tuned and cal.tuned.get("verified"), cal.tuned)
        self.assertEqual(cal.tuned.get("internet"), "expected_answer")
        applied = cal.as_dict().get("applied_settings")
        self.assertTrue(applied and applied.get("method") == "post", applied)
        self.assertEqual(applied.get("pass_mode"), "empty")
        self.assertNotIn("020124042", json.dumps(cal.as_dict()))
        trial = cal.tuned.get("trial") or {}
        self.assertEqual(trial.get("status"), 200)
        self.assertEqual(trial.get("code"), "UNKNOWN")
        self.assertTrue(trial.get("online_transition"), trial)

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

    def test_unproven_known_card_stops_and_limits_tuning_requests(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty") as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info, pass_mode="empty")
            eng = engine.Engine(store.Store(), persist=False,
                               checks=selftest.mock_checks(portal))
            eng.start(p, attempts=50, threads=1, known_card="020124999")
            deadline = time.time() + 10
            while time.time() < deadline and eng.state != "done":
                time.sleep(0.05)

            self.assertEqual(eng.state, "done")
            self.assertEqual(eng.stop_reason, "calibration_failed")
            self.assertEqual(eng.calibration.get("error"), "known_card_not_proven")
            self.assertEqual(eng.progress.get("attempts", 0), 0)
            step = next(s for s in eng.calibration["steps"]
                        if s["id"] == "shape_tuned")
            self.assertFalse(step["ok"], step)
            self.assertEqual(step["reason"], "known_card_not_proven")
            trials = step["detail"]["trials"]
            self.assertTrue(trials, step["detail"])
            self.assertLessEqual(len(trials), config.KNOWN_CARD_TRIAL_LIMIT)
            self.assertTrue(all(t["code"] == "REJECTED" for t in trials), trials)
            # The router's answer is recorded, not just "it failed".
            self.assertTrue(any(t.get("word") for t in trials), trials)


class BrowserParityTests(unittest.TestCase):
    """A real portal hands out a cookie and a token on the login page, and
    refuses the post without them: "bad request" instead of a judgement.
    That is the difference between a browser - which asks for the page first
    - and a script that only posts.
    """

    def test_a_bare_post_is_refused_but_the_run_gets_judged(self):
        with MockPortal(valid_cards={"020124042"}, pass_mode="empty",
                        require_session=True) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="020124", length=9,
                                      portal_info=info)
            # no page was ever asked for: the router refuses the request
            sess = engine.new_session()
            self.addCleanup(sess.close)
            r = engine.send_login(sess, p, "020124000")
            self.assertEqual(r.status, 400, r.text[:120])

            # asking for the page first hands us what the portal wants
            warmed = engine.warm_up(sess, p)
            self.assertTrue((warmed.get("extra_fields") or {}).get("tok"),
                            warmed.get("extra_fields"))
            r = engine.send_login(sess, warmed, "020124000")
            self.assertEqual(r.status, 200, r.text[:120])

            # and a whole run gets its cards judged, not refused
            eng = engine.Engine(store.Store(), persist=False,
                                checks=selftest.mock_checks(portal))
            eng.start(p, attempts=20, threads=2, delay_ms=0, verify_after=False)
            deadline = time.time() + 60
            while time.time() < deadline and eng.state != "done":
                time.sleep(0.1)
            st = eng.status()
            self.assertGreater(st["counters"].get("REJECTED", 0), 5,
                               st["counters"])
            self.assertEqual(st["counters"].get("NET_ERROR", 0), 0,
                             st["counters"])
            self.assertEqual(portal.state.bad_requests, 1)   # only the bare one

    def test_the_request_looks_like_the_browser_that_scanned_it(self):
        p = selftest.make_profile("http://10.5.50.1/login",
                                  prefix="020124", length=9)
        h = engine.browser_headers(p, p["login_url"])
        self.assertEqual(h["Referer"], p["login_url"])
        self.assertEqual(h["Origin"], "http://10.5.50.1")
        self.assertIn("x-www-form-urlencoded", h["Content-Type"])
        # the operator can send another identity - some portals refuse others
        p2 = dict(p, user_agent="Mozilla/5.0 (iPhone)", send_referer=False)
        h2 = engine.browser_headers(p2, p2["login_url"])
        self.assertEqual(h2["User-Agent"], "Mozilla/5.0 (iPhone)")
        self.assertNotIn("Referer", h2)

        # A browser GET form has a Referer but no POST-only Origin/content type.
        get_profile = dict(p, method="get")
        h3 = engine.browser_headers(get_profile, get_profile["login_url"])
        self.assertIn("Referer", h3)
        self.assertNotIn("Origin", h3)
        self.assertNotIn("Content-Type", h3)

    def test_known_card_tuning_keeps_rotating_session_tokens(self):
        """Calibration tries many shapes; every one needs the token just returned."""
        with MockPortal(valid_cards={"0242"}, pass_mode="same",
                        require_session=True) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="02", length=4,
                                      portal_info=info, pass_mode="empty")
            cal = engine.calibrate(p, known_card="0242",
                                   checks=selftest.mock_checks(portal))
            self.assertTrue(cal.ok, cal.as_dict())
            self.assertEqual(cal.profile["pass_mode"], "same")
            self.assertEqual((cal.tuned or {}).get("mode"), "same", cal.tuned)
            self.assertEqual(portal.state.bad_requests, 0,
                             "a one-use token was reused during calibration")

    def test_diagnosis_uses_a_browser_session_in_every_thread(self):
        with MockPortal(valid_cards={"0299"}, pass_mode="empty",
                        require_session=True) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="03", length=4,
                                      portal_info=info)
            result = engine.diagnose(p, threads=4,
                                     checks=selftest.mock_checks(portal))
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["latency"]["sequential"]["errors"], 0,
                             result["latency"])
            self.assertEqual(result["latency"]["parallel"]["errors"], 0,
                             result["latency"])
            self.assertEqual(portal.state.bad_requests, 0,
                             "parallel diagnosis posted without a page session")
            self.assertLessEqual(portal.state.logins,
                                 config.DIAGNOSTIC_SAMPLE_LIMIT)

    def test_get_submission_preserves_query_order_and_omits_absent_fields(self):
        from unittest import mock
        url = "http://example.invalid/login?username=&password="
        p = store.new_profile(login_url=url, method="get",
                              user_field="username", pass_field="password",
                              pass_mode="empty", send_dst=False,
                              send_popup=False,
                              extra_fields={"dst": "stale", "popup": "stale"})
        page = ("<form method='get' action='/login?username=&password='>"
                "<input name='username'><input name='password' type='password'>"
                "</form>")
        p = engine.absorb_form(p, page, url)
        self.assertFalse(p.get("send_dst"))
        self.assertFalse(p.get("send_popup"))
        self.assertNotIn("dst", engine.build_fields(p, "CARD"))
        self.assertNotIn("popup", engine.build_fields(p, "CARD"))

        sess = mock.MagicMock()
        engine.send_login(sess, p, "CARD")
        method, request_url = sess.request.call_args.args[:2]
        self.assertEqual(method, "GET")
        pairs = parse_qsl(urlsplit(request_url).query, keep_blank_values=True)
        self.assertEqual([key for key, _ in pairs], ["username", "password"])
        self.assertEqual(pairs[0][1], "CARD")
        self.assertEqual(pairs[1][1], "")
        self.assertNotIn("dst=", request_url)
        self.assertNotIn("popup=", request_url)

    def test_safe_request_shape_preserves_order_and_redacts_values(self):
        p = store.new_profile(
            login_url="https://url-user:url-pass@portal.invalid/login?token=secret-token&username=OLD&password=",
            method="get", user_field="username", pass_field="password",
            pass_mode="same", send_dst=False, send_popup=False)
        shape = engine.safe_request_shape(p, "CARD-123")
        self.assertEqual(shape["method"], "GET")
        self.assertEqual(shape["field_names"], ["password", "username"])
        self.assertNotIn("secret-token", shape["url"])
        self.assertNotIn("OLD", shape["url"])
        self.assertNotIn("CARD-123", shape["url"])
        self.assertNotIn("secret-token", repr(shape))
        self.assertNotIn("url-user", repr(shape))
        self.assertNotIn("url-pass", repr(shape))
        self.assertEqual(shape["body_field_names"], [])

    def test_scanning_a_copied_success_url_does_not_spend_its_card(self):
        with MockPortal(valid_cards={"0242"}, method="get",
                        pass_mode="empty") as portal:
            copied = portal.url + "?username=0242&password=&dst=%2F"
            sess = engine.new_session()
            self.addCleanup(sess.close)
            found = portals.discover(sess, copied)
            self.assertEqual(portal.state.logins, 0,
                             "the scan submitted and consumed the real card")
            self.assertEqual(found.form.method, "get")
            self.assertNotIn("username=0242", found.form.action)

    def test_a_copied_success_url_replaces_old_credentials(self):
        """Never append USER2 after ?username=USER1&password=.

        The user's exact report was that changing the username in this URL in
        a browser works. Many routers read the first duplicate query value, so
        appending fields would silently test USER1 for the entire run.
        """
        with MockPortal(valid_cards={"0242"}, method="get",
                        pass_mode="empty") as portal:
            p = selftest.make_profile(
                portal.url + "?username=OLD&amp;password=", prefix="02", length=4,
                method="get", pass_mode="empty")
            sess = engine.new_session()
            self.addCleanup(sess.close)
            r = engine.send_login(sess, p, "0242")
            self.assertEqual(r.status, 302, r.text[:120])
            self.assertEqual(portal.state.asked_cards[-1], "0242")
            self.assertNotIn("OLD", portal.state.asked_cards)

    def test_http_400_is_not_learned_as_a_wrong_card(self):
        """A bad request is the router rejecting the shape, not the card."""
        with MockPortal(valid_cards={"0242"}, pass_mode="empty",
                        reject_shape=True) as portal:
            info = selftest.scan(portal.url)
            p = selftest.make_profile(portal.url, prefix="02", length=4,
                                      portal_info=info)
            cal = engine.calibrate(p)
            self.assertFalse(cal.ok, cal.as_dict())
            self.assertEqual(cal.error, "request_shape_rejected")
            step = next(s for s in cal.steps
                        if s["reason"] == "request_shape_rejected")
            self.assertEqual(step["detail"]["status"], [400, 400, 400])


class ResumeProgressTests(unittest.TestCase):
    def test_live_coverage_advances_for_unique_judged_cards(self):
        eng = engine.Engine(store.Store(), persist=False)
        eng.state = "running"
        eng.started_at = time.time() - 10
        eng._run_start_pos = 200
        eng.progress.update(total=1000, covered=200, space=2000)
        eng.counters["REJECTED"] = 1000

        self.assertEqual(eng.status()["progress"]["covered"], 1200)

        # Retries and cards that are blocked, unanswered, or still awaiting a
        # retry are requests, but they do not add unique coverage.
        eng._retry_processed = 25
        eng._unevaluated = 4
        eng._pending = [("pending", 1001, True)]
        self.assertEqual(eng.status()["progress"]["covered"], 1170)
        self.assertEqual(eng.status_snapshot()["progress"]["covered"], 1170)

    def test_resumed_run_only_queues_the_remaining_unique_cards(self):
        with MockPortal(valid_cards={"9999"}, pass_mode="empty") as portal:
            info = selftest.scan(portal.url)
            prof = selftest.make_profile(portal.url, prefix="02", length=4,
                                         portal_info=info, pass_mode="empty")
            prof.update(space_pos=92, walk_a=1, walk_b=0)
            eng = engine.Engine(store.Store(), persist=False,
                                checks=selftest.mock_checks(portal))
            self.assertTrue(eng.start(prof, attempts=2000, threads=1,
                                      verify_after=False)["ok"])
            deadline = time.time() + 30
            while time.time() < deadline and eng.state != "done":
                time.sleep(0.05)
            self.assertEqual(eng.state, "done", eng.status())
            progress = eng.status()["progress"]
            self.assertEqual(progress["space"], 100)
            self.assertEqual(progress["total"], 8)
            self.assertEqual(progress["queued"], 8)
            self.assertLessEqual(progress["percent"], 100)
            self.assertLessEqual(progress["covered"], 100)
            self.assertEqual(len(portal.state.asked_cards[-8:]), 8)
            self.assertEqual(len(set(portal.state.asked_cards[-8:])), 8)


class LostAnswerTests(unittest.TestCase):
    """A request can die on the way while the router did take it.

    Such a card has no answer, so it is not tested: the tool has to ask about
    it again instead of moving on - otherwise a run over a whole card space
    can finish without ever really asking about the card that works.
    """

    def test_status_is_safe_before_the_first_run(self):
        eng = engine.Engine(store.Store(), persist=False)
        st = eng.status()
        self.assertEqual(st["state"], "idle")
        self.assertEqual(st["progress"]["threads"], 0)

    def test_a_card_that_got_no_answer_is_asked_again(self):
        from kirapass import httpclient, selftest as _st

        with MockPortal(valid_cards={"0242"}, pass_mode="empty") as portal:
            info = _st.scan(portal.url)
            p = _st.make_profile(portal.url, prefix="02", length=4,
                                 portal_info=info, pass_mode="empty")
            real = engine.send_login
            real_bench = engine.bench_cards
            lost = {"left": 2}

            def deterministic_bench(profile, count=3, seed=0, exclude=()):
                return [card for card in ("0200", "0201", "0202")
                        if card not in set(exclude)][:count]

            def silent_twice(session, prof, card, *a, **k):
                # "refused" is not retryable on the spot, so without the
                # re-queue the card would simply be dropped
                if card == "0242" and lost["left"] > 0:
                    lost["left"] -= 1
                    raise httpclient.NetError("refused", "simulated silence",
                                              prof.get("login_url", ""))
                return real(session, prof, card, *a, **k)

            engine.send_login = silent_twice
            engine.bench_cards = deterministic_bench
            try:
                st, _eng = _st.run_engine(p, attempts=200, threads=2,
                                          checks=_st.mock_checks(portal))
            finally:
                engine.send_login = real
                engine.bench_cards = real_bench
            counters = st.get("counters", {})
            self.assertTrue(st.get("hits"), f"hits={st.get('hits')} "
                                            f"counters={counters}")
            self.assertGreaterEqual(counters.get("NET_ERROR", 0), 1, counters)
            self.assertEqual(lost["left"], 0, "the card was never asked again")

    def test_a_redirect_out_of_the_portal_is_never_called_rejected(self):
        # A router that answers with an empty body and a redirect for wrong
        # cards (and never the same target twice) leaves the judge with
        # nothing but the status to compare.  A card that goes somewhere else
        # entirely must not then be reported as a normal rejection.
        # ... two different targets, so there is no single "wrong card" target
        # to compare with and only the status is left
        fp = fingerprint.Fingerprinter.learn([
            _FakeReply("", status=302,
                       headers={"Location": "http://portal/login?e=1"}),
            _FakeReply("", status=302,
                       headers={"Location": "http://portal/status?e=2"})])
        judge = fingerprint.Judge(fp, "http://portal/login")
        v = judge.classify(_FakeReply(
            "", status=302,
            headers={"Location":
                     "http://connectivitycheck.gstatic.com/generate_204"}),
            submitted=["0242"])
        self.assertNotEqual(v.code, "REJECTED", v.as_dict())
        self.assertEqual(
            v.reason, "redirect_out_of_portal_but_page_matches", v.as_dict())


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
    def test_calibration_report_redacts_hints_and_url_secrets(self):
        from kirapass.web.server import _safe_calibration_report
        profile = {"user_field": "username", "pass_field": "password"}
        safe = _safe_calibration_report({
            "steps": [{"detail": {"card_hint": "020124...",
                                    "sample_cards": ["020124001"],
                                    "extra_fields": {"tok": "private-token"},
                                    "url": "https://u:p@portal.invalid/login?token=private"}}],
        }, profile)
        blob = json.dumps(safe)
        for secret in ("020124", "private", "https://u:p@"):
            self.assertNotIn(secret, blob)
        self.assertIn("[REDACTED]", blob)

    def test_report_snapshot_redacts_query_and_live_profile_secrets(self):
        card, digest, challenge, csrf = (
            "2972801416", "4529b5cb476335e9a70a5f7acd29b663",
            "private-challenge", "live-csrf-token")
        snapshot = engine.safe_profile_snapshot({
            "name": "safe-report",
            "login_url": ("http://a.com/login?username=" + card +
                          "&amp;password=" + digest),
            "user_field": "username", "pass_field": "password",
            "pass_fixed": "fixed-secret",
            "chap": {"id": "private-id", "challenge": challenge,
                     "field": "password"},
            "extra_fields": {"csrf_token": csrf, "remember": "ON"},
        })
        blob = json.dumps(snapshot)
        for secret in (card, digest, challenge, "private-id", "fixed-secret", csrf):
            self.assertNotIn(secret, blob)
        self.assertEqual(snapshot["extra_fields"]["remember"], "ON")
        self.assertTrue(snapshot["chap"]["challenge_present"])
        self.assertIn("username=&password=", snapshot["login_url"])

    def test_migration_redacts_credentials_from_copied_get_url(self):
        card, digest = "2972801416", "4529b5cb476335e9a70a5f7acd29b663"
        prof = store.migrate({
            "name": "old-get",
            "login_url": ("http://a.com/login?password=" + digest +
                          "&amp;username=" + card + "&amp;dst=%2F"),
            "method": "get", "user_field": "username",
            "pass_field": "password", "length": 10, "prefix": "29",
        })
        self.assertEqual(prof["login_url"],
                         "http://a.com/login?password=&username=&dst=%2F")
        self.assertNotIn(card, json.dumps(prof))
        self.assertNotIn(digest, json.dumps(prof))
        self.assertNotIn("&amp;", prof["login_url"])

    def test_migration_preserves_explicit_dst_popup_flags(self):
        current = store.migrate({"schema": store.SCHEMA,
                                 "send_dst": False, "send_popup": False,
                                 "extras": True})
        self.assertFalse(current["send_dst"])
        self.assertFalse(current["send_popup"])
        legacy = store.migrate({"network_type": "1", "extras": False})
        self.assertFalse(legacy["send_dst"])
        self.assertFalse(legacy["send_popup"])

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

    def test_review_body_redacts_mac_and_ip(self):
        body = ("<html><body>client AA:BB:CC:DD:EE:FF at 10.5.50.42 "
                "and also aa-bb-cc-dd-ee-ff</body></html>")
        red = store.redact_review_body(body)
        self.assertNotIn("AA:BB:CC:DD:EE:FF", red)
        self.assertNotIn("10.5.50.42", red)
        self.assertIn("[mac-redacted]", red)
        self.assertIn("[ip-redacted]", red)
        st = store.Store()
        saved = st.save_review(2, "card1",
                               {"code": "UNKNOWN", "reason": "x", "data": {}},
                               body)
        content = st.read_review(saved["file"])
        self.assertNotIn("AA:BB:CC", content)
        self.assertNotIn("10.5.50.42", content)
        st.clear_cache("temp")

    def test_sha_password_modes_are_replayable(self):
        from kirapass import engine
        p = store.new_profile(pass_mode="sha1user")
        self.assertEqual(engine.password_value(p, "0201"),
                         capture._sha1("0201"))
        p["pass_mode"] = "sha256user"
        self.assertEqual(engine.password_value(p, "0201"),
                         capture._sha256("0201"))
        self.assertIn("sha1user", store.PASS_MODES)
        self.assertIn("sha256user", store.PASS_MODES)

    def test_ban_evidence_structure(self):
        from kirapass import engine

        class R:
            status = 403
            text = "<html><body>you are blocked</body></html>"

        stop, word, evidence = engine._is_protective_reply(
            R(), "http://10.5.50.1/login")
        self.assertTrue(stop)
        self.assertIsInstance(evidence, dict)
        self.assertIn("status", evidence)
        self.assertIn("has_form", evidence)
        self.assertIn("kind_hint", evidence)
        self.assertEqual(evidence["status"], 403)

    def test_custom_internet_checks_parse(self):
        from kirapass import verify
        checks = verify.resolve_internet_checks(
            "http://example.test/ok|200|OK")
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0][0], "http://example.test/ok")
        self.assertEqual(checks[0][1], 200)
        self.assertEqual(checks[0][2], "OK")
        # empty falls back to defaults
        defaults = verify.resolve_internet_checks("")
        self.assertTrue(len(defaults) >= 1)


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
    def test_form_action_decodes_html_entities_and_redacts_get_credentials(self):
        html = """<form action="/login?username=29728014&amp;password=hash123&amp;dst=%2F"
        method="get"><input type="text" name="username">
        <input type="password" name="password"></form>"""
        form = portals.parse_form(html, "http://a.com/login")
        self.assertEqual(form.action,
                         "http://a.com/login?username=&password=&dst=%2F")
        self.assertNotIn("29728014", form.action)
        self.assertNotIn("hash123", form.action)
        self.assertNotIn("&amp;", form.action)

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


class CaptureTests(unittest.TestCase):
    """Redacted browser-assisted recorder: secrets stay out of the report."""

    def test_learn_words_uses_only_visible_body_text(self):
        html = """<html lang='en'><head><title>HeadOnlyMarker</title>
        <meta name='description' content='MetaOnlyMarker windows theme color apple touch icon sizes'>
        <script>ScriptOnlyMarker</script><style>.css { content: 'StyleOnlyMarker'; }</style>
        </head><body data-theme='BodyAttributeMarker'>
        <p>PortalVisibleGreeting welcomes every guest today.</p>
        </body></html>"""
        words = {word.lower() for word in capture.learn_words(html)}
        self.assertIn("portalvisiblegreeting", words)
        for hidden in ("headonlymarker", "metaonlymarker", "windows", "theme",
                       "color", "apple", "touch", "icon", "sizes",
                       "scriptonlymarker", "styleonlymarker", "bodyattributemarker"):
            self.assertNotIn(hidden, words)

    def test_only_generalizable_password_patterns_are_learned(self):
        html = "<form><input name='username'><input name='password'></form>"
        same = capture.infer_pass_mode("0201", "0201", "0201", "0201", html,
                                       ["username", "password"])
        self.assertEqual(same["pass_mode"], "same")
        self.assertFalse(same["needs_browser_js"])
        empty = capture.infer_pass_mode("0201", "", "0201", "", html,
                                        ["username", "password"])
        self.assertEqual(empty["pass_mode"], "empty")
        omit = capture.infer_pass_mode("0201", "x", "0201", "", html, ["username"])
        self.assertEqual(omit["pass_mode"], "omit")
        digest = capture._md5("0201")
        md5user = capture.infer_pass_mode("0201", "0201", "0201", digest, html,
                                          ["username", "password"])
        self.assertEqual(md5user["pass_mode"], "md5user")
        sha1 = capture.infer_pass_mode(
            "0201", "0201", "0201", capture._sha1("0201"), html,
            ["username", "password"])
        self.assertEqual(sha1["pass_mode"], "sha1user")
        self.assertFalse(sha1["needs_browser_js"])
        sha256 = capture.infer_pass_mode(
            "0201", "0201", "0201", capture._sha256("0201"), html,
            ["username", "password"])
        self.assertEqual(sha256["pass_mode"], "sha256user")
        self.assertFalse(sha256["needs_browser_js"])
        chap_html = ("<script>document.login.password.value = hexMD5('id12' +"
                     " document.login.password.value + 'chal34');</script>"
                     "<form><input name='username'><input name='password'></form>")
        hashed = capture._md5("id12" + "0201" + "chal34")
        chap = capture.infer_pass_mode("0201", "0201", "0201", hashed, chap_html,
                                       ["username", "password"])
        self.assertEqual(chap["pass_mode"], "chap")
        self.assertFalse(chap["needs_browser_js"])

    def test_unknown_js_password_transform_blocks_automation(self):
        html = "<form><input name='username'><input name='password'></form>"
        learned = capture.infer_pass_mode(
            "020124042", "secret", "020124042", "deadbeefdeadbeefdeadbeefdeadbeef",
            html, ["username", "password"])
        self.assertTrue(learned["needs_browser_js"])
        self.assertEqual(learned["reason"], "unknown_js_transform")
        self.assertIn("JavaScript", learned["reason_ar"])
        prof = store.new_profile(login_url="http://10.5.50.1/login",
                                 charset="0123456789", length=10, prefix="02",
                                 capture_needs_browser_js=True)
        self.assertIn("needs_browser_js", store.validate(prof))

    def test_http_200_is_not_success_or_reject_without_teaching(self):
        self.assertEqual(capture.verdict_from_status(200), "unknown_http_200")
        self.assertEqual(capture.verdict_from_status(200, "success"), "success")
        self.assertEqual(capture.verdict_from_status(302), "redirect")

    def test_login_form_cannot_be_marked_success_or_status(self):
        with MockPortal(valid_cards={"0242"}) as portal:
            hub = capture.Hub()
            cap = hub.start(portal.url)
            self.addCleanup(cap.close)
            success = hub.mark(cap.id, "success")
            status = hub.mark(cap.id, "status")
            self.assertFalse(success["ok"])
            self.assertEqual(success["error"], "login_form_still_visible")
            self.assertFalse(status["ok"])
            self.assertEqual(status["error"], "login_form_still_visible")
            reject = hub.mark(cap.id, "reject")
            self.assertTrue(reject["ok"])
            duplicate = hub.mark(cap.id, "reject")
            self.assertTrue(duplicate["ok"])
            self.assertEqual(len(cap.marks), 1)

    def test_report_never_contains_secrets(self):
        card = "020124042"
        with MockPortal(valid_cards={card}, pass_mode="same",
                        require_session=True, success_page=True,
                        dynamic=True) as portal:
            hub = capture.Hub()
            cap = hub.start(portal.url, guard="http://127.0.0.1:8770")
            form = portals.parse_form(cap.html, cap.url)
            fields = {
                form.user_field: card,
                form.pass_field: card,
            }
            for name, value in (form.fields or {}).items():
                if name not in fields:
                    fields[name] = value
            hub.step(cap.id, {
                "kind": "form", "method": form.method, "url": form.action,
                "fields": fields, "fields_before": dict(fields),
                "fields_after": dict(fields),
            })
            hub.mark(cap.id, "success")
            learned_before_status = dict(cap.pass_learn)
            hub.step(cap.id, {
                "kind": "navigate", "method": "GET",
                "url": portal.base + "/status",
            })
            self.assertEqual(cap.form.user_field, "username")
            self.assertEqual(cap.form.pass_field, "password")
            self.assertEqual(cap.form.dst_field, "dst")
            self.assertEqual(cap.form.popup_field, "popup")
            hub.mark(cap.id, "status")
            # A form on the statistics page must not replace the login model
            # or make its empty fields look like a new password transform.
            hub.step(cap.id, {
                "kind": "form", "method": "POST",
                "url": portal.base + "/status",
                "fields": {"erase-cookie": "1"},
                "fields_before": {"erase-cookie": "1"},
                "fields_after": {"erase-cookie": "1"},
            })
            self.assertEqual(cap.pass_learn, learned_before_status)
            st = store.Store()
            result = hub.finish(cap.id, st)
            self.assertEqual(result["profile"]["user_field"], "username")
            self.assertEqual(result["profile"]["pass_field"], "password")
            self.assertEqual(result["profile"]["dst_field"], "dst")
            self.assertEqual(result["profile"]["popup_field"], "popup")
            self.assertEqual(result["profile"]["pass_mode"], "same")
            blob = json.dumps(result["report"], ensure_ascii=False)
            self.assertNotIn(card, blob)
            self.assertNotIn("portal_sid=", blob)
            for value in (form.fields or {}).values():
                if value and len(str(value)) >= 8:
                    self.assertNotIn(str(value), blob)
            self.assertTrue(result["report"]["cookie_names"])
            self.assertNotIn("values", json.dumps(result["report"].get("cookie_names")))
            self.assertEqual(capture.rewrite_html("<html><head></head></html>",
                                                  portal.url, cap.id,
                                                  "http://127.0.0.1:8770").count(
                "allow-same-origin"), 0)
            self.assertIn("sandbox=\"allow-scripts allow-forms\"",
                          capture.view_page(cap.id).decode("utf-8"))
            self.assertNotIn("allow-same-origin",
                             capture.view_page(cap.id).decode("utf-8"))
            self.assertTrue(os.path.exists(
                os.path.join(config.RUN_DIR, result["report_name"])))
            self.assertTrue(result["profile"]["login_url"])
            self.assertIn("/api/capture/start", " ".join([
                "/api/capture/start", "/api/capture/step", "/api/capture/mark",
                "/api/capture/finish", "/api/capture/status",
                "/api/capture/report", "/capture/view"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
