# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Check captive-portal and internet connectivity states.

The helpers distinguish an open internet connection, a captive-portal redirect,
and an unavailable network, and preserve the evidence behind each result.

    internet_state()      before we touch any card:  ONLINE / WALLED / OFFLINE
    verify_online()       after a card looked accepted: does internet work?
    portal_status_page()  secondary check: the router's own /status page
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

from urllib.parse import urlsplit  # استيراد urlsplit من الوحدة urllib.parse

from . import config  # استيراد config من الوحدة .


def resolve_internet_checks(custom=None) -> tuple:  # تعريف الدالة resolve_internet_checks(custom) ترجع tuple
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Build the check list from an optional custom URL string or env default.

    `custom` accepts the same pipe format as KIRAPASS_INTERNET_CHECKS, e.g.
    ``http://example.com/generate_204|204`` or a bare URL (expects HTTP 204).
    """  # نهاية النص متعدد الأسطر
    if custom is None or custom == "":  # شرط مركّب (أو)
        return config.INTERNET_CHECKS  # إرجاع config.INTERNET_CHECKS
    if isinstance(custom, (list, tuple)):  # شرط: نتيجة isinstance(custom, مجموعة)
        return tuple(custom) if custom else config.INTERNET_CHECKS  # إرجاع tuple(custom) إن custom وإلا config.INTERNET_CHECKS
    raw = str(custom).strip()  # إسناد نتيجة استدعاء str(custom).strip إلى raw
    if not raw:  # شرط معكوس: ليس raw
        return config.INTERNET_CHECKS  # إرجاع config.INTERNET_CHECKS
    parsed = config._parse_internet_checks(raw)  # إسناد نتيجة استدعاء config._parse_internet_checks (معامل واحد) إلى parsed
    return parsed or config.INTERNET_CHECKS  # إرجاع parsed أو config.INTERNET_CHECKS


# السؤال الوحيد المهم: هل هذا الجهاز متصل فعلاً الآن؟
# allow_redirects=False مقصود: التحويل إلى صفحة الدخول هو دليل WALLED.
# ترجع (state, detail) حيث state ∈ {ONLINE, WALLED, OFFLINE}.
def probe_internet(session, checks=None, timeout=(3.0, 6.0)) -> dict:  # تعريف الدالة probe_internet(session, checks, timeout) ترجع dict
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """-> {state, label, detail, status, location}

    state: ONLINE  -> the check URL answered exactly as expected (no portal)
           WALLED  -> we were redirected to the portal (needs a card)
           OFFLINE -> nothing answered at all
    """  # نهاية النص متعدد الأسطر
    last_error = None  # إسناد القيمة الثابتة last_error
    for url, want_status, want_text, label in (checks or config.INTERNET_CHECKS):  # دورة على checks أو config.INTERNET_CHECKS باسم مجموعة
        try:  # بدايةtry محمية (يليها except/finally)
            resp = session.get(url, allow_redirects=False, timeout=timeout)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…، timeout=…) إلى resp
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                       # noqa: BLE001
            last_error = exc  # إسناد exc إلى last_error
            continue  # الانتقال إلى الدورة التالية
        body = resp.text or ""  # دمج منطقي (أو) وإسناده إلى body
        if resp.status == want_status and (want_text is None or want_text in body):  # شرط مركّب (و)
            return {"state": "ONLINE", "label": label, "detail": "expected_answer",  # إرجاع قاموس
                    "status": resp.status, "url": url, "location": ""}  # مفتاح status في القاموس
        if resp.is_redirect():  # شرط: نتيجة resp.is_redirect()
            return {"state": "WALLED", "label": label, "detail": "portal_redirect",  # إرجاع قاموس
                    "status": resp.status, "url": url,  # مفتاح status في القاموس
                    "location": resp.location[:200]}  # مفتاح location في القاموس
        if resp.status in (200, 204) and want_text and want_text not in body:  # شرط مركّب (و)
            return {"state": "WALLED", "label": label, "detail": "portal_page",  # إرجاع قاموس
                    "status": resp.status, "url": url,  # مفتاح status في القاموس
                    "location": ""}  # مفتاح location في القاموس
        if resp.status in (403, 429, 503):  # شرط: resp.status ضمن مجموعة
            return {"state": "BLOCKED", "label": label, "detail": f"http_{resp.status}",  # إرجاع قاموس
                    "status": resp.status, "url": url, "location": ""}  # مفتاح status في القاموس
    # لم يردّ شيء إطلاقاً. قل *لماذا* بنفس الكلمات التي تستخدمها
    # بقية الأداة (dns / refused / stale / tls …) حتى تستطيع الواجهة ترجمتها.
    kind = "no_answer"  # إسناد القيمة الثابتة kind
    if last_error is not None:  # شرط: last_error ليس نفسه None
        try:  # بدايةtry محمية (يليها except/finally)
            from .errors import classify  # استيراد classify من الوحدة errors
            kind = classify(last_error, "").kind  # إسناد classify(last_error, '').kind إلى kind
        # تكملة السطر السابق داخل القوس
        except Exception:                              # noqa: BLE001
            kind = type(last_error).__name__  # إسناد type(last_error).__name__ إلى kind
    return {"state": "OFFLINE", "label": "", "detail": kind,  # إرجاع قاموس
            "status": 0, "url": "", "location": ""}  # مفتاح status في القاموس


def verify_online(session, checks=None, timeout=(3.0, 6.0)) -> tuple:  # تعريف الدالة verify_online(session, checks, timeout) ترجع tuple
    """After a card is accepted: -> (True/False, dict with the reason)."""  # نص توثيقي (docstring) يشرح ما يليه
    info = probe_internet(session, checks=checks, timeout=timeout)  # إسناد نتيجة استدعاء probe_internet (معامل واحد، checks=…، timeout=…) إلى info
    ok = info["state"] == "ONLINE"  # مقارنة (يساوي) وإسناد النتيجة المنطقية إلى ok
    return ok, info  # إرجاع مجموعة


def portal_status_page(session, portal_url: str, timeout=(4.0, 8.0)) -> dict:  # تعريف الدالة portal_status_page(session, portal_url, timeout) ترجع dict
    """Look for the router's own status/logout page as a second opinion."""  # نص توثيقي (docstring) يشرح ما يليه
    parts = urlsplit(portal_url)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    base = f"{parts.scheme}://{parts.netloc}"  # بناء نص منسّق وإسناده إلى base
    for path in ("/status", "/status.html", "/logout"):  # دورة على مجموعة باسم path
        url = base + path  # حساب جمع بين base وpath وإسناده إلى url
        try:  # بدايةtry محمية (يليها except/finally)
            resp = session.get(url, allow_redirects=False, timeout=timeout)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…، timeout=…) إلى resp
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                       # noqa: BLE001
            return {"checked": False, "reason": type(exc).__name__, "url": url}  # إرجاع قاموس
        body = (resp.text or "").lower()  # إسناد نتيجة استدعاء resp.text أو ''.lower إلى body
        if resp.status == 200 and not resp.is_redirect():  # شرط مركّب (و)
            logged_in = any(w in body for w in  # إسناد نتيجة استدعاء any (معامل واحد) إلى logged_in
                            ("logout", "log out", "remaining", "uptime",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                             "session", "bytes", "disconnect"))  # تكملة السطر السابق داخل القوس
            login_form = ('type="password"' in body or "type='password'" in body  # دمج منطقي (أو) وإسناده إلى login_form
                          or "name=\"password\"" in body)  # تكملة السطر السابق داخل القوس
            return {"checked": True, "url": url, "status": resp.status,  # إرجاع قاموس
                    "looks_logged_in": bool(logged_in and not login_form),  # مفتاح looks_logged_in في القاموس
                    "reason": "status_page_reachable"}  # مفتاح reason في القاموس
        if resp.is_redirect():  # شرط: نتيجة resp.is_redirect()
            return {"checked": True, "url": url, "status": resp.status,  # إرجاع قاموس
                    "looks_logged_in": False, "reason": "redirected_to_login",  # مفتاح looks_logged_in في القاموس
                    "location": resp.location[:160]}  # مفتاح location في القاموس
    return {"checked": False, "reason": "no_status_page"}  # إرجاع قاموس


# يعيد الشبكة إلى حالة WALLED حتى لا نترك بطاقة المستخدم مستهلكة.
# تأكيد الخروج شرط لكل دليل نجاح في المعايرة.
def logout(session, portal_url: str, timeout=(4.0, 8.0)) -> dict:  # تعريف الدالة logout(session, portal_url, timeout) ترجع dict
    """Log the test card out again so a paid card is not left consumed."""  # نص توثيقي (docstring) يشرح ما يليه
    parts = urlsplit(portal_url)  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    base = f"{parts.scheme}://{parts.netloc}"  # بناء نص منسّق وإسناده إلى base
    for path in ("/logout", "/login?erase-cookie=on"):  # دورة على مجموعة باسم path
        url = base + path  # حساب جمع بين base وpath وإسناده إلى url
        try:  # بدايةtry محمية (يليها except/finally)
            resp = session.get(url, allow_redirects=False, timeout=timeout)  # إسناد نتيجة استدعاء session.get (معامل واحد، allow_redirects=…، timeout=…) إلى resp
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                       # noqa: BLE001
            continue  # الانتقال إلى الدورة التالية
        if resp.status in (200, 302):  # شرط: resp.status ضمن مجموعة
            return {"ok": True, "url": url, "status": resp.status}  # إرجاع قاموس
    return {"ok": False, "reason": "no_logout_endpoint"}  # إرجاع قاموس
