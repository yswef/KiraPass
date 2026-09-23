# KiraPass 5 — full user guide (plain English)

Everything here is written without jargon. Each step says what it does, why it
exists, and what to do when it does not work.

---

## 0) Before you start

1. **Permission:** the network is yours, or you hold written permission from
   its owner. Otherwise do not use the tool.
2. **You are on the guest network** you want to test (the one whose login page
   opens in your browser).
3. **Optional but recommended - train first:**
   ```bash
   python3 tools/practice_portal.py --card 0201240007
   ```
   That starts a fake portal on your own machine. Point the tool at
   `http://127.0.0.1:8899/login` and watch what every message means. Nothing
   real is touched.

---

## 1) Start it

```bash
python3 KiraPass.py
```

It prints a local link such as `http://127.0.0.1:8770/` — open it. Everything
after that happens in the page; no terminal commands, no long question list.

**Why a web page instead of a terminal menu?** The old version asked 9 menu
choices and up to 12 questions; answering them wrongly silently produced
meaningless results. The page shows options with explanations, previews the
cards it is about to try, and works with taps on a phone.

---

## 2) Step 1 — scan

Paste the hotspot login URL exactly as you see it in the browser
(`http://10.5.50.1/login`), press **Scan now**. The tool reports:

* **Internet state** — *actually online* (you are already outside the portal),
  *behind the portal* (the normal state before testing), *offline*, or *blocked*.
* **Form action + method (POST/GET)** — read from the page itself, so no `F12`.
* **Field names** — username, password, hidden `dst`/`popup` values.
* **MikroTik MD5 (chap) detection** — if the page uses `md5.js`, the tool says
  so and will send the correct hashed value automatically.

## 3) Step 2 — card format

| Field | Meaning | Example |
|---|---|---|
| Fixed prefix | digits that never change | `020124` |
| Full card length | digits on the printed card | `10` |
| Variable characters | digits, hex, letters… | digits |
| Password value | what to send as the password | empty / same as card |

The preview shows the **number of combinations** and **sample cards**: check
that they look exactly like your real cards. A wrong shape makes every result
meaningless, so this preview exists on purpose.

**Password value options:** empty (most card networks), same as card, omit the
field, a fixed value, MikroTik chap (auto-detected), or MD5 of the card.

**A card you know works** — the most valuable optional field: give the tool one
valid card and press *Learn from the known card*. It finds the exact request
shape, learns the success words, and logs the card out afterwards so you do not
consume it.

## 4) Step 3 — run

Three presets (safe / normal / fast), threads, attempts, delay, "verify
internet", "auto-stop", "continue where you stopped". Tick the authorization
box — the start button stays disabled without it. **Diagnose the network
first** runs a handful of requests and explains whether the link is clean,
whether you are already blocked, and how many threads are safe.

## 5) Step 4 — reading the results

Every attempt is classified, colour-coded and explained:

| Result | What actually happened | What to do |
|---|---|---|
| **Accepted & verified** | the router let the card through *and* a real external page loaded | valid card |
| **Accepted** | a redirect out of the portal (strong evidence) | confirm in a browser |
| **Accepted, unverified** | the router accepted, but the internet proof was not possible (you were already online, or the network blocks the check) | open the portal status page, or retest from the walled state |
| **Rejected** | byte-identical to the rejection page | keep going |
| **Unclear reply** | different, but nothing proves acceptance | open the saved page in *review pages* and read it |
| **Blocked by router** | an explicit block page | stop, change IP, use the safe preset |
| **Rate limited** | 429 / "slow down" | the tool slowed itself down and told you why |
| **Network error** | cut connection, refused, timeout, DNS | the exact kind is shown; retried automatically |

Live counters, latency, current slowdown (with reason), a per-attempt log, the
accepted cards, the review pages, and a **"why it stopped"** panel with the real
reason and what to do next.

### The "why each attempt ended the way it did" table

Under the counters there is a histogram of every verdict reason
(`same_as_rejection_page_exact`, `rejection_wording`, `reset`, ...) with counts.
It is copied into every run report, so you can explain a session weeks later.

### When the internet check itself is blocked

Some networks block the three well-known probe sites (google / msft / apple).
Point the check at a URL your network allows:

```bash
KIRAPASS_INTERNET_CHECKS="http://example.com/generate_204|204" python3 KiraPass.py
# format: url|expected_status|optional_text, separated by commas
```

Without it, successes stay "accepted" or "unverified accept" - still true, just
less certain.

## 6) Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| everything rejected | correct shape, no valid card in that range | widen the range (longer length) or another prefix |
| many "unclear reply" | the portal page changes a lot | run diagnostics, and use a known-good card so the shape is learned |
| blocked after a while | the router protects itself | restart the router / reconnect for a new IP, safe preset, add delay |
| offline mid-run | wifi dropped or router rebooted | reconnect; the run resumes where it stopped |
| stops after 1–2 attempts | (in the old version: a bug) now every stop has a printed reason | read "why it stopped" |

## 7) FAQ

**Is this cracking user passwords?** No. It tries guest access codes inside a
range you define on a network you own, to measure how strong those codes are.

**Phones?** Android via Termux/Pydroid with `--host 0.0.0.0` (prints a token for
the phone's browser). iPhone: not supported.

**Does it need internet or extra libraries?** No libraries at all. The internet
is only used by the optional verification check.

**Does it send my data anywhere?** No. Everything stays on your machine in
`kirapass_data/`.

**Clear the cache:**
```bash
python3 KiraPass.py --clear-cache [temp|results|profiles|all]
```

**Trust check:**
```bash
python3 KiraPass.py --selftest     # 13 scenarios against local mock routers
```
