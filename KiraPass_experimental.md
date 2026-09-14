# KiraPass experimental — live hotspot dissection & CHAP/hexMD5 diagnosis

Version **0.1-exp** · entry point `KiraPass_experimental.py` · standard library only
(no `requests`, no `bs4`, nothing to `pip install`).

This file exists for one reason: **the previous hand-extraction could not be
trusted**, so instead of writing a tool on top of assumptions, this script goes
to the live page, reads it, and prints what is really there.

`KiraPass.py` is **not touched** by any of this. `KiraPass_experimental.py` never
imports it and does not modify it.

> ⚠️ Use it only on a network you own or manage, or one you have written
> permission to test. Every "attempt" is one real login request.

---

## 1. Run it

```bash
# interactive (asks for the URL and what to do)
python3 KiraPass_experimental.py

# read-only: page + scripts + JS + fact-check  (sends no login)
python3 KiraPass_experimental.py --url http://10.10.10.10/login --dissect

# read-only + 2 attempts with random wrong data (proves the shape works)
python3 KiraPass_experimental.py --url http://10.10.10.10/login --probe

# with your own real card + keep watching the network for 5 minutes
python3 KiraPass_experimental.py --url http://10.10.10.10/login \
        --probe --login --user 1234 --pass abcd --watch 5

# pack the last run into ONE pasteable text block (no network at all)
python3 KiraPass_experimental.py --collect
```

Everything is written to `KiraPass_experimental_out/` (git-ignored):

| File | What it is |
|------|------------|
| `report_<stamp>.txt` | the text report: every step, every warning, every error |
| `login_page.html` | the raw page, exactly as the router served it |
| `login_page_2nd_load.html` | the second load (used for the rotating-salt question) |
| `md5.js` (any external script) | the real hash code, for the record |
| `bundle_<stamp>.txt` | everything above in one block (`--collect`) |

Exit code: `0` = no errors, `1` = at least one error was reported, `2` = no URL.

---

## 2. What it actually checks

| # | Step | Question it answers |
|---|------|---------------------|
| 1 | fetch the page | is it reachable, does it redirect, does a portal intercept |
| 2 | dissect the HTML | every `<form>` (name/id/method/action/onSubmit), every field with all attributes, buttons, duplicate `id`s, which fields are created later by `document.write` |
| 3 | read the scripts | fetches `/md5.js` (or whatever the page loads) and reports `chrsz`, `hexcase`, `charCodeAt & mask`, and the body of `hexMD5` |
| 3b | second page load | is the challenge **fixed** or **rotates on every load** — the difference decides whether one hash can be reused at all |
| 4 | decode the hash call | `hexMD5('\043' + document.login.password.value + '\247…')` → real bytes (`23`, `a7 b3 46 …`) |
| 5 | fact check | every claim of the previous extraction → `CONFIRMED` / `DIFFERS` / `MISSING`, with the live value next to it |
| 6 | attempts | real POST/GET, full redirect chain, HTTP codes, failure/success words, cookies |
| 7 | network check | captive-portal test before/after, so you *see* the network open |
| 8 | report | text file + `ERRORS`/`WARNINGS` summary + one pasteable bundle |

### The fact-check section

It never asks you to trust it. Each line prints the live value:

```
 ✓ CONFIRMED form "sendin" exists
 ✓ CONFIRMED sendin: method is post   [found 'post']
 ⚠ DIFFERS   sendin: fields = username, password, dst, popup
             [found [username, password, dst, popup, speed, update, facebook]
              extra=['speed', 'update', 'facebook']]
 ⚠ WARNING : the old extraction said "sendin" has NO other elements, but the
             live page has extra field(s): speed, update, facebook — the old
             extraction was INCOMPLETE
```

### What the tool refuses to do

- **It never invents a salt.** If the page has no `hexMD5(...)` call, it says so
  and stops; it does not fall back to the salt quoted in the old file.
- **It never picks a `domain` value at random.** `domain` / `Hspeed` /
  `checkbox1` are only reported as *present in the form*; the tool does not send
  a guessed value for them, and it does not claim they are required.
- **It does not claim a credential is wrong when the reply is ambiguous** — it
  warns and tells you to read the saved HTML by hand.
- **It always prints the bytes it used**, so you can check the math yourself.

---

## 3. The one result that changes everything

If section **3b** says the challenge rotates, then a fixed `hexMD5` salt is
worthless: the router hands out a new salt on every page load, and a hash
computed once is only valid for the page load that produced it. Sending one
old salt thousands of times is rejected exactly like a wrong password — and
you could never tell it apart from an expired card. The tool reports this as an
**ERROR**, not as a footnote.

The tool also answers the second half of that question by observation, not by
argument: it runs the captive-portal check **before** and **after** an attempt
with your own card, and if the network goes `CAPTIVE → OPEN`, then the whole
chain (URL + form + fields + hash + credentials) is proven correct end to end.

---

## 4. Files

| File | Role |
|------|------|
| `KiraPass_experimental.py` | the diagnosis tool (this document's subject) |
| `KiraPass_experimental.md` | this file |
| `tests/fake_hotspot.py` | a fake MikroTik-style hotspot for offline testing, with 5 variants |
| `tests/test_offline.py` | 32 checks: dissection, hash decode, fact-check, real attempt, network flip, bundle |
| `tests/test_negatives.py` | 13 checks: rotating salt, no hash, uppercase hex, missing fields |
| `tests/run_all.py` | runs both suites |
| `KiraPass_experimental_out/` | run artifacts (git-ignored) |

```bash
python3 tests/run_all.py        # 45 checks, no real network is touched
```

The offline suite is not decoration: the fake hotspot **validates the hash**
the tool sends, so a wrong byte in `hexMD5` makes the test fail. That is how the
`#` prefix byte and the 16-byte salt were verified as bytes, not as text.

---

## 5. Known limits

1. **The salt's lifetime is not fully known.** The tool tells you whether it is
   fixed or rotating. If it rotates, the run logic (fetch → hash → send for each
   attempt, or one page load per batch) still has to be designed — that is the
   next step, not this one.
2. **No JS engine.** The tool reads `hexMD5`'s semantics from the code
   (`chrsz`, `charCodeAt`, `hexcase`); it does not execute the page. If a page
   obfuscates its hash code, the tool says so instead of guessing.
3. **One attempt per shape, on purpose.** The probes prove the shape; they do
   not search. Searching stays in `KiraPass.py` / a future module once the
   shape is proven.
4. **`domain` / `Hspeed` / `checkbox1`** are described, never guessed. If the
   router needs them, you will see it in the reply of a real attempt with a
   valid card.
