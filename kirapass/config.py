"""Paths, defaults and constants for KiraPass.

Everything the tool writes on disk lives in one of the folders below, so the
"clear cache" button can clean the whole tool in one shot and nothing is
scattered around the project.
"""

from __future__ import annotations

import os

APP_NAME = "KiraPass"
VERSION = "5.0"

# --------------------------------------------------------------------------
# Folders
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "kirapass_data")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
HITS_FILE = os.path.join(DATA_DIR, "hits.txt")
RUN_DIR = os.path.join(DATA_DIR, "runs")          # one report per run
REVIEW_DIR = os.path.join(DATA_DIR, "review")     # pages we could not judge
CACHE_DIR = os.path.join(DATA_DIR, "cache")       # learned pages / temporary
LOG_DIR = os.path.join(DATA_DIR, "logs")

ALL_DIRS = (DATA_DIR, RUN_DIR, REVIEW_DIR, CACHE_DIR, LOG_DIR)


def set_data_dir(path: str) -> str:
    """Point every file the tool writes at another folder.

    The self-test uses this so `KiraPass.py --selftest` can never mix its
    practice cards into the user's real profiles, hits or reports.
    """
    global DATA_DIR, PROFILES_FILE, SETTINGS_FILE, HITS_FILE
    global RUN_DIR, REVIEW_DIR, CACHE_DIR, LOG_DIR, ALL_DIRS
    DATA_DIR = os.path.abspath(path)
    PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")
    SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
    HITS_FILE = os.path.join(DATA_DIR, "hits.txt")
    RUN_DIR = os.path.join(DATA_DIR, "runs")
    REVIEW_DIR = os.path.join(DATA_DIR, "review")
    CACHE_DIR = os.path.join(DATA_DIR, "cache")
    LOG_DIR = os.path.join(DATA_DIR, "logs")
    ALL_DIRS = (DATA_DIR, RUN_DIR, REVIEW_DIR, CACHE_DIR, LOG_DIR)
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR

# Legacy files from the old version - removed by "clear cache".
LEGACY_FILES = (
    os.path.join(BASE_DIR, "kirapass_hits.txt"),
    os.path.join(BASE_DIR, "mikrotikbf_profiles.json"),
    os.path.join(BASE_DIR, "kirapass_profiles.json"),
)

# --------------------------------------------------------------------------
# Network defaults
# --------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

CONNECT_TIMEOUT = 4.0      # seconds to open the TCP connection
READ_TIMEOUT = 8.0         # seconds to wait for a page (scan/calibration)
ATTACK_READ_TIMEOUT = 5.0  # a login POST that takes longer than this is dead
                           # weight in a guessing loop: count it and move on
VERIFY_TLS = False         # captive portals use self-signed certificates

DEFAULT_THREADS = 12
MIN_THREADS = 1
MAX_THREADS = 200
DEFAULT_ATTEMPTS = 2000
MAX_ATTEMPTS = 20_000_000
DEFAULT_DELAY_MS = 0

# How many requests in a row may fail (no HTTP answer at all) before we stop
# and tell the user the link is gone instead of pretending those cards were
# tested.
SLOW_DIAG_AFTER = 8.0  # seconds: above this a router counts as slow
BURST_LIMIT = 20
SILENCE_SECONDS = 6.0

# --------------------------------------------------------------------------
# "Is the guest really online?" checks
# --------------------------------------------------------------------------
# A captive portal answers these with a redirect to the login page.
# When the card works we get the expected answer instead.
#
# Some networks block these three test sites on purpose.  In that case put your
# own check URL(s) in an environment variable, entries separated by commas:
#
#   KIRAPASS_INTERNET_CHECKS="http://example.com/generate_204|204"
#   KIRAPASS_INTERNET_CHECKS="http://a.test/ok|200|OK,http://b.test/204|204"
#
# format:  url|expected_status|expected_text(optional)
def _parse_internet_checks(raw: str) -> tuple:
    out = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        bits = item.split("|")
        url = bits[0].strip()
        if not url:
            continue
        try:
            status = int(bits[1]) if len(bits) > 1 and bits[1].strip() else 204
        except ValueError:
            status = 204
        text = bits[2].strip() if len(bits) > 2 and bits[2].strip() else None
        out.append((url, status, text, "custom"))
    return tuple(out)


INTERNET_CHECKS = _parse_internet_checks(
    os.environ.get("KIRAPASS_INTERNET_CHECKS", "")) or (
    # (url, expected_status, expected_text_or_None, label)
    ("http://connectivitycheck.gstatic.com/generate_204", 204, None, "google204"),
    ("http://www.msftconnecttest.com/connecttest.txt", 200, "Microsoft Connect Test", "msft"),
    ("http://captive.apple.com/hotspot-detect.html", 200, "Success", "apple"),
)

# Extra hosts that mean "the portal let us out" when they show up in Location.
EXIT_HOST_MARKERS = (
    "msftconnecttest", "gstatic", "captive.apple", "generate_204",
    "connectivitycheck", "detectportal", "google.com", "icloud",
)

# A reply page carrying these words almost always means "wrong card".
REJECT_WORDS = (
    "invalid username or password", "invalid password", "wrong password",
    "invalid user", "unknown user", "user not found", "authentication failed",
    "login failed", "failed to log in", "access denied", "not authorized",
    "incorrect", "try again", "error", "denied", "expired", "already used",
    "no valid profile", "voucher not found", "code not found", "صلاحية",
    "غير صحيح", "خطأ", "منتهي",
)

# Pages/replies carrying these words mean "the router started blocking us".
BAN_WORDS = (
    "you are blocked", "your ip is blocked", "ip has been blocked",
    "address is blocked", "access blocked", "<title>blocked", "blocked.html",
    "too many attempts", "too many login attempts", "too many failed",
    "banned", "temporarily blocked", "rate limit", "slow down",
    "محظور", "تم حظر",
)

# Positive words: card accepted
ACCEPT_WORDS = (
    "you are logged in", "logged in successfully", "login successful",
    "welcome", "status", "remaining time", "time left", "uptime",
    "logout", "log out", "disconnect", "session started", "تم الدخول",
    "مرحبا", "المتبقي",
)

# How many wrong cards we send to learn the rejection page.  Every one of them
# is a failed login for the router, so we keep this small: a router that locks
# after two failures is locked by our own learning otherwise.
CALIBRATION_PROBES = 3
# ... and how few we use when the first try already tripped a lockout.
CALIBRATION_PROBES_RETRY = 2
# Routers that lock a device usually unlock it on their own.  Wait this long,
# then try the learning again once (the web page shows the countdown).
# Override it without editing code:  KIRAPASS_BLOCK_WAIT=120 python3 KiraPass.py
BLOCK_WAIT_SECONDS = max(0, int(os.environ.get("KIRAPASS_BLOCK_WAIT", "45")))
# ... and after sitting one out we keep going at this pace, not faster.
BAN_COOLDOWN_MS = 3000

# Some routers log the guest in and STILL answer with the rejection page.  The
# only honest signal then is the internet itself: while the run is going we ask
# "are we still behind the wall?" every few seconds.  When the answer flips to
# "online", one of the cards we just sent did it - those cards are the suspects
# we hand the user, instead of losing them.
WATCH_INTERNET = True
WATCH_EVERY_SECONDS = 3.0
WATCH_SUSPECTS = 40

# Hosts we treat as "inside the portal" (so a redirect to them is not an exit).
PORTAL_HINT_WORDS = ("login", "hotspot", "portal", "welcome", "splash", "auth")

# A redirect carrying one of these in the URL is still the portal - it is not
# proof that the guest got out (some routers bounce you between their own
# pages: /login -> /status -> /login, and every bounce used to look like a hit).
PORTAL_URL_WORDS = ("login", "hotspot", "portal", "splash", "auth", "captive")

DEFAULT_PREFIX = ""

# Sampling used when the tool has to talk about the space size.
BIG_SPACE = 10 ** 12
