"""Read a captive-portal login page and copy exactly what the browser sends.

No questions are asked here: the page itself says which URL the form posts to,
which field names are used, which hidden values (dst / popup / chap-id) must
travel with the request.  MikroTik's `md5.js` trick is detected too, because
most custom card templates use it:

    document.login.password.value = hexMD5('$(chap-id)' + password +
                                          '$(chap-challenge)')

Sending the raw card instead of that hash is a silent killer: the portal
rejects everything, and the tool looks broken.
"""

from __future__ import annotations

import html as htmlmod
import re
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

FORM_RE = re.compile(r"<form\b[^>]*>", re.I)
INPUT_RE = re.compile(r"<input\b[^>]*>", re.I)
ATTR_RE = re.compile(r"([\w\-:]+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
CHAP_CALL_RE = re.compile(
    r"hexMD5\s*\(\s*'([^']*)'\s*\+\s*([^+)]+?)\s*\+\s*'([^']*)'\s*\)", re.I)
CHAP_SIMPLE_RE = re.compile(r"hexMD5\s*\(\s*([^)]+)\)", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

# Fields we must never copy as "fixed extras" (they carry our own values).
CORE_FIELDS = ("username", "user", "password", "passwd", "pass", "card",
               "code", "voucher", "dst", "popup")


def _attrs(tag: str) -> dict:
    out = {}
    for name, value in ATTR_RE.findall(tag):
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        # HTML serializes ampersands as &amp; in attributes. Decode before
        # joining/parsing the URL, otherwise the browser's URL shape changes.
        out[name.lower()] = htmlmod.unescape(value)
    return out


class FormInfo:
    def __init__(self, action, method, fields, inputs):
        self.action = action
        self.method = method
        self.fields = fields          # name -> default value
        self.inputs = inputs          # list of (name, type)
        self.user_field = ""
        self.pass_field = ""
        self.dst_field = ""
        self.dst_value = ""
        self.popup_field = ""
        self.extra_fields = {}        # hidden fields to always send
        self.chap = None              # {'id':..,'challenge':..,'field':'password'}

    @property
    def is_post(self) -> bool:
        return self.method.lower() == "post"

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "method": self.method,
            "user_field": self.user_field,
            "pass_field": self.pass_field,
            "dst_field": self.dst_field,
            "dst_value": self.dst_value,
            "popup_field": self.popup_field,
            "extra_fields": self.extra_fields,
            "all_fields": list(self.fields.keys()),
            "chap": self.chap or None,
        }


def _form_segments(html: str) -> list:
    """-> [(form tag, html inside that form)] for every <form> on the page."""
    out = []
    marks = list(FORM_RE.finditer(html))
    for i, m in enumerate(marks):
        start = m.end()
        close = html.lower().find("</form", start)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)
        if close != -1:
            end = min(end, close)
        out.append((m.group(0), html[start:max(end, start)]))
    return out


def _score_form(attrs: dict, segment: str) -> int:
    """How much does this form look like the login form? (higher = better)."""
    score = 0
    tags = [_attrs(t) for t in INPUT_RE.findall(segment)]
    types = [(a.get("type") or "text").lower() for a in tags]
    names = [(a.get("name") or "").lower() for a in tags]
    if "password" in types:
        score += 5
    if any(t in ("text", "tel", "number", "email") for t in types):
        score += 2
    if any(w in n for n in names for w in ("user", "pass", "card", "voucher",
                                           "code", "pin")):
        score += 2
    blob = " ".join((attrs.get("name") or "", attrs.get("id") or "",
                     attrs.get("action") or "")).lower()
    if any(w in blob for w in ("login", "logon", "auth", "hotspot", "portal",
                               "signin", "sign-in", "connect")):
        score += 3
    if (attrs.get("method") or "").lower() == "post":
        score += 1
    return score


def parse_form(html: str, base_url: str) -> FormInfo:
    """Find the login form and classify every field in it.

    A captive-portal page often carries more than one form (a language picker,
    a search box, a "buy a card" form).  Taking the first <form> blindly used
    to fill the request with the wrong field names, so every form is scored
    and the most login-looking one wins; fields are then read from inside it.
    """
    html = html or ""
    base_url = htmlmod.unescape(str(base_url or ""))
    action, method = base_url, "post"
    body = html

    segments = _form_segments(html)
    # A copied successful browser URL often *is* the form submission:
    #   /login?username=293...&password=
    # If the page has no HTML form, that query is direct evidence of GET - do
    # not default to POST and do not append a second username later.
    query_pairs = parse_qsl(urlsplit(base_url).query, keep_blank_values=True)
    query_names = {name.lower() for name, _ in query_pairs}
    query_login = (not segments and
                   any(any(w in name for w in
                           ("user", "login", "card", "voucher", "account"))
                       for name in query_names) and
                   any(any(w in name for w in ("pass", "pwd", "pin"))
                       for name in query_names))
    if query_login:
        method = "get"
    if segments:
        best = max(segments, key=lambda pair: _score_form(_attrs(pair[0]),
                                                          pair[1]))
        a = _attrs(best[0])
        if a.get("action"):
            action = urljoin(base_url, a["action"])
        if a.get("method"):
            method = a["method"].lower()
        if INPUT_RE.search(best[1]):
            body = best[1]

    fields, inputs = {}, []
    for tag in INPUT_RE.findall(body):
        a = _attrs(tag)
        name = a.get("name")
        if not name:
            continue
        fields[name] = a.get("value", "")
        inputs.append((name, a.get("type", "text").lower()))

    if not inputs and body is not html:
        # malformed page: the form tag was found but the inputs sit outside it
        for tag in INPUT_RE.findall(html):
            a = _attrs(tag)
            name = a.get("name")
            if not name:
                continue
            fields[name] = a.get("value", "")
            inputs.append((name, a.get("type", "text").lower()))

    if query_login:
        existing = {name for name, _type in inputs}
        for name, value in query_pairs:
            fields.setdefault(name, value)
            if name in existing:
                continue
            low = name.lower()
            typ = ("password" if any(w in low for w in ("pass", "pwd", "pin"))
                   else "text" if any(w in low for w in
                                      ("user", "login", "card", "voucher",
                                       "account"))
                   else "hidden")
            inputs.append((name, typ))

    info = FormInfo(action, method, fields, inputs)

    # password field first (type=password wins, then the name)
    info.pass_field = _pick(inputs, lambda n, t: t == "password") or \
        _pick(inputs, lambda n, t: any(w in n.lower() for w in
                                       ("pass", "pwd", "pin", "voucher", "code"))
              and t not in ("hidden", "submit")) or "password"
    info.user_field = _pick(inputs, lambda n, t: n != info.pass_field
                            and any(w in n.lower() for w in
                                    ("user", "card", "code", "voucher", "login",
                                     "account", "name"))
                            and t not in ("hidden", "submit", "button", "reset",
                                          "checkbox", "radio", "image",
                                          "file")) or \
        _pick(inputs, lambda n, t: n != info.pass_field
              and t in ("text", "tel", "number", "email")) or "username"

    # buttons are not data: a browser only sends the one that was clicked, and
    # sending every named button on the page confuses some portals
    NON_DATA_TYPES = ("submit", "button", "reset", "image", "file")
    for name, _type in inputs:
        low = name.lower()
        if low in ("dst", "link-orig"):
            info.dst_field, info.dst_value = name, fields.get(name, "")
            continue
        if _type in NON_DATA_TYPES:
            continue
        if low == "popup":
            info.popup_field = name
        elif low not in (info.user_field.lower(), info.pass_field.lower(),
                         info.dst_field.lower()):
            info.extra_fields[name] = fields.get(name, "")
    if not info.dst_field:
        info.dst_field = "dst"
    if not info.popup_field:
        info.popup_field = "popup"

    # Persist a URL with the same query keys/order but empty user/password
    # values. GET submission code supplies the fresh values for each attempt.
    info.action = sanitize_login_url(info.action, info.user_field, info.pass_field)

    # MikroTik chap: hexMD5('id' + password + 'challenge')
    cm = CHAP_CALL_RE.search(html)
    if cm:
        info.chap = {"id": cm.group(1), "challenge": cm.group(3),
                     "field": info.pass_field}
    elif "hexMD5" in html:
        info.chap = {"id": "", "challenge": "", "field": info.pass_field}
    return info


def _pick(inputs, predicate) -> str:
    for name, typ in inputs:
        try:
            if predicate(name, typ):
                return name
        except Exception:
            continue
    return ""


class Portal:
    def __init__(self, url, resp, form, dst_candidates, notes):
        self.url = url
        self.status = resp.status
        self.html = (resp.text or "")[:400000]
        self.form = form
        self.dst_candidates = dst_candidates
        self.notes = notes
        self.host = (urlsplit(url).hostname or "").lower()
        mt = TITLE_RE.search(self.html)
        self.title = re.sub(r"\s+", " ", mt.group(1)).strip() if mt else ""

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "host": self.host,
            "title": self.title,
            "status": self.status,
            "has_login_form": bool(self.form and self.form.fields),
            "form": self.form.as_dict() if self.form else None,
            "dst_candidates": self.dst_candidates,
            "notes": self.notes,
        }




def sanitize_login_url(url: str, user_field: str = "username",
                       pass_field: str = "password") -> str:
    """Canonicalize a login URL and remove credential values from its query.

    Keep the query keys and their order (some portals depend on the URL shape),
    but never persist a card or password/hash copied from a submitted GET link.
    """
    value = htmlmod.unescape(str(url or "")).strip()
    try:
        parts = urlsplit(value)
        secret_keys = {str(user_field or "username").lower(),
                       str(pass_field or "password").lower()}
        query = [(key, "" if key.lower() in secret_keys else item)
                 for key, item in parse_qsl(parts.query, keep_blank_values=True)]
        return urlunsplit((parts.scheme, parts.netloc, parts.path,
                           urlencode(query, doseq=True), parts.fragment))
    except Exception:
        return value


def _copied_login_query(url: str) -> tuple:
    """(looks like a submitted GET login, credential field names)."""
    url = htmlmod.unescape(str(url or ""))
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    names = {name.lower(): name for name, _ in pairs}
    users = {original for low, original in names.items()
             if any(w in low for w in
                    ("user", "login", "card", "voucher", "account"))}
    passwords = {original for low, original in names.items()
                 if any(w in low for w in ("pass", "pwd", "pin"))}
    return bool(users and passwords), users | passwords


def _safe_page_url(url: str) -> str:
    """Open the login *page*, never spend the card embedded in a copied URL."""
    url = htmlmod.unescape(str(url or "")).strip()
    copied, credential_names = _copied_login_query(url)
    if not copied:
        return url
    parts = urlsplit(url)
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k not in credential_names]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(pairs, doseq=True), parts.fragment))


def discover(session, url: str, timeout=None) -> Portal:
    """Open the login page and report everything the tool learned from it.

    If the operator pasted an already-submitted GET URL, remove its username
    and password before opening it: scanning must never consume a real card.
    The original query still teaches us that this is a GET portal.
    """
    url = htmlmod.unescape(str(url or "")).strip()
    page_url = _safe_page_url(url)
    resp = session.get(page_url, allow_redirects=True, timeout=timeout)
    base = resp.url or page_url
    form = parse_form(resp.text, base)
    copied_get, _credential_names = _copied_login_query(url)
    if copied_get and not _form_segments(resp.text or ""):
        form = parse_form(resp.text, url)
        form.action = base

    dsts, seen = [], set()
    for src in (parse_qs(urlsplit(base).query).get("dst", [None])[0],
                form.dst_value if form else None,
                _js_var(resp.text, "link-orig"),
                ""):
        if src is not None and src not in seen:
            seen.add(src)
            dsts.append(src)

    notes = []
    if form and form.chap:
        notes.append("chap_md5_detected")
    if form and form.is_post:
        notes.append("post_form")
    else:
        notes.append("get_form")
    if not form or not form.fields:
        notes.append("no_form_found")
    if resp.history:
        notes.append("page_redirected_here")

    return Portal(base, resp, form, dsts, notes)


def _js_var(html: str, name: str) -> str:
    m = re.search(rf"{re.escape(name)}\s*[:=]\s*[\"']([^\"']*)[\"']", html or "", re.I)
    return m.group(1) if m else ""
