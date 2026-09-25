# KiraPass 5 — developer notes (structure, tests, design rules)

## Layout

```
KiraPass.py                 launcher (CLI: --selftest --clear-cache --host ...)
kirapass/
  config.py                 paths, timeouts, word lists, defaults
  errors.py                 every network exception -> one kind + plain hint
  httpclient.py             stdlib HTTP (keep-alive, cookies, redirects, gzip)
  fingerprint.py            dynamic-token learning, masking, verdict engine
  portals.py                login page parsing (fields, dst, MikroTik md5/chap)
  verify.py                 "is the guest really online?" checks + logout
  engine.py                 calibration, threaded run, verdict accounting
  store.py                  profiles (+migration), reports, cache clearing
  mockportal.py             local mock router used by the self-test
  selftest.py               14 end-to-end scenarios
  cli.py, __main__.py       command line entry points
  web/server.py             JSON API + static assets (ThreadingHTTPServer)
  web/ui.html|ui.js|ui.css  the whole UI (no build step, no CDN)
tools/practice_portal.py    a fake hotspot for safe training
tools/checks/web_e2e.py     scan -> format -> calibrate -> run, through the API
tests/test_kirapass.py      unittest wrapper (scenarios + units)
```

## Design rules (each one exists because the old version broke it)

1. **No success without evidence.** `Verdict.is_hit` is only true for
   `ACCEPTED*`, and those codes require a redirect out of the portal, learned
   success words, or a real internet check.
2. **Never lose an attempt.** `sum(counters) == cards really tried`; the
   producer uses a bounded `put()` so a stop can never deadlock it (that bug
   hung the old design), and whatever is dropped is counted as `dropped`.
3. **The rejection baseline is learned, not assumed**, using format-valid
   probe cards, and it is compared with learned value/pattern masking plus a
   structural similarity fallback. A profile that cannot produce a single card
   is refused with a reason instead of calibrating against an empty baseline.
3b. **A run resumes, it does not repeat.** `space_pos` + the shuffled walk
   (`walk_a`/`walk_b`) live in the profile; the page sends them back with every
   start, and the next run continues where the previous one stopped. The engine
   emits a `resume` event, and `resume=False` starts a fresh pass with a new
   walk.
4. **Actions are isolated per thread**: one `Session` (connection + cookies)
   per worker, throw-away sessions for diagnostics.
5. **Reasons are machine keys** (`same_as_rejection_page_exact`,
   `net_read_timeout`, `banned_by_router`, ...) and the UI translates them -
   so nothing is hardcoded in two places.
6. **Anything unknown is saved, not guessed**: unclear replies land in
   `kirapass_data/review/` with the diff words.
7. **Standard library only.** No `pip install`, ever.

## Tests

```bash
python3 -m unittest discover -s tests -v     # 36 tests
python3 KiraPass.py --selftest               # the 14 scenarios, readable output
python3 -m kirapass.selftest --keep          # keep the test data folder
```

The self-test runs inside a throw-away folder (`config.set_data_dir` on a
tempdir), so it can never mix its practice cards into your profiles, hits or
reports; `--keep` leaves the folder behind and prints where it is.

The scenarios cover: format math/validation, legacy profile migration,
calibration with dynamic tokens, 50 wrong cards never reported as hits, finding
and verifying a real card, router ban, 429 rate limiting, dropped connections,
a dead target, MikroTik chap, a GET portal, diagnostics on a dead target,
**a second run continuing where the first one stopped**, cache clearing.

What changed in this revision - and why - is written down in
[docs/CHANGES.md](CHANGES.md) (bugs found by reading the code file by file,
each one with the test that now covers it).

Everything runs against `mockportal.MockPortal` on 127.0.0.1, so tests never
touch a real network.

## Web API (used by ui.js)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/meta` | version, charsets, pass modes, presets, cache info |
| GET | `/api/run/status?since=N` | engine status + events since sequence N |
| GET | `/api/job?id=` | status of a diagnose/calibrate job |
| GET | `/api/review` / `/api/review/file?name=` | saved unclear replies |
| GET | `/api/cache`, `/api/reports`, `/api/report?name=` | cache info, reports |
| POST | `/api/scan` | read a login page, detect form + internet state |
| POST | `/api/format/preview` | space size, sample cards, validation problems |
| POST | `/api/calibrate` | background job: learn + tune with a known card |
| POST | `/api/diagnose` | background job: reachability, latency, ban check |
| POST | `/api/run/start`, `/api/run/stop` | start/stop a run |
| POST | `/api/cache/clear`, `/api/settings`, `/api/profiles/*` | housekeeping |
| POST | `/api/quit` | shut the tool down (phone users have no Ctrl+C) |

`/api/run/start` accepts `resume` (default true): when the profile carries
`space_pos`/`walk_a`/`walk_b` the run continues from there; with `resume`
false the space is restarted from the beginning with a fresh walk.

`/api/run/status` returns `{ok, status, events}`; every attempt event carries
`{card, code, reason, ...}`, and `status.reason_counts` is the histogram of why
attempts ended the way they did (also written into the run report as
`reason_counts`).

Access control: loopback clients are always allowed; when the tool is opened to
the LAN (`--host 0.0.0.0`) every `/api/...` call needs the printed token
(`?token=` or `X-KiraPass-Token`), while the static page stays readable so the
UI can ask for the token.

## Environment knobs

* `KIRAPASS_INTERNET_CHECKS` - override the "is the guest really online" URLs
  when a network blocks the well-known ones:
  `"http://my.check/generate_204|204"` or `"http://a/ok|200|Expected text"`,
  comma separated. Defaults to google204 / msft / apple.
* `--host 0.0.0.0 --token <secret>` - serve the page to the LAN (phone on the
  same Wi-Fi). Non-loopback API calls then need the token.

## Ideas left out on purpose (and why)

* **No separate "username + different password" guessing mode.** Card networks
  send the same value in one or two fields; the password modes cover that. The
  old dual-space mode doubled the code and the failure modes.
* **No "fetch md5.js" menu entry.** The chap values are read from the login
  page itself, which is more reliable than downloading a script.
* **No pure-random tried-set file.** The shuffled walk covers everything once,
  resumes, and never repeats - without a million-entry JSON on disk.
