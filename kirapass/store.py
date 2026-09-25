"""Profiles, settings, reports and the "clear cache" logic - all in one place.

Profiles from the old version are **migrated automatically** instead of
crashing.  That KeyError('charset') crash is one of the reasons the tool
"stopped working" for a user who only replaced the .py file: the saved profile
on disk was written by an older version.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import time

from . import config

SCHEMA = 5
CHARSETS = {
    "digits": "0123456789",
    "lower": "abcdefghijklmnopqrstuvwxyz",
    "upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "alnum": "0123456789abcdefghijklmnopqrstuvwxyz",
    "alnum_upper": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "hex": "0123456789abcdef",
    "hex_upper": "0123456789ABCDEF",
}
PASS_MODES = ("same", "empty", "omit", "fixed", "chap", "chap_empty",
              "md5user")


def ensure_dirs() -> None:
    for d in config.ALL_DIRS:
        os.makedirs(d, exist_ok=True)


def atomic_write(path: str, text: str) -> None:
    """Write a file so that a reader never sees half of it.

    Tolerates the folder being deleted at the same moment (the user pressing
    "clear cache" while a run is saving something).
    """
    for attempt in range(2):
        try:
            ensure_dirs()
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
            return
        except OSError:
            if attempt:
                return


def read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def clean(name: str, limit: int = 60) -> str:
    name = re.sub(r"[^A-Za-z0-9_\u0600-\u06FF .-]+", "_", (name or "").strip())
    return name[:limit] or "profile"


# ---------------------------------------------------------------------------
# profile helpers (pure functions - easy to test)
# ---------------------------------------------------------------------------
def new_profile(**kw) -> dict:
    p = {
        "schema": SCHEMA,
        "name": "",
        "login_url": "",
        "method": "post",
        "user_field": "username",
        "pass_field": "password",
        "pass_mode": "empty",
        "pass_fixed": "",
        "extra_fields": {},
        "dst_field": "dst",
        "dst_value": "",
        "send_dst": True,
        "popup_field": "popup",
        "send_popup": True,
        "chap": None,
        "charset": CHARSETS["digits"],
        "length": 10,
        "prefix": "",
        "suffix": "",
        "space_pos": 0,
        "space_pass": 0,
        "walk_a": 0,
        "walk_b": 0,
        "note": "",
        "success_words": [],
        "success_url_contains": "",
    }
    p.update(kw)
    return p


def variable_len(p: dict) -> int:
    return int(p.get("length", 0)) - len(p.get("prefix", "")) - \
        len(p.get("suffix", ""))


def space_size(p: dict) -> int:
    vlen = variable_len(p)
    chars = len(set(p.get("charset", "")))
    if vlen <= 0 or chars < 2:
        return 0
    return chars ** vlen


def validate(p: dict) -> list:
    """-> list of machine-readable problems (empty = good to go)."""
    problems = []
    if not (p.get("login_url") or "").startswith(("http://", "https://")):
        problems.append("url_missing_or_invalid")
    if not p.get("user_field"):
        problems.append("user_field_missing")
    vlen = variable_len(p)
    if vlen <= 0:
        problems.append("length_not_bigger_than_prefix_and_suffix")
    if len(set(p.get("charset") or "")) < 2:
        problems.append("charset_too_small")
    if p.get("pass_mode") not in PASS_MODES:
        problems.append("unknown_pass_mode")
    if p.get("pass_mode") == "fixed" and not p.get("pass_fixed"):
        problems.append("fixed_password_empty")
    if len(set(p.get("charset") or "")) ** max(vlen, 1) > config.BIG_SPACE:
        problems.append("space_is_astronomically_big")   # warning, not a blocker
    return problems


def decode_card(p: dict, index: int) -> str:
    charset = p.get("charset", "")
    vlen = variable_len(p)
    base = len(set(charset))
    chars = sorted(set(charset))
    out = []
    for _ in range(vlen):
        out.append(chars[index % base])
        index //= base
    return p.get("prefix", "") + "".join(out) + p.get("suffix", "")


def sample_cards(p: dict, count: int = 3) -> list:
    space = space_size(p)
    if space <= 0:
        return []
    picks = {0, space // 2, space - 1, space // 3}
    return [decode_card(p, i) for i in sorted(picks)][:count]


def card_at_walk_pos(p: dict, pos: int) -> str:
    """Shuffled but repeat-free walk over the whole space."""
    space = space_size(p)
    if space <= 1:
        return decode_card(p, 0)
    a = int(p.get("walk_a", 0)) % space
    b = int(p.get("walk_b", 0)) % space
    if a == 0:
        a = 1
    idx = (b + a * pos) % space
    return decode_card(p, idx)


def migrate(raw: dict) -> dict:
    """Accept a profile written by ANY older version of the tool."""
    if not isinstance(raw, dict):
        return new_profile()
    p = new_profile()
    p.update({k: v for k, v in raw.items() if k in p})

    nt = str(raw.get("network_type", "1"))
    prefix = raw.get("prefix", p["prefix"]) or ""
    suffix = raw.get("suffix", p["suffix"]) or ""
    charset = raw.get("charset") or p["charset"]
    vlen = raw.get("var_len")
    if vlen:
        length = int(vlen) + len(prefix) + len(suffix)
    else:
        length = int(raw.get("length", p["length"]) or p["length"])

    if nt == "3":
        # old "username + different password" profiles: keep the username
        # shape, the password side becomes a fixed/derived value.
        prefix = raw.get("u_prefix", prefix) or ""
        suffix = raw.get("u_suffix", suffix) or ""
        charset = raw.get("u_charset", charset) or charset
        length = int(raw.get("u_len", 0) or 0) + len(prefix) + len(suffix) or length
        p["pass_mode"] = "fixed"
    elif nt == "2" and raw.get("pass_mode") in (None, "same"):
        p["pass_mode"] = "same"
    elif p.get("pass_mode") in (None, ""):
        p["pass_mode"] = "empty"

    p.update({
        "charset": charset,
        "length": max(length, len(prefix) + len(suffix) + 1),
        "prefix": prefix,
        "suffix": suffix,
        "method": "post" if str(raw.get("method", "2")) in ("2", "post") else "get",
        "send_dst": bool(raw.get("extras", True)),
        "send_popup": bool(raw.get("extras", True)),
        "dst_value": raw.get("dst_value", ""),
        "dst_field": raw.get("dst_field") or "dst",
        "popup_field": raw.get("popup_field") or "popup",
        "extra_fields": raw.get("fixed_fields") or raw.get("extra_fields") or {},
        "success_words": raw.get("success_signature") or raw.get("success_words") or [],
        "success_url_contains": raw.get("success_url_contains", "") or "",
        "space_pos": int(raw.get("space_pos", 0) or 0),
        "schema": SCHEMA,
    })
    if (raw.get("walk") or {}).get("pos"):
        p["space_pos"] = int(raw["walk"]["pos"])
    return p


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------
class Store:
    def __init__(self):
        ensure_dirs()
        self.path = config.PROFILES_FILE
        self._profiles = self._load()
        self.settings = read_json(config.SETTINGS_FILE, {}) or {}

    # -- profiles ---------------------------------------------------------
    def _load(self) -> dict:
        raw = read_json(self.path, {})
        out = {}
        if isinstance(raw, dict) and "profiles" in raw:
            items = raw.get("profiles") or []
        elif isinstance(raw, list):
            items = raw
        else:
            items = [raw] if raw else []
        for item in items:
            try:
                prof = migrate(item)
            except Exception:
                continue
            name = clean(prof.get("name") or "")
            if not name or name == "profile":
                name = clean(prof.get("login_url", "profile").split("//")[-1])
            prof["name"] = name
            out[name] = prof
        return out

    def save(self) -> None:
        payload = {"schema": SCHEMA, "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "profiles": list(self._profiles.values())}
        atomic_write(self.path, json.dumps(payload, ensure_ascii=False, indent=2))

    def all(self) -> list:
        return sorted(self._profiles.values(), key=lambda x: x.get("name", ""))

    def get(self, name: str):
        return self._profiles.get(clean(name))

    def put(self, profile: dict) -> dict:
        prof = migrate(profile)
        name = clean(prof.get("name") or
                     prof.get("login_url", "profile").split("//")[-1])
        if name == "profile":
            name = f"profile-{len(self._profiles) + 1}"
        prof["name"] = name
        self._profiles[name] = prof
        self.save()
        return prof

    def delete(self, name: str) -> bool:
        prof = self._profiles.pop(clean(name), None)
        if prof:
            self.save()
            return True
        return False

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value) -> None:
        self.settings[key] = value
        atomic_write(config.SETTINGS_FILE, json.dumps(self.settings,
                                                      ensure_ascii=False, indent=2))

    # -- reports / review pages ------------------------------------------
    def save_review(self, seq: int, card: str, verdict: dict, body: str) -> dict:
        ensure_dirs()
        name = f"{int(time.time())}_{seq:05d}_{clean(card, 24)}.html"
        path = os.path.join(config.REVIEW_DIR, name)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body[:400000])
        except OSError:
            return {}
        try:
            index = read_json(os.path.join(config.REVIEW_DIR, "index.json"), [])
            index.append({"file": name, "card": card,
                          "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
                          **{k: verdict.get(k)
                             for k in ("code", "reason", "data")}})
            atomic_write(os.path.join(config.REVIEW_DIR, "index.json"),
                         json.dumps(index[-500:], ensure_ascii=False, indent=2))
        except OSError:
            pass
        return {"file": name, "card": card, "reason": verdict.get("reason"),
                "data": verdict.get("data")}

    def list_review(self) -> list:
        index = read_json(os.path.join(config.REVIEW_DIR, "index.json"), [])
        return list(reversed(index))

    def read_review(self, name: str) -> str:
        safe = os.path.basename(name)
        path = os.path.join(config.REVIEW_DIR, safe)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""

    def save_run(self, report: dict) -> str:
        ensure_dirs()
        name = time.strftime("%Y%m%d_%H%M%S") + "_" + clean(report.get("profile", "run"), 24)
        path = os.path.join(config.RUN_DIR, name + ".json")
        atomic_write(path, json.dumps(report, ensure_ascii=False, indent=2))
        return path

    def append_hit(self, line: str) -> None:
        ensure_dirs()
        with open(config.HITS_FILE, "a", encoding="utf-8") as fh:
            fh.write(line.rstrip() + "\n")

    # -- cache ------------------------------------------------------------
    def cache_info(self) -> dict:
        info = {"folders": {}, "files": {}, "total_bytes": 0}
        for label, folder in (("review", config.REVIEW_DIR),
                              ("runs", config.RUN_DIR),
                              ("cache", config.CACHE_DIR),
                              ("logs", config.LOG_DIR)):
            size, count = _dir_size(folder)
            info["folders"][label] = {"files": count, "bytes": size,
                                      "path": folder}
            info["total_bytes"] += size
        for path in (config.HITS_FILE,) + config.LEGACY_FILES:
            if os.path.exists(path):
                size = os.path.getsize(path)
                info["files"][os.path.basename(path)] = size
                info["total_bytes"] += size
        prof = config.PROFILES_FILE
        info["profiles"] = {"file": os.path.basename(prof),
                            "count": len(self._profiles),
                            "bytes": os.path.getsize(prof) if os.path.exists(prof) else 0}
        return info

    def clear_cache(self, scope: str = "temp") -> dict:
        """Delete tool data by scope.

        temp     -> saved review pages + cache folders (never the hits log)
        results  -> run reports, logs and hits.txt
        profiles -> profiles.json
        all      -> everything above + legacy files from the old version
        """
        removed, freed = [], 0
        targets = []
        if scope in ("temp", "all"):
            targets += [config.CACHE_DIR, config.REVIEW_DIR]
        if scope in ("results", "all"):
            # the hits log belongs to the results, not to the "temp" cleanup:
            # clearing the cache must never quietly delete found cards
            targets += [config.RUN_DIR, config.LOG_DIR, config.HITS_FILE]
        always = []
        if scope == "all":
            always += list(config.LEGACY_FILES)
            targets += [config.DATA_DIR]
        for path in targets + always:
            if not os.path.exists(path):
                continue                      # never list what was not there
            freed += _remove_path(path)
            removed.append(os.path.basename(path))
        if scope in ("profiles", "all") and os.path.exists(config.PROFILES_FILE):
            try:
                os.remove(config.PROFILES_FILE)
                removed.append(os.path.basename(config.PROFILES_FILE))
                self._profiles = {}
            except OSError:
                pass
        # python bytecode caches of the tool itself
        for pattern in ("**/__pycache__", "__pycache__"):
            for path in glob.glob(os.path.join(config.BASE_DIR, pattern),
                                  recursive=True):
                size, _ = _dir_size(path)
                shutil.rmtree(path, ignore_errors=True)
                freed += size
                removed.append(os.path.relpath(path, config.BASE_DIR))
        ensure_dirs()
        return {"scope": scope, "removed": sorted(set(removed)),
                "freed_bytes": freed, "freed_human": human_size(freed)}


def _dir_size(path: str) -> tuple:
    total, count = 0, 0
    if not os.path.isdir(path):
        return 0, 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
                count += 1
            except OSError:
                continue
    return total, count


def _remove_path(path: str) -> int:
    """Delete a file or a folder and return the bytes really freed.

    `shutil.rmtree(..., ignore_errors=True)` silently does nothing when handed
    a *file* - which is how the old code managed to list hits.txt as "removed"
    without removing it.  This helper never lies about what it did.
    """
    if os.path.isdir(path) and not os.path.islink(path):
        size, _ = _dir_size(path)
        shutil.rmtree(path, ignore_errors=True)
        return size
    try:
        size = os.path.getsize(path)
        os.remove(path)
        return size
    except OSError:
        return 0


def human_size(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} GB"


def load_legacy_profiles() -> list:
    """Import profiles written by the old version, if any exist."""
    out = []
    for path in (config.LEGACY_FILES[1], config.LEGACY_FILES[2]):
        raw = read_json(path, None)
        if not raw:
            continue
        items = raw if isinstance(raw, list) else raw.get("profiles", [raw])
        for item in items or []:
            try:
                out.append(migrate(item))
            except Exception:
                continue
    return out
