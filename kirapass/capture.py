# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Interactive, redacted browser-assisted portal recorder.

The operator logs in once through a sandboxed iframe with an opaque origin
(no allow-same-origin). Portal JavaScript cannot read KiraPass files or call
its API: forms and fetch/XHR never go to the portal directly and never to
the local API; they are posted to the parent and replayed by a dedicated
server-side Session that keeps cookies, rotating hidden tokens and redirects.

Nothing secret is written down. The JSON report keeps field names, lengths,
safe fingerprints and cookie *names* - never a card number, a password or
its hash, a cookie value, or a live CSRF/nonce/session token.
"""  # نهاية النص متعدد الأسطر
from __future__ import annotations  # استيراد annotations من الوحدة __future__

import hashlib  # استيراد الوحدة hashlib من المكتبة
import html as htmlmod  # استيراد الوحدة html من المكتبة
from html.parser import HTMLParser  # استيراد HTMLParser من الوحدة html.parser
import json  # استيراد الوحدة json من المكتبة
import re  # استيراد الوحدة re من المكتبة
import threading  # استيراد الوحدة threading من المكتبة
import time  # استيراد الوحدة time من المكتبة
import uuid  # استيراد الوحدة uuid من المكتبة
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit  # استيراد parse_qsl, urlencode, urljoin, urlsplit, urlunsplit من الوحدة urllib.parse

from . import portals, store  # استيراد portals, store من الوحدة .
from .httpclient import MAX_REDIRECTS, Session  # استيراد MAX_REDIRECTS, Session من الوحدة httpclient

SECRET_NAME_RE = re.compile(  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى SECRET_NAME_RE
    r"(pass|passwd|pwd|pin|user|username|login|card|voucher|account|"  # تكملة السطر السابق داخل القوس
    r"token|csrf|nonce|session|chap|challenge|cookie|auth|secret|otp)",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    re.I)  # تكملة السطر السابق داخل القوس
TOKEN_NAME_RE = re.compile(  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى TOKEN_NAME_RE
    r"(token|csrf|nonce|session|chap|challenge|tok$|authenticity)", re.I)  # تكملة السطر السابق داخل القوس
HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى HEX32_RE
HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى HEX40_RE
HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى HEX64_RE
WORD_RE = re.compile(r"[A-Za-z\u0600-\u06FF]{4,}")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى WORD_RE
SKIP_WORDS = {  # إسناد مجموعة فريدة إلى SKIP_WORDS
    "html", "head", "body", "div", "span", "form", "input", "script", "style",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "login", "password", "username", "submit", "button", "true", "false",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "http", "https", "title", "type", "text", "hidden", "value", "name",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "connect", "function", "return", "document", "window", "charset",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "content", "wrapper", "main", "session", "popup", "hotspot",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "doctype", "href", "src", "rel", "meta", "link", "class",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
}  # إغلاق القوس المفتوح في السطر السابق
STANDARD_HEADERS = {  # إسناد مجموعة فريدة إلى STANDARD_HEADERS
    "host", "user-agent", "cookie", "content-type", "content-length",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "accept", "accept-language", "accept-encoding", "connection",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "referer", "origin", "upgrade-insecure-requests", "cache-control",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "pragma", "accept-charset",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
}  # إغلاق القوس المفتوح في السطر السابق
KNOWN_PASS_MODES = ("same", "empty", "omit", "md5user", "sha1user",  # إسناد مجموعة إلى KNOWN_PASS_MODES
                    "sha256user", "chap", "chap_empty")  # تكملة السطر السابق داخل القوس

AR_UNKNOWN_JS = (  # إسناد القيمة الثابتة AR_UNKNOWN_JS
    "تحويل كلمة المرور في الصفحة يستخدم JavaScript مخصصاً غير معروف، "  # تكملة السطر السابق داخل القوس
    "لذلك لا يمكن تشغيل التخمين الآلي بأمان."  # تكملة السطر السابق داخل القوس
)  # إغلاق القوس المفتوح في السطر السابق
AR_NEXT_UNKNOWN = (  # إسناد القيمة الثابتة AR_NEXT_UNKNOWN
    "الخطوة التالية: سجّل الدخول يدوياً عند الحاجة عبر المتصفح، وافتح دليل "  # تكملة السطر السابق داخل القوس
    "المسجل في docs/GUIDE_AR.md (قسم «المسجل اليدوي») إن أردت تعلّم شكل "  # تكملة السطر السابق داخل القوس
    "الطلب. التقرير المنقّح لا يحتوي رقم البطاقة ولا كلمة المرور، ويمكن "  # تكملة السطر السابق داخل القوس
    "تصدير أمر curl منقّح من المسجل لمراجعته يدوياً."  # تكملة السطر السابق داخل القوس
)  # إغلاق القوس المفتوح في السطر السابق
AR_NEXT_UNKNOWN_EN = (  # إسناد القيمة الثابتة AR_NEXT_UNKNOWN_EN
    "Next: log in by hand in a browser when needed, and open docs/GUIDE_EN.md "  # تكملة السطر السابق داخل القوس
    "(section «Manual recorder») if you want to learn the request shape. "  # تكملة السطر السابق داخل القوس
    "The redacted report contains neither the card nor the password; the "  # تكملة السطر السابق داخل القوس
    "recorder can also export a redacted curl command for manual review."  # تكملة السطر السابق داخل القوس
)  # إغلاق القوس المفتوح في السطر السابق
AR_HTTP200 = (  # إسناد القيمة الثابتة AR_HTTP200
    "HTTP 200 وحده ليس دليلاً على نجاح أو رفض. علّم الصفحة بنفسك "  # تكملة السطر السابق داخل القوس
    "(نجاح / رفض / إحصائيات) حتى تتعلّم الأداة النمط."  # تكملة السطر السابق داخل القوس
)  # إغلاق القوس المفتوح في السطر السابق


def _safe_page_url(url: str) -> str:  # تعريف الدالة _safe_page_url(url) ترجع str
    return portals._safe_page_url(url)  # إرجاع portals._safe_page_url(url)


# يمنع كود البوابة من الوصول إلى واجهة الأداة المحلية (SSRF محلي).
def is_kirapass_url(url: str, guard: str) -> bool:  # تعريف الدالة is_kirapass_url(url, guard) ترجع bool
    """True when the portal is trying to talk to this KiraPass process."""  # نص توثيقي (docstring) يشرح ما يليه
    if not url:  # شرط معكوس: ليس url
        return False  # إرجاع False
    try:  # بدايةtry محمية (يليها except/finally)
        target = urlsplit(urljoin(guard or "", url))  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى target
        guard_p = urlsplit(guard or "")  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى guard_p
    except Exception:  # تكملة السطر السابق داخل القوس
        return False  # إرجاع False
    host = (target.hostname or "").lower()  # إسناد نتيجة استدعاء target.hostname أو ''.lower إلى host
    ghost = (guard_p.hostname or "").lower()  # إسناد نتيجة استدعاء guard_p.hostname أو ''.lower إلى ghost
    path = target.path or "/"  # دمج منطقي (أو) وإسناده إلى path
    local = host in ("127.0.0.1", "localhost", "::1", "0.0.0.0") or (  # دمج منطقي (أو) وإسناده إلى local
        ghost and host == ghost)  # تكملة السطر السابق داخل القوس
    if not local:  # شرط معكوس: ليس local
        return False  # إرجاع False
    if guard_p.port and target.port and target.port == guard_p.port:  # شرط مركّب (و)
        return True  # إرجاع True
    if path.startswith("/api/") or path.startswith("/capture"):  # شرط مركّب (أو)
        return True  # إرجاع True
    if path in ("/", "/ui.js", "/ui.css", "/index.html"):  # شرط: path ضمن مجموعة
        return True  # إرجاع True
    return False  # إرجاع False


def looks_secret_name(name: str) -> bool:  # تعريف الدالة looks_secret_name(name) ترجع bool
    return bool(SECRET_NAME_RE.search(name or ""))  # إرجاع bool(SECRET_NAME_RE.search(name أو ''))


def looks_token_name(name: str) -> bool:  # تعريف الدالة looks_token_name(name) ترجع bool
    return bool(TOKEN_NAME_RE.search(name or ""))  # إرجاع bool(TOKEN_NAME_RE.search(name أو ''))


# قيمة طويلة بشكل hex أو base64 ⇒ تُعتبر رمزاً حياً وتُحذف.
def looks_live_token(value: str) -> bool:  # تعريف الدالة looks_live_token(value) ترجع bool
    value = value or ""  # دمج منطقي (أو) وإسناده إلى value
    if not value or len(value) < 8:  # شرط مركّب (أو)
        return False  # إرجاع False
    if HEX32_RE.match(value):  # شرط: نتيجة HEX32_RE.match(value)
        return True  # إرجاع True
    if re.fullmatch(r"[0-9a-fA-F]{8,64}", value) and len(value) >= 12:  # شرط مركّب (و)
        return True  # إرجاع True
    if re.fullmatch(r"[A-Za-z0-9._-]{16,}", value):  # شرط: نتيجة re.fullmatch('[A-Za-z0-9._-]{16,}', value)
        return True  # إرجاع True
    return False  # إرجاع False


def field_shape(value: str) -> dict:  # تعريف الدالة field_shape(value) ترجع dict
    value = "" if value is None else str(value)  # إسناد '' إن مقارنة وإلا str(value) إلى value
    classes = []  # إسناد قائمة إلى classes
    if not value:  # شرط معكوس: ليس value
        classes.append("empty")  # استدعاء classes.append (معامل واحد)
    else:  # مفتاح else في القاموس
        if re.fullmatch(r"[0-9]+", value):  # شرط: نتيجة re.fullmatch('[0-9]+', value)
            classes.append("digits")  # استدعاء classes.append (معامل واحد)
        elif HEX32_RE.match(value):  # شرط: نتيجة HEX32_RE.match(value)
            classes.append("hex32")  # استدعاء classes.append (معامل واحد)
        elif re.fullmatch(r"[0-9a-fA-F]+", value):  # شرط: نتيجة re.fullmatch('[0-9a-fA-F]+', value)
            classes.append("hex")  # استدعاء classes.append (معامل واحد)
        elif re.fullmatch(r"[A-Za-z0-9]+", value):  # شرط: نتيجة re.fullmatch('[A-Za-z0-9]+', value)
            classes.append("alnum")  # استدعاء classes.append (معامل واحد)
        else:  # مفتاح else في القاموس
            classes.append("other")  # استدعاء classes.append (معامل واحد)
    return {"length": len(value), "class": classes[0]}  # إرجاع قاموس


# كل حقل باسم سرّي ⇒ يُحفظ طوله وتصنيفه فقط، ولا قيمته.
def redact_fields(fields) -> list:  # تعريف الدالة redact_fields(fields) ترجع list
    out = []  # إسناد قائمة إلى out
    if not isinstance(fields, dict):  # شرط معكوس: ليس isinstance(fields, dict)
        return out  # إرجاع out
    for name, value in fields.items():  # دورة على fields.items() باسم مجموعة
        value = "" if value is None else str(value)  # إسناد '' إن مقارنة وإلا str(value) إلى value
        item = {"name": str(name), **field_shape(value)}  # إسناد قاموس إلى item
        item["secret_name"] = looks_secret_name(str(name))  # إسناد نتيجة استدعاء looks_secret_name (معامل واحد) إلى item['secret_name']
        item["token_name"] = looks_token_name(str(name))  # إسناد نتيجة استدعاء looks_token_name (معامل واحد) إلى item['token_name']
        out.append(item)  # استدعاء out.append (معامل واحد)
    return out  # إرجاع out


def _md5(text: str) -> str:  # تعريف الدالة _md5(text) ترجع str
    return hashlib.md5((text or "").encode("utf-8", "replace")).hexdigest()  # إرجاع hashlib.md5(text أو ''.encode('utf-8', 'replace')).hexdigest()


def _sha1(text: str) -> str:  # تعريف الدالة _sha1(text) ترجع str
    return hashlib.sha1((text or "").encode("utf-8", "replace")).hexdigest()  # إرجاع hashlib.sha1(text أو ''.encode('utf-8', 'replace')).hexdigest()


def _sha256(text: str) -> str:  # تعريف الدالة _sha256(text) ترجع str
    return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()  # إرجاع hashlib.sha256(text أو ''.encode('utf-8', 'replace')).hexdigest()


# يستنتج وضع كلمة المرور من كود البوابة. تحويل JS مجهول ⇒
# needs_browser_js = True والأداة ترفض الأتمتة بدل أن تدّعي ما لا تعرفه.
def infer_pass_mode(user_before, pass_before, user_after, pass_after,  # تعريف الدالة infer_pass_mode(user_before, pass_before, user_after, pass_after, html, sent_keys) ترجع dict
                    html: str, sent_keys) -> dict:  # مفتاح html في القاموس
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Learn only the patterns KiraPass can replay without a browser.

    Anything else sets needs_browser_js and must not be claimed automatable.
    sha1(user) and sha256(user) are learned the same way as md5user when the
    captured password hex matches those digests — no arbitrary JS is executed.
    """  # نهاية النص متعدد الأسطر
    sent = {str(k) for k in (sent_keys or [])}  # بناء اشتقاق مجموعة وإسناده إلى sent
    user_b = "" if user_before is None else str(user_before)  # إسناد '' إن مقارنة وإلا str(user_before) إلى user_b
    user_a = "" if user_after is None else str(user_after)  # إسناد '' إن مقارنة وإلا str(user_after) إلى user_a
    pass_b = None if pass_before is None else str(pass_before)  # إسناد None إن مقارنة وإلا str(pass_before) إلى pass_b
    pass_a = None if pass_after is None else str(pass_after)  # إسناد None إن مقارنة وإلا str(pass_after) إلى pass_a
    user = user_a or user_b  # دمج منطقي (أو) وإسناده إلى user

    pass_field_sent = any(looks_secret_name(k) and "user" not in k.lower()  # إسناد نتيجة استدعاء any (معامل واحد) إلى pass_field_sent
                          and "card" not in k.lower()  # تكملة السطر السابق داخل القوس
                          and "login" not in k.lower()  # تكملة السطر السابق داخل القوس
                          and "account" not in k.lower()  # تكملة السطر السابق داخل القوس
                          for k in sent)  # تكملة السطر السابق داخل القوس
    if sent and not pass_field_sent and pass_a in (None, ""):  # شرط مركّب (و)
        return {"pass_mode": "omit", "needs_browser_js": False,  # إرجاع قاموس
                "reason": "omit", "reason_ar": "حقل كلمة المرور لم يُرسل."}  # مفتاح reason في القاموس

    chap = None  # إسناد القيمة الثابتة chap
    form = portals.parse_form(html or "", "http://capture.invalid/")  # إسناد نتيجة استدعاء portals.parse_form (2 معاملات) إلى form
    if form and form.chap:  # شرط مركّب (و)
        chap = form.chap  # إسناد form.chap إلى chap

    if chap and pass_a and HEX32_RE.match(pass_a):  # شرط مركّب (و)
        cid, chal = chap.get("id") or "", chap.get("challenge") or ""  # إسناد مجموعة إلى مجموعة
        if cid or chal:  # شرط مركّب (أو)
            raw_candidates = []  # إسناد قائمة إلى raw_candidates
            if pass_b is not None:  # شرط: pass_b ليس نفسه None
                raw_candidates.append(("typed", pass_b))  # استدعاء raw_candidates.append (معامل واحد)
            raw_candidates.append(("user", user))  # استدعاء raw_candidates.append (معامل واحد)
            raw_candidates.append(("empty", ""))  # استدعاء raw_candidates.append (معامل واحد)
            for label, raw in raw_candidates:  # دورة على raw_candidates باسم مجموعة
                if pass_a.lower() == _md5(f"{cid}{raw}{chal}"):  # شرط: pass_a.lower() يساوي _md5(نص منسّق (f-string))
                    if label == "empty" or raw == "":  # شرط مركّب (أو)
                        mode = "chap_empty"  # إسناد القيمة الثابتة mode
                    else:  # مفتاح else في القاموس
                        mode = "chap"  # إسناد القيمة الثابتة mode
                    return {"pass_mode": mode, "needs_browser_js": False,  # إرجاع قاموس
                            "reason": "mikrotik_chap",  # مفتاح reason في القاموس
                            "reason_ar": "MikroTik CHAP (hexMD5) معروف وقابل للأتمتة."}  # مفتاح reason_ar في القاموس

    if pass_a is not None and user and pass_a.lower() == _md5(user):  # شرط مركّب (و)
        return {"pass_mode": "md5user", "needs_browser_js": False,  # إرجاع قاموس
                "reason": "md5user",  # مفتاح reason في القاموس
                "reason_ar": "كلمة المرور = MD5 للبطاقة."}  # مفتاح reason_ar في القاموس

    # شرط مركّب (و)
    if pass_a is not None and user and HEX40_RE.match(pass_a) and \
            pass_a.lower() == _sha1(user):  # تكملة تعريف متعدد الأسطر
        return {"pass_mode": "sha1user", "needs_browser_js": False,  # إرجاع قاموس
                "reason": "sha1user",  # مفتاح reason في القاموس
                "reason_ar": "كلمة المرور = SHA1 للبطاقة."}  # مفتاح reason_ar في القاموس

    # شرط مركّب (و)
    if pass_a is not None and user and HEX64_RE.match(pass_a) and \
            pass_a.lower() == _sha256(user):  # تكملة تعريف متعدد الأسطر
        return {"pass_mode": "sha256user", "needs_browser_js": False,  # إرجاع قاموس
                "reason": "sha256user",  # مفتاح reason في القاموس
                "reason_ar": "كلمة المرور = SHA256 للبطاقة."}  # مفتاح reason_ar في القاموس

    if pass_a == "":  # شرط: pass_a يساوي ''
        return {"pass_mode": "empty", "needs_browser_js": False,  # إرجاع قاموس
                "reason": "empty", "reason_ar": "كلمة المرور أُرسلت فارغة."}  # مفتاح reason في القاموس

    if pass_a is not None and user and pass_a == user:  # شرط مركّب (و)
        return {"pass_mode": "same", "needs_browser_js": False,  # إرجاع قاموس
                "reason": "same", "reason_ar": "كلمة المرور نفس البطاقة."}  # مفتاح reason في القاموس

    transformed = (pass_b is not None and pass_a is not None  # دمج منطقي (و) وإسناده إلى transformed
                   and pass_a != pass_b)  # تكملة السطر السابق داخل القوس
    custom_constant = (pass_a not in (None, "", user)  # دمج منطقي (و) وإسناده إلى custom_constant
                       and not transformed)  # تكملة السطر السابق داخل القوس
    if transformed or custom_constant:  # شرط مركّب (أو)
        return {  # إرجاع قاموس
            "pass_mode": "",  # مفتاح pass_mode في القاموس
            "needs_browser_js": True,  # مفتاح needs_browser_js في القاموس
            "reason": "unknown_js_transform",  # مفتاح reason في القاموس
            "reason_ar": AR_UNKNOWN_JS,  # مفتاح reason_ar في القاموس
            "next_ar": AR_NEXT_UNKNOWN,  # مفتاح next_ar في القاموس
            "next_en": AR_NEXT_UNKNOWN_EN,  # مفتاح next_en في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق
    if pass_a is None and not sent:  # شرط مركّب (و)
        return {"pass_mode": "empty", "needs_browser_js": False,  # إرجاع قاموس
                "reason": "empty", "reason_ar": "لا توجد كلمة مرور مرصودة."}  # مفتاح reason في القاموس
    return {"pass_mode": "empty", "needs_browser_js": False,  # إرجاع قاموس
            "reason": "empty", "reason_ar": "لا يوجد تحويل؛ القيمة فارغة أو غير مرسلة."}  # مفتاح reason في القاموس


def verdict_from_status(status: int, marked: str = "") -> str:  # تعريف الدالة verdict_from_status(status, marked) ترجع str
    """HTTP 200 is not success or rejection without a mark or other evidence."""  # نص توثيقي (docstring) يشرح ما يليه
    if marked in ("success", "reject", "status", "statistics"):  # شرط: marked ضمن مجموعة
        return marked if marked != "statistics" else "status"  # إرجاع marked إن مقارنة وإلا 'status'
    if status in (301, 302, 303, 307, 308):  # شرط: status ضمن مجموعة
        return "redirect"  # إرجاع 'redirect'
    if status in (401, 403):  # شرط: status ضمن مجموعة
        return "forbidden"  # إرجاع 'forbidden'
    if status == 429:  # شرط: status يساوي 429
        return "rate"  # إرجاع 'rate'
    if status == 200:  # شرط: status يساوي 200
        return "unknown_http_200"  # إرجاع 'unknown_http_200'
    return "unknown"  # إرجاع 'unknown'


def safe_url(url: str) -> dict:  # تعريف الدالة safe_url(url) ترجع dict
    parts = urlsplit(url or "")  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    keys = [k for k, _ in parse_qsl(parts.query, keep_blank_values=True)]  # بناء اشتقاق قائمة وإسناده إلى keys
    keys = [k for k in keys if not looks_secret_name(k)]  # بناء اشتقاق قائمة وإسناده إلى keys
    return {  # إرجاع قاموس
        "scheme": parts.scheme,  # مفتاح scheme في القاموس
        "host": parts.hostname or "",  # مفتاح host في القاموس
        "path": parts.path or "/",  # مفتاح path في القاموس
        "query_keys": keys,  # مفتاح query_keys في القاموس
    }  # إغلاق القوس المفتوح في السطر السابق


def success_url_hint(url: str) -> str:  # تعريف الدالة success_url_hint(url) ترجع str
    parts = urlsplit(url or "")  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    path = parts.path or "/"  # دمج منطقي (أو) وإسناده إلى path
    if any(w in path.lower() for w in ("login", "logon", "auth")):  # شرط: نتيجة any(مولّد)
        return ""  # إرجاع ''
    return path  # إرجاع path


class _VisibleBodyText(HTMLParser):  # تعريف الصنف _VisibleBodyText يرث من HTMLParser
    """Collect text nodes in body; ignore head metadata and executable/style text."""  # نص توثيقي (docstring) يشرح ما يليه

    _IGNORED = {"head", "script", "style"}  # إسناد مجموعة فريدة إلى _IGNORED

    def __init__(self):  # تعريف الدالة __init__(self)
        super().__init__(convert_charrefs=True)  # استدعاء super().__init__ (convert_charrefs=…)
        self.in_body = False  # إسناد القيمة الثابتة self.in_body
        self.ignored = []  # إسناد قائمة إلى self.ignored
        self.parts = []  # إسناد قائمة إلى self.parts

    def handle_starttag(self, tag, attrs):  # تعريف الدالة handle_starttag(self, tag, attrs)
        tag = tag.lower()  # إسناد نتيجة استدعاء tag.lower إلى tag
        if tag == "body":  # شرط: tag يساوي 'body'
            self.in_body = True  # إسناد القيمة الثابتة self.in_body
        if self.in_body and tag in self._IGNORED:  # شرط مركّب (و)
            self.ignored.append(tag)  # استدعاء self.ignored.append (معامل واحد)

    def handle_endtag(self, tag):  # تعريف الدالة handle_endtag(self, tag)
        tag = tag.lower()  # إسناد نتيجة استدعاء tag.lower إلى tag
        if self.ignored and tag == self.ignored[-1]:  # شرط مركّب (و)
            self.ignored.pop()  # استدعاء self.ignored.pop
        if tag == "body":  # شرط: tag يساوي 'body'
            self.in_body = False  # إسناد القيمة الثابتة self.in_body

    def handle_data(self, data):  # تعريف الدالة handle_data(self, data)
        if self.in_body and not self.ignored:  # شرط مركّب (و)
            self.parts.append(data)  # استدعاء self.parts.append (معامل واحد)


def _visible_body_text(document: str) -> str:  # تعريف الدالة _visible_body_text(document) ترجع str
    """Return body text only, never tags/attributes/head/script/style contents."""  # نص توثيقي (docstring) يشرح ما يليه
    parser = _VisibleBodyText()  # إسناد نتيجة استدعاء _VisibleBodyText إلى parser
    try:  # بدايةtry محمية (يليها except/finally)
        parser.feed(document or "")  # استدعاء parser.feed (معامل واحد)
        parser.close()  # استدعاء parser.close
    except Exception:  # تكملة السطر السابق داخل القوس
        # HTMLParser متسامح عمداً، لكن ترميز بوابة مشوّه
        # يجب أن يفشل مغلقاً بدل أن يتعلّم من مصدر HTML الخام.
        return ""  # إرجاع ''
    return " ".join(parser.parts)  # إرجاع ' '.join(parser.parts)


def _is_login_form(form) -> bool:  # تعريف الدالة _is_login_form(form) ترجع bool
    """Require real username and password inputs, not a status-page action form."""  # نص توثيقي (docstring) يشرح ما يليه
    if not form:  # شرط معكوس: ليس form
        return False  # إرجاع False
    inputs = {str(name).lower(): str(kind).lower()  # بناء قاموس بالاشتقاق وإسناده إلى inputs
              for name, kind in (form.inputs or [])}  # تكملة السطر السابق داخل القوس
    user_name = (form.user_field or "").lower()  # إسناد نتيجة استدعاء form.user_field أو ''.lower إلى user_name
    pass_name = (form.pass_field or "").lower()  # إسناد نتيجة استدعاء form.pass_field أو ''.lower إلى pass_name
    user_kind = inputs.get(user_name, "")  # إسناد نتيجة استدعاء inputs.get (2 معاملات) إلى user_kind
    pass_kind = inputs.get(pass_name, "")  # إسناد نتيجة استدعاء inputs.get (2 معاملات) إلى pass_kind
    has_user = bool(user_kind and user_kind not in  # إسناد نتيجة استدعاء bool (معامل واحد) إلى has_user
                    ("hidden", "submit", "button", "reset", "checkbox", "radio",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                     "image", "file"))  # تكملة السطر السابق داخل القوس
    has_password = bool(pass_kind == "password" or  # إسناد نتيجة استدعاء bool (معامل واحد) إلى has_password
                        any(part in pass_name for part in ("pass", "pwd", "pin")))  # تكملة السطر السابق داخل القوس
    return has_user and has_password  # إرجاع has_user و has_password


# كلمات النجاح من نص body المرئي فقط (لا script ولا style ولا meta)،
# وتُحذف منها القيم التي أدخلها المستخدم حتى لا تُتعلَّم بطاقته ككلمة نجاح.
def learn_words(text: str, strip_values=()) -> list:  # تعريف الدالة learn_words(text, strip_values) ترجع list
    # المصدر مستند HTML. وتحديداً، لا تتعلّم كلمات من
    # خصائص meta مثل lang أو windows أو theme أو color أو apple أو touch أو icon
    # أو sizes؛ فهي ليست نصاً يراه مستخدم البوابة.
    blob = _visible_body_text(text or "")  # إسناد نتيجة استدعاء _visible_body_text (معامل واحد) إلى blob
    for value in strip_values:  # دورة على strip_values باسم value
        if value and len(str(value)) >= 4:  # شرط مركّب (و)
            blob = blob.replace(str(value), " ")  # إسناد نتيجة استدعاء blob.replace (2 معاملات) إلى blob
    words, seen = [], set()  # إسناد مجموعة إلى مجموعة
    for word in WORD_RE.findall(blob):  # دورة على WORD_RE.findall(blob) باسم word
        low = word.lower()  # إسناد نتيجة استدعاء word.lower إلى low
        if low in SKIP_WORDS or low in seen:  # شرط مركّب (أو)
            continue  # الانتقال إلى الدورة التالية
        seen.add(low)  # استدعاء seen.add (معامل واحد)
        words.append(word)  # استدعاء words.append (معامل واحد)
        if len(words) >= 8:  # شرط: len(words) أكبر أو يساوي 8
            break  # قطع الحلقة فوراً
    return words  # إرجاع words


def cookie_names_from_session(session: Session) -> list:  # تعريف الدالة cookie_names_from_session(session) ترجع list
    names = getattr(session.cookies, "names", None)  # إسناد نتيجة استدعاء getattr (3 معاملات) إلى names
    if callable(names):  # شرط: نتيجة callable(names)
        return list(names())  # إرجاع list(names())
    jar = getattr(session.cookies, "_jar", {}) or {}  # دمج منطقي (أو) وإسناده إلى jar
    return sorted(jar.keys())  # إرجاع sorted(jar.keys())


def custom_header_names(headers) -> list:  # تعريف الدالة custom_header_names(headers) ترجع list
    out = []  # إسناد قائمة إلى out
    for key in (headers or {}):  # دورة على headers أو قاموس باسم key
        low = str(key).lower()  # إسناد نتيجة استدعاء str(key).lower إلى low
        if low in STANDARD_HEADERS or looks_secret_name(low):  # شرط مركّب (أو)
            continue  # الانتقال إلى الدورة التالية
        out.append(str(key))  # استدعاء out.append (معامل واحد)
    return out  # إرجاع out


def extra_fields_for_profile(fields: dict) -> dict:  # تعريف الدالة extra_fields_for_profile(fields) ترجع dict
    extras = {}  # إسناد قاموس إلى extras
    for name, value in (fields or {}).items():  # دورة على fields أو قاموس.items() باسم مجموعة
        low = (name or "").lower()  # إسناد نتيجة استدعاء name أو ''.lower إلى low
        if low in portals.CORE_FIELDS or looks_secret_name(name):  # شرط مركّب (أو)
            continue  # الانتقال إلى الدورة التالية
        if looks_token_name(name) or looks_live_token(str(value or "")):  # شرط مركّب (أو)
            continue  # الانتقال إلى الدورة التالية
        extras[name] = str(value or "")  # إسناد نتيجة استدعاء str (معامل واحد) إلى extras[name]
    return extras  # إرجاع extras


def _strip_hop(resp) -> dict:  # تعريف الدالة _strip_hop(resp) ترجع dict
    set_cookie = resp.header("set-cookie")  # إسناد نتيجة استدعاء resp.header (معامل واحد) إلى set_cookie
    cookie_names = []  # إسناد قائمة إلى cookie_names
    if set_cookie:  # شرط: set_cookie
        for part in set_cookie.split(","):  # دورة على set_cookie.split(',') باسم part
            piece = part.split(";", 1)[0]  # إسناد part.split(';', 1)[0] إلى piece
            if "=" in piece:  # شرط: '=' ضمن piece
                cookie_names.append(piece.split("=", 1)[0].strip())  # استدعاء cookie_names.append (معامل واحد)
    return {  # إرجاع قاموس
        "status": resp.status,  # مفتاح status في القاموس
        "url": safe_url(resp.url),  # مفتاح url في القاموس
        "location": safe_url(resp.location) if resp.location else None,  # مفتاح location في القاموس
        "length": resp.length,  # مفتاح length في القاموس
        "content_type": (resp.header("content-type") or "").split(";")[0],  # مفتاح content_type في القاموس
        "ms": round(getattr(resp, "elapsed_ms", 0) or 0),  # مفتاح ms في القاموس
        "cookie_names": [n for n in cookie_names if n],  # مفتاح cookie_names في القاموس
        "custom_request_headers": custom_header_names(  # مفتاح custom_request_headers في القاموس
            getattr(resp, "request_headers", None)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    }  # إغلاق القوس المفتوح في السطر السابق


# ---------------------------------------------------------------------------
# إعادة كتابة HTML + المعترض (يعمل داخل iframe بأصل معتم)
# ---------------------------------------------------------------------------
# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
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
"""  # نهاية النص متعدد الأسطر


# يعيد كتابة صفحة البوابة لتعمل داخل إطار معزول: CSP + base + اعتراض النماذج.
def rewrite_html(page_html: str, base_url: str, capture_id: str,  # تعريف الدالة rewrite_html(page_html, base_url, capture_id, guard) ترجع str
                 guard: str) -> str:  # مفتاح guard في القاموس
    raw = page_html or "<html><head></head><body></body></html>"  # دمج منطقي (أو) وإسناده إلى raw
    cfg = json.dumps({"id": capture_id, "guard": guard or ""},  # إسناد نتيجة استدعاء json.dumps (معامل واحد، ensure_ascii=…) إلى cfg
                     ensure_ascii=False)  # المعامل المسمّى ensure_ascii
    base = htmlmod.escape(base_url or "", quote=True)  # إسناد نتيجة استدعاء htmlmod.escape (معامل واحد، quote=…) إلى base
    inject = (  # بناء نص منسّق وإسناده إلى inject
        '<meta http-equiv="Content-Security-Policy" '  # تكملة السطر السابق داخل القوس
        'content="connect-src \'none\'; form-action \'none\'">'  # تكملة السطر السابق داخل القوس
        f'<base href="{base}">'  # تكملة السطر السابق داخل القوس
        f"<script>window.__KP__={cfg};</script>"  # تكملة السطر السابق داخل القوس
        f"<script>{INTERCEPTOR}</script>"  # تكملة السطر السابق داخل القوس
    )  # إغلاق القوس المفتوح في السطر السابق
    if re.search(r"<head[^>]*>", raw, re.I):  # شرط: نتيجة re.search('<head[^>]*>', raw, re.I)
        return re.sub(r"<head[^>]*>", lambda m: m.group(0) + inject,  # إرجاع re.sub('<head[^>]*>', دالة مجهولة, raw, count=1, flags=re.I)
                      raw, count=1, flags=re.I)  # تكملة السطر السابق داخل القوس
    return inject + raw  # إرجاع جمع


# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
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
    show(r.message_ar || (r.ok ? "تم التعليم" : (r.error || "فشل")), r.ok ? "" : "warn");
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
"""  # نهاية النص متعدد الأسطر


def view_page(capture_id: str, token: str = "") -> bytes:  # تعريف الدالة view_page(capture_id, token) ترجع bytes
    page = VIEW_PAGE % (  # حساب باقي القسمة بين VIEW_PAGE ومجموعة وإسناده إلى page
        json.dumps(capture_id),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        json.dumps(token or ""),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        json.dumps(AR_HTTP200),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    )  # إغلاق القوس المفتوح في السطر السابق
    return page.encode("utf-8")  # إرجاع page.encode('utf-8')


class Capture:  # تعريف الصنف Capture
    def __init__(self, url: str, guard: str):  # تعريف الدالة __init__(self, url, guard)
        self.id = uuid.uuid4().hex[:16]  # إسناد uuid.uuid4().hex[] إلى self.id
        self.start_url = _safe_page_url(url)  # إسناد نتيجة استدعاء _safe_page_url (معامل واحد) إلى self.start_url
        self.guard = guard or ""  # دمج منطقي (أو) وإسناده إلى self.guard
        self.session = Session(allow_redirects=False)  # إسناد نتيجة استدعاء Session (allow_redirects=…) إلى self.session
        self.created = time.time()  # إسناد نتيجة استدعاء time.time إلى self.created
        self.html = ""  # إسناد القيمة الثابتة self.html
        self.url = self.start_url  # إسناد self.start_url إلى self.url
        self.last_status = 0  # إسناد القيمة الثابتة self.last_status
        self.events = []  # إسناد قائمة إلى self.events
        self.marks = []  # إسناد قائمة إلى self.marks
        self.pass_learn = {"pass_mode": "", "needs_browser_js": False,  # إسناد قاموس إلى self.pass_learn
                           "reason": "", "reason_ar": "", "next_ar": ""}  # مفتاح reason في القاموس
        # أبقِ نموذج الدخول منفصلاً عن صفحات النجاح/الحالة اللاحقة، التي
        # كثيراً ما تحتوي نماذج لا علاقة لها مثل erase-cookie.
        self.form = None  # إسناد القيمة الثابتة self.form
        self.login_html = ""  # إسناد القيمة الثابتة self.login_html
        self.last_fields_redacted = []  # إسناد قائمة إلى self.last_fields_redacted
        self._strip_values = []  # إسناد قائمة إلى self._strip_values
        self.success_words = []  # إسناد قائمة إلى self.success_words
        self.reject_words = []  # إسناد قائمة إلى self.reject_words
        self.success_url_contains = ""  # إسناد القيمة الثابتة self.success_url_contains
        self.stats_url = ""  # إسناد القيمة الثابتة self.stats_url
        self.method = "post"  # إسناد القيمة الثابتة self.method
        self.content_types = []  # إسناد قائمة إلى self.content_types
        self.custom_headers = []  # إسناد قائمة إلى self.custom_headers
        self.cookie_names = []  # إسناد قائمة إلى self.cookie_names
        self.redirects = []  # إسناد قائمة إلى self.redirects
        self.report = None  # إسناد القيمة الثابتة self.report
        self.report_name = ""  # إسناد القيمة الثابتة self.report_name
        self.profile = None  # إسناد القيمة الثابتة self.profile
        self.hint_ar = AR_HTTP200  # إسناد AR_HTTP200 إلى self.hint_ar
        self._last_raw_fields = {}  # إسناد قاموس إلى self._last_raw_fields

    def close(self):  # تعريف الدالة close(self)
        try:  # بدايةtry محمية (يليها except/finally)
            self.session.close()  # استدعاء self.session.close
        except Exception:  # تكملة السطر السابق داخل القوس
            pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً

    def as_public(self) -> dict:  # تعريف الدالة as_public(self) ترجع dict
        return {  # إرجاع قاموس
            "ok": True,  # مفتاح ok في القاموس
            "id": self.id,  # مفتاح id في القاموس
            "url": self.url,  # مفتاح url في القاموس
            "last_status": self.last_status,  # مفتاح last_status في القاموس
            "html_view": rewrite_html(self.html, self.url, self.id, self.guard),  # مفتاح html_view في القاموس
            "needs_browser_js": bool(self.pass_learn.get("needs_browser_js")),  # مفتاح needs_browser_js في القاموس
            "reason_ar": self.pass_learn.get("reason_ar") or "",  # مفتاح reason_ar في القاموس
            "next_ar": self.pass_learn.get("next_ar") or "",  # مفتاح next_ar في القاموس
            "pass_mode": self.pass_learn.get("pass_mode") or "",  # مفتاح pass_mode في القاموس
            "hint_ar": self.hint_ar,  # مفتاح hint_ar في القاموس
            "marks": list(self.marks),  # مفتاح marks في القاموس
            "cookie_names": list(self.cookie_names),  # مفتاح cookie_names في القاموس
            "report_name": self.report_name,  # مفتاح report_name في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق


class Hub:  # تعريف الصنف Hub
    def __init__(self):  # تعريف الدالة __init__(self)
        self._lock = threading.Lock()  # إسناد نتيجة استدعاء threading.Lock إلى self._lock
        self._items = {}  # إسناد قاموس إلى self._items

    def get(self, capture_id: str) -> Capture:  # تعريف الدالة get(self, capture_id) ترجع Capture
        with self._lock:  # سياق مُدار: self._lock
            cap = self._items.get(capture_id)  # إسناد نتيجة استدعاء self._items.get (معامل واحد) إلى cap
        if not cap:  # شرط معكوس: ليس cap
            raise KeyError("capture_not_found")  # رفع KeyError('capture_not_found')
        return cap  # إرجاع cap

    def _remember(self, cap: Capture) -> None:  # تعريف الدالة _remember(self, cap) ترجع None
        with self._lock:  # سياق مُدار: self._lock
            self._items[cap.id] = cap  # إسناد cap إلى self._items[cap.id]
            if len(self._items) > 8:  # شرط: len(self._items) أكبر من 8
                oldest = sorted(self._items.values(), key=lambda c: c.created)[:-8]  # إسناد sorted(self._items.values(), key=دالة مجهولة)[] إلى oldest
                for old in oldest:  # دورة على oldest باسم old
                    self._items.pop(old.id, None)  # استدعاء self._items.pop (2 معاملات)
                    old.close()  # استدعاء old.close

    def start(self, url: str, guard: str = "") -> Capture:  # تعريف الدالة start(self, url, guard) ترجع Capture
        if not (url or "").startswith(("http://", "https://")):  # شرط معكوس: ليس url أو ''.startswith(مجموعة)
            url = "http://" + (url or "").lstrip("/")  # حساب جمع بين 'http://' وurl أو ''.lstrip('/') وإسناده إلى url
        if is_kirapass_url(url, guard):  # شرط: نتيجة is_kirapass_url(url, guard)
            raise ValueError("target_is_kirapass")  # رفع ValueError('target_is_kirapass')
        cap = Capture(url, guard)  # إسناد نتيجة استدعاء Capture (2 معاملات) إلى cap
        self._exchange(cap, "GET", cap.start_url, kind="navigate")  # استدعاء self._exchange (3 معاملات، kind=…)
        self._remember(cap)  # استدعاء self._remember (معامل واحد)
        return cap  # إرجاع cap

    def step(self, capture_id: str, payload: dict, guard: str = "") -> dict:  # تعريف الدالة step(self, capture_id, payload, guard) ترجع dict
        cap = self.get(capture_id)  # إسناد نتيجة استدعاء self.get (معامل واحد) إلى cap
        if guard:  # شرط: guard
            cap.guard = guard  # إسناد guard إلى cap.guard
        kind = (payload.get("kind") or payload.get("type") or "navigate").lower()  # إسناد نتيجة استدعاء payload.get('kind') أو payload.get('type') أو 'navigate'.lower إلى kind
        if kind in ("kp-form",):  # شرط: kind ضمن مجموعة
            kind = "form"  # إسناد القيمة الثابتة kind
        if kind in ("kp-fetch", "kp-xhr"):  # شرط: kind ضمن مجموعة
            kind = payload.get("kind") or "fetch"  # دمج منطقي (أو) وإسناده إلى kind
        method = (payload.get("method") or "GET").upper()  # إسناد نتيجة استدعاء payload.get('method') أو 'GET'.upper إلى method
        url = payload.get("url") or cap.url  # دمج منطقي (أو) وإسناده إلى url
        if is_kirapass_url(url, cap.guard):  # شرط: نتيجة is_kirapass_url(url, cap.guard)
            return {"ok": False, "error": "blocked_kirapass_target"}  # إرجاع قاموس
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else None  # إسناد payload.get('fields') إن isinstance(payload.get('fields'), dict) وإلا None إلى fields
        before = payload.get("fields_before") if isinstance(payload.get("fields_before"), dict) else None  # إسناد payload.get('fields_before') إن isinstance(payload.get('fields_before'), dict) وإلا None إلى before
        after = payload.get("fields_after") if isinstance(payload.get("fields_after"), dict) else None  # إسناد payload.get('fields_after') إن isinstance(payload.get('fields_after'), dict) وإلا None إلى after
        headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}  # إسناد payload.get('headers') إن isinstance(payload.get('headers'), dict) وإلا قاموس إلى headers
        content_type = payload.get("content_type") or ""  # دمج منطقي (أو) وإسناده إلى content_type
        body = payload.get("body") if isinstance(payload.get("body"), str) else None  # إسناد payload.get('body') إن isinstance(payload.get('body'), str) وإلا None إلى body
        if after or before:  # شرط مركّب (أو)
            self._learn_password(cap, before or {}, after or fields or {},  # استدعاء self._learn_password (4 معاملات)
                                 (after or fields or {}).keys())  # تكملة السطر السابق داخل القوس
        if fields:  # شرط: fields
            cap.last_fields_redacted = redact_fields(fields)  # إسناد نتيجة استدعاء redact_fields (معامل واحد) إلى cap.last_fields_redacted
            cap._last_raw_fields = dict(fields)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى cap._last_raw_fields
            for key, value in fields.items():  # دورة على fields.items() باسم مجموعة
                if looks_secret_name(key) and value:  # شرط مركّب (و)
                    cap._strip_values.append(str(value))  # استدعاء cap._strip_values.append (معامل واحد)
        data = fields  # إسناد fields إلى data
        if data is None and body and "json" in (content_type or "").lower():  # شرط مركّب (و)
            try:  # بدايةtry محمية (يليها except/finally)
                parsed = json.loads(body)  # إسناد نتيجة استدعاء json.loads (معامل واحد) إلى parsed
                data = parsed if isinstance(parsed, dict) else body  # إسناد parsed إن isinstance(parsed, dict) وإلا body إلى data
            except Exception:  # تكملة السطر السابق داخل القوس
                data = body  # إسناد body إلى data
        elif data is None:  # شرط: data هو نفسه None
            data = body  # إسناد body إلى data
        frame_kind = "fetch" if kind in ("fetch", "xhr") else kind  # إسناد 'fetch' إن مقارنة وإلا kind إلى frame_kind
        resp, hops = self._exchange(  # إسناد نتيجة استدعاء self._exchange (3 معاملات، data=…، headers=…، content_type=…، kind=…) إلى مجموعة
            cap, method, url, data=data, headers=headers,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            content_type=content_type, kind=frame_kind)  # المعامل المسمّى content_type
        public = cap.as_public()  # إسناد نتيجة استدعاء cap.as_public إلى public
        public["ok"] = True  # إسناد القيمة الثابتة public['ok']
        public["meta"] = hops[-1] if hops else {"status": cap.last_status}  # إسناد hops[نفي/سالب] إن hops وإلا قاموس إلى public['meta']
        public["redirects"] = hops[:-1]  # إسناد hops[] إلى public['redirects']
        public["frame_body"] = cap.html if frame_kind in ("fetch", "xhr") else ""  # إسناد cap.html إن مقارنة وإلا '' إلى public['frame_body']
        if frame_kind in ("fetch", "xhr"):  # شرط: frame_kind ضمن مجموعة
            public["frame_body"] = resp.decode()[:400000] if resp is not None else ""  # إسناد resp.decode()[] إن مقارنة وإلا '' إلى public['frame_body']
        public["url"] = cap.url  # إسناد cap.url إلى public['url']
        public["needs_browser_js"] = bool(cap.pass_learn.get("needs_browser_js"))  # إسناد نتيجة استدعاء bool (معامل واحد) إلى public['needs_browser_js']
        public["reason_ar"] = cap.pass_learn.get("reason_ar") or ""  # دمج منطقي (أو) وإسناده إلى public['reason_ar']
        public["next_ar"] = cap.pass_learn.get("next_ar") or ""  # دمج منطقي (أو) وإسناده إلى public['next_ar']
        public["pass_mode"] = cap.pass_learn.get("pass_mode") or ""  # دمج منطقي (أو) وإسناده إلى public['pass_mode']
        public["marked"] = bool(cap.marks)  # إسناد نتيجة استدعاء bool (معامل واحد) إلى public['marked']
        return public  # إرجاع public

    # تعليم صفحة كنجاح/حالة مرفوض إن كان فيها نموذج دخول: وإلا تُتعلَّم
    # صفحة الدخول نفسها كصفحة نجاح فيصبح كل رفض نجاحاً.
    def mark(self, capture_id: str, mark: str) -> dict:  # تعريف الدالة mark(self, capture_id, mark) ترجع dict
        cap = self.get(capture_id)  # إسناد نتيجة استدعاء self.get (معامل واحد) إلى cap
        mark = (mark or "").lower().strip()  # إسناد نتيجة استدعاء mark أو ''.lower().strip إلى mark
        if mark == "statistics":  # شرط: mark يساوي 'statistics'
            mark = "status"  # إسناد القيمة الثابتة mark
        if mark not in ("success", "reject", "status"):  # شرط: mark ليس ضمن مجموعة
            return {"ok": False, "error": "bad_mark"}  # إرجاع قاموس
        current_form = portals.parse_form(cap.html, cap.url)  # إسناد نتيجة استدعاء portals.parse_form (2 معاملات) إلى current_form
        if mark in ("success", "status") and _is_login_form(current_form):  # شرط مركّب (و)
            return {  # إرجاع قاموس
                "ok": False,  # مفتاح ok في القاموس
                "error": "login_form_still_visible",  # مفتاح error في القاموس
                "message_ar": (  # مفتاح message_ar في القاموس
                    "ما زالت الصفحة تعرض نموذج الدخول؛ افتح صفحة النجاح أو "  # تكملة السطر السابق داخل القوس
                    "الإحصائيات أولاً ثم علّمها."  # تكملة السطر السابق داخل القوس
                ),  # إغلاق القوس المفتوح في السطر السابق
            }  # إغلاق القوس المفتوح في السطر السابق
        words = learn_words(cap.html, cap._strip_values)  # إسناد نتيجة استدعاء learn_words (2 معاملات) إلى words
        entry = {"mark": mark, "url": safe_url(cap.url),  # إسناد قاموس إلى entry
                 "status": cap.last_status, "words": words}  # مفتاح status في القاموس
        for existing in cap.marks:  # دورة على cap.marks باسم existing
            if (existing.get("mark") == mark and existing.get("url") == entry["url"]  # شرط مركّب (و)
                    and existing.get("status") == entry["status"]  # تكملة السطر السابق داخل القوس
                    and existing.get("words") == words):  # تكملة تعريف متعدد الأسطر
                return {"ok": True, "message_ar": "هذه الصفحة مسجّلة بهذا التصنيف بالفعل.",  # إرجاع قاموس
                        "mark": existing}  # مفتاح mark في القاموس
        cap.marks.append(entry)  # استدعاء cap.marks.append (معامل واحد)
        if mark == "success":  # شرط: mark يساوي 'success'
            cap.success_words = words  # إسناد words إلى cap.success_words
            cap.success_url_contains = success_url_hint(cap.url)  # إسناد نتيجة استدعاء success_url_hint (معامل واحد) إلى cap.success_url_contains
            msg = "عُلّمت صفحة النجاح. سأحتفظ بالكلمات والرابط الآمن فقط."  # إسناد القيمة الثابتة msg
        elif mark == "reject":  # شرط: mark يساوي 'reject'
            cap.reject_words = words  # إسناد words إلى cap.reject_words
            msg = "عُلّمت صفحة الرفض."  # إسناد القيمة الثابتة msg
        else:  # مفتاح else في القاموس
            cap.stats_url = success_url_hint(cap.url) or (urlsplit(cap.url).path or "/")  # دمج منطقي (أو) وإسناده إلى cap.stats_url
            msg = "عُلّمت صفحة الإحصائيات."  # إسناد القيمة الثابتة msg
        return {"ok": True, "message_ar": msg, "mark": entry}  # إرجاع قاموس

    def finish(self, capture_id: str, st: store.Store = None,  # تعريف الدالة finish(self, capture_id, st, hints) ترجع dict
               hints: dict = None) -> dict:  # مفتاح hints في القاموس
        cap = self.get(capture_id)  # إسناد نتيجة استدعاء self.get (معامل واحد) إلى cap
        report = self._build_report(cap)  # إسناد نتيجة استدعاء self._build_report (معامل واحد) إلى report
        cap.report = report  # إسناد report إلى cap.report
        profile = self._build_profile(cap, hints or {})  # إسناد نتيجة استدعاء self._build_profile (2 معاملات) إلى profile
        cap.profile = profile  # إسناد profile إلى cap.profile
        if st is not None:  # شرط: st ليس نفسه None
            path = st.save_run(report)  # إسناد نتيجة استدعاء st.save_run (معامل واحد) إلى path
            cap.report_name = os_basename(path)  # إسناد نتيجة استدعاء os_basename (معامل واحد) إلى cap.report_name
            report["file"] = cap.report_name  # إسناد cap.report_name إلى report['file']
            try:  # بدايةtry محمية (يليها except/finally)
                saved = st.put(profile)  # إسناد نتيجة استدعاء st.put (معامل واحد) إلى saved
                cap.profile = saved  # إسناد saved إلى cap.profile
            except Exception:  # تكملة السطر السابق داخل القوس
                pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
        cap.close()  # استدعاء cap.close
        public = cap.as_public()  # إسناد نتيجة استدعاء cap.as_public إلى public
        public["ok"] = True  # إسناد القيمة الثابتة public['ok']
        public["report"] = report  # إسناد report إلى public['report']
        public["profile"] = cap.profile  # إسناد cap.profile إلى public['profile']
        public["report_name"] = cap.report_name  # إسناد cap.report_name إلى public['report_name']
        public["needs_browser_js"] = bool(profile.get("capture_needs_browser_js"))  # إسناد نتيجة استدعاء bool (معامل واحد) إلى public['needs_browser_js']
        public["reason_ar"] = profile.get("capture_block_reason") or cap.pass_learn.get("reason_ar") or ""  # دمج منطقي (أو) وإسناده إلى public['reason_ar']
        public["next_ar"] = cap.pass_learn.get("next_ar") or (  # دمج منطقي (أو) وإسناده إلى public['next_ar']
            AR_NEXT_UNKNOWN if profile.get("capture_needs_browser_js") else "")  # تكملة السطر السابق داخل القوس
        return public  # إرجاع public

    def status(self, capture_id: str) -> dict:  # تعريف الدالة status(self, capture_id) ترجع dict
        return self.get(capture_id).as_public()  # إرجاع self.get(capture_id).as_public()

    def report_of(self, capture_id: str) -> dict:  # تعريف الدالة report_of(self, capture_id) ترجع dict
        cap = self.get(capture_id)  # إسناد نتيجة استدعاء self.get (معامل واحد) إلى cap
        if cap.report is None:  # شرط: cap.report هو نفسه None
            cap.report = self._build_report(cap)  # إسناد نتيجة استدعاء self._build_report (معامل واحد) إلى cap.report
        return cap.report  # إرجاع cap.report

    # -- الداخليات -------------------------------------------------------
    def _learn_password(self, cap: Capture, before: dict, after: dict,  # تعريف الدالة _learn_password(self, cap, before, after, sent_keys) ترجع None
                        sent_keys) -> None:  # تكملة تعريف متعدد الأسطر
        form = cap.form  # إسناد cap.form إلى form
        if not _is_login_form(form):  # شرط معكوس: ليس _is_login_form(form)
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        user_f, pass_f = form.user_field, form.pass_field  # إسناد مجموعة إلى مجموعة
        # نموذج فارغ لاحق (مثلاً erase-cookie على /status.html) ليس
        # دليلاً على تحويل كلمة المرور. تعلّم فقط من إرسال
        # أدخل فيه المسؤول فعلاً اسم مستخدم/بطاقة أو كلمة مرور.
        entered = any(str(before.get(key) or "").strip()  # إسناد نتيجة استدعاء any (معامل واحد) إلى entered
                      for key in (user_f, pass_f))  # تكملة السطر السابق داخل القوس
        if not entered:  # شرط معكوس: ليس entered
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        learned = infer_pass_mode(  # إسناد نتيجة استدعاء infer_pass_mode (6 معاملات) إلى learned
            before.get(user_f), before.get(pass_f),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            after.get(user_f), after.get(pass_f),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            cap.login_html, sent_keys)  # تكملة السطر السابق داخل القوس
        cap.pass_learn = learned  # إسناد learned إلى cap.pass_learn

    def _exchange(self, cap: Capture, method: str, url: str, data=None,  # تعريف الدالة _exchange(self, cap, method, url, data, headers, content_type, kind)
                  headers=None, content_type: str = "", kind: str = "navigate"):  # المعامل المسمّى headers
        extra = {}  # إسناد قاموس إلى extra
        for key, value in (headers or {}).items():  # دورة على headers أو قاموس.items() باسم مجموعة
            low = str(key).lower()  # إسناد نتيجة استدعاء str(key).lower إلى low
            if low in ("host", "cookie", "content-length", "connection"):  # شرط: low ضمن مجموعة
                continue  # الانتقال إلى الدورة التالية
            extra[key] = value  # إسناد value إلى extra[key]
        if content_type and "content-type" not in {k.lower() for k in extra}:  # شرط مركّب (و)
            extra["Content-Type"] = content_type  # إسناد content_type إلى extra['Content-Type']
        if cap.url and "referer" not in {k.lower() for k in extra}:  # شرط مركّب (و)
            extra["Referer"] = cap.url  # إسناد cap.url إلى extra['Referer']
        # المتصفحات ترسل Origin مع نماذج POST وطلبات fetch/XHR، لا مع
        # تنقّلات GET العادية. إضافته إلى GET ملتقط قد يغيّر
        # ردّ البوابة مقارنة بسير متصفح المستخدم الناجح.
        request_kind = (kind or "").lower()  # إسناد نتيجة استدعاء kind أو ''.lower إلى request_kind
        if (cap.url and (method.upper() != "GET" or  # شرط مركّب (و)
                         request_kind in ("fetch", "xhr")) and  # تكملة السطر السابق داخل القوس
                "origin" not in {k.lower() for k in extra}):  # تكملة تعريف متعدد الأسطر
            origin = urlsplit(cap.url)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى origin
            if origin.scheme and origin.netloc:  # شرط مركّب (و)
                extra["Origin"] = f"{origin.scheme}://{origin.netloc}"  # بناء نص منسّق وإسناده إلى extra['Origin']
        hops = []  # إسناد قائمة إلى hops
        body = data  # إسناد data إلى body
        last = None  # إسناد القيمة الثابتة last
        orig_method = method  # إسناد method إلى orig_method
        for _ in range(MAX_REDIRECTS + 1):  # دورة على range(جمع) باسم _
            if is_kirapass_url(url, cap.guard):  # شرط: نتيجة is_kirapass_url(url, cap.guard)
                raise ValueError("blocked_kirapass_target")  # رفع ValueError('blocked_kirapass_target')
            if method == "GET" and isinstance(body, dict):  # شرط مركّب (و)
                last = cap.session.request(  # إسناد نتيجة استدعاء cap.session.request (2 معاملات، params=…، headers=…، allow_redirects=…) إلى last
                    method, url, params=body, headers=extra, allow_redirects=False)  # تكملة السطر السابق داخل القوس
                body = None  # إسناد القيمة الثابتة body
            else:  # مفتاح else في القاموس
                last = cap.session.request(  # إسناد نتيجة استدعاء cap.session.request (2 معاملات، data=…، headers=…، allow_redirects=…) إلى last
                    method, url, data=body, headers=extra, allow_redirects=False)  # تكملة السطر السابق داخل القوس
            hop = _strip_hop(last)  # إسناد نتيجة استدعاء _strip_hop (معامل واحد) إلى hop
            hops.append(hop)  # استدعاء hops.append (معامل واحد)
            cap.redirects.append(hop)  # استدعاء cap.redirects.append (معامل واحد)
            if content_type:  # شرط: content_type
                cap.content_types.append(content_type.split(";")[0])  # استدعاء cap.content_types.append (معامل واحد)
            cap.custom_headers = sorted(set(cap.custom_headers) |  # إسناد نتيجة استدعاء sorted (معامل واحد) إلى cap.custom_headers
                                        set(hop.get("custom_request_headers") or []))  # تكملة السطر السابق داخل القوس
            cap.cookie_names = cookie_names_from_session(cap.session)  # إسناد نتيجة استدعاء cookie_names_from_session (معامل واحد) إلى cap.cookie_names
            if not last.is_redirect():  # شرط معكوس: ليس last.is_redirect()
                break  # قطع الحلقة فوراً
            url = urljoin(url, last.location)  # إسناد نتيجة استدعاء urljoin (2 معاملات) إلى url
            if last.status in (301, 302, 303) and method == "POST":  # شرط مركّب (و)
                method, body, extra = "GET", None, {}  # إسناد مجموعة إلى مجموعة
        cap.url = last.url if last is not None else url  # إسناد last.url إن مقارنة وإلا url إلى cap.url
        cap.last_status = last.status if last is not None else 0  # إسناد last.status إن مقارنة وإلا 0 إلى cap.last_status
        text = last.decode() if last is not None else ""  # إسناد last.decode() إن مقارنة وإلا '' إلى text
        ctype = (last.header("content-type") if last is not None else "") or ""  # دمج منطقي (أو) وإسناده إلى ctype
        if "html" in ctype.lower() or text.lstrip()[:15].lower().startswith(("<!", "<html")):  # شرط مركّب (أو)
            cap.html = text[:400000]  # إسناد text[] إلى cap.html
            page_form = portals.parse_form(cap.html, cap.url)  # إسناد نتيجة استدعاء portals.parse_form (2 معاملات) إلى page_form
            if _is_login_form(page_form):  # شرط: نتيجة _is_login_form(page_form)
                cap.form = page_form  # إسناد page_form إلى cap.form
                cap.login_html = cap.html  # إسناد cap.html إلى cap.login_html
                cap.method = page_form.method  # إسناد page_form.method إلى cap.method
        cap.events.append({  # استدعاء cap.events.append (معامل واحد)
            "kind": kind,  # مفتاح kind في القاموس
            "method": orig_method,  # مفتاح method في القاموس
            "content_type": (ctype.split(";")[0] if ctype else content_type),  # مفتاح content_type في القاموس
            "request_fields": list(cap.last_fields_redacted),  # مفتاح request_fields في القاموس
            "response": hops[-1] if hops else {},  # مفتاح response في القاموس
            "redirects": hops[:-1],  # مفتاح redirects في القاموس
            "cookie_names": list(cap.cookie_names),  # مفتاح cookie_names في القاموس
            "http_200_not_verdict": cap.last_status == 200,  # مفتاح http_200_not_verdict في القاموس
        })  # إغلاق القوس المفتوح في السطر السابق
        cap.last_fields_redacted = []  # إسناد قائمة إلى cap.last_fields_redacted
        cap._last_raw_fields = {}  # إسناد قاموس إلى cap._last_raw_fields
        return last, hops  # إرجاع مجموعة

    def _build_report(self, cap: Capture) -> dict:  # تعريف الدالة _build_report(self, cap) ترجع dict
        report = {  # إسناد قاموس إلى report
            "kind": "capture",  # مفتاح kind في القاموس
            "profile": "capture",  # مفتاح profile في القاموس
            "started": time.strftime("%Y-%m-%d %H:%M:%S",  # مفتاح started في القاموس
                                     time.localtime(cap.created)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            "start_url": safe_url(cap.start_url),  # مفتاح start_url في القاموس
            "final_url": safe_url(cap.url),  # مفتاح final_url في القاموس
            "events": cap.events,  # مفتاح events في القاموس
            "marks": cap.marks,  # مفتاح marks في القاموس
            "pass_mode": cap.pass_learn.get("pass_mode") or "",  # مفتاح pass_mode في القاموس
            "capture_needs_browser_js": bool(cap.pass_learn.get("needs_browser_js")),  # مفتاح capture_needs_browser_js في القاموس
            "reason": cap.pass_learn.get("reason") or "",  # مفتاح reason في القاموس
            "reason_ar": cap.pass_learn.get("reason_ar") or "",  # مفتاح reason_ar في القاموس
            "next_ar": cap.pass_learn.get("next_ar") or "",  # مفتاح next_ar في القاموس
            "next_en": cap.pass_learn.get("next_en") or "",  # مفتاح next_en في القاموس
            "success_words": list(cap.success_words),  # مفتاح success_words في القاموس
            "success_url_contains": cap.success_url_contains,  # مفتاح success_url_contains في القاموس
            "stats_url": cap.stats_url,  # مفتاح stats_url في القاموس
            "method": cap.method,  # مفتاح method في القاموس
            "content_types": sorted(set(cap.content_types)),  # مفتاح content_types في القاموس
            "custom_header_names": list(cap.custom_headers),  # مفتاح custom_header_names في القاموس
            "cookie_names": list(cap.cookie_names),  # مفتاح cookie_names في القاموس
            "form_fields": [i["name"] for i in redact_fields(  # مفتاح form_fields في القاموس
                cap.form.fields if cap.form else {})],  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            "http_200_policy": "never_success_or_reject_without_mark_or_evidence",  # مفتاح http_200_policy في القاموس
            "curl_export": export_curl(cap),  # مفتاح curl_export في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق
        try:  # بدايةtry محمية (يليها except/finally)
            scrubbed = _scrub(json.dumps(report, ensure_ascii=False),  # إسناد نتيجة استدعاء _scrub (2 معاملات) إلى scrubbed
                              cap._strip_values)  # تكملة السطر السابق داخل القوس
            return json.loads(scrubbed)  # إرجاع json.loads(scrubbed)
        except Exception:  # تكملة السطر السابق داخل القوس
            return report  # إرجاع report

    def _build_profile(self, cap: Capture, hints: dict) -> dict:  # تعريف الدالة _build_profile(self, cap, hints) ترجع dict
        form = cap.form or portals.parse_form(cap.html, cap.url)  # دمج منطقي (أو) وإسناده إلى form
        needs = bool(cap.pass_learn.get("needs_browser_js"))  # إسناد نتيجة استدعاء bool (معامل واحد) إلى needs
        mode = cap.pass_learn.get("pass_mode") or ""  # دمج منطقي (أو) وإسناده إلى mode
        if needs:  # شرط: needs
            mode = mode if mode in KNOWN_PASS_MODES else "empty"  # إسناد mode إن مقارنة وإلا 'empty' إلى mode
        extra = extra_fields_for_profile(form.fields if form else {})  # إسناد نتيجة استدعاء extra_fields_for_profile (معامل واحد) إلى extra
        host = (urlsplit(cap.start_url).hostname or "capture").replace(".", "-")  # إسناد نتيجة استدعاء urlsplit(cap.start_url).hostname أو 'capture'.replace (2 معاملات) إلى host
        prof = store.new_profile(  # إسناد نتيجة استدعاء store.new_profile (name=…، login_url=…، method=…، user_field=…، pass_field=…، pass_mode=…، extra_fields=…، dst_field=…، dst_value=…، popup_field=…، send_dst=…، send_popup=…، chap=…، success_words=…، success_url_contains=…، capture_needs_browser_js=…، capture_block_reason=…، stats_url=…، prefix=…، length=…، charset=…) إلى prof
            name=hints.get("name") or host,  # المعامل المسمّى name
            login_url=(form.action if form else "") or cap.start_url,  # المعامل المسمّى login_url
            method=(form.method if form else cap.method) or "post",  # المعامل المسمّى method
            user_field=(form.user_field if form else "") or "username",  # المعامل المسمّى user_field
            pass_field=(form.pass_field if form else "") or "password",  # المعامل المسمّى pass_field
            pass_mode=mode or "empty",  # المعامل المسمّى pass_mode
            extra_fields=extra,  # المعامل المسمّى extra_fields
            dst_field=(form.dst_field if form else "dst") or "dst",  # المعامل المسمّى dst_field
            dst_value=(form.dst_value if form else "") or "",  # المعامل المسمّى dst_value
            popup_field=(form.popup_field if form else "popup") or "popup",  # المعامل المسمّى popup_field
            send_dst=bool(form and form.dst_field in (form.fields or {})),  # المعامل المسمّى send_dst
            send_popup=bool(form and form.popup_field in (form.fields or {})),  # المعامل المسمّى send_popup
            chap=(form.chap if form else None),  # المعامل المسمّى chap
            success_words=list(cap.success_words),  # المعامل المسمّى success_words
            success_url_contains=cap.success_url_contains,  # المعامل المسمّى success_url_contains
            capture_needs_browser_js=needs,  # المعامل المسمّى capture_needs_browser_js
            capture_block_reason=(cap.pass_learn.get("reason_ar") or "") if needs else "",  # المعامل المسمّى capture_block_reason
            stats_url=cap.stats_url,  # المعامل المسمّى stats_url
            prefix=hints.get("prefix") or "",  # المعامل المسمّى prefix
            length=int(hints.get("length") or 10),  # المعامل المسمّى length
            charset=hints.get("charset") or store.CHARSETS["digits"],  # المعامل المسمّى charset
        )  # إغلاق القوس المفتوح في السطر السابق
        return prof  # إرجاع prof


def os_basename(path: str) -> str:  # تعريف الدالة os_basename(path) ترجع str
    import os  # استيراد الوحدة os من المكتبة
    return os.path.basename(path)  # إرجاع os.path.basename(path)


# أمر curl منقّح: كل قيمة سرّية ⇒ <redacted> والترويسات المخصصة أسماء فقط.
def export_curl(cap: "Capture") -> str:  # تعريف الدالة export_curl(cap) ترجع str
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Build a redacted curl sketch of the last login request (no secrets).

    Values that look like secrets/tokens are replaced with placeholders so the
    operator can study the request shape without storing credentials.
    """  # نهاية النص متعدد الأسطر
    method = (cap.method or "POST").upper()  # إسناد نتيجة استدعاء cap.method أو 'POST'.upper إلى method
    url = _safe_page_url(cap.url or cap.start_url or "")  # إسناد نتيجة استدعاء _safe_page_url (معامل واحد) إلى url
    parts = [f"curl -X {method} '{url}'"]  # إسناد قائمة إلى parts
    for name in (cap.custom_headers or []):  # دورة على cap.custom_headers أو قائمة باسم name
        parts.append(f"  -H '{name}: <redacted>'")  # استدعاء parts.append (معامل واحد)
    fields = []  # إسناد قائمة إلى fields
    raw = getattr(cap, "_last_raw_fields", None) or {}  # دمج منطقي (أو) وإسناده إلى raw
    if not raw and cap.form and getattr(cap.form, "fields", None):  # شرط مركّب (و)
        raw = dict(cap.form.fields)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى raw
    for name, value in (raw or {}).items():  # دورة على raw أو قاموس.items() باسم مجموعة
        key = str(name)  # إسناد نتيجة استدعاء str (معامل واحد) إلى key
        if looks_secret_name(key) or looks_token_name(key) or looks_live_token(  # شرط مركّب (أو)
                "" if value is None else str(value)):  # تكملة تعريف متعدد الأسطر
            fields.append(f"{key}=<redacted>")  # استدعاء fields.append (معامل واحد)
        else:  # مفتاح else في القاموس
            fields.append(f"{key}={value}")  # استدعاء fields.append (معامل واحد)
    if fields:  # شرط: fields
        body = "&".join(fields)  # إسناد نتيجة استدعاء '&'.join (معامل واحد) إلى body
        parts.append(f"  --data-raw '{body}'")  # استدعاء parts.append (معامل واحد)
    parts.append("  # secrets redacted — for manual review only")  # استدعاء parts.append (معامل واحد)
    return " \\\n".join(parts)  # إرجاع ' \\\n'.join(parts)


def _scrub(blob: str, values) -> str:  # تعريف الدالة _scrub(blob, values) ترجع str
    out = blob  # إسناد blob إلى out
    for value in values or []:  # دورة على values أو قائمة باسم value
        text = str(value)  # إسناد نتيجة استدعاء str (معامل واحد) إلى text
        if len(text) >= 3:  # شرط: len(text) أكبر أو يساوي 3
            out = out.replace(text, "")  # إسناد نتيجة استدعاء out.replace (2 معاملات) إلى out
            out = out.replace(json.dumps(text)[1:-1], "")  # إسناد نتيجة استدعاء out.replace (2 معاملات) إلى out
    return out  # إرجاع out


# المحور على مستوى الوحدة يستخدمه سيرفر الويب
HUB = Hub()  # إسناد نتيجة استدعاء Hub إلى HUB
