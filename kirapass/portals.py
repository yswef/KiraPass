# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Read a captive-portal login page and copy exactly what the browser sends.

No questions are asked here: the page itself says which URL the form posts to,
which field names are used, which hidden values (dst / popup / chap-id) must
travel with the request.  MikroTik's `md5.js` trick is detected too, because
most custom card templates use it:

    document.login.password.value = hexMD5('$(chap-id)' + password +
                                          '$(chap-challenge)')

Sending the raw card instead of that hash is a silent killer: the portal
rejects everything, and the tool looks broken.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import html as htmlmod  # استيراد الوحدة html من المكتبة
import re  # استيراد الوحدة re من المكتبة
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit  # استيراد parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit من الوحدة urllib.parse

FORM_RE = re.compile(r"<form\b[^>]*>", re.I)  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى FORM_RE
INPUT_RE = re.compile(r"<input\b[^>]*>", re.I)  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى INPUT_RE
ATTR_RE = re.compile(r"([\w\-:]+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى ATTR_RE
CHAP_CALL_RE = re.compile(  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى CHAP_CALL_RE
    r"hexMD5\s*\(\s*'([^']*)'\s*\+\s*([^+)]+?)\s*\+\s*'([^']*)'\s*\)", re.I)  # تكملة السطر السابق داخل القوس
CHAP_SIMPLE_RE = re.compile(r"hexMD5\s*\(\s*([^)]+)\)", re.I)  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى CHAP_SIMPLE_RE
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى TITLE_RE

# حقول يجب ألا ننسخها أبداً كـ«إضافات ثابتة» (هي تحمل قيمنا نحن).
CORE_FIELDS = ("username", "user", "password", "passwd", "pass", "card",  # إسناد مجموعة إلى CORE_FIELDS
               "code", "voucher", "dst", "popup")  # تكملة السطر السابق داخل القوس


def _attrs(tag: str) -> dict:  # تعريف الدالة _attrs(tag) ترجع dict
    out = {}  # إسناد قاموس إلى out
    for name, value in ATTR_RE.findall(tag):  # دورة على ATTR_RE.findall(tag) باسم مجموعة
        value = value.strip()  # إسناد نتيجة استدعاء value.strip إلى value
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:  # شرط مركّب (و)
            value = value[1:-1]  # إسناد value[] إلى value
        # HTML يرمّز علامة & كـ&amp; داخل الخصائص. فكّك الترميز قبل
        # ضم/تحليل الرابط، وإلا تغيّر شكل رابط المتصفح.
        out[name.lower()] = htmlmod.unescape(value)  # إسناد نتيجة استدعاء htmlmod.unescape (معامل واحد) إلى out[name.lower()]
    return out  # إرجاع out


class FormInfo:  # تعريف الصنف FormInfo
    def __init__(self, action, method, fields, inputs):  # تعريف الدالة __init__(self, action, method, fields, inputs)
        self.action = action  # إسناد action إلى self.action
        self.method = method  # إسناد method إلى self.method
        self.fields = fields          # الاسم ← القيمة الافتراضية
        self.inputs = inputs          # قائمة (الاسم، النوع)
        self.user_field = ""  # إسناد القيمة الثابتة self.user_field
        self.pass_field = ""  # إسناد القيمة الثابتة self.pass_field
        self.dst_field = ""  # إسناد القيمة الثابتة self.dst_field
        self.dst_value = ""  # إسناد القيمة الثابتة self.dst_value
        self.popup_field = ""  # إسناد القيمة الثابتة self.popup_field
        self.extra_fields = {}        # حقول مخفية تُرسل دائماً
        self.chap = None              # {'id':..,'challenge':..,'field':'password'}

    @property  # مُزخرف (decorator) بـproperty
    def is_post(self) -> bool:  # تعريف الدالة is_post(self) ترجع bool
        return self.method.lower() == "post"  # إرجاع مقارنة

    def as_dict(self) -> dict:  # تعريف الدالة as_dict(self) ترجع dict
        return {  # إرجاع قاموس
            "action": self.action,  # مفتاح action في القاموس
            "method": self.method,  # مفتاح method في القاموس
            "user_field": self.user_field,  # مفتاح user_field في القاموس
            "pass_field": self.pass_field,  # مفتاح pass_field في القاموس
            "dst_field": self.dst_field,  # مفتاح dst_field في القاموس
            "dst_value": self.dst_value,  # مفتاح dst_value في القاموس
            "popup_field": self.popup_field,  # مفتاح popup_field في القاموس
            "extra_fields": self.extra_fields,  # مفتاح extra_fields في القاموس
            "all_fields": list(self.fields.keys()),  # مفتاح all_fields في القاموس
            "chap": self.chap or None,  # مفتاح chap في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق


def _form_segments(html: str) -> list:  # تعريف الدالة _form_segments(html) ترجع list
    """-> [(form tag, html inside that form)] for every <form> on the page."""  # نص توثيقي (docstring) يشرح ما يليه
    out = []  # إسناد قائمة إلى out
    marks = list(FORM_RE.finditer(html))  # إسناد نتيجة استدعاء list (معامل واحد) إلى marks
    for i, m in enumerate(marks):  # دورة على enumerate(marks) باسم مجموعة
        start = m.end()  # إسناد نتيجة استدعاء m.end إلى start
        close = html.lower().find("</form", start)  # إسناد نتيجة استدعاء html.lower().find (2 معاملات) إلى close
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)  # إسناد marks[جمع].start() إن مقارنة وإلا len(html) إلى end
        if close != -1:  # شرط: close لا يساوي نفي/سالب
            end = min(end, close)  # إسناد نتيجة استدعاء min (2 معاملات) إلى end
        out.append((m.group(0), html[start:max(end, start)]))  # استدعاء out.append (معامل واحد)
    return out  # إرجاع out


def _score_form(attrs: dict, segment: str) -> int:  # تعريف الدالة _score_form(attrs, segment) ترجع int
    """How much does this form look like the login form? (higher = better)."""  # نص توثيقي (docstring) يشرح ما يليه
    score = 0  # إسناد القيمة الثابتة score
    tags = [_attrs(t) for t in INPUT_RE.findall(segment)]  # بناء اشتقاق قائمة وإسناده إلى tags
    types = [(a.get("type") or "text").lower() for a in tags]  # بناء اشتقاق قائمة وإسناده إلى types
    names = [(a.get("name") or "").lower() for a in tags]  # بناء اشتقاق قائمة وإسناده إلى names
    if "password" in types:  # شرط: 'password' ضمن types
        score += 5  # تحديث score بعملية جمع
    if any(t in ("text", "tel", "number", "email") for t in types):  # شرط: نتيجة any(مولّد)
        score += 2  # تحديث score بعملية جمع
    if any(w in n for n in names for w in ("user", "pass", "card", "voucher",  # شرط: نتيجة any(مولّد)
                                           "code", "pin")):  # تكملة تعريف متعدد الأسطر
        score += 2  # تحديث score بعملية جمع
    blob = " ".join((attrs.get("name") or "", attrs.get("id") or "",  # إسناد نتيجة استدعاء ' '.join(مجموعة).lower إلى blob
                     attrs.get("action") or "")).lower()  # تكملة السطر السابق داخل القوس
    if any(w in blob for w in ("login", "logon", "auth", "hotspot", "portal",  # شرط: نتيجة any(مولّد)
                               "signin", "sign-in", "connect")):  # تكملة تعريف متعدد الأسطر
        score += 3  # تحديث score بعملية جمع
    if (attrs.get("method") or "").lower() == "post":  # شرط: attrs.get('method') أو ''.lower() يساوي 'post'
        score += 1  # تحديث score بعملية جمع
    return score  # إرجاع score


# يختار نموذج الدخول من بين نماذج الصفحة بأعلى نتيجة، لا أول نموذج.
# يسقط على username/password إن لم يجد أسماء أوضح.
def parse_form(html: str, base_url: str) -> FormInfo:  # تعريف الدالة parse_form(html, base_url) ترجع FormInfo
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Find the login form and classify every field in it.

    A captive-portal page often carries more than one form (a language picker,
    a search box, a "buy a card" form).  Taking the first <form> blindly used
    to fill the request with the wrong field names, so every form is scored
    and the most login-looking one wins; fields are then read from inside it.
    """  # نهاية النص متعدد الأسطر
    html = html or ""  # دمج منطقي (أو) وإسناده إلى html
    base_url = htmlmod.unescape(str(base_url or ""))  # إسناد نتيجة استدعاء htmlmod.unescape (معامل واحد) إلى base_url
    action, method = base_url, "post"  # إسناد مجموعة إلى مجموعة
    body = html  # إسناد html إلى body

    segments = _form_segments(html)  # إسناد نتيجة استدعاء _form_segments (معامل واحد) إلى segments
    # رابط متصفح ناجح منسوخ غالباً *هو* إرسال النموذج:
    # /login?username=293...&password=
    # إن لم يكن في الصفحة نموذج HTML، فذلك الاستعلام دليل مباشر على GET —
    # لا تسقط على POST ولا تضف username ثانياً لاحقاً.
    query_pairs = parse_qsl(urlsplit(base_url).query, keep_blank_values=True)  # إسناد نتيجة استدعاء parse_qsl (معامل واحد، keep_blank_values=…) إلى query_pairs
    query_names = {name.lower() for name, _ in query_pairs}  # بناء اشتقاق مجموعة وإسناده إلى query_names
    query_login = (not segments and  # دمج منطقي (و) وإسناده إلى query_login
                   any(any(w in name for w in  # تكملة السطر السابق داخل القوس
                           ("user", "login", "card", "voucher", "account"))  # تكملة السطر السابق داخل القوس
                       for name in query_names) and  # تكملة السطر السابق داخل القوس
                   any(any(w in name for w in ("pass", "pwd", "pin"))  # تكملة السطر السابق داخل القوس
                       for name in query_names))  # تكملة السطر السابق داخل القوس
    if query_login:  # شرط: query_login
        method = "get"  # إسناد القيمة الثابتة method
    if segments:  # شرط: segments
        best = max(segments, key=lambda pair: _score_form(_attrs(pair[0]),  # إسناد نتيجة استدعاء max (معامل واحد، key=…) إلى best
                                                          pair[1]))  # تكملة السطر السابق داخل القوس
        a = _attrs(best[0])  # إسناد نتيجة استدعاء _attrs (معامل واحد) إلى a
        if a.get("action"):  # شرط: نتيجة a.get('action')
            action = urljoin(base_url, a["action"])  # إسناد نتيجة استدعاء urljoin (2 معاملات) إلى action
        if a.get("method"):  # شرط: نتيجة a.get('method')
            method = a["method"].lower()  # إسناد نتيجة استدعاء a['method'].lower إلى method
        if INPUT_RE.search(best[1]):  # شرط: نتيجة INPUT_RE.search(best[1])
            body = best[1]  # إسناد best[1] إلى body

    fields, inputs = {}, []  # إسناد مجموعة إلى مجموعة
    for tag in INPUT_RE.findall(body):  # دورة على INPUT_RE.findall(body) باسم tag
        a = _attrs(tag)  # إسناد نتيجة استدعاء _attrs (معامل واحد) إلى a
        name = a.get("name")  # إسناد نتيجة استدعاء a.get (معامل واحد) إلى name
        if not name:  # شرط معكوس: ليس name
            continue  # الانتقال إلى الدورة التالية
        fields[name] = a.get("value", "")  # إسناد نتيجة استدعاء a.get (2 معاملات) إلى fields[name]
        inputs.append((name, a.get("type", "text").lower()))  # استدعاء inputs.append (معامل واحد)

    if not inputs and body is not html:  # شرط مركّب (و)
        # صفحة مشوّهة: وُجد وسم النموذج لكن الحقول خارجه
        for tag in INPUT_RE.findall(html):  # دورة على INPUT_RE.findall(html) باسم tag
            a = _attrs(tag)  # إسناد نتيجة استدعاء _attrs (معامل واحد) إلى a
            name = a.get("name")  # إسناد نتيجة استدعاء a.get (معامل واحد) إلى name
            if not name:  # شرط معكوس: ليس name
                continue  # الانتقال إلى الدورة التالية
            fields[name] = a.get("value", "")  # إسناد نتيجة استدعاء a.get (2 معاملات) إلى fields[name]
            inputs.append((name, a.get("type", "text").lower()))  # استدعاء inputs.append (معامل واحد)

    if query_login:  # شرط: query_login
        existing = {name for name, _type in inputs}  # بناء اشتقاق مجموعة وإسناده إلى existing
        for name, value in query_pairs:  # دورة على query_pairs باسم مجموعة
            fields.setdefault(name, value)  # استدعاء fields.setdefault (2 معاملات)
            if name in existing:  # شرط: name ضمن existing
                continue  # الانتقال إلى الدورة التالية
            low = name.lower()  # إسناد نتيجة استدعاء name.lower إلى low
            typ = ("password" if any(w in low for w in ("pass", "pwd", "pin"))  # إسناد 'password' إن any(مولّد) وإلا 'text' إن any(مولّد) وإلا 'hidden' إلى typ
                   else "text" if any(w in low for w in  # تكملة السطر السابق داخل القوس
                                      ("user", "login", "card", "voucher",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                       "account"))  # تكملة السطر السابق داخل القوس
                   else "hidden")  # تكملة السطر السابق داخل القوس
            inputs.append((name, typ))  # استدعاء inputs.append (معامل واحد)

    info = FormInfo(action, method, fields, inputs)  # إسناد نتيجة استدعاء FormInfo (4 معاملات) إلى info

    # حقل كلمة المرور أولاً (type=password يفوز، ثم الاسم)
    # دمج منطقي (أو) وإسناده إلى info.pass_field
    info.pass_field = _pick(inputs, lambda n, t: t == "password") or \
        _pick(inputs, lambda n, t: any(w in n.lower() for w in  # تكملة السطر السابق داخل القوس
                                       ("pass", "pwd", "pin", "voucher", "code"))  # تكملة السطر السابق داخل القوس
              and t not in ("hidden", "submit")) or "password"  # تكملة السطر السابق داخل القوس
    info.user_field = _pick(inputs, lambda n, t: n != info.pass_field  # دمج منطقي (أو) وإسناده إلى info.user_field
                            and any(w in n.lower() for w in  # تكملة السطر السابق داخل القوس
                                    ("user", "card", "code", "voucher", "login",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                     "account", "name"))  # تكملة السطر السابق داخل القوس
                            and t not in ("hidden", "submit", "button", "reset",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                          "checkbox", "radio", "image",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                          # تكملة السطر السابق داخل القوس
                                          "file")) or \
        _pick(inputs, lambda n, t: n != info.pass_field  # تكملة السطر السابق داخل القوس
              and t in ("text", "tel", "number", "email")) or "username"  # تكملة السطر السابق داخل القوس

    # الأزرار ليست بيانات: المتصفح يرسل فقط الزر المضغوط، و
    # إرسال كل زر مسمّى في الصفحة يربك بعض البوابات
    NON_DATA_TYPES = ("submit", "button", "reset", "image", "file")  # إسناد مجموعة إلى NON_DATA_TYPES
    for name, _type in inputs:  # دورة على inputs باسم مجموعة
        low = name.lower()  # إسناد نتيجة استدعاء name.lower إلى low
        if low in ("dst", "link-orig"):  # شرط: low ضمن مجموعة
            info.dst_field, info.dst_value = name, fields.get(name, "")  # إسناد مجموعة إلى مجموعة
            continue  # الانتقال إلى الدورة التالية
        if _type in NON_DATA_TYPES:  # شرط: _type ضمن NON_DATA_TYPES
            continue  # الانتقال إلى الدورة التالية
        if low == "popup":  # شرط: low يساوي 'popup'
            info.popup_field = name  # إسناد name إلى info.popup_field
        elif low not in (info.user_field.lower(), info.pass_field.lower(),  # شرط: low ليس ضمن مجموعة
                         info.dst_field.lower()):  # تكملة تعريف متعدد الأسطر
            info.extra_fields[name] = fields.get(name, "")  # إسناد نتيجة استدعاء fields.get (2 معاملات) إلى info.extra_fields[name]
    if not info.dst_field:  # شرط معكوس: ليس info.dst_field
        info.dst_field = "dst"  # إسناد القيمة الثابتة info.dst_field
    if not info.popup_field:  # شرط معكوس: ليس info.popup_field
        info.popup_field = "popup"  # إسناد القيمة الثابتة info.popup_field

    # احفظ رابطاً بنفس مفاتيح/ترتيب الاستعلام لكن بقيم فارغة للمستخدم/كلمة المرور.
    # كود إرسال GET يمدّ القيم الطازجة لكل محاولة.
    info.action = sanitize_login_url(info.action, info.user_field, info.pass_field)  # إسناد نتيجة استدعاء sanitize_login_url (3 معاملات) إلى info.action

    # chap في ميكروتيك: hexMD5('id' + كلمة المرور + 'challenge')
    cm = CHAP_CALL_RE.search(html)  # إسناد نتيجة استدعاء CHAP_CALL_RE.search (معامل واحد) إلى cm
    if cm:  # شرط: cm
        info.chap = {"id": cm.group(1), "challenge": cm.group(3),  # إسناد قاموس إلى info.chap
                     "field": info.pass_field}  # مفتاح field في القاموس
    elif "hexMD5" in html:  # شرط: 'hexMD5' ضمن html
        info.chap = {"id": "", "challenge": "", "field": info.pass_field}  # إسناد قاموس إلى info.chap
    return info  # إرجاع info


def _pick(inputs, predicate) -> str:  # تعريف الدالة _pick(inputs, predicate) ترجع str
    for name, typ in inputs:  # دورة على inputs باسم مجموعة
        try:  # بدايةtry محمية (يليها except/finally)
            if predicate(name, typ):  # شرط: نتيجة predicate(name, typ)
                return name  # إرجاع name
        except Exception:  # تكملة السطر السابق داخل القوس
            continue  # الانتقال إلى الدورة التالية
    return ""  # إرجاع ''


class Portal:  # تعريف الصنف Portal
    def __init__(self, url, resp, form, dst_candidates, notes):  # تعريف الدالة __init__(self, url, resp, form, dst_candidates, notes)
        self.url = url  # إسناد url إلى self.url
        self.status = resp.status  # إسناد resp.status إلى self.status
        self.html = (resp.text or "")[:400000]  # إسناد resp.text أو ''[] إلى self.html
        self.form = form  # إسناد form إلى self.form
        self.dst_candidates = dst_candidates  # إسناد dst_candidates إلى self.dst_candidates
        self.notes = notes  # إسناد notes إلى self.notes
        self.host = (urlsplit(url).hostname or "").lower()  # إسناد نتيجة استدعاء urlsplit(url).hostname أو ''.lower إلى self.host
        mt = TITLE_RE.search(self.html)  # إسناد نتيجة استدعاء TITLE_RE.search (معامل واحد) إلى mt
        self.title = re.sub(r"\s+", " ", mt.group(1)).strip() if mt else ""  # إسناد re.sub('\\s+', ' ', mt.group(1)).strip() إن mt وإلا '' إلى self.title

    def as_dict(self) -> dict:  # تعريف الدالة as_dict(self) ترجع dict
        return {  # إرجاع قاموس
            "url": self.url,  # مفتاح url في القاموس
            "host": self.host,  # مفتاح host في القاموس
            "title": self.title,  # مفتاح title في القاموس
            "status": self.status,  # مفتاح status في القاموس
            "has_login_form": bool(self.form and self.form.fields),  # مفتاح has_login_form في القاموس
            "form": self.form.as_dict() if self.form else None,  # مفتاح form في القاموس
            "dst_candidates": self.dst_candidates,  # مفتاح dst_candidates في القاموس
            "notes": self.notes,  # مفتاح notes في القاموس
        }  # إغلاق القوس المفتوح في السطر السابق




# يحذف قيم username/password من رابط منسوخ قبل حفظه أو عرضه.
def sanitize_login_url(url: str, user_field: str = "username",  # تعريف الدالة sanitize_login_url(url, user_field, pass_field) ترجع str
                       pass_field: str = "password") -> str:  # مفتاح pass_field في القاموس
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Canonicalize a login URL and remove credential values from its query.

    Keep the query keys and their order (some portals depend on the URL shape),
    but never persist a card or password/hash copied from a submitted GET link.
    """  # نهاية النص متعدد الأسطر
    value = htmlmod.unescape(str(url or "")).strip()  # إسناد نتيجة استدعاء htmlmod.unescape(str(url أو '')).strip إلى value
    try:  # بدايةtry محمية (يليها except/finally)
        parts = urlsplit(value)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
        secret_keys = {str(user_field or "username").lower(),  # إسناد مجموعة فريدة إلى secret_keys
                       str(pass_field or "password").lower()}  # تكملة السطر السابق داخل القوس
        query = [(key, "" if key.lower() in secret_keys else item)  # بناء اشتقاق قائمة وإسناده إلى query
                 for key, item in parse_qsl(parts.query, keep_blank_values=True)]  # تكملة السطر السابق داخل القوس
        return urlunsplit((parts.scheme, parts.netloc, parts.path,  # إرجاع urlunsplit(مجموعة)
                           urlencode(query, doseq=True), parts.fragment))  # تكملة السطر السابق داخل القوس
    except Exception:  # تكملة السطر السابق داخل القوس
        return value  # إرجاع value


def _copied_login_query(url: str) -> tuple:  # تعريف الدالة _copied_login_query(url) ترجع tuple
    """(looks like a submitted GET login, credential field names)."""  # نص توثيقي (docstring) يشرح ما يليه
    url = htmlmod.unescape(str(url or ""))  # إسناد نتيجة استدعاء htmlmod.unescape (معامل واحد) إلى url
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)  # إسناد نتيجة استدعاء parse_qsl (معامل واحد، keep_blank_values=…) إلى pairs
    names = {name.lower(): name for name, _ in pairs}  # بناء قاموس بالاشتقاق وإسناده إلى names
    users = {original for low, original in names.items()  # بناء اشتقاق مجموعة وإسناده إلى users
             if any(w in low for w in  # تكملة السطر السابق داخل القوس
                    ("user", "login", "card", "voucher", "account"))}  # تكملة السطر السابق داخل القوس
    passwords = {original for low, original in names.items()  # بناء اشتقاق مجموعة وإسناده إلى passwords
                 if any(w in low for w in ("pass", "pwd", "pin"))}  # تكملة السطر السابق داخل القوس
    return bool(users and passwords), users | passwords  # إرجاع مجموعة


def _safe_page_url(url: str) -> str:  # تعريف الدالة _safe_page_url(url) ترجع str
    """Open the login *page*, never spend the card embedded in a copied URL."""  # نص توثيقي (docstring) يشرح ما يليه
    url = htmlmod.unescape(str(url or "")).strip()  # إسناد نتيجة استدعاء htmlmod.unescape(str(url أو '')).strip إلى url
    copied, credential_names = _copied_login_query(url)  # إسناد نتيجة استدعاء _copied_login_query (معامل واحد) إلى مجموعة
    if not copied:  # شرط معكوس: ليس copied
        return url  # إرجاع url
    parts = urlsplit(url)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)  # بناء اشتقاق قائمة وإسناده إلى pairs
             if k not in credential_names]  # تكملة السطر السابق داخل القوس
    return urlunsplit((parts.scheme, parts.netloc, parts.path,  # إرجاع urlunsplit(مجموعة)
                       urlencode(pairs, doseq=True), parts.fragment))  # تكملة السطر السابق داخل القوس


def discover(session, url: str, timeout=None) -> Portal:  # تعريف الدالة discover(session, url, timeout) ترجع Portal
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Open the login page and report everything the tool learned from it.

    If the operator pasted an already-submitted GET URL, remove its username
    and password before opening it: scanning must never consume a real card.
    The original query still teaches us that this is a GET portal.
    """  # نهاية النص متعدد الأسطر
    url = htmlmod.unescape(str(url or "")).strip()  # إسناد نتيجة استدعاء htmlmod.unescape(str(url أو '')).strip إلى url
    page_url = _safe_page_url(url)  # إسناد نتيجة استدعاء _safe_page_url (معامل واحد) إلى page_url
    resp = session.get(page_url, allow_redirects=True, timeout=timeout)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…، timeout=…) إلى resp
    base = resp.url or page_url  # دمج منطقي (أو) وإسناده إلى base
    form = parse_form(resp.text, base)  # إسناد نتيجة استدعاء parse_form (2 معاملات) إلى form
    copied_get, _credential_names = _copied_login_query(url)  # إسناد نتيجة استدعاء _copied_login_query (معامل واحد) إلى مجموعة
    if copied_get and not _form_segments(resp.text or ""):  # شرط مركّب (و)
        form = parse_form(resp.text, url)  # إسناد نتيجة استدعاء parse_form (2 معاملات) إلى form
        form.action = base  # إسناد base إلى form.action

    dsts, seen = [], set()  # إسناد مجموعة إلى مجموعة
    for src in (parse_qs(urlsplit(base).query).get("dst", [None])[0],  # دورة على مجموعة باسم src
                form.dst_value if form else None,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                _js_var(resp.text, "link-orig"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                ""):  # تكملة تعريف متعدد الأسطر
        if src is not None and src not in seen:  # شرط مركّب (و)
            seen.add(src)  # استدعاء seen.add (معامل واحد)
            dsts.append(src)  # استدعاء dsts.append (معامل واحد)

    notes = []  # إسناد قائمة إلى notes
    if form and form.chap:  # شرط مركّب (و)
        notes.append("chap_md5_detected")  # استدعاء notes.append (معامل واحد)
    if form and form.is_post:  # شرط مركّب (و)
        notes.append("post_form")  # استدعاء notes.append (معامل واحد)
    else:  # مفتاح else في القاموس
        notes.append("get_form")  # استدعاء notes.append (معامل واحد)
    if not form or not form.fields:  # شرط مركّب (أو)
        notes.append("no_form_found")  # استدعاء notes.append (معامل واحد)
    if resp.history:  # شرط: resp.history
        notes.append("page_redirected_here")  # استدعاء notes.append (معامل واحد)

    return Portal(base, resp, form, dsts, notes)  # إرجاع Portal(base, resp, form, …)


def _js_var(html: str, name: str) -> str:  # تعريف الدالة _js_var(html, name) ترجع str
    m = re.search(rf"{re.escape(name)}\s*[:=]\s*[\"']([^\"']*)[\"']", html or "", re.I)  # إسناد نتيجة استدعاء re.search (3 معاملات) إلى m
    return m.group(1) if m else ""  # إرجاع m.group(1) إن m وإلا ''
