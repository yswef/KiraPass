# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Self-test: prove the tool works without touching any real network.

    python3 KiraPass.py --selftest

It spins up local mock routers (see mockportal.py), including the exact
situations that broke the old version:

    * a page whose session token changes on every request
    * wrong cards that must NEVER be reported as a hit
    * a router that bans you, one that rate limits you, one that drops
      connections, a chap/md5.js portal, a GET portal, an old saved profile
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import os  # استيراد الوحدة os من المكتبة
import shutil  # استيراد الوحدة shutil من المكتبة
import sys  # استيراد الوحدة sys من المكتبة
import time  # استيراد الوحدة time من المكتبة

from . import config, engine, portals, store  # استيراد config, engine, portals, store من الوحدة .
from .httpclient import Session  # استيراد Session من الوحدة httpclient
from .mockportal import MockPortal  # استيراد MockPortal من الوحدة mockportal


# ---------------------------------------------------------------------------
# مساعدات
# ---------------------------------------------------------------------------
def make_profile(url: str, prefix="02", length=4, charset="0123456789",  # تعريف الدالة make_profile(url, prefix, length, charset, portal_info, **kw) ترجع dict
                 portal_info=None, **kw) -> dict:  # المعامل المسمّى portal_info
    p = store.new_profile(login_url=url, prefix=prefix, length=length,  # إسناد نتيجة استدعاء store.new_profile (login_url=…، prefix=…، length=…، charset=…، name=…، pass_mode=…) إلى p
                          charset=charset, name="selftest", pass_mode="empty")  # المعامل المسمّى charset
    if portal_info:  # شرط: portal_info
        form = portal_info.get("form") or {}  # دمج منطقي (أو) وإسناده إلى form
        p.update({  # استدعاء p.update (معامل واحد)
            "login_url": form.get("action") or url,  # مفتاح login_url في القاموس
            "method": (form.get("method") or "post").lower(),  # مفتاح method في القاموس
            "user_field": form.get("user_field") or "username",  # مفتاح user_field في القاموس
            "pass_field": form.get("pass_field") or "password",  # مفتاح pass_field في القاموس
            "extra_fields": form.get("extra_fields") or {},  # مفتاح extra_fields في القاموس
            "dst_field": form.get("dst_field") or "dst",  # مفتاح dst_field في القاموس
            "dst_value": form.get("dst_value") or "",  # مفتاح dst_value في القاموس
            "chap": form.get("chap") or None,  # مفتاح chap في القاموس
        })  # إغلاق القوس المفتوح في السطر السابق
    p.update(kw)  # استدعاء p.update (معامل واحد)
    return p  # إرجاع p


def mock_checks(portal) -> tuple:  # تعريف الدالة mock_checks(portal) ترجع tuple
    """The mock router's own internet endpoints - keeps tests off the internet."""  # نص توثيقي (docstring) يشرح ما يليه
    base = f"http://127.0.0.1:{portal.port}"  # بناء نص منسّق وإسناده إلى base
    return ((base + "/generate_204", 204, None, "mock204"),  # إرجاع مجموعة
            (base + "/connecttest.txt", 200, "Microsoft Connect Test", "mocktxt"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
            (base + "/hotspot-detect.html", 200, "Success", "mockapple"))  # تكملة السطر السابق داخل القوس


def scan(url: str) -> dict:  # تعريف الدالة scan(url) ترجع dict
    session = Session(allow_redirects=True)  # إسناد نتيجة استدعاء Session (allow_redirects=…) إلى session
    try:  # بدايةtry محمية (يليها except/finally)
        return portals.discover(session, url).as_dict()  # إرجاع portals.discover(session, url).as_dict()
    finally:  # مفتاح finally في القاموس
        session.close()  # استدعاء session.close


_RUN_ID = [0]  # إسناد قائمة إلى _RUN_ID


def run_engine(profile: dict, attempts: int, threads: int = 3,  # تعريف الدالة run_engine(profile, attempts, threads, timeout, checks, reset, **kw)
               timeout: float = 90.0, checks=None, reset: bool = True, **kw):  # مفتاح timeout في القاموس
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Fresh, throw-away run: no resume state, nothing saved on disk.

    `reset=False` keeps `space_pos`/`walk_*` - that is how the "continue where
    you stopped" path is tested (the UI sends them back with the profile).
    """  # نهاية النص متعدد الأسطر
    _RUN_ID[0] += 1  # تحديث _RUN_ID[0] بعملية جمع
    profile = dict(profile)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى profile
    profile.update({"name": f"selftest-{_RUN_ID[0]}"})  # استدعاء profile.update (معامل واحد)
    if reset:  # شرط: reset
        profile.update({"space_pos": 0, "walk_a": 0, "walk_b": 0})  # استدعاء profile.update (معامل واحد)
    eng = engine.Engine(store.Store(), persist=False, checks=checks)  # إسناد نتيجة استدعاء engine.Engine (معامل واحد، persist=…، checks=…) إلى eng
    res = eng.start(profile, attempts=attempts, threads=threads, **kw)  # إسناد نتيجة استدعاء eng.start (معامل واحد، attempts=…، threads=…، **=…) إلى res
    if not res.get("ok"):  # شرط معكوس: ليس res.get('ok')
        return {"state": "rejected", "error": res.get("error"),  # إرجاع مجموعة
                "problems": res.get("problems", [])}, eng  # مفتاح problems في القاموس
    deadline = time.time() + timeout  # حساب جمع بين time.time() وtimeout وإسناده إلى deadline
    while eng.state in ("calibrating", "running", "stopping"):  # حلقة ما دام مقارنة
        if time.time() > deadline:  # شرط: time.time() أكبر من deadline
            eng.stop("timeout")  # استدعاء eng.stop (معامل واحد)
            break  # قطع الحلقة فوراً
        time.sleep(0.05)  # استدعاء time.sleep (معامل واحد)
    if eng.thread is not None:  # شرط: eng.thread ليس نفسه None
        eng.thread.join(timeout=5)  # استدعاء eng.thread.join (timeout=…)
    return eng.status(), eng  # إرجاع مجموعة


class Result:  # تعريف الصنف Result
    def __init__(self, name, ok, detail=""):  # تعريف الدالة __init__(self, name, ok, detail)
        self.name = name  # إسناد name إلى self.name
        self.ok = ok  # إسناد ok إلى self.ok
        self.detail = detail  # إسناد detail إلى self.detail

    def __str__(self):  # تعريف الدالة __str__(self)
        mark = "PASS" if self.ok else "FAIL"  # إسناد 'PASS' إن self.ok وإلا 'FAIL' إلى mark
        return f"[{mark}] {self.name}: {self.detail}"  # إرجاع نص منسّق (f-string)


# ---------------------------------------------------------------------------
# السيناريوهات
# ---------------------------------------------------------------------------
def t_calibration():  # تعريف الدالة t_calibration()
    """The rejection baseline must be learned even with a changing token."""  # نص توثيقي (docstring) يشرح ما يليه
    with MockPortal(valid_cards={"0299"}, dynamic=True,  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, dynamic=True, pass_mode='empty') باسم portal
                    pass_mode="empty") as portal:  # المعامل المسمّى pass_mode
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, portal_info=info)  # إسناد نتيجة استدعاء make_profile (معامل واحد، portal_info=…) إلى p
        cal = engine.calibrate(p)  # إسناد نتيجة استدعاء engine.calibrate (معامل واحد) إلى cal
        fp = cal.fingerprint  # إسناد cal.fingerprint إلى fp
        ok = (cal.ok and fp is not None and fp.samples == 3  # دمج منطقي (و) وإسناده إلى ok
              and (fp.exact or len(fp.literals) >= 0))  # تكملة السطر السابق داخل القوس
        detail = (f"baseline {'exact' if fp and fp.exact else 'shaped'}, "  # بناء نص منسّق وإسناده إلى detail
                  f"dynamic tokens={len(fp.literals) if fp else 0}, "  # تكملة السطر السابق داخل القوس
                  f"status={fp.reject_status if fp else '-'}, "  # تكملة السطر السابق داخل القوس
                  f"bytes={fp.reject_len if fp else '-'}")  # تكملة السطر السابق داخل القوس
        return Result("calibration_learns_rejection_page", bool(ok), detail)  # إرجاع Result('calibration_learns_rejection_page', bool(ok), detail)


def t_no_false_hits():  # تعريف الدالة t_no_false_hits()
    """50 wrong cards: zero accepted. This is the old bug, in a test."""  # نص توثيقي (docstring) يشرح ما يليه
    with MockPortal(valid_cards={"0299"}, pass_mode="empty") as portal:  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, pass_mode='empty') باسم portal
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info,  # إسناد نتيجة استدعاء make_profile (معامل واحد، prefix=…، length=…، portal_info=…، pass_mode=…) إلى p
                         pass_mode="empty")  # المعامل المسمّى pass_mode
        st, _eng = run_engine(p, attempts=50, threads=3,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…) إلى مجموعة
                              checks=mock_checks(portal))  # المعامل المسمّى checks
        c = st.get("counters", {})  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى c
        accepted = sum(v for k, v in c.items() if k.startswith("ACCEPTED"))  # إسناد نتيجة استدعاء sum (معامل واحد) إلى accepted
        ok = accepted == 0 and c.get("REJECTED", 0) >= 40  # دمج منطقي (و) وإسناده إلى ok
        return Result("wrong_cards_are_never_reported_as_hits", ok,  # إرجاع Result('wrong_cards_are_never_reported_as_hits', ok, نص منسّق (f-string))
                      f"counters={dict(c)} accepted={accepted} "  # تكملة السطر السابق داخل القوس
                      f"stop={st.get('stop_reason')} "  # تكملة السطر السابق داخل القوس
                      f"progress={st.get('progress')}")  # تكملة السطر السابق داخل القوس


def t_find_card():  # تعريف الدالة t_find_card()
    """The card that exists gets found AND verified against the internet."""  # نص توثيقي (docstring) يشرح ما يليه
    with MockPortal(valid_cards={"0242"}) as portal:  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة) باسم portal
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, portal_info=info, pass_mode="empty")  # إسناد نتيجة استدعاء make_profile (معامل واحد، portal_info=…، pass_mode=…) إلى p
        st, eng = run_engine(p, attempts=200, threads=4,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…، known_card=…) إلى مجموعة
                             checks=mock_checks(portal), known_card="0242")  # المعامل المسمّى checks
        hits = st.get("hits", [])  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى hits
        ok = (bool(hits) and hits[0]["card"] == "0242"  # دمج منطقي (و) وإسناده إلى ok
              and hits[0]["code"] == "ACCEPTED_VERIFIED"  # تكملة السطر السابق داخل القوس
              and st.get("stop_reason") == "found_verified")  # تكملة السطر السابق داخل القوس
        return Result("finds_the_working_card_and_proves_internet", ok,  # إرجاع Result('finds_the_working_card_and_proves_internet', ok, نص منسّق (f-string))
                      f"hits={hits} stop={st.get('stop_reason')} "  # تكملة السطر السابق داخل القوس
                      f"counters={st.get('counters')}")  # تكملة السطر السابق داخل القوس


def t_verified_hit_stops_before_shared_online_false_hits():  # تعريف الدالة t_verified_hit_stops_before_shared_online_false_hits()
    """One device-wide online transition must not verify later wrong cards."""  # نص توثيقي (docstring) يشرح ما يليه
    with MockPortal(valid_cards={"0242"}, pass_mode="empty",  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, pass_mode='empty', global_online_login_page=True) باسم portal
                    global_online_login_page=True) as portal:  # المعامل المسمّى global_online_login_page
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, portal_info=info, pass_mode="empty",  # إسناد نتيجة استدعاء make_profile (معامل واحد، portal_info=…، pass_mode=…، walk_a=…، walk_b=…، space_pos=…) إلى p
                         walk_a=1, walk_b=24, space_pos=0)  # المعامل المسمّى walk_a
        st, eng = run_engine(p, attempts=20, threads=8, reset=False,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، reset=…، checks=…، known_card=…، auto_stop=…) إلى مجموعة
                             checks=mock_checks(portal), known_card="0242",  # المعامل المسمّى checks
                             auto_stop=False)  # المعامل المسمّى auto_stop
        hits = st.get("hits", [])  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى hits
        ok = (len(hits) == 1 and hits[0]["code"] == "ACCEPTED_VERIFIED"  # دمج منطقي (و) وإسناده إلى ok
              and st.get("stop_reason") == "found_verified"  # تكملة السطر السابق داخل القوس
              and st.get("plan", {}).get("verification_serialized") is True  # تكملة السطر السابق داخل القوس
              and st.get("progress", {}).get("threads") == 1)  # تكملة السطر السابق داخل القوس
        return Result("shared_online_state_does_not_create_extra_verified_hits",  # إرجاع Result('shared_online_state_does_not_create_extra_verified_hits', ok, نص منسّق (f-string))
                      ok, f"hits={len(hits)} stop={st.get('stop_reason')} "  # تكملة السطر السابق داخل القوس
                      f"plan={st.get('plan')} counters={st.get('counters')}")  # تكملة السطر السابق داخل القوس


def t_ban_is_reported():  # تعريف الدالة t_ban_is_reported()
    """A ban must be named as a ban - never as a hit or as 'tested'."""  # نص توثيقي (docstring) يشرح ما يليه
    with MockPortal(valid_cards={"0299"}, ban_after=5, pass_mode="empty") as portal:  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, ban_after=5, pass_mode='empty') باسم portal
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)  # إسناد نتيجة استدعاء make_profile (معامل واحد، prefix=…، length=…، portal_info=…) إلى p
        st, _eng = run_engine(p, attempts=60, threads=2,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…) إلى مجموعة
                              checks=mock_checks(portal))  # المعامل المسمّى checks
        c = st.get("counters", {})  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى c
        accepted = sum(v for k, v in c.items() if k.startswith("ACCEPTED"))  # إسناد نتيجة استدعاء sum (معامل واحد) إلى accepted
        ok = (c.get("BANNED", 0) >= 1 and accepted == 0  # دمج منطقي (و) وإسناده إلى ok
              and st.get("stop_reason") == "banned_by_router")  # تكملة السطر السابق داخل القوس
        return Result("ban_from_router_is_named_and_stops_the_run", ok,  # إرجاع Result('ban_from_router_is_named_and_stops_the_run', ok, نص منسّق (f-string))
                      f"banned={c.get('BANNED', 0)} accepted={accepted} "  # تكملة السطر السابق داخل القوس
                      f"stop={st.get('stop_reason')}")  # تكملة السطر السابق داخل القوس


def t_rate_limit_stops():  # تعريف الدالة t_rate_limit_stops()
    with MockPortal(valid_cards={"0299"}, rate_limit_after=4,  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, rate_limit_after=4, pass_mode='empty') باسم portal
                    pass_mode="empty") as portal:  # المعامل المسمّى pass_mode
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)  # إسناد نتيجة استدعاء make_profile (معامل واحد، prefix=…، length=…، portal_info=…) إلى p
        eng = engine.Engine(store.Store(), persist=False,  # إسناد نتيجة استدعاء engine.Engine (معامل واحد، persist=…، checks=…) إلى eng
                            checks=mock_checks(portal))  # المعامل المسمّى checks
        eng.start(dict(p, name="selftest-rate", space_pos=0, walk_a=0, walk_b=0),  # استدعاء eng.start (معامل واحد، attempts=…، threads=…)
                  attempts=40, threads=2)  # المعامل المسمّى attempts
        deadline = time.time() + 60  # حساب جمع بين time.time() و60 وإسناده إلى deadline
        while eng.state in ("calibrating", "running") and time.time() < deadline:  # حلقة ما دام مقارنة و مقارنة
            time.sleep(0.05)  # استدعاء time.sleep (معامل واحد)
        st = eng.status()  # إسناد نتيجة استدعاء eng.status إلى st
        c = st.get("counters", {})  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى c
        delay = (st.get("throttle") or {}).get("delay_ms", 0)  # إسناد نتيجة استدعاء st.get('throttle') أو قاموس.get (2 معاملات) إلى delay
        ok = (c.get("RATE_LIMITED", 0) >= 1 and delay > 0  # دمج منطقي (و) وإسناده إلى ok
              and st.get("stop_reason") == "rate_limited_by_router")  # تكملة السطر السابق داخل القوس
        return Result("rate_limit_is_reported_and_stops_the_run", ok,  # إرجاع Result('rate_limit_is_reported_and_stops_the_run', ok, نص منسّق (f-string))
                      f"rate_limited={c.get('RATE_LIMITED', 0)} delay={delay}ms "  # تكملة السطر السابق داخل القوس
                      f"reason={(st.get('throttle') or {}).get('reason')}")  # تكملة السطر السابق داخل القوس


def t_dropped_connections():  # تعريف الدالة t_dropped_connections()
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Half the sockets are cut: retries must save the card, and nothing may
    be reported as tested when it never got an answer."""  # نهاية النص متعدد الأسطر
    with MockPortal(valid_cards={"0299"}, drop_every=2,  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, drop_every=2, pass_mode='empty') باسم portal
                    pass_mode="empty") as portal:  # المعامل المسمّى pass_mode
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)  # إسناد نتيجة استدعاء make_profile (معامل واحد، prefix=…، length=…، portal_info=…) إلى p
        st, _eng = run_engine(p, attempts=30, threads=3,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…) إلى مجموعة
                              checks=mock_checks(portal))  # المعامل المسمّى checks
        c = st.get("counters", {})  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى c
        accepted = sum(v for k, v in c.items() if k.startswith("ACCEPTED"))  # إسناد نتيجة استدعاء sum (معامل واحد) إلى accepted
        pr = st.get("progress", {})  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى pr
        accounted = pr.get("attempts", 0) == pr.get("queued", -1)  # مقارنة (يساوي) وإسناد النتيجة المنطقية إلى accounted
        ok = accepted == 0 and accounted and pr.get("dropped", 0) == 0  # دمج منطقي (و) وإسناده إلى ok
        return Result("dropped_connections_are_counted_not_hidden", ok,  # إرجاع Result('dropped_connections_are_counted_not_hidden', ok, نص منسّق (f-string))
                      f"counters={dict(c)} progress={pr} accepted={accepted}")  # تكملة السطر السابق داخل القوس


def t_dead_target_stops():  # تعريف الدالة t_dead_target_stops()
    """The router stops answering entirely: stop with that reason, honestly."""  # نص توثيقي (docstring) يشرح ما يليه
    with MockPortal(valid_cards={"0299"}, pass_mode="empty") as portal:  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, pass_mode='empty') باسم portal
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)  # إسناد نتيجة استدعاء make_profile (معامل واحد، prefix=…، length=…، portal_info=…) إلى p
        portal.state.drop_after = 12          # كل شيء يُقطع من هنا فصاعداً
        st, _eng = run_engine(p, attempts=400, threads=3,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…، timeout=…) إلى مجموعة
                              checks=mock_checks(portal), timeout=60)  # المعامل المسمّى checks
        c = st.get("counters", {})  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى c
        ok = (st.get("stop_reason") == "target_unreachable"  # دمج منطقي (و) وإسناده إلى ok
              and c.get("NET_ERROR", 0) >= config.CONSECUTIVE_TRANSPORT_FAILURE_LIMIT  # تكملة السطر السابق داخل القوس
              and not any(k.startswith("ACCEPTED") for k in c))  # تكملة السطر السابق داخل القوس
        return Result("dead_target_is_detected_and_stops_the_run", ok,  # إرجاع Result('dead_target_is_detected_and_stops_the_run', ok, نص منسّق (f-string))
                      f"stop={st.get('stop_reason')} counters={dict(c)} "  # تكملة السطر السابق داخل القوس
                      f"kinds={st.get('net_kinds')}")  # تكملة السطر السابق داخل القوس


def t_chap_portal():  # تعريف الدالة t_chap_portal()
    """MikroTik md5.js (chap) portal - the tool must find the right formula."""  # نص توثيقي (docstring) يشرح ما يليه
    with MockPortal(valid_cards={"0242"}, chap=True, pass_mode="chap") as portal:  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, chap=True, pass_mode='chap') باسم portal
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, portal_info=info, pass_mode="empty")  # إسناد نتيجة استدعاء make_profile (معامل واحد، portal_info=…، pass_mode=…) إلى p
        cal = engine.calibrate(p, known_card="0242", checks=mock_checks(portal))  # إسناد نتيجة استدعاء engine.calibrate (معامل واحد، known_card=…، checks=…) إلى cal
        tuned = cal.tuned or {}  # دمج منطقي (أو) وإسناده إلى tuned
        ok = bool(tuned) and tuned.get("mode", "").startswith("chap")  # دمج منطقي (و) وإسناده إلى ok
        if not ok:  # شرط معكوس: ليس ok
            return Result("chap_md5_portal_shape_is_discovered", False,  # إرجاع Result('chap_md5_portal_shape_is_discovered', False, نص منسّق (f-string))
                          f"tuned={tuned} steps={[s['id'] + ':' + s['reason'] for s in cal.steps]}")  # تكملة السطر السابق داخل القوس
        # الآن تشغيل كامل بالشكل المكتشف
        p2 = dict(cal.profile)  # إسناد نتيجة استدعاء dict (معامل واحد) إلى p2
        st, _eng = run_engine(p2, attempts=200, threads=4,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…) إلى مجموعة
                              checks=mock_checks(portal))  # المعامل المسمّى checks
        hits = st.get("hits", [])  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى hits
        ok = bool(hits) and hits[0]["code"] == "ACCEPTED_VERIFIED"  # دمج منطقي (و) وإسناده إلى ok
        return Result("chap_md5_portal_shape_is_discovered", ok,  # إرجاع Result('chap_md5_portal_shape_is_discovered', ok, نص منسّق (f-string))
                      f"mode={tuned.get('mode')} verified={tuned.get('verified')} "  # تكملة السطر السابق داخل القوس
                      f"hits={hits}")  # تكملة السطر السابق داخل القوس


def t_get_portal():  # تعريف الدالة t_get_portal()
    with MockPortal(valid_cards={"0242"}, method="get",  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, method='get', pass_mode='empty') باسم portal
                    pass_mode="empty") as portal:  # المعامل المسمّى pass_mode
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, portal_info=info)  # إسناد نتيجة استدعاء make_profile (معامل واحد، portal_info=…) إلى p
        st, _eng = run_engine(p, attempts=200, threads=4,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…) إلى مجموعة
                              checks=mock_checks(portal))  # المعامل المسمّى checks
        hits = st.get("hits", [])  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى hits
        ok = bool(hits) and hits[0]["card"] == "0242"  # دمج منطقي (و) وإسناده إلى ok
        return Result("get_style_portal_is_supported", ok,  # إرجاع Result('get_style_portal_is_supported', ok, نص منسّق (f-string))
                      f"method={(info.get('form') or {}).get('method')} hits={hits} "  # تكملة السطر السابق داخل القوس
                      f"stop={st.get('stop_reason')} counters={st.get('counters')} "  # تكملة السطر السابق داخل القوس
                      f"net={st.get('net_kinds')}")  # تكملة السطر السابق داخل القوس


def t_legacy_profile():  # تعريف الدالة t_legacy_profile()
    """A profile saved by the OLD version must not crash the new one."""  # نص توثيقي (docstring) يشرح ما يليه
    old = {"name": "old-network", "login_url": "http://127.0.0.1:1/login",  # إسناد قاموس إلى old
           "method": "2", "network_type": "1", "var_len": 2, "prefix": "02",  # مفتاح method في القاموس
           "extras": True, "dst_value": "", "pass_mode": "empty"}  # مفتاح extras في القاموس
    p = store.migrate(old)  # إسناد نتيجة استدعاء store.migrate (معامل واحد) إلى p
    problems = store.validate(p)  # إسناد نتيجة استدعاء store.validate (معامل واحد) إلى problems
    with MockPortal(valid_cards={"0242"}, pass_mode="empty") as portal:  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, pass_mode='empty') باسم portal
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p["login_url"] = (info.get("form") or {}).get("action") or portal.url  # دمج منطقي (أو) وإسناده إلى p['login_url']
        st, _eng = run_engine(p, attempts=200, threads=3,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…، known_card=…) إلى مجموعة
                              checks=mock_checks(portal), known_card="0242")  # المعامل المسمّى checks
        hits = st.get("hits", [])  # إسناد نتيجة استدعاء st.get (2 معاملات) إلى hits
        ok = bool(hits) and not [x for x in problems if x != "space_is_astronomically_big"]  # دمج منطقي (و) وإسناده إلى ok
        return Result("old_profile_is_migrated_without_crashing", ok,  # إرجاع Result('old_profile_is_migrated_without_crashing', ok, نص منسّق (f-string))
                      f"migrated='{p.get('prefix')}' len={p.get('length')} "  # تكملة السطر السابق داخل القوس
                      f"problems={problems} hits={len(hits)}")  # تكملة السطر السابق داخل القوس


def t_diagnose_dead_target():  # تعريف الدالة t_diagnose_dead_target()
    r = engine.diagnose({"login_url": "http://127.0.0.1:9/login", "prefix": "02",  # إسناد نتيجة استدعاء engine.diagnose (معامل واحد) إلى r
                         "length": 4, "charset": "0123456789", "name": "dead"})  # مفتاح length في القاموس
    step = next((s for s in r.get("steps", []) if s["id"] == "reach"), None)  # إسناد نتيجة استدعاء next (2 معاملات) إلى step
    ok = bool(step) and not step["ok"] and step["reason"].startswith("net_")  # دمج منطقي (و) وإسناده إلى ok
    return Result("diagnose_explains_a_dead_target", ok,  # إرجاع Result('diagnose_explains_a_dead_target', ok, نص منسّق (f-string))
                  f"reason={step['reason'] if step else '-'}")  # تكملة السطر السابق داخل القوس


def t_resume_continues():  # تعريف الدالة t_resume_continues()
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """A second run must continue - not repeat the cards of the first one.

    The run position lives in the profile (`space_pos` + the shuffled walk).
    The page sends it back with the profile, so the next run starts where the
    previous one stopped; this scenario is that promise, tested.
    """  # نهاية النص متعدد الأسطر
    with MockPortal(valid_cards={"9999"}, pass_mode="empty") as portal:  # سياق مُدار: MockPortal(valid_cards=مجموعة فريدة, pass_mode='empty') باسم portal
        info = scan(portal.url)  # إسناد نتيجة استدعاء scan (معامل واحد) إلى info
        p = make_profile(portal.url, prefix="03", length=4, portal_info=info)  # إسناد نتيجة استدعاء make_profile (معامل واحد، prefix=…، length=…، portal_info=…) إلى p
        _st1, eng1 = run_engine(p, attempts=20, threads=2,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…) إلى مجموعة
                                checks=mock_checks(portal))  # المعامل المسمّى checks
        resumed = dict(eng1.profile)      # بالضبط ما الذي ترسله الصفحة
        st2, eng2 = run_engine(resumed, attempts=20, threads=2,  # إسناد نتيجة استدعاء run_engine (معامل واحد، attempts=…، threads=…، checks=…، reset=…) إلى مجموعة
                               checks=mock_checks(portal), reset=False)  # المعامل المسمّى checks
        pos1 = int(eng1.profile.get("space_pos", 0))  # إسناد نتيجة استدعاء int (معامل واحد) إلى pos1
        pos2 = int(eng2.profile.get("space_pos", 0))  # إسناد نتيجة استدعاء int (معامل واحد) إلى pos2
        same_walk = (eng1.profile.get("walk_a") == eng2.profile.get("walk_a")  # دمج منطقي (و) وإسناده إلى same_walk
                     and eng1.profile.get("walk_b") == eng2.profile.get("walk_b"))  # تكملة السطر السابق داخل القوس
        ok = pos1 == 20 and pos2 == 40 and same_walk  # دمج منطقي (و) وإسناده إلى ok
        return Result("a_second_run_continues_where_the_first_stopped", ok,  # إرجاع Result('a_second_run_continues_where_the_first_stopped', ok, نص منسّق (f-string))
                      f"first_run_ended_at={pos1} second_run_ended_at={pos2} "  # تكملة السطر السابق داخل القوس
                      f"same_walk={same_walk} counters={st2.get('counters')}")  # تكملة السطر السابق داخل القوس


def t_cache_clear():  # تعريف الدالة t_cache_clear()
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Clearing the cache must not eat the results.

    `temp` removes review pages and cache folders but MUST leave the hits log
    alone; only `results`/`all` are allowed to delete it.
    """  # نهاية النص متعدد الأسطر
    st = store.Store()  # إسناد نتيجة استدعاء store.Store إلى st
    saved = st.save_review(1, "0201242548",  # إسناد نتيجة استدعاء st.save_review (4 معاملات) إلى saved
                           {"code": "UNKNOWN", "reason": "reply_differs_not_proven",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                            "data": {}}, "<html>interesting</html>")  # مفتاح data في القاموس
    st.append_hit("selftest card=0242 code=ACCEPTED_VERIFIED")  # استدعاء st.append_hit (معامل واحد)
    before = len(st.list_review())  # إسناد نتيجة استدعاء len (معامل واحد) إلى before
    temp = st.clear_cache("temp")  # إسناد نتيجة استدعاء st.clear_cache (معامل واحد) إلى temp
    review_gone = before >= 1 and not st.list_review()  # دمج منطقي (و) وإسناده إلى review_gone
    hits_kept = os.path.exists(config.HITS_FILE)  # إسناد نتيجة استدعاء os.path.exists (معامل واحد) إلى hits_kept
    results = st.clear_cache("results")  # إسناد نتيجة استدعاء st.clear_cache (معامل واحد) إلى results
    hits_gone = not os.path.exists(config.HITS_FILE)  # إسناد نفي/سالب إلى hits_gone
    ok = review_gone and hits_kept and hits_gone  # دمج منطقي (و) وإسناده إلى ok
    return Result("clear_cache_scope_keeps_results_safe", ok,  # إرجاع Result('clear_cache_scope_keeps_results_safe', ok, نص منسّق (f-string))
                  f"saved={saved.get('file')} before={before} "  # تكملة السطر السابق داخل القوس
                  f"temp_removed={temp.get('removed')} hits_after_temp={hits_kept} "  # تكملة السطر السابق داخل القوس
                  f"results_removed={results.get('removed')} "  # تكملة السطر السابق داخل القوس
                  f"freed={temp.get('freed_human')}")  # تكملة السطر السابق داخل القوس


def t_format_preview():  # تعريف الدالة t_format_preview()
    p = store.new_profile(prefix="020124", length=10, charset="0123456789")  # إسناد نتيجة استدعاء store.new_profile (prefix=…، length=…، charset=…) إلى p
    ok = (store.variable_len(p) == 4 and store.space_size(p) == 10 ** 4  # دمج منطقي (و) وإسناده إلى ok
          and all(len(c) == 10 and c.startswith("020124")  # تكملة السطر السابق داخل القوس
                  for c in store.sample_cards(p, 3)))  # تكملة السطر السابق داخل القوس
    bad = store.validate(store.new_profile(prefix="020124", length=3))  # إسناد نتيجة استدعاء store.validate (معامل واحد) إلى bad
    return Result("card_format_math_and_validation", ok and  # إرجاع Result('card_format_math_and_validation', ok و مقارنة, نص منسّق (f-string))
                  "length_not_bigger_than_prefix_and_suffix" in bad,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                  f"samples={store.sample_cards(p, 3)} space={store.space_size(p)} "  # تكملة السطر السابق داخل القوس
                  f"problems={bad}")  # تكملة السطر السابق داخل القوس


SCENARIOS = (  # إسناد مجموعة إلى SCENARIOS
    t_format_preview,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_legacy_profile,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_calibration,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_no_false_hits,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_find_card,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_verified_hit_stops_before_shared_online_false_hits,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_ban_is_reported,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_rate_limit_stops,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_dropped_connections,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_dead_target_stops,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_chap_portal,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_get_portal,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_diagnose_dead_target,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_resume_continues,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    t_cache_clear,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
)  # إغلاق القوس المفتوح في السطر السابق


# يشغّل السيناريوهات كلها داخل مجلد بيانات مؤقت حتى لا تختلط
# بطاقات التجربة ببروفايلات المستخدم الحقيقية.
def run_all(verbose: bool = True, keep_files: bool = False) -> dict:  # تعريف الدالة run_all(verbose, keep_files) ترجع dict
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Run every scenario inside a throw-away data folder.

    The self-test writes real reports and review pages; they must never land in
    the user's kirapass_data.  `keep_files=True` leaves them behind for
    debugging and prints where they are.
    """  # نهاية النص متعدد الأسطر
    import tempfile  # استيراد الوحدة tempfile من المكتبة
    tmp = tempfile.mkdtemp(prefix="kirapass_selftest_")  # إسناد نتيجة استدعاء tempfile.mkdtemp (prefix=…) إلى tmp
    config.set_data_dir(tmp)  # استدعاء config.set_data_dir (معامل واحد)
    results = []  # إسناد قائمة إلى results
    t_start = time.time()  # إسناد نتيجة استدعاء time.time إلى t_start
    for fn in SCENARIOS:  # دورة على SCENARIOS باسم fn
        t0 = time.time()  # إسناد نتيجة استدعاء time.time إلى t0
        try:  # بدايةtry محمية (يليها except/finally)
            res = fn()  # إسناد نتيجة استدعاء fn إلى res
        # تكملة السطر السابق داخل القوس
        except Exception as exc:                          # noqa: BLE001
            import traceback  # استيراد الوحدة traceback من المكتبة
            res = Result(fn.__name__, False,  # إسناد نتيجة استدعاء Result (3 معاملات) إلى res
                         f"{type(exc).__name__}: {exc} "  # تكملة السطر السابق داخل القوس
                         f"{traceback.format_exc().splitlines()[-1]}")  # تكملة السطر السابق داخل القوس
        res.detail = f"{res.detail} ({time.time() - t0:.1f}s)"  # بناء نص منسّق وإسناده إلى res.detail
        results.append(res)  # استدعاء results.append (معامل واحد)
        if verbose:  # شرط: verbose
            print(("  " + str(res)).ljust(110), flush=True)  # استدعاء print (معامل واحد، flush=…)
    passed = sum(1 for r in results if r.ok)  # إسناد نتيجة استدعاء sum (معامل واحد) إلى passed
    summary = {"ok": passed == len(results), "passed": passed,  # إسناد قاموس إلى summary
               "total": len(results), "seconds": round(time.time() - t_start, 1),  # مفتاح total في القاموس
               "results": [{"name": r.name, "ok": r.ok, "detail": r.detail}  # مفتاح results في القاموس
                           for r in results]}  # تكملة السطر السابق داخل القوس
    summary["data_dir"] = tmp  # إسناد tmp إلى summary['data_dir']
    if keep_files:  # شرط: keep_files
        if verbose:  # شرط: verbose
            print(f"\n  test files kept in: {tmp}")  # استدعاء print (معامل واحد)
    else:  # مفتاح else في القاموس
        shutil.rmtree(tmp, ignore_errors=True)  # استدعاء shutil.rmtree (معامل واحد، ignore_errors=…)
    if verbose:  # شرط: verbose
        print(f"\n  {passed}/{len(results)} passed in {summary['seconds']}s"  # استدعاء print (معامل واحد)
              f"  ->  {'ALL GOOD' if summary['ok'] else 'SOMETHING FAILED'}")  # تكملة السطر السابق داخل القوس
    return summary  # إرجاع summary


if __name__ == "__main__":  # شرط: __name__ يساوي '__main__'
    print("KiraPass self-test (local mock routers only, no real network used)\n")  # استدعاء print (معامل واحد)
    run_all(keep_files="--keep" in sys.argv)  # استدعاء run_all (keep_files=…)
