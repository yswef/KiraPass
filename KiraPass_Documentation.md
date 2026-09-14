# KiraPass — Technical Documentation

Version **3.2** · entry point `KiraPass.py` · Developer: ENG.YOUSEF

This document describes how the tool is built: the data model, the coverage
engine, the concurrency model, the success detector and the self-diagnostics.
For day-to-day usage see [`README.md`](README.md).

---

## 1. Overview

KiraPass is a single-file Python tool that tests the login page of a Mikrotik
hotspot. It enumerates **every** combination that matches a described shape
(card/code, username, or username+password pair), sends them to the login page
over HTTP(S) with a pool of worker threads, decides for each reply whether the
login succeeded, and reports both the outcome and the health of the link.

Three properties define the current version:

1. **No repeated guesses.** The search space is walked with a full-cycle
   permutation, so a run of N attempts always covers N *distinct* combinations.
2. **Resumable.** Progress (`walk.pos`) is saved in the profile, so a stopped or
   capped run continues exactly where it left off.
3. **Self-diagnosing.** Connection failures are classified into 15 kinds, each
   with a human-readable cause, and the final report turns those counts into a
   verdict (router overloaded / link unstable / harmless keep-alive churn).

---

## 2. Files

| File | Role |
|------|------|
| `KiraPass.py` | the tool itself (no package layout, no build step) |
| `KiraPass_extras.py` | optional side flows (known-good card check, diagnostics) — **not** imported by `KiraPass.py` |
| `kirapass_profiles.json` | persisted profiles, created next to the script |
| `README.md` | user manual |
| `KiraPass_Documentation.md` | this file |

Runtime dependencies: **Python 3.8+**, `requests`, `urllib3`.

> **Rename note.** Profiles used to live in `mikrotikbf_profiles.json`. The tool
> now writes `kirapass_profiles.json`, and `load_db()` still reads the old file
> when the new one does not exist, so upgrading loses nothing. The next save
> writes the new name.

---

## 3. High-level flow

```
main()
 ├─ 1) use_profile_flow()      ── choose_profile() ──► attack() ──► show_result()
 ├─ 2) create_profile_flow()   ── ask_url_and_test()
 │                              ask_method_and_fields()
 │                              ask_network_shape()
 │                              [learn_success_page()]
 │                              [_probe() diagnostics]
 │                              save_db() ──► attack() ──► show_result()
 └─ 3) manage_profiles_flow()  ── list / delete

attack()
 ├─ get_walk()            → (walk, space, note)
 ├─ card_gen()            → generator of distinct (user, pass) pairs
 ├─ N × worker()          → do_attempt() → send_login() → is_successful()
 ├─ progress_updater()    → one thread redrawing the bar every 0.08 s
 └─ shared{} + lock       → counters, error kinds, HTTP codes, latencies
```

---

## 4. Data model — the profile

A profile is a plain dict serialised as JSON.

| Key | Set by | Meaning |
|-----|--------|---------|
| `login_url` | `ask_url_and_test` | normalised login page (`http://` is added if missing) |
| `method` | `ask_method_and_fields` | `"1"` = GET, `"2"` = POST |
| `user_field`, `pass_field` | same | HTML input names (defaults `username` / `password`) |
| `extras`, `dst_field`, `popup_field` | same | also send Mikrotik's hidden `dst` / `popup` |
| `network_type` | `ask_network_shape` | `"1"` card only, `"2"` user = pass, `"3"` user + pass |
| `charset`, `var_len`, `prefix`, `suffix` | same | shape for types 1 and 2 |
| `u_charset`, `u_len`, `u_prefix`, `u_suffix` | same | username shape for type 3 |
| `p_charset`, `p_len`, `p_prefix`, `p_suffix` | same | password shape for type 3 |
| `threads` | wizard / run | default worker count |
| `keyword` | wizard / run | success keyword (`status` by default) |
| `success_url`, `success_signature` | `learn_success_page` | learned success page |
| `walk` | `attack` | `{a, b, space, pos, passes}` — resumable position |
| `name`, `created`, `last_used` | wizard | listing and sort order |

Character sets: `1` → `0-9`, `2` → `a-z`, `3` → `0-9a-z` (`CHARSETS`).

---

## 5. Coverage engine

### 5.1 Space size

```
_space_size(charset, n) = len(charset) ** n
type 1/2 → _space_size(charset, var_len)
type 3   → _space_size(u_charset, u_len) * _space_size(p_charset, p_len)
```

`_decode_index(idx, charset, n)` turns an index into a string (little-endian base
conversion). Together they form a **bijection** between `[0, space)` and all
possible strings, so "covering the space" is exactly "visiting every index".

### 5.2 Full-cycle walk (why nothing repeats)

```
index(i) = (b + a * i) mod space        with gcd(a, space) = 1
```

Because `a` is coprime with `space`, the sequence visits **every** index exactly
once before returning to the start, and since `a` and `b` are random the order is
scattered — not `0000, 0001, 0002, …`. Memory is O(1): only `a`, `b`, `space`,
`pos`, `passes` are kept. This replaced the old `random.choices` generator, which
could repeat a card it had already tried and therefore wasted attempts.

### 5.3 Resuming

`get_walk()` rebuilds the walk when the space changed (you edited the card
shape) or when `pos` is out of range, bumps `passes` when a full round finished,
and otherwise keeps the stored position. `attack()` then starts at
`start_pos = walk['pos']`, and if you ask for more attempts than remain it caps
the run and says so:

```
⚠ The whole space is only 100 combinations — the run was capped at 100 attempts
```

### 5.4 Honest coverage counters

`show_result()` separates four numbers that older versions mixed together:

| Counter | Meaning |
|---------|---------|
| `Distinct cards tested` | cards the generator produced (`sent`) |
| `Total HTTP requests` | sends performed, including retries (`tested`) |
| `Cards never delivered` | cards whose every retry failed at the network level |
| `Cumulative coverage` | `min(start + sent, space)` / `space` |

A card that never reached the router is **not** counted as covered; the tool says
so explicitly and tells you to re-run the pass.

---

## 6. Concurrency model

- One **producer**: the main thread pulls from `card_gen()` and pushes into a
  bounded `queue.Queue(maxsize=max(10, threads * 2))` — back-pressure keeps
  memory flat on huge spaces.
- **N workers** (`threads`): pop a card, call `do_attempt()`.
- **One progress thread**: redraws the bar every `0.08 s` from the shared
  counters, and announces `✓ MATCH FOUND` or `✗ TARGET UNREACHABLE` once.
- All shared state lives in one `shared` dict guarded by a single `Lock`.
- Each worker owns a **thread-local `requests.Session`** (`thread_session()`),
  so keep-alive works and no session is shared across threads.
- `Ctrl+C` sets `stop_event`; the producer stops, `task_q.join()` drains, and the
  walk position is saved.

Per-card retry policy inside `do_attempt()`: up to `MAX_TRIES_PER_CARD` (3) extra
sends, `0.05 * (tries + 1)` s apart. A card that still fails is counted in
`failed_cards` and reported as not covered, instead of being silently dropped
into a full queue.

---

## 7. Request layer

`_raw_send()` builds the request from the profile:

| method | shape |
|--------|-------|
| GET (`1`)  | `GET login_url?username=…[&password=…][&dst=&popup=true]` |
| POST (`2`) | `POST login_url` with the same fields form-encoded |

`send_login()` adds a **single automatic retry** when the failure is classified
as `stale_keepalive` or `conn_reset`: it closes the thread session and resends on
a fresh one, and records `_tls.retried` so the report can count
`↻ N stale connections were auto-retried`. This alone removed most of the
phantom error count of v3.0.

`test_connection()` does the same for the reachability test: 3 attempts with
`0.2 * (i + 1)` s back-off, so one transient `RemoteDisconnected` no longer stops
the whole program with a false "Cannot reach target".

Every request uses browser-like `HEADERS` (Chrome UA, `Accept`, `Accept-Language`,
`Connection: keep-alive`) and `verify=False` with the urllib3 warning silenced,
because hotspots are normally plain HTTP with self-signed certificates.

Timeouts: `CONNECT_TIMEOUT = 3.0 s`, `READ_TIMEOUT = 8.0 s`.

---

## 8. Success detection

`is_successful(profile, response, keyword)` evaluates in this order — the first
match wins:

| # | Test | Notes |
|---|------|-------|
| 1 | **Learned word signature** | words `[a-z]{3,}` present on the learned success page and absent from a failed login; needs `≥ max(2, 40% of the words)` |
| 2 | **Learned success URL** | same host+path as the recorded success URL |
| 3 | `/status` in the final URL | the classic Mikrotik redirect |
| 4 | `/status` anywhere in `response.history` | survives later redirects |
| 5 | **Failure sentence** in the HTML | `invalid username or password`, `login failed`, `access denied`, … → explicit failure |
| 6 | **Keyword** in the HTML or the URL | default `status` |
| — | otherwise | not a success |

`extract_signature()` builds rule 1 by diffing a real successful login against a
deliberately wrong one (12 words max). `learn_success_page()` refuses to learn
when both pages look identical and falls back to `/status` + keyword.

Important consequence for reading the report: **an expired or wrong card is not
an error.** It produces a normal HTTP page and counts as *tested*, never as
`Err:N`.

---

## 9. Error classification and self-diagnostics

`classify_error(exc)` maps an exception onto one of **15** kinds
(`stale_keepalive`, `conn_reset`, `conn_refused`, `conn_timeout`, `read_timeout`,
`connect_timeout`, `timeout`, `dns`, `unreachable`, `ssl`, `proxy`, `conn_error`,
`redirect_loop`, `request_error`, `other`), and `ERROR_HINTS` explains each one
in plain language.

Abort rule (`note_error`): the run is stopped only when
`err_since_resp >= NET_ERR_BURST` (25) **and** either the target never answered
at all, or it has been silent for `NET_SILENCE_SEC` (6 s). Any HTTP reply resets
the counter (`note_response`).

`note_response` also watches for server-side protection: `403`, `429` or any
`5xx` seen **5 or more** times raises a one-time warning, because that is the
shape of a captive portal fighting back — not of expired cards.

The final `print_error_report()` prints:

```
ERROR BREAKDOWN  (12 of 840 = 1.4%)
   stale_keepalive        9  (75.0%)  the server closed a reused keep-alive …
HTTP status codes seen: 200×820, 302×8
Latency: avg 42 ms | p95 48 ms | max 51 ms
VERDICT
 ✓ Error rate looks healthy (1.4%).
```

The verdict logic distinguishes: no errors · stale keep-alive churn (harmless) ·
timeouts → router overloaded, with a concrete recommended thread count ·
resets/refusals → Mikrotik HTTP connection limit · DNS/unreachable → unstable
path · error rate ≥ 10% → real pressure.

---

## 10. Configuration constants

```python
MAX_TRIES_PER_CARD = 3     # extra retries for one card on network-level failure
NET_ERR_BURST      = 25    # consecutive connection errors before the target counts as lost
NET_SILENCE_SEC    = 6.0   # total silence (no HTTP reply at all) before aborting
SLOW_DIAG_AFTER    = 8.0   # response slower than this is tagged "slow" in diagnostics
READ_TIMEOUT       = 8.0   # was 4.0 → too short for a busy router or a slow RADIUS
CONNECT_TIMEOUT    = 3.0
```

> `SLOW_DIAG_AFTER` is currently declared but not referenced anywhere in the
> code — it is a leftover from the diagnostics work and can be removed or wired
> into `_probe()`.

---

## 11. Known gaps

1. **Two flows live outside the tool, in `KiraPass_extras.py`.** They were
   taken out of `KiraPass.py` to keep the main tool small, and the main script
   never imports that file. Run them on their own:

       python3 KiraPass_extras.py

   - `verify_flow()` — known-good card check. It fetches the login page as a
     baseline, then sends one card you know is valid in every request shape
     (GET/POST × with/without `dst`+`popup`, each once user-only and once with
     the password = 4 shapes, 8 once a password is involved) and classifies
     every reply — so you learn whether the problem is the request shape, the
     success detection, or the card itself.
   - `diagnose_flow()` — read-only probe: 30 sequential requests vs.
     `max(60, threads * 3)` parallel ones, then a verdict. It guesses nothing
     and consumes no attempts.

   Both import everything they need from `KiraPass.py` (`_probe` included — the
   main tool still uses it for the diagnostics offered while creating a
   profile), so there is no duplicated logic to keep in sync. Messages inside
   the main tool name `KiraPass_extras.py` explicitly instead of promising a
   menu entry that does not exist.
2. **No CHAP (`chap-id` / `chap-challenge`) support.** Hotspots configured with
   CHAP MD5 challenge-response cannot be tested by sending the password in
   clear text; the tool would report every card as rejected.
3. **Single target per run.** A profile holds one URL; there is no multi-router
   mode.
4. **`requests` + threads, not asyncio.** Fine at 20–40 threads, which is where
   a hotspot router saturates anyway; going much higher is limited by the
   router, not by the client.

---

## 12. Testing it without touching a real network

Everything can be exercised on loopback. A ~40-line `http.server` handler that
serves a fake login page, replies `invalid username or password` for a wrong
card and `302 → /status` for the right one is enough to drive the whole wizard,
the walk, the coverage counters and the report. This is how the current code was
verified: with a space of 100 combinations and a prefix of `test12`, the run
found `test1234`, saved `kirapass_profiles.json`, and the next run resumed at
`pos = 93` instead of starting over.

---

## 13. What changed since the first analysis

The earlier revision of this document reviewed the original script (then
`layer_3.py`) and listed its defects. Where each one stands in v3.2:

| Old problem | Status in v3.2 |
|-------------|----------------|
| `random.sample` crashing / repeating cards | **Fixed** — bijective full-cycle walk, no repetition, no `ValueError` |
| GET only, no POST, no hidden fields | **Fixed** — GET and POST, configurable field names, optional `dst`/`popup` |
| Single-threaded with `sleep(0.5)` | **Fixed** — thread pool with a bounded queue, no artificial delay |
| Progress bar destroyed by per-attempt printing | **Fixed** — one dedicated progress thread with `\r` redraw |
| Any non-200 treated as connection error | **Fixed** — status codes are recorded, redirects are followed, failures are classified |
| No `User-Agent` / browser headers | **Fixed** — full browser header set + keep-alive sessions |
| Success detection based on a single keyword | **Improved** — learned signature/URL, `/status` in URL *or* history, explicit failure sentences, keyword last |
| No diagnosis when everything errors out | **Improved** — 15 error kinds, latency percentiles, per-kind verdict, honest coverage counters |
