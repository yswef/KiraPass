# ═══════════════════════════════════════════
#  KiraPass v3.2 — User Manual
#  Developer : ENG.YOUSEF
# ═══════════════════════════════════════════

**KiraPass** is a terminal tool that tests the login page of a Mikrotik hotspot:
it builds every card / username / password combination that matches the shape you
describe, sends them to the login page in parallel, and tells you which one was
accepted — plus a full report about the link itself (errors, latency, HTTP codes).

Everything the tool prints is in **English**.

> ⚠️ **Use it only on a network you own or manage, or one you have written
> permission to test.** Guessing credentials on somebody else's network is
> unauthorized access and is illegal in most countries. The intended use is
> checking your own voucher/card scheme (how guessable it is, whether the
> hotspot answers correctly, how many threads your router can take).

---

## 📋 Requirements

    Python 3.8+
    pip install requests
    pip install urllib3

---

## 🚀 Running it

    python3 KiraPass.py

On Windows:

    py KiraPass.py

---

## 🧭 Main menu

    ┌──────────────── Main Menu ────────────────┐
     1) Use saved profile
     2) New profile + save
     3) Manage profiles
     0) Exit
    └───────────────────────────────────────────┘

A **profile** is one saved network: its login URL, the request shape, the card
shape, and how far the tool already got. Profiles are stored in
`kirapass_profiles.json` next to the script.

| Option | What it does |
|--------|--------------|
| **1) Use saved profile** | Pick a saved network and start testing again. It continues from where the last run stopped — it never repeats a card it already tried. |
| **2) New profile + save** | Full setup wizard: URL → method → card shape → threads → success detection → save → run. |
| **3) Manage profiles** | List saved profiles and delete one. |
| **0) Exit** | Quit. |

---

## 📖 Every prompt, explained

═══════════════════════════════════════════
 **Login URL**
═══════════════════════════════════════════

What to type: the hotspot login page address.

    http://10.5.50.1/login
    http://192.168.88.1/login.html
    http://hotspot.mynetwork.com/login

How to find it: open your browser and visit any website while connected to the
hotspot — you get redirected to the login page. Copy the address from the bar.

KiraPass immediately tests the URL and prints
`✓ Connected! (HTTP 200, 2 ms)` or a classified error with a hint.

═══════════════════════════════════════════
 **Method: GET or POST**
═══════════════════════════════════════════

    1) GET  → the data shows up in the URL
    2) POST → the data is hidden (newer)

100% reliable way to know:

1. Open the login page in a browser.
2. Press **F12** → tab **Elements**.
3. Find `<form` and read `method="..."`:
   - `method="post"` → choose **2 (POST)**
   - `method="get"` → choose **1 (GET)**

Quick check: log in normally once and watch the address bar. If you can see
`username=xxx&password=xxx` in the URL, it is **GET**.

Rule of thumb: older Mikrotik firmware → usually GET, newer → usually POST.

═══════════════════════════════════════════
 **Field names (POST only)**
═══════════════════════════════════════════

The `name=` attributes of the HTML inputs. With F12 → Elements look for:

    <input name="username">
    <input name="password">

The value between the quotes is what you type. Press **Enter** to keep the
defaults. Common names on Mikrotik:

- `username` / `user` / `usr`
- `password` / `pass` / `pwd`
- `dst` (usually empty), `popup` (`true` / `false`)

KiraPass can also send the hidden Mikrotik fields `dst` and `popup`
(`Send Mikrotik hidden fields (dst/popup)?`).

═══════════════════════════════════════════
 **Network type**
═══════════════════════════════════════════

    1) username only (card / code)
    2) username = password
    3) username + password (different)

| Type | Meaning | Typical case |
|------|---------|--------------|
| **1** | Only a card/code, no separate password | café / voucher cards |
| **2** | The card is sent as both username and password | older voucher schemes |
| **3** | Username and password are two different values | the largest search space |

═══════════════════════════════════════════
 **Characters, length, prefix, suffix**
═══════════════════════════════════════════

    1) only numbers   (0-9)
    2) only letters   (a-z)
    3) both           (0-9 a-z)

Then:

- **Full card length** — the total length of the card, prefix included.
- **Prefix** — a fixed beginning, e.g. `NET`.
- **Suffix** — a fixed ending, if any.

The tool only varies what is left. Example: full length **8**, prefix `test12`
→ 2 variable digits → **100** combinations (`test1200` … `test1299`).

Prefix + suffix must be shorter than the full length, otherwise you get
`✗ Prefix+Suffix is longer than the full length!`.

═══════════════════════════════════════════
 **Threads**
═══════════════════════════════════════════

How many requests fly at the same time.

| Threads | Result |
|---------|--------|
| 5–10    | very safe, slow |
| 15–20   | balanced (default 20) |
| 30–40   | fast, may stress a small router |
| 50+     | likely ban / heavy errors, not recommended |

More threads on a home hotspot router usually means **more errors and less
speed**, not more speed — the router is the bottleneck. Above 60 threads the
tool warns you.

═══════════════════════════════════════════
 **Success detection**
═══════════════════════════════════════════

How does KiraPass know a card worked? In this order:

1. a **learned success page** (word signature or URL) if you taught it one;
2. a redirect to `/status`;
3. known failure sentences on the page ("invalid username or password", …);
4. your **Success Keyword** anywhere in the page or the final URL.

- **Success Keyword** — press Enter to accept the default `status`, which works
  on almost every Mikrotik hotspot. To find your own: log in manually, press
  **Ctrl+U**, and pick a word that only appears after a successful login
  (`logged in`, `welcome`, `connected`).
- **Teach me the SUCCESS page now?** — say `y` and log in once with credentials
  you know are valid. KiraPass compares that page with a failed login and learns
  the difference by itself. This is the most accurate mode, and it is saved in
  the profile.

═══════════════════════════════════════════
 **Attempts**
═══════════════════════════════════════════

How many combinations to try in this run. The prompt shows the size of the
whole space, e.g. `(space 100, Enter = cover all 100)`.

If you ask for more attempts than there are combinations, the run is capped:

    ⚠ The whole space is only 100 combinations — the run was capped at 100
      attempts so it covers every combination without repeating them

---

## 📊 Reading the output

**While it runs** — a live progress bar:

    [======--------------]  30.0%  | 30/100  | Err:0  | 114.0/s

`Err:N` counts *connection* errors only. An expired or wrong card is not an
error: it is a normal HTTP reply that counted as tested.

**When a card works:**

    ╔══════════════════════════════════════════╗
    ║        ✓ SUCCESS — FOUND CREDENTIALS     ║
    ╚══════════════════════════════════════════╝
       Target   : http://10.5.50.1/login
       Card/Code : test1234
       Tested   : 82 attempts
       Errors   : 0
       Time     : 0m 0s

**COVERAGE** — how much of the space you have really covered:

    COVERAGE
       Full search space        : 100 combinations
       Starting position        : 0
       Distinct cards tested    : 93 (no repetition)
       Total HTTP requests      : 82 (includes resent failures)
       Cards never delivered    : 0 (every retry failed)
       HTTP replies read        : 82
       Cumulative coverage      : 93 / 100 = 93.00%

**ERROR BREAKDOWN** — every connection error, classified, with a hint, plus
latency (`avg` / `p95` / `max`) and the HTTP status codes seen.

**VERDICT** — one of:

| Verdict | Meaning |
|---------|---------|
| `✓ Error rate looks healthy` | the link is fine |
| `▲ Most errors were stale keep-alive connections` | harmless, auto-retried |
| `▲ Errors are timeouts → the router is overloaded` | lower the threads |
| `▲ Connections are being reset/refused by the router` | Mikrotik HTTP connection limit |
| `▲ Network-level failures dominate` | your path to the router is unreliable |
| `✗ The target stopped answering` | you left the network or the router is gone |

**✗ NOT FOUND** — the space was not exhausted: re-run with the same settings and
it resumes from where it stopped. If the space *was* exhausted, the tool tells
you the remaining suspects (request shape, the card itself, success detection)
instead of asking you to guess again.

---

## 🩺 Connection error kinds

| Kind | What it means |
|------|---------------|
| `stale_keepalive` | the server closed a reused keep-alive connection — not a ban, not an expired card (auto-retried) |
| `conn_reset` | the router sent RST — usually the Mikrotik HTTP server connection limit |
| `conn_refused` | port closed — hotspot http service stopped, or a drop rule |
| `conn_timeout` | no reply at all — Wi-Fi/router problem, or a drop rule |
| `read_timeout` | the router was late to answer — overload or slow RADIUS |
| `connect_timeout` | TCP connection could not be opened — link down or dropped |
| `dns` | name resolution failed — the link is down |
| `unreachable` | no route to host — you left the hotspot network |
| `ssl` | TLS problem — usually http against https |
| `proxy` | proxy interference |
| `redirect_loop` | redirect loop |

The tool gives up on a target only after **25** consecutive errors *and* either
it never answered at all, or it has been silent for **6 s**.

---

## 🗂 Files

| File | What it is |
|------|------------|
| `KiraPass.py` | the tool |
| `KiraPass_extras.py` | optional extra checks, run separately — the main tool does not use it |
| `kirapass_profiles.json` | saved profiles — created automatically, safe to delete |
| `README.md` | this manual |
| `KiraPass_Documentation.md` | technical documentation (architecture, data model, algorithms) |

Profiles written by the old `mikrotikbf_profiles.json` name are still read
automatically after the rename.

---

## 🔧 Troubleshooting

- **`✗ Cannot reach target`** — check you are connected to that hotspot, that
  the URL is the real login page, and that nothing blocks the port.
- **Nothing is ever found, but the cards are valid** — the request shape is
  wrong. Re-check GET vs POST with F12, the field names, and try sending
  `dst`/`popup`.
- **Success is found manually but not by the tool** — teach the success page, or
  set a Success Keyword that only appears after login.
- **Lots of `read_timeout`** — lower the threads (try half).
- **Errors grow when threads grow** — the router is the bottleneck; fewer
  threads are faster in practice.
- **You have one valid card and nothing works** — run
  `python3 KiraPass_extras.py` → option **1**. It sends that card in every
  request shape and tells you whether the problem is the shape, the success
  detection, or the card.
- **You want to measure the link without guessing anything** — run
  `python3 KiraPass_extras.py` → option **2** (read-only: latency, errors,
  HTTP codes).
