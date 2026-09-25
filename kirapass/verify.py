"""Proof, not guesswork: is the guest really online?

The user's complaint - "the connection test connects but the tool does not
recognise it" - is exactly this: the portal answered 302 to the internet
check URL and the old code had no rule that called that a success.

Three questions are answered here, and each answer says *why*:

    internet_state()      before we touch any card:  ONLINE / WALLED / OFFLINE
    verify_online()       after a card looked accepted: does internet work?
    portal_status_page()  secondary check: the router's own /status page
"""

from __future__ import annotations

from urllib.parse import urlsplit

from . import config


def probe_internet(session, checks=None, timeout=(3.0, 6.0)) -> dict:
    """-> {state, label, detail, status, location}

    state: ONLINE  -> the check URL answered exactly as expected (no portal)
           WALLED  -> we were redirected to the portal (needs a card)
           OFFLINE -> nothing answered at all
    """
    last_error = None
    for url, want_status, want_text, label in (checks or config.INTERNET_CHECKS):
        try:
            resp = session.get(url, allow_redirects=False, timeout=timeout)
        except Exception as exc:                       # noqa: BLE001
            last_error = exc
            continue
        body = resp.text or ""
        if resp.status == want_status and (want_text is None or want_text in body):
            return {"state": "ONLINE", "label": label, "detail": "expected_answer",
                    "status": resp.status, "url": url, "location": ""}
        if resp.is_redirect():
            return {"state": "WALLED", "label": label, "detail": "portal_redirect",
                    "status": resp.status, "url": url,
                    "location": resp.location[:200]}
        if resp.status in (200, 204) and want_text and want_text not in body:
            return {"state": "WALLED", "label": label, "detail": "portal_page",
                    "status": resp.status, "url": url,
                    "location": ""}
        if resp.status in (403, 429, 503):
            return {"state": "BLOCKED", "label": label, "detail": f"http_{resp.status}",
                    "status": resp.status, "url": url, "location": ""}
    # Nothing answered at all.  Say *why* in the same words the rest of the
    # tool uses (dns / refused / stale / tls ...) so the UI can translate it.
    kind = "no_answer"
    if last_error is not None:
        try:
            from .errors import classify
            kind = classify(last_error, "").kind
        except Exception:                              # noqa: BLE001
            kind = type(last_error).__name__
    return {"state": "OFFLINE", "label": "", "detail": kind,
            "status": 0, "url": "", "location": ""}


def verify_online(session, checks=None, timeout=(3.0, 6.0)) -> tuple:
    """After a card is accepted: -> (True/False, dict with the reason)."""
    info = probe_internet(session, checks=checks, timeout=timeout)
    ok = info["state"] == "ONLINE"
    return ok, info


def portal_status_page(session, portal_url: str, timeout=(4.0, 8.0)) -> dict:
    """Look for the router's own status/logout page as a second opinion."""
    parts = urlsplit(portal_url)
    base = f"{parts.scheme}://{parts.netloc}"
    for path in ("/status", "/status.html", "/logout"):
        url = base + path
        try:
            resp = session.get(url, allow_redirects=False, timeout=timeout)
        except Exception as exc:                       # noqa: BLE001
            return {"checked": False, "reason": type(exc).__name__, "url": url}
        body = (resp.text or "").lower()
        if resp.status == 200 and not resp.is_redirect():
            logged_in = any(w in body for w in
                            ("logout", "log out", "remaining", "uptime",
                             "session", "bytes", "disconnect"))
            login_form = ('type="password"' in body or "type='password'" in body
                          or "name=\"password\"" in body)
            return {"checked": True, "url": url, "status": resp.status,
                    "looks_logged_in": bool(logged_in and not login_form),
                    "reason": "status_page_reachable"}
        if resp.is_redirect():
            return {"checked": True, "url": url, "status": resp.status,
                    "looks_logged_in": False, "reason": "redirected_to_login",
                    "location": resp.location[:160]}
    return {"checked": False, "reason": "no_status_page"}


def logout(session, portal_url: str, timeout=(4.0, 8.0)) -> dict:
    """Log the test card out again so a paid card is not left consumed."""
    parts = urlsplit(portal_url)
    base = f"{parts.scheme}://{parts.netloc}"
    for path in ("/logout", "/login?erase-cookie=on"):
        url = base + path
        try:
            resp = session.get(url, allow_redirects=False, timeout=timeout)
        except Exception as exc:                       # noqa: BLE001
            continue
        if resp.status in (200, 302):
            return {"ok": True, "url": url, "status": resp.status}
    return {"ok": False, "reason": "no_logout_endpoint"}
