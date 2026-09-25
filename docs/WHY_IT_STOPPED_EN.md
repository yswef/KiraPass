# Why the old KiraPass stopped working — explained with evidence

Short version: **the tool was not "broken by itself" — it was comparing pages
in a way that cannot work on a modern POST hotspot, then reporting the wrong
thing.** Nothing in it was ever disabled on purpose; it just had no rule for
what it was looking at. Below is exactly what went wrong, how each failure was
reproduced, and how version 5 avoids it.

> The Arabic version, with the same content, is
> [WHY_IT_STOPPED_AR.md](WHY_IT_STOPPED_AR.md).

---

## 1. The rejection page was never a stable thing to compare with

The old code sent two dummy cards first to build a "baseline" ("this is what
the router says for a wrong card"), then compared every later reply with it
using **length ±40 bytes**.

A real MikroTik hotspot page is not byte-stable:

* it carries a **session token that changes on every request**
  (`name="session" value="5f30507b2c…"`),
* it echoes back what you submitted (your card, your password field),
* it prints a small nonce for `md5.js` when chap is in use.

So the baseline from two probes never matched a later reply, and the old rule
fell through to "**DIFFERENT page → suspected match**". That is how wrong cards
ended up in `kirapass_hits.txt` — the file in the old repository is full of
false "hits" for that reason.

**How it was proven:** run the practice portal with `--dynamic` (a new session
token per request), send two wrong cards, and print the diff. The two pages
differ in the token value only; the old rule saw "different length/page" and
reported a suspected match.

**In version 5:** the rejection baseline is learned from format-valid probe
cards and compared **after masking** every dynamic part (learned literals,
learned patterns, and generic shapes). The verdict names the rule that matched
(`same_as_rejection_page_exact`) or says `looks_rejected_but_success_words_found`
and parks the page in `kirapass_data/review/` for you to read. A wrong card can
never be reported as accepted without positive evidence.

## 2. `KeyError: 'charset'` — old saved profiles crashed every run

Old profiles on disk look like:

```json
{"network_type": "3", "charset": "0", "var_len": 4, "prefix": "020124", ...}
```

The old code reached `profile["charset"]` expecting a *string of characters*;
some profiles saved it as a number/index, and other keys simply were not there.
The exception happened inside the attempt loop, so **every** attempt degraded to
"DIFFERENT page" (the code caught the error and kept going). The user sees a
tool that runs and never finds anything.

**How it was proven:** load an old-format profile dictionary, call the old
profile loader, and watch it raise `KeyError: 'charset'`; the surrounding
`try/except` swallowed it per attempt.

**In version 5:** `store.migrate()` converts old profiles (schema 5), fills
defaults, and `store.validate()` returns a readable list of problems
(`prefix_and_suffix_longer_than_length`, `charset_too_small`,
`url_missing_or_invalid`, …) that the page shows *before* a run starts instead
of dying in the middle.

## 3. The first request's cookie / nonce was thrown away

A captive portal hands out a session cookie (often also a hidden `dst` and a
chap nonce) with the login page. The browser sends it back with the POST. The
old `send_login()` built a fresh request with only `username`/`password`, so the
router answered with the login page again — a page that looks *almost* like the
rejection page, which fed problem #1.

**How it was proven:** capture the login GET response, then the POST the old
code sent: no `Cookie` header, no hidden fields.

**In version 5:** one `Session` object per worker thread keeps cookies
(`Set-Cookie` → `Cookie`), sends the hidden fields the page declared
(`dst`, `popup`, `extra_fields`), and only then evaluates the reply.

## 4. A working card *was* accepted, and the tool said "no"

When the correct card goes in, the router answers `302` and sends the browser to
the URL the guest originally asked for (for example
`http://connectivitycheck.gstatic.com/generate_204`). The old `is_successful()`
only looked for words like "welcome" or "success" in the body of a `200`
reply, so this case — the most common one on real routers — was read as
"DIFFERENT page".

**How it was proven:** post the valid card to the mock portal, print
`status=302`, `Location=…/generate_204`, then call the old `is_successful()` on
that reply: `False`.

**In version 5:** evidence, in order of strength:

1. the reply redirects **out of** the portal (to a URL that is not the portal),
2. the **internet check** then works from that session (`204` on
   `/generate_204`, or the expected text from the other check URLs),
3. learned success words appear,
4. the user's own keyword appears.

Only then is it `ACCEPTED_VERIFIED` / `ACCEPTED`. The router's own `/status`
page is used as a second opinion.

## 5. Bans and rate limits arrived as "wrong password"

After a few failures a router may answer `403` with `Login failed` or a ban
page, or `429` when it throttles. The old rule only *warned* after seeing five
such replies, and never stopped: the run kept hammering a router that had
already blocked it, and every `403` counted as a rejected card.

**How it was proven:** practice portal with `--ban-after 3`: replies `403`;
the old code kept sending.

**In version 5:** a ban page/`403` becomes `BANNED` (with the word that gave it
away), `429` becomes `RATE_LIMITED` (with `Retry-After` honoured), and the run
**stops and says why** (`banned_by_router`, `rate_limited_by_router`,
`target_unreachable`, `captcha_challenge`) after a small threshold instead of
burning your IP.

## 6. The version-5 producer could deadlock (fixed, and the self-test proves it)

While rebuilding, one more real bug showed up: the producer thread waited on a
queue that the workers never drained once the run was asked to stop, and the run
hung at "stopping". The fix: bounded `put()` with a timeout, a drain step that
counts whatever was not tested as `dropped`, and an explicit stop condition.
`--selftest` covers it (`stopping_mid_run_leaves_no_queue_behind`).

---

## What the self-test does and does not prove

The self-test starts **local mock routers** and exercises 13 scenarios: dynamic
tokens, 50 wrong cards that must never be a hit, finding and *verifying* a real
card, ban, rate limit, dropped connections, a dead target, chap/md5, a GET
portal, an old saved profile, cache clearing, and the stop behaviour above.

It does **not** prove anything about your network's page. Your page is read live
by the "scan" step, and calibration learns *your* rejection page before the run.

## Reproducing the whole thing yourself

```bash
python3 KiraPass.py --selftest        # local mock routers, nothing real touched
python3 tools/practice_portal.py --card 0201240007 --ban-after 300
```

The practice portal is the same code path as the mock routers in the self-test,
so what you watch on `http://127.0.0.1:8899/login` is exactly what the tool does
on a real hotspot.
