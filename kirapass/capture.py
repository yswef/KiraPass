"""Interactive, redacted browser-assisted portal recorder.

The operator logs in once through a sandboxed iframe with an opaque origin
(no allow-same-origin). Portal JavaScript cannot read KiraPass files or call
its API: forms and fetch/XHR never go to the portal directly and never to
the local API; they are posted to the parent and replayed by a dedicated
server-side Session that keeps cookies, rotating hidden tokens and redirects.

Nothing secret is written down. The JSON report keeps field names, lengths,
safe fingerprints and cookie *names* - never a card number, a password or
its hash, a cookie value, or a live CSRF/nonce/session token.
"""
from __future__ import annotations

import hashlib
import html as htmlmod
from html.parser import HTMLParser
import json
import re
import threading
import time
import uuid
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from . import portals, store
from .httpclient import MAX_REDIRECTS, Session

SECRET_NAME_RE = re.compile(
    r"(pass|passwd|pwd|pin|user|username|login|card|voucher|account|"
    r"token|csrf|nonce|session|chap|challenge|cookie|auth|secret|otp)",
    re.I)
TOKEN_NAME_RE = re.compile(
    r"(token|csrf|nonce|session|chap|challenge|tok$|authenticity)", re.I)
HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
WORD_RE = re.compile(r"[A-Za-z\u0600-\u06FF]{4,}")
SKIP_WORDS = {
    "html", "head", "body", "div", "span", "form", "input", "script", "style",
    "login", "password", "username", "submit", "button", "true", "false",
    "http", "https", "title", "type", "text", "hidden", "value", "name",
    "connect", "function", "return", "document", "window", "charset",
    "content", "wrapper", "main", "session", "popup", "hotspot",
    "doctype", "href", "src", "rel", "meta", "link", "class",
}
STANDARD_HEADERS = {
    "host", "user-agent", "cookie", "content-type", "content-length",
    "accept", "accept-language", "accept-encoding", "connection",
    "referer", "origin", "upgrade-insecure-requests", "cache-control",
    "pragma", "accept-charset",
}
KNOWN_PASS_MODES = ("same", "empty", "omit", "md5user", "chap", "chap_empty")

AR_UNKNOWN_JS = (
    "تحويل كلمة المرور في الصفحة يستخدم JavaScript مخصصاً غير معروف، "
    "لذلك لا يمكن تشغيل التخمين الآلي بأمان."
)
AR_NEXT_UNKNOWN = (
    "الخطوة التالية: سجّل الدخول يدوياً عند الحاجة، ولا تشغّل التخمين الآلي "
    "على هذه البوابة حتى يُعرف نمط التحويل. التقرير المنقّح لا يحتوي رقم "
    "البطاقة ولا كلمة المرور."
)
AR_HTTP200 = (
    "HTTP 200 وحده ليس دليلاً على نجاح أو رفض. علّم الصفحة بنفسك "
    "(نجاح / رفض / إحصائيات) حتى تتعلّم الأداة النمط."
)


def _safe_page_url(url: str) -> str:
    return portals._safe_page_url(url)


def is_kirapass_url(url: str, guard: str) -> bool:
    """True when the portal is trying to talk to this KiraPass process."""
    if not url:
        return False
    try:
        target = urlsplit(urljoin(guard or "", url))
        guard_p = urlsplit(guard or "")
    except Exception:
        return False
    host = (target.hostname or "").lower()
    ghost = (guard_p.hostname or "").lower()
    path = target.path or "/"
    local = host in ("127.0.0.1", "localhost", "::1", "0.0.0.0") or (
        ghost and host == ghost)
    if not local:
        return False
    if guard_p.port and target.port and target.port == guard_p.port:
        return True
    if path.startswith("/api/") or path.startswith("/capture"):
        return True
    if path in ("/", "/ui.js", "/ui.css", "/index.html"):
        return True
    return False


def looks_secret_name(name: str) -> bool:
    return bool(SECRET_NAME_RE.search(name or ""))


def looks_token_name(name: str) -> bool:
    return bool(TOKEN_NAME_RE.search(name or ""))


def looks_live_token(value: str) -> bool:
    value = value or ""
    if not value or len(value) < 8:
        return False
    if HEX32_RE.match(value):
        return True
    if re.fullmatch(r"[0-9a-fA-F]{8,64}", value) and len(value) >= 12:
        return True
    if re.fullmatch(r"[A-Za-z0-9._-]{16,}", value):
        return True
    return False


def field_shape(value: str) -> dict:
    value = "" if value is None else str(value)
    classes = []
    if not value:
        classes.append("empty")
    else:
        if re.fullmatch(r"[0-9]+", value):
            classes.append("digits")
        elif HEX32_RE.match(value):
            classes.append("hex32")
        elif re.fullmatch(r"[0-9a-fA-F]+", value):
            classes.append("hex")
        elif re.fullmatch(r"[A-Za-z0-9]+", value):
            classes.append("alnum")
        else:
            classes.append("other")
    return {"length": len(value), "class": classes[0]}


def redact_fields(fields) -> list:
    out = []
    if not isinstance(fields, dict):
        return out
    for name, value in fields.items():
        value = "" if value is None else str(value)
        item = {"name": str(name), **field_shape(value)}
        item["secret_name"] = looks_secret_name(str(name))
        item["token_name"] = looks_token_name(str(name))
        out.append(item)
    return out


def _md5(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8", "replace")).hexdigest()


def infer_pass_mode(user_before, pass_before, user_after, pass_after,
                    html: str, sent_keys) -> dict:
    """Learn only the patterns KiraPass can replay without a browser.

    Anything else sets needs_browser_js and must not be claimed automatable.
    """
    sent = {str(k) for k in (sent_keys or [])}
    user_b = "" if user_before is None else str(user_before)
    user_a = "" if user_after is None else str(user_after)
    pass_b = None if pass_before is None else str(pass_before)
    pass_a = None if pass_after is None else str(pass_after)
    user = user_a or user_b

    pass_field_sent = any(looks_secret_name(k) and "user" not in k.lower()
                          and "card" not in k.lower()
                          and "login" not in k.lower()
                          and "account" not in k.lower()
                          for k in sent)
    if sent and not pass_field_sent and pass_a in (None, ""):
        return {"pass_mode": "omit", "needs_browser_js": False,
                "reason": "omit", "reason_ar": "حقل كلمة المرور لم يُرسل."}

    chap = None
    form = portals.parse_form(html or "", "http://capture.invalid/")
    if form and form.chap:
        chap = form.chap

    if chap and pass_a and HEX32_RE.match(pass_a):
        cid, chal = chap.get("id") or "", chap.get("challenge") or ""
        if cid or chal:
            raw_candidates = []
            if pass_b is not None:
                raw_candidates.append(("typed", pass_b))
            raw_candidates.append(("user", user))
            raw_candidates.append(("empty", ""))
            for label, raw in raw_candidates:
                if pass_a.lower() == _md5(f"{cid}{raw}{chal}"):
                    if label == "empty" or raw == "":
                        mode = "chap_empty"
                    else:
                        mode = "chap"
                    return {"pass_mode": mode, "needs_browser_js": False,
                            "reason": "mikrotik_chap",
                            "reason_ar": "MikroTik CHAP (hexMD5) معروف وقابل للأتمتة."}

    if pass_a is not None and user and pass_a.lower() == _md5(user):
        return {"pass_mode": "md5user", "needs_browser_js": False,
                "reason": "md5user",
                "reason_ar": "كلمة المرور = MD5 للبطاقة."}

    if pass_a == "":
        return {"pass_mode": "empty", "needs_browser_js": False,
                "reason": "empty", "reason_ar": "كلمة المرور أُرسلت فارغة."}

    if pass_a is not None and user and pass_a == user:
        return {"pass_mode": "same", "needs_browser_js": False,
                "reason": "same", "reason_ar": "كلمة المرور نفس البطاقة."}

    transformed = (pass_b is not None and pass_a is not None
                   and pass_a != pass_b)
    custom_constant = (pass_a not in (None, "", user)
                       and not transformed)
    if transformed or custom_constant:
        return {
            "pass_mode": "",
            "needs_browser_js": True,
            "reason": "unknown_js_transform",
            "reason_ar": AR_UNKNOWN_JS,
            "next_ar": AR_NEXT_UNKNOWN,
        }
    if pass_a is None and not sent:
        return {"pass_mode": "empty", "needs_browser_js": False,
                "reason": "empty", "reason_ar": "لا توجد كلمة مرور مرصودة."}
    return {"pass_mode": "empty", "needs_browser_js": False,
            "reason": "empty", "reason_ar": "لا يوجد تحويل؛ القيمة فارغة أو غير مرسلة."}


def verdict_from_status(status: int, marked: str = "") -> str:
    """HTTP 200 is not success or rejection without a mark or other evidence."""
    if marked in ("success", "reject", "status", "statistics"):
        return marked if marked != "statistics" else "status"
    if status in (301, 302, 303, 307, 308):
        return "redirect"
    if status in (401, 403):
        return "forbidden"
    if status == 429:
        return "rate"
    if status == 200:
        return "unknown_http_200"
    return "unknown"


def safe_url(url: str) -> dict:
    parts = urlsplit(url or "")
    keys = [k for k, _ in parse_qsl(parts.query, keep_blank_values=True)]
    keys = [k for k in keys if not looks_secret_name(k)]
    return {
        "scheme": parts.scheme,
        "host": parts.hostname or "",
        "path": parts.path or "/",
        "query_keys": keys,
    }


def success_url_hint(url: str) -> str:
    parts = urlsplit(url or "")
    path = parts.path or "/"
    if any(w in path.lower() for w in ("login", "logon", "auth")):
        return ""
    return path


class _VisibleBodyText(HTMLParser):
    """Collect text nodes in body; ignore head metadata and executable/style text."""

    _IGNORED = {"head", "script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.ignored = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "body":
            self.in_body = True
        if self.in_body and tag in self._IGNORED:
            self.ignored.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.ignored and tag == self.ignored[-1]:
            self.ignored.pop()
        if tag == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body and not self.ignored:
            self.parts.append(data)


def _visible_body_text(document: str) -> str:
    """Return body text only, never tags/attributes/head/script/style contents."""
    parser = _VisibleBodyText()
    try:
        parser.feed(document or "")
        parser.close()
    except Exception:
        # HTMLParser is deliberately forgiving, but malformed portal markup
        # should fail closed rather than learn from the raw HTML source.
        return ""
    return " ".join(parser.parts)


def _is_login_form(form) -> bool:
    """Require real username and password inputs, not a status-page action form."""
    if not form:
        return False
    inputs = {str(name).lower(): str(kind).lower()
              for name, kind in (form.inputs or [])}
    user_name = (form.user_field or "").lower()
    pass_name = (form.pass_field or "").lower()
    user_kind = inputs.get(user_name, "")
    pass_kind = inputs.get(pass_name, "")
    has_user = bool(user_kind and user_kind not in
                    ("hidden", "submit", "button", "reset", "checkbox", "radio",
                     "image", "file"))
    has_password = bool(pass_kind == "password" or
                        any(part in pass_name for part in ("pass", "pwd", "pin")))
    return has_user and has_password


def learn_words(text: str, strip_values=()) -> list:
    # The source is an HTML document. In particular, do not learn words from
    # meta attributes such as lang, windows, theme, color, apple, touch, icon,
    # or sizes; they are not text visible to the person using the portal.
    blob = _visible_body_text(text or "")
    for value in strip_values:
        if value and len(str(value)) >= 4:
            blob = blob.replace(str(value), " ")
    words, seen = [], set()
    for word in WORD_RE.findall(blob):
        low = word.lower()
        if low in SKIP_WORDS or low in seen:
            continue
        seen.add(low)
        words.append(word)
        if len(words) >= 8:
            break
    return words


def cookie_names_from_session(session: Session) -> list:
    names = getattr(session.cookies, "names", None)
    if callable(names):
        return list(names())
    jar = getattr(session.cookies, "_jar", {}) or {}
    return sorted(jar.keys())


def custom_header_names(headers) -> list:
    out = []
    for key in (headers or {}):
        low = str(key).lower()
        if low in STANDARD_HEADERS or looks_secret_name(low):
            continue
        out.append(str(key))
    return out


def extra_fields_for_profile(fields: dict) -> dict:
    extras = {}
    for name, value in (fields or {}).items():
        low = (name or "").lower()
        if low in portals.CORE_FIELDS or looks_secret_name(name):
            continue
        if looks_token_name(name) or looks_live_token(str(value or "")):
            continue
        extras[name] = str(value or "")
    return extras


def _strip_hop(resp) -> dict:
    set_cookie = resp.header("set-cookie")
    cookie_names = []
    if set_cookie:
        for part in set_cookie.split(","):
            piece = part.split(";", 1)[0]
            if "=" in piece:
                cookie_names.append(piece.split("=", 1)[0].strip())
    return {
        "status": resp.status,
        "url": safe_url(resp.url),
        "location": safe_url(resp.location) if resp.location else None,
        "length": resp.length,
        "content_type": (resp.header("content-type") or "").split(";")[0],
        "ms": round(getattr(resp, "elapsed_ms", 0) or 0),
        "cookie_names": [n for n in cookie_names if n],
        "custom_request_headers": custom_header_names(
            getattr(resp, "request_headers", None)),
    }


# ---------------------------------------------------------------------------
# HTML rewrite + interceptor (runs inside the opaque-origin iframe)
# ---------------------------------------------------------------------------
INTERCEPTOR = r"""
(function () {
  var CFG = window.__KP__ || {};
  var parentWin = window.parent;
  function serialize(form) {
    var out = {}, i, el, name;
    if (!form || !form.elements) return out;
    for (i = 0; i < form.elements.length; i++) {
      el = form.elements[i];
      name = el.name;
      if (!name || el.disabled) continue;
      if ((el.type === "radio" || el.type === "checkbox") && !el.checked) continue;
      if (el.type === "submit" || el.type === "button" || el.type === "reset" || el.type === "file") continue;
      out[name] = el.value == null ? "" : String(el.value);
    }
    return out;
  }
  function forbidden(url) {
    try {
      var u = new URL(url, (document.querySelector("base") && document.querySelector("base").href) || document.baseURI);
      if (CFG.guard) {
        var g = new URL(CFG.guard);
        if (u.origin === g.origin) return true;
      }
      var host = (u.hostname || "").toLowerCase();
      if ((host === "127.0.0.1" || host === "localhost" || host === "::1") &&
          (u.pathname.indexOf("/api/") === 0 || u.pathname.indexOf("/capture") === 0))
        return true;
    } catch (e) {}
    return false;
  }
  function post(msg) {
    try { parentWin.postMessage(msg, "*"); } catch (e) {}
  }
  var pending = {};
  var reqSeq = 0;
  window.addEventListener("message", function (ev) {
    var d = ev.data || {};
    if (!d || d.type !== "kp-http") return;
    var waiter = pending[d.rid];
    if (waiter) { delete pending[d.rid]; waiter(d); }
  });
  function sendAndWait(payload) {
    var rid = "r" + (++reqSeq);
    payload.rid = rid;
    payload.id = CFG.id;
    return new Promise(function (resolve) {
      pending[rid] = resolve;
      post(payload);
      setTimeout(function () {
        if (pending[rid]) {
          delete pending[rid];
          resolve({ status: 0, body: "", content_type: "text/plain", url: payload.url });
        }
      }, 20000);
    });
  }
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form || !form.elements) return;
    if (!form.__kpBefore) form.__kpBefore = serialize(form);
  }, true);
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form || !form.elements) return;
    ev.preventDefault();
    ev.stopPropagation();
    var before = form.__kpBefore || serialize(form);
    var after = serialize(form);
    form.__kpBefore = null;
    var action = form.getAttribute("action") || "";
    var url;
    try { url = new URL(action, document.querySelector("base") ? document.querySelector("base").href : document.baseURI).href; }
    catch (e) { url = action; }
    if (forbidden(url)) { post({type:"kp-blocked", url: url}); return; }
    post({
      type: "kp-form",
      method: (form.method || "GET").toUpperCase(),
      url: url,
      content_type: "application/x-www-form-urlencoded",
      fields: after,
      fields_before: before,
      fields_after: after
    });
  }, false);
  var nativeSubmit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function () {
    var before = serialize(this);
    var action = this.getAttribute("action") || "";
    var url;
    try { url = new URL(action, document.querySelector("base") ? document.querySelector("base").href : document.baseURI).href; }
    catch (e) { url = action; }
    if (forbidden(url)) { post({type:"kp-blocked", url: url}); return; }
    post({
      type: "kp-form",
      method: (this.method || "GET").toUpperCase(),
      url: url,
      content_type: "application/x-www-form-urlencoded",
      fields: before,
      fields_before: before,
      fields_after: before
    });
  };
  document.addEventListener("click", function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest("a") : null;
    if (!a || !a.href) return;
    if ((a.getAttribute("target") || "") === "_blank") return;
    ev.preventDefault();
    if (forbidden(a.href)) { post({type:"kp-blocked", url: a.href}); return; }
    post({ type: "kp-nav", method: "GET", url: a.href });
  }, true);
  var nativeFetch = window.fetch;
  window.fetch = function (input, init) {
    init = init || {};
    var url = (typeof input === "string") ? input : (input && input.url) || "";
    try { url = new URL(url, document.querySelector("base") ? document.querySelector("base").href : document.baseURI).href; }
    catch (e) {}
    if (forbidden(url)) {
      return Promise.reject(new TypeError("blocked"));
    }
    var method = (init.method || "GET").toUpperCase();
    var headers = {};
    try {
      var h = init.headers;
      if (h && h.forEach) h.forEach(function (v, k) { headers[k] = v; });
      else if (h) { for (var k in h) headers[k] = h[k]; }
    } catch (e) {}
    var fields = null, body = "";
    var ct = headers["Content-Type"] || headers["content-type"] || "";
    if (init.body && typeof FormData !== "undefined" && init.body instanceof FormData) {
      fields = {};
      init.body.forEach(function (v, k) { fields[k] = String(v); });
      ct = ct || "application/x-www-form-urlencoded";
    } else if (typeof init.body === "string") {
      body = init.body.slice(0, 65536);
    }
    return sendAndWait({
      type: "kp-fetch", kind: "fetch", method: method, url: url,
      content_type: ct, fields: fields, body: body, headers: headers
    }).then(function (d) {
      return new Response(d.body || "", {
        status: d.status || 0,
        headers: {"Content-Type": d.content_type || "text/plain"}
      });
    });
  };
  var XHR = window.XMLHttpRequest;
  if (XHR) {
    var open = XHR.prototype.open;
    var send = XHR.prototype.send;
    var seth = XHR.prototype.setRequestHeader;
    XHR.prototype.open = function (method, url) {
      this.__kpMethod = method;
      try { this.__kpUrl = new URL(url, document.querySelector("base") ? document.querySelector("base").href : document.baseURI).href; }
      catch (e) { this.__kpUrl = url; }
      this.__kpHeaders = {};
      return open.apply(this, arguments);
    };
    XHR.prototype.setRequestHeader = function (k, v) {
      this.__kpHeaders = this.__kpHeaders || {};
      this.__kpHeaders[k] = v;
      return seth.apply(this, arguments);
    };
    XHR.prototype.send = function (body) {
      var self = this;
      if (forbidden(self.__kpUrl)) {
        self.status = 0;
        if (self.onerror) self.onerror(new ProgressEvent("error"));
        return;
      }
      var fields = null, text = "";
      if (body && typeof FormData !== "undefined" && body instanceof FormData) {
        fields = {};
        body.forEach(function (v, k) { fields[k] = String(v); });
      } else if (typeof body === "string") {
        text = body.slice(0, 65536);
      }
      sendAndWait({
        type: "kp-fetch", kind: "xhr",
        method: (self.__kpMethod || "GET").toUpperCase(),
        url: self.__kpUrl, fields: fields, body: text,
        headers: self.__kpHeaders || {},
        content_type: (self.__kpHeaders || {})["Content-Type"] || ""
      }).then(function (d) {
        Object.defineProperty(self, "status", {value: d.status || 0});
        Object.defineProperty(self, "responseText", {value: d.body || ""});
        Object.defineProperty(self, "response", {value: d.body || ""});
        Object.defineProperty(self, "readyState", {value: 4});
        if (self.onreadystatechange) self.onreadystatechange();
        if (self.onload) self.onload();
      });
    };
  }
})();
"""


def rewrite_html(page_html: str, base_url: str, capture_id: str,
                 guard: str) -> str:
    raw = page_html or "<html><head></head><body></body></html>"
    cfg = json.dumps({"id": capture_id, "guard": guard or ""},
                     ensure_ascii=False)
    base = htmlmod.escape(base_url or "", quote=True)
    inject = (
        '<meta http-equiv="Content-Security-Policy" '
        'content="connect-src \'none\'; form-action \'none\'">'
        f'<base href="{base}">'
        f"<script>window.__KP__={cfg};</script>"
        f"<script>{INTERCEPTOR}</script>"
    )
    if re.search(r"<head[^>]*>", raw, re.I):
        return re.sub(r"<head[^>]*>", lambda m: m.group(0) + inject,
                      raw, count=1, flags=re.I)
    return inject + raw


VIEW_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>مسجّل دخول البوابة — KiraPass</title>
<link rel="stylesheet" href="/ui.css">
<style>
  body{margin:0;display:flex;flex-direction:column;min-height:100vh}
  #bar{padding:.6rem .8rem;display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;
       border-bottom:1px solid rgba(127,127,127,.3);background:var(--bg,#111)}
  #note{flex:1 1 12rem;font-size:.85rem;opacity:.9}
  iframe{flex:1;width:100%%;border:0;background:#fff;min-height:60vh}
  .warn{color:#c08000}
</style>
</head>
<body>
<div id="bar">
  <strong>مسجّل الدخول</strong>
  <span id="note">سجّل دخولاً ناجحاً داخل الإطار، ثم علّم الصفحات.</span>
  <button class="btn" id="btnSuccess">هذه صفحة النجاح</button>
  <button class="btn" id="btnReject">هذه صفحة رفض</button>
  <button class="btn" id="btnStatus">هذه صفحة الإحصائيات</button>
  <button class="btn primary" id="btnFinish">إنهاء + تنزيل التقرير</button>
</div>
<iframe id="portal" sandbox="allow-scripts allow-forms" referrerpolicy="no-referrer"></iframe>
<script>
(function(){
  const ID = %s;
  const TOKEN = %s;
  const iframe = document.getElementById("portal");
  const note = document.getElementById("note");
  function withToken(path){
    if (!TOKEN) return path;
    return path + (path.indexOf("?")>=0?"&":"?") + "token=" + encodeURIComponent(TOKEN);
  }
  async function api(path, body){
    const opt = {method: body ? "POST" : "GET", headers: {}};
    if (body){ opt.headers["Content-Type"]="application/json"; opt.body=JSON.stringify(body); }
    const res = await fetch(withToken(path), opt);
    return await res.json();
  }
  function show(msg, cls){
    note.textContent = msg;
    note.className = cls || "";
  }
  function loadSrcdoc(html){
    iframe.srcdoc = html || "<html><body></body></html>";
  }
  async function refresh(){
    const st = await api("/api/capture/status?id=" + encodeURIComponent(ID));
    if (!st.ok){ show(st.error || "تعذّر التحميل", "warn"); return; }
    loadSrcdoc(st.html_view || "");
    if (st.needs_browser_js){
      show((st.reason_ar || "") + " " + (st.next_ar || ""), "warn");
    } else if (st.last_status){
      show("HTTP " + st.last_status + " — " + (st.hint_ar || "علّم الصفحة إن كانت نجاحاً أو رفضاً."), "");
    }
  }
  async function step(payload){
    payload.id = ID;
    const r = await api("/api/capture/step", payload);
    if (!r.ok){ show(r.error || "فشلت الخطوة", "warn"); return r; }
    if (payload.kind === "fetch" || payload.kind === "xhr" || payload.type === "kp-fetch"){
      iframe.contentWindow.postMessage({
        type:"kp-http", rid: payload.rid,
        status: (r.meta||{}).status || 0,
        body: r.frame_body || "",
        content_type: (r.meta||{}).content_type || "text/plain",
        url: r.url || payload.url
      }, "*");
    } else {
      loadSrcdoc(r.html_view || "");
    }
    if (r.needs_browser_js){
      show((r.reason_ar||"") + " " + (r.next_ar||""), "warn");
    } else if ((r.meta||{}).status === 200 && !r.marked){
      show("HTTP 200 — " + %s, "");
    }
    return r;
  }
  window.addEventListener("message", function(ev){
    if (ev.source !== iframe.contentWindow) return;
    const d = ev.data || {};
    if (d.type === "kp-form"){
      step({
        kind:"form", method:d.method, url:d.url, content_type:d.content_type,
        fields:d.fields, fields_before:d.fields_before, fields_after:d.fields_after
      });
    } else if (d.type === "kp-nav"){
      step({kind:"navigate", method:"GET", url:d.url});
    } else if (d.type === "kp-fetch"){
      d.kind = d.kind || "fetch";
      step(d);
    } else if (d.type === "kp-blocked"){
      show("مُنع طلب نحو واجهة KiraPass المحلية.", "warn");
    }
  });
  async function mark(kind){
    const r = await api("/api/capture/mark", {id:ID, mark:kind});
    show(r.ok ? (r.message_ar || "تم التعليم") : (r.error || "فشل"), r.ok ? "" : "warn");
  }
  document.getElementById("btnSuccess").onclick = function(){ mark("success"); };
  document.getElementById("btnReject").onclick = function(){ mark("reject"); };
  document.getElementById("btnStatus").onclick = function(){ mark("status"); };
  document.getElementById("btnFinish").onclick = async function(){
    const r = await api("/api/capture/finish", {id:ID});
    if (!r.ok){ show(r.error || "فشل الإنهاء", "warn"); return; }
    if (r.needs_browser_js){
      show((r.reason_ar||"") + " " + (r.next_ar||""), "warn");
    } else {
      show("حُفظ التقرير والملف التعريفي.", "");
    }
    if (r.report_name){
      location.href = withToken("/api/capture/report?id=" + encodeURIComponent(ID) + "&download=1");
    }
  };
  refresh();
})();
</script>
</body>
</html>
"""


def view_page(capture_id: str, token: str = "") -> bytes:
    page = VIEW_PAGE % (
        json.dumps(capture_id),
        json.dumps(token or ""),
        json.dumps(AR_HTTP200),
    )
    return page.encode("utf-8")


class Capture:
    def __init__(self, url: str, guard: str):
        self.id = uuid.uuid4().hex[:16]
        self.start_url = _safe_page_url(url)
        self.guard = guard or ""
        self.session = Session(allow_redirects=False)
        self.created = time.time()
        self.html = ""
        self.url = self.start_url
        self.last_status = 0
        self.events = []
        self.marks = []
        self.pass_learn = {"pass_mode": "", "needs_browser_js": False,
                           "reason": "", "reason_ar": "", "next_ar": ""}
        # Keep the login form separately from later success/status pages, which
        # often contain unrelated forms such as erase-cookie.
        self.form = None
        self.login_html = ""
        self.last_fields_redacted = []
        self._strip_values = []
        self.success_words = []
        self.reject_words = []
        self.success_url_contains = ""
        self.stats_url = ""
        self.method = "post"
        self.content_types = []
        self.custom_headers = []
        self.cookie_names = []
        self.redirects = []
        self.report = None
        self.report_name = ""
        self.profile = None
        self.hint_ar = AR_HTTP200
        self._last_raw_fields = {}

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def as_public(self) -> dict:
        return {
            "ok": True,
            "id": self.id,
            "url": self.url,
            "last_status": self.last_status,
            "html_view": rewrite_html(self.html, self.url, self.id, self.guard),
            "needs_browser_js": bool(self.pass_learn.get("needs_browser_js")),
            "reason_ar": self.pass_learn.get("reason_ar") or "",
            "next_ar": self.pass_learn.get("next_ar") or "",
            "pass_mode": self.pass_learn.get("pass_mode") or "",
            "hint_ar": self.hint_ar,
            "marks": list(self.marks),
            "cookie_names": list(self.cookie_names),
            "report_name": self.report_name,
        }


class Hub:
    def __init__(self):
        self._lock = threading.Lock()
        self._items = {}

    def get(self, capture_id: str) -> Capture:
        with self._lock:
            cap = self._items.get(capture_id)
        if not cap:
            raise KeyError("capture_not_found")
        return cap

    def _remember(self, cap: Capture) -> None:
        with self._lock:
            self._items[cap.id] = cap
            if len(self._items) > 8:
                oldest = sorted(self._items.values(), key=lambda c: c.created)[:-8]
                for old in oldest:
                    self._items.pop(old.id, None)
                    old.close()

    def start(self, url: str, guard: str = "") -> Capture:
        if not (url or "").startswith(("http://", "https://")):
            url = "http://" + (url or "").lstrip("/")
        if is_kirapass_url(url, guard):
            raise ValueError("target_is_kirapass")
        cap = Capture(url, guard)
        self._exchange(cap, "GET", cap.start_url, kind="navigate")
        self._remember(cap)
        return cap

    def step(self, capture_id: str, payload: dict, guard: str = "") -> dict:
        cap = self.get(capture_id)
        if guard:
            cap.guard = guard
        kind = (payload.get("kind") or payload.get("type") or "navigate").lower()
        if kind in ("kp-form",):
            kind = "form"
        if kind in ("kp-fetch", "kp-xhr"):
            kind = payload.get("kind") or "fetch"
        method = (payload.get("method") or "GET").upper()
        url = payload.get("url") or cap.url
        if is_kirapass_url(url, cap.guard):
            return {"ok": False, "error": "blocked_kirapass_target"}
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else None
        before = payload.get("fields_before") if isinstance(payload.get("fields_before"), dict) else None
        after = payload.get("fields_after") if isinstance(payload.get("fields_after"), dict) else None
        headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
        content_type = payload.get("content_type") or ""
        body = payload.get("body") if isinstance(payload.get("body"), str) else None
        if after or before:
            self._learn_password(cap, before or {}, after or fields or {},
                                 (after or fields or {}).keys())
        if fields:
            cap.last_fields_redacted = redact_fields(fields)
            cap._last_raw_fields = dict(fields)
            for key, value in fields.items():
                if looks_secret_name(key) and value:
                    cap._strip_values.append(str(value))
        data = fields
        if data is None and body and "json" in (content_type or "").lower():
            try:
                parsed = json.loads(body)
                data = parsed if isinstance(parsed, dict) else body
            except Exception:
                data = body
        elif data is None:
            data = body
        frame_kind = "fetch" if kind in ("fetch", "xhr") else kind
        resp, hops = self._exchange(
            cap, method, url, data=data, headers=headers,
            content_type=content_type, kind=frame_kind)
        public = cap.as_public()
        public["ok"] = True
        public["meta"] = hops[-1] if hops else {"status": cap.last_status}
        public["redirects"] = hops[:-1]
        public["frame_body"] = cap.html if frame_kind in ("fetch", "xhr") else ""
        if frame_kind in ("fetch", "xhr"):
            public["frame_body"] = resp.decode()[:400000] if resp is not None else ""
        public["url"] = cap.url
        public["needs_browser_js"] = bool(cap.pass_learn.get("needs_browser_js"))
        public["reason_ar"] = cap.pass_learn.get("reason_ar") or ""
        public["next_ar"] = cap.pass_learn.get("next_ar") or ""
        public["pass_mode"] = cap.pass_learn.get("pass_mode") or ""
        public["marked"] = bool(cap.marks)
        return public

    def mark(self, capture_id: str, mark: str) -> dict:
        cap = self.get(capture_id)
        mark = (mark or "").lower().strip()
        if mark == "statistics":
            mark = "status"
        if mark not in ("success", "reject", "status"):
            return {"ok": False, "error": "bad_mark"}
        words = learn_words(cap.html, cap._strip_values)
        entry = {"mark": mark, "url": safe_url(cap.url),
                 "status": cap.last_status, "words": words}
        cap.marks.append(entry)
        if mark == "success":
            cap.success_words = words
            cap.success_url_contains = success_url_hint(cap.url)
            msg = "عُلّمت صفحة النجاح. سأحتفظ بالكلمات والرابط الآمن فقط."
        elif mark == "reject":
            cap.reject_words = words
            msg = "عُلّمت صفحة الرفض."
        else:
            cap.stats_url = success_url_hint(cap.url) or (urlsplit(cap.url).path or "/")
            msg = "عُلّمت صفحة الإحصائيات."
        return {"ok": True, "message_ar": msg, "mark": entry}

    def finish(self, capture_id: str, st: store.Store = None,
               hints: dict = None) -> dict:
        cap = self.get(capture_id)
        report = self._build_report(cap)
        cap.report = report
        profile = self._build_profile(cap, hints or {})
        cap.profile = profile
        if st is not None:
            path = st.save_run(report)
            cap.report_name = os_basename(path)
            report["file"] = cap.report_name
            try:
                saved = st.put(profile)
                cap.profile = saved
            except Exception:
                pass
        cap.close()
        public = cap.as_public()
        public["ok"] = True
        public["report"] = report
        public["profile"] = cap.profile
        public["report_name"] = cap.report_name
        public["needs_browser_js"] = bool(profile.get("capture_needs_browser_js"))
        public["reason_ar"] = profile.get("capture_block_reason") or cap.pass_learn.get("reason_ar") or ""
        public["next_ar"] = cap.pass_learn.get("next_ar") or (
            AR_NEXT_UNKNOWN if profile.get("capture_needs_browser_js") else "")
        return public

    def status(self, capture_id: str) -> dict:
        return self.get(capture_id).as_public()

    def report_of(self, capture_id: str) -> dict:
        cap = self.get(capture_id)
        if cap.report is None:
            cap.report = self._build_report(cap)
        return cap.report

    # -- internals -------------------------------------------------------
    def _learn_password(self, cap: Capture, before: dict, after: dict,
                        sent_keys) -> None:
        form = cap.form
        if not _is_login_form(form):
            return
        user_f, pass_f = form.user_field, form.pass_field
        # A later empty form (for example erase-cookie on /status.html) is not
        # evidence about the password transform. Only learn from a submission
        # where the operator actually entered a username/card or password.
        entered = any(str(before.get(key) or "").strip()
                      for key in (user_f, pass_f))
        if not entered:
            return
        learned = infer_pass_mode(
            before.get(user_f), before.get(pass_f),
            after.get(user_f), after.get(pass_f),
            cap.login_html, sent_keys)
        cap.pass_learn = learned

    def _exchange(self, cap: Capture, method: str, url: str, data=None,
                  headers=None, content_type: str = "", kind: str = "navigate"):
        extra = {}
        for key, value in (headers or {}).items():
            low = str(key).lower()
            if low in ("host", "cookie", "content-length", "connection"):
                continue
            extra[key] = value
        if content_type and "content-type" not in {k.lower() for k in extra}:
            extra["Content-Type"] = content_type
        if cap.url and "referer" not in {k.lower() for k in extra}:
            extra["Referer"] = cap.url
            origin = urlsplit(cap.url)
            if origin.scheme and origin.netloc:
                extra.setdefault("Origin", f"{origin.scheme}://{origin.netloc}")
        hops = []
        body = data
        last = None
        orig_method = method
        for _ in range(MAX_REDIRECTS + 1):
            if is_kirapass_url(url, cap.guard):
                raise ValueError("blocked_kirapass_target")
            if method == "GET" and isinstance(body, dict):
                last = cap.session.request(
                    method, url, params=body, headers=extra, allow_redirects=False)
                body = None
            else:
                last = cap.session.request(
                    method, url, data=body, headers=extra, allow_redirects=False)
            hop = _strip_hop(last)
            hops.append(hop)
            cap.redirects.append(hop)
            if content_type:
                cap.content_types.append(content_type.split(";")[0])
            cap.custom_headers = sorted(set(cap.custom_headers) |
                                        set(hop.get("custom_request_headers") or []))
            cap.cookie_names = cookie_names_from_session(cap.session)
            if not last.is_redirect():
                break
            url = urljoin(url, last.location)
            if last.status in (301, 302, 303) and method == "POST":
                method, body, extra = "GET", None, {}
        cap.url = last.url if last is not None else url
        cap.last_status = last.status if last is not None else 0
        text = last.decode() if last is not None else ""
        ctype = (last.header("content-type") if last is not None else "") or ""
        if "html" in ctype.lower() or text.lstrip()[:15].lower().startswith(("<!", "<html")):
            cap.html = text[:400000]
            page_form = portals.parse_form(cap.html, cap.url)
            if _is_login_form(page_form):
                cap.form = page_form
                cap.login_html = cap.html
                cap.method = page_form.method
        cap.events.append({
            "kind": kind,
            "method": orig_method,
            "content_type": (ctype.split(";")[0] if ctype else content_type),
            "request_fields": list(cap.last_fields_redacted),
            "response": hops[-1] if hops else {},
            "redirects": hops[:-1],
            "cookie_names": list(cap.cookie_names),
            "http_200_not_verdict": cap.last_status == 200,
        })
        cap.last_fields_redacted = []
        cap._last_raw_fields = {}
        return last, hops

    def _build_report(self, cap: Capture) -> dict:
        report = {
            "kind": "capture",
            "profile": "capture",
            "started": time.strftime("%Y-%m-%d %H:%M:%S",
                                     time.localtime(cap.created)),
            "start_url": safe_url(cap.start_url),
            "final_url": safe_url(cap.url),
            "events": cap.events,
            "marks": cap.marks,
            "pass_mode": cap.pass_learn.get("pass_mode") or "",
            "capture_needs_browser_js": bool(cap.pass_learn.get("needs_browser_js")),
            "reason": cap.pass_learn.get("reason") or "",
            "reason_ar": cap.pass_learn.get("reason_ar") or "",
            "next_ar": cap.pass_learn.get("next_ar") or "",
            "success_words": list(cap.success_words),
            "success_url_contains": cap.success_url_contains,
            "stats_url": cap.stats_url,
            "method": cap.method,
            "content_types": sorted(set(cap.content_types)),
            "custom_header_names": list(cap.custom_headers),
            "cookie_names": list(cap.cookie_names),
            "form_fields": [i["name"] for i in redact_fields(
                cap.form.fields if cap.form else {})],
            "http_200_policy": "never_success_or_reject_without_mark_or_evidence",
        }
        try:
            scrubbed = _scrub(json.dumps(report, ensure_ascii=False),
                              cap._strip_values)
            return json.loads(scrubbed)
        except Exception:
            return report

    def _build_profile(self, cap: Capture, hints: dict) -> dict:
        form = cap.form or portals.parse_form(cap.html, cap.url)
        needs = bool(cap.pass_learn.get("needs_browser_js"))
        mode = cap.pass_learn.get("pass_mode") or ""
        if needs:
            mode = mode if mode in KNOWN_PASS_MODES else "empty"
        extra = extra_fields_for_profile(form.fields if form else {})
        host = (urlsplit(cap.start_url).hostname or "capture").replace(".", "-")
        prof = store.new_profile(
            name=hints.get("name") or host,
            login_url=(form.action if form else "") or cap.start_url,
            method=(form.method if form else cap.method) or "post",
            user_field=(form.user_field if form else "") or "username",
            pass_field=(form.pass_field if form else "") or "password",
            pass_mode=mode or "empty",
            extra_fields=extra,
            dst_field=(form.dst_field if form else "dst") or "dst",
            dst_value=(form.dst_value if form else "") or "",
            popup_field=(form.popup_field if form else "popup") or "popup",
            chap=(form.chap if form else None),
            success_words=list(cap.success_words),
            success_url_contains=cap.success_url_contains,
            capture_needs_browser_js=needs,
            capture_block_reason=(cap.pass_learn.get("reason_ar") or "") if needs else "",
            stats_url=cap.stats_url,
            prefix=hints.get("prefix") or "",
            length=int(hints.get("length") or 10),
            charset=hints.get("charset") or store.CHARSETS["digits"],
        )
        return prof


def os_basename(path: str) -> str:
    import os
    return os.path.basename(path)


def _scrub(blob: str, values) -> str:
    out = blob
    for value in values or []:
        text = str(value)
        if len(text) >= 3:
            out = out.replace(text, "")
            out = out.replace(json.dumps(text)[1:-1], "")
    return out


# module-level hub used by the web server
HUB = Hub()
