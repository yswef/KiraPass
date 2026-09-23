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

import re
from urllib.parse import parse_qs, urljoin, urlsplit

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
        out[name.lower()] = value
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


def parse_form(html: str, base_url: str) -> FormInfo:
    """Find the login form and classify every field in it."""
    html = html or ""
    action, method = base_url, "post"
    m = FORM_RE.search(html)
    if m:
        a = _attrs(m.group(0))
        if a.get("action"):
            action = urljoin(base_url, a["action"])
        if a.get("method"):
            method = a["method"].lower()

    fields, inputs = {}, []
    for tag in INPUT_RE.findall(html):
        a = _attrs(tag)
        name = a.get("name")
        if not name:
            continue
        fields[name] = a.get("value", "")
        inputs.append((name, a.get("type", "text").lower()))

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
                            and t not in ("hidden", "submit")) or \
        _pick(inputs, lambda n, t: n != info.pass_field
              and t in ("text", "tel", "number", "email")) or "username"

    for name, _type in inputs:
        low = name.lower()
        if low in ("dst", "link-orig"):
            info.dst_field, info.dst_value = name, fields.get(name, "")
        elif low == "popup":
            info.popup_field = name
        elif low not in (info.user_field.lower(), info.pass_field.lower(),
                         info.dst_field.lower()):
            info.extra_fields[name] = fields.get(name, "")
    if not info.dst_field:
        info.dst_field = "dst"
    if not info.popup_field:
        info.popup_field = "popup"

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


def discover(session, url: str, timeout=None) -> Portal:
    """Open the login page and report everything the tool learned from it."""
    resp = session.get(url, allow_redirects=True, timeout=timeout)
    base = resp.url or url
    form = parse_form(resp.text, base)

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
