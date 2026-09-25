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
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kirapass import (config, fingerprint, httpclient, portals,  # noqa: E402
                     selftest, store)
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
