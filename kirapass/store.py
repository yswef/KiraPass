# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Profiles, settings, reports and the "clear cache" logic - all in one place.

Profiles from the old version are **migrated automatically** instead of
crashing.  That KeyError('charset') crash is one of the reasons the tool
"stopped working" for a user who only replaced the .py file: the saved profile
on disk was written by an older version.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import glob  # استيراد الوحدة glob من المكتبة
import json  # استيراد الوحدة json من المكتبة
import os  # استيراد الوحدة os من المكتبة
import re  # استيراد الوحدة re من المكتبة
import shutil  # استيراد الوحدة shutil من المكتبة
import time  # استيراد الوحدة time من المكتبة

from . import config  # استيراد config من الوحدة .

SCHEMA = 5  # إسناد القيمة الثابتة SCHEMA
CHARSETS = {  # إسناد قاموس إلى CHARSETS
    "digits": "0123456789",  # مفتاح digits في القاموس
    "lower": "abcdefghijklmnopqrstuvwxyz",  # مفتاح lower في القاموس
    "upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # مفتاح upper في القاموس
    "alnum": "0123456789abcdefghijklmnopqrstuvwxyz",  # مفتاح alnum في القاموس
    "alnum_upper": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # مفتاح alnum_upper في القاموس
    "hex": "0123456789abcdef",  # مفتاح hex في القاموس
    "hex_upper": "0123456789ABCDEF",  # مفتاح hex_upper في القاموس
}  # إغلاق القوس المفتوح في السطر السابق
PASS_MODES = ("same", "empty", "omit", "fixed", "chap", "chap_empty",  # إسناد مجموعة إلى PASS_MODES
              "md5user", "sha1user", "sha256user")  # تكملة السطر السابق داخل القوس


def ensure_dirs() -> None:  # تعريف الدالة ensure_dirs() ترجع None
    for d in config.ALL_DIRS:  # دورة على config.ALL_DIRS باسم d
        os.makedirs(d, exist_ok=True)  # استدعاء os.makedirs (معامل واحد، exist_ok=…)


# كتابة آمنة: ملف مؤقت ثم os.replace() — لا يرى القارئ نصف JSON أبداً.
# محاولتان تتحمّلان حذف المجلد أثناء الكتابة (زر «مسح البيانات»).
def atomic_write(path: str, text: str) -> None:  # تعريف الدالة atomic_write(path, text) ترجع None
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Write a file so that a reader never sees half of it.

    Tolerates the folder being deleted at the same moment (the user pressing
    "clear cache" while a run is saving something).
    """  # نهاية النص متعدد الأسطر
    for attempt in range(2):  # دورة على range(2) باسم attempt
        try:  # بدايةtry محمية (يليها except/finally)
            ensure_dirs()  # استدعاء ensure_dirs
            tmp = path + ".tmp"  # حساب جمع بين path و'.tmp' وإسناده إلى tmp
            with open(tmp, "w", encoding="utf-8") as fh:  # سياق مُدار: open(tmp, 'w', encoding='utf-8') باسم fh
                fh.write(text)  # استدعاء fh.write (معامل واحد)
            os.replace(tmp, path)  # استدعاء os.replace (2 معاملات)
            return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)
        except OSError:  # تكملة السطر السابق داخل القوس
            if attempt:  # شرط: attempt
                return  # إنهاء الدالة بلا قيمة (ترجع None ضمناً)


def read_json(path: str, default):  # تعريف الدالة read_json(path, default)
    try:  # بدايةtry محمية (يليها except/finally)
        with open(path, "r", encoding="utf-8") as fh:  # سياق مُدار: open(path, 'r', encoding='utf-8') باسم fh
            return json.load(fh)  # إرجاع json.load(fh)
    except Exception:  # تكملة السطر السابق داخل القوس
        return default  # إرجاع default


def clean(name: str, limit: int = 60) -> str:  # تعريف الدالة clean(name, limit) ترجع str
    name = re.sub(r"[^A-Za-z0-9_\u0600-\u06FF .-]+", "_", (name or "").strip())  # إسناد نتيجة استدعاء re.sub (3 معاملات) إلى name
    return name[:limit] or "profile"  # إرجاع name[] أو 'profile'


# ---------------------------------------------------------------------------
# مساعدات البروفايل (دوال صرفة — سهلة الاختبار)
# ---------------------------------------------------------------------------
# الصيغة الكاملة للبروفايل: أي حقل غير موجود هنا يُسقطه migrate().
# لذلك إضافة حقل جديد تبدأ دائماً من هذه الدالة.
def new_profile(**kw) -> dict:  # تعريف الدالة new_profile(**kw) ترجع dict
    p = {  # إسناد قاموس إلى p
        "schema": SCHEMA,  # مفتاح schema في القاموس
        "name": "",  # مفتاح name في القاموس
        "login_url": "",  # مفتاح login_url في القاموس
        "method": "post",  # مفتاح method في القاموس
        "user_field": "username",  # مفتاح user_field في القاموس
        "pass_field": "password",  # مفتاح pass_field في القاموس
        "pass_mode": "empty",  # مفتاح pass_mode في القاموس
        "pass_fixed": "",  # مفتاح pass_fixed في القاموس
        "extra_fields": {},  # مفتاح extra_fields في القاموس
        "dst_field": "dst",  # مفتاح dst_field في القاموس
        "dst_value": "",  # مفتاح dst_value في القاموس
        "send_dst": True,  # مفتاح send_dst في القاموس
        "popup_field": "popup",  # مفتاح popup_field في القاموس
        "send_popup": True,  # مفتاح send_popup في القاموس
        "chap": None,  # مفتاح chap في القاموس
        "charset": CHARSETS["digits"],  # مفتاح charset في القاموس
        "length": 10,  # مفتاح length في القاموس
        "prefix": "",  # مفتاح prefix في القاموس
        "suffix": "",  # مفتاح suffix في القاموس
        "space_pos": 0,  # مفتاح space_pos في القاموس
        "space_pass": 0,  # مفتاح space_pass في القاموس
        "walk_a": 0,  # مفتاح walk_a في القاموس
        "walk_b": 0,  # مفتاح walk_b في القاموس
        "note": "",  # مفتاح note في القاموس
        "success_words": [],  # مفتاح success_words في القاموس
        "success_url_contains": "",  # مفتاح success_url_contains في القاموس
        "stats_url": "",  # مفتاح stats_url في القاموس
        "capture_needs_browser_js": False,  # مفتاح capture_needs_browser_js في القاموس
        "capture_block_reason": "",  # مفتاح capture_block_reason في القاموس
        # ما الذي قاسه فحص الحجب على هذا الراوتر (انظر
        # engine.probe_lockout) — يستخدمه التشغيل لينتظر بالضبط
        # ما يحتاجه هذا الراوتر بدل 45 ثانية مخمَّنة
        # كيف يجب أن يبدو الطلب لهذه البوابة: بعضها يرفض
        # أي شيء لا يبدو كالمتصفح الذي فحصها
        "user_agent": "",  # مفتاح user_agent في القاموس
        "send_referer": True,  # مفتاح send_referer في القاموس
        "ban_after": None,  # مفتاح ban_after في القاموس
        "clears_after": None,  # مفتاح clears_after في القاموس
        "safe_delay_ms": 0,  # مفتاح safe_delay_ms في القاموس
    }  # إغلاق القوس المفتوح في السطر السابق
    p.update(kw)  # استدعاء p.update (معامل واحد)
    return p  # إرجاع p


def variable_len(p: dict) -> int:  # تعريف الدالة variable_len(p) ترجع int
    # إرجاع طرح
    return int(p.get("length", 0)) - len(p.get("prefix", "")) - \
        len(p.get("suffix", ""))  # تكملة السطر السابق داخل القوس


def space_size(p: dict) -> int:  # تعريف الدالة space_size(p) ترجع int
    vlen = variable_len(p)  # إسناد نتيجة استدعاء variable_len (معامل واحد) إلى vlen
    chars = len(set(p.get("charset", "")))  # إسناد نتيجة استدعاء len (معامل واحد) إلى chars
    if vlen <= 0 or chars < 2:  # شرط مركّب (أو)
        return 0  # إرجاع 0
    return chars ** vlen  # إرجاع أسّ


# يرجع قائمة مفاتيح آلية للمشاكل (فارغة = البروفايل صالح).
# space_is_astronomically_big تحذير لا مانع.
def validate(p: dict) -> list:  # تعريف الدالة validate(p) ترجع list
    """-> list of machine-readable problems (empty = good to go)."""  # نص توثيقي (docstring) يشرح ما يليه
    problems = []  # إسناد قائمة إلى problems
    if not (p.get("login_url") or "").startswith(("http://", "https://")):  # شرط معكوس: ليس p.get('login_url') أو ''.startswith(مجموعة)
        problems.append("url_missing_or_invalid")  # استدعاء problems.append (معامل واحد)
    if not p.get("user_field"):  # شرط معكوس: ليس p.get('user_field')
        problems.append("user_field_missing")  # استدعاء problems.append (معامل واحد)
    vlen = variable_len(p)  # إسناد نتيجة استدعاء variable_len (معامل واحد) إلى vlen
    if vlen <= 0:  # شرط: vlen أصغر أو يساوي 0
        problems.append("length_not_bigger_than_prefix_and_suffix")  # استدعاء problems.append (معامل واحد)
    if len(set(p.get("charset") or "")) < 2:  # شرط: len(set(p.get('charset') أو '')) أصغر من 2
        problems.append("charset_too_small")  # استدعاء problems.append (معامل واحد)
    if p.get("pass_mode") not in PASS_MODES:  # شرط: p.get('pass_mode') ليس ضمن PASS_MODES
        problems.append("unknown_pass_mode")  # استدعاء problems.append (معامل واحد)
    if p.get("pass_mode") == "fixed" and not p.get("pass_fixed"):  # شرط مركّب (و)
        problems.append("fixed_password_empty")  # استدعاء problems.append (معامل واحد)
    if p.get("capture_needs_browser_js"):  # شرط: نتيجة p.get('capture_needs_browser_js')
        problems.append("needs_browser_js")  # استدعاء problems.append (معامل واحد)
    if len(set(p.get("charset") or "")) ** max(vlen, 1) > config.BIG_SPACE:  # شرط: أسّ أكبر من config.BIG_SPACE
        problems.append("space_is_astronomically_big")   # تحذير، لا مانع
    return problems  # إرجاع problems


# رقم ⇒ بطاقة: تحويل بأساس عدد المحارف الفريدة المرتّبة.
# sorted(set(charset)) مقصود: أبجدية فيها تكرار تُنتج بطاقات مكرّرة.
def decode_card(p: dict, index: int) -> str:  # تعريف الدالة decode_card(p, index) ترجع str
    charset = p.get("charset", "")  # إسناد نتيجة استدعاء p.get (2 معاملات) إلى charset
    vlen = variable_len(p)  # إسناد نتيجة استدعاء variable_len (معامل واحد) إلى vlen
    base = len(set(charset))  # إسناد نتيجة استدعاء len (معامل واحد) إلى base
    chars = sorted(set(charset))  # إسناد نتيجة استدعاء sorted (معامل واحد) إلى chars
    out = []  # إسناد قائمة إلى out
    for _ in range(vlen):  # دورة على range(vlen) باسم _
        out.append(chars[index % base])  # استدعاء out.append (معامل واحد)
        index //= base  # تحديث index بعملية قسمة صحيحة
    return p.get("prefix", "") + "".join(out) + p.get("suffix", "")  # إرجاع جمع


def sample_cards(p: dict, count: int = 3) -> list:  # تعريف الدالة sample_cards(p, count) ترجع list
    space = space_size(p)  # إسناد نتيجة استدعاء space_size (معامل واحد) إلى space
    if space <= 0:  # شرط: space أصغر أو يساوي 0
        return []  # إرجاع قائمة
    picks = {0, space // 2, space - 1, space // 3}  # إسناد مجموعة فريدة إلى picks
    return [decode_card(p, i) for i in sorted(picks)][:count]  # إرجاع اشتقاق قائمة[]


# مشي مخلوط بلا تكرار: (b + a*pos) mod space حيث a أولي نسبياً مع space.
def card_at_walk_pos(p: dict, pos: int) -> str:  # تعريف الدالة card_at_walk_pos(p, pos) ترجع str
    """Shuffled but repeat-free walk over the whole space."""  # نص توثيقي (docstring) يشرح ما يليه
    space = space_size(p)  # إسناد نتيجة استدعاء space_size (معامل واحد) إلى space
    if space <= 1:  # شرط: space أصغر أو يساوي 1
        return decode_card(p, 0)  # إرجاع decode_card(p, 0)
    a = int(p.get("walk_a", 0)) % space  # حساب باقي القسمة بين int(p.get('walk_a', 0)) وspace وإسناده إلى a
    b = int(p.get("walk_b", 0)) % space  # حساب باقي القسمة بين int(p.get('walk_b', 0)) وspace وإسناده إلى b
    if a == 0:  # شرط: a يساوي 0
        a = 1  # إسناد القيمة الثابتة a
    idx = (b + a * pos) % space  # حساب باقي القسمة بين جمع وspace وإسناده إلى idx
    return decode_card(p, idx)  # إرجاع decode_card(p, idx)


# يقبل بروفايلاً من أي نسخة قديمة ويحوّله إلى الصيغة الحالية.
# في النهاية يمرّر login_url عبر sanitize_login_url حتى تُحذف أي بطاقة
# أو كلمة مرور قديمة منسوخة داخل رابط GET.
def migrate(raw: dict) -> dict:  # تعريف الدالة migrate(raw) ترجع dict
    """Accept a profile written by ANY older version of the tool."""  # نص توثيقي (docstring) يشرح ما يليه
    if not isinstance(raw, dict):  # شرط معكوس: ليس isinstance(raw, dict)
        return new_profile()  # إرجاع new_profile()
    p = new_profile()  # إسناد نتيجة استدعاء new_profile إلى p
    p.update({k: v for k, v in raw.items() if k in p})  # استدعاء p.update (معامل واحد)

    nt = str(raw.get("network_type", "1"))  # إسناد نتيجة استدعاء str (معامل واحد) إلى nt
    prefix = raw.get("prefix", p["prefix"]) or ""  # دمج منطقي (أو) وإسناده إلى prefix
    suffix = raw.get("suffix", p["suffix"]) or ""  # دمج منطقي (أو) وإسناده إلى suffix
    charset = raw.get("charset") or p["charset"]  # دمج منطقي (أو) وإسناده إلى charset
    vlen = raw.get("var_len")  # إسناد نتيجة استدعاء raw.get (معامل واحد) إلى vlen
    if vlen:  # شرط: vlen
        length = int(vlen) + len(prefix) + len(suffix)  # حساب جمع بين جمع وlen(suffix) وإسناده إلى length
    else:  # مفتاح else في القاموس
        length = int(raw.get("length", p["length"]) or p["length"])  # إسناد نتيجة استدعاء int (معامل واحد) إلى length

    if nt == "3":  # شرط: nt يساوي '3'
        # بروفايلات «اسم مستخدم + كلمة مرور مختلفة» القديمة: أبقِ شكل
        # اسم المستخدم، ويصير جانب كلمة المرور قيمة ثابتة/مشتقة.
        prefix = raw.get("u_prefix", prefix) or ""  # دمج منطقي (أو) وإسناده إلى prefix
        suffix = raw.get("u_suffix", suffix) or ""  # دمج منطقي (أو) وإسناده إلى suffix
        charset = raw.get("u_charset", charset) or charset  # دمج منطقي (أو) وإسناده إلى charset
        length = int(raw.get("u_len", 0) or 0) + len(prefix) + len(suffix) or length  # دمج منطقي (أو) وإسناده إلى length
        p["pass_mode"] = "fixed"  # إسناد القيمة الثابتة p['pass_mode']
    elif nt == "2" and raw.get("pass_mode") in (None, "same"):  # شرط مركّب (و)
        p["pass_mode"] = "same"  # إسناد القيمة الثابتة p['pass_mode']
    elif p.get("pass_mode") in (None, ""):  # شرط: p.get('pass_mode') ضمن مجموعة
        p["pass_mode"] = "empty"  # إسناد القيمة الثابتة p['pass_mode']

    p.update({  # استدعاء p.update (معامل واحد)
        "charset": charset,  # مفتاح charset في القاموس
        "length": max(length, len(prefix) + len(suffix) + 1),  # مفتاح length في القاموس
        "prefix": prefix,  # مفتاح prefix في القاموس
        "suffix": suffix,  # مفتاح suffix في القاموس
        "method": "post" if str(raw.get("method", "2")) in ("2", "post") else "get",  # مفتاح method في القاموس
        "send_dst": bool(raw.get("send_dst")) if "send_dst" in raw  # مفتاح send_dst في القاموس
                    else bool(raw.get("extras", True)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        "send_popup": bool(raw.get("send_popup")) if "send_popup" in raw  # مفتاح send_popup في القاموس
                      else bool(raw.get("extras", True)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        "dst_value": raw.get("dst_value", ""),  # مفتاح dst_value في القاموس
        "dst_field": raw.get("dst_field") or "dst",  # مفتاح dst_field في القاموس
        "popup_field": raw.get("popup_field") or "popup",  # مفتاح popup_field في القاموس
        "extra_fields": raw.get("fixed_fields") or raw.get("extra_fields") or {},  # مفتاح extra_fields في القاموس
        "success_words": raw.get("success_signature") or raw.get("success_words") or [],  # مفتاح success_words في القاموس
        "success_url_contains": raw.get("success_url_contains", "") or "",  # مفتاح success_url_contains في القاموس
        "space_pos": int(raw.get("space_pos", 0) or 0),  # مفتاح space_pos في القاموس
        "space_pass": int(raw.get("space_pass", 0) or 0),  # مفتاح space_pass في القاموس
        "walk_a": int(raw.get("walk_a", 0) or 0),  # مفتاح walk_a في القاموس
        "walk_b": int(raw.get("walk_b", 0) or 0),  # مفتاح walk_b في القاموس
        "schema": SCHEMA,  # مفتاح schema في القاموس
    })  # إغلاق القوس المفتوح في السطر السابق
    if (raw.get("walk") or {}).get("pos"):  # شرط: نتيجة raw.get('walk') أو قاموس.get('pos')
        p["space_pos"] = int(raw["walk"]["pos"])  # إسناد نتيجة استدعاء int (معامل واحد) إلى p['space_pos']
    # البروفايلات القديمة قد تحتوي رابط GET ناجحاً منسوخاً بالبطاقة
    # وتجزئة كلمة المرور في استعلامه. أبقِ شكل طلبه، لا أسرار.
    from .portals import sanitize_login_url  # استيراد sanitize_login_url من الوحدة portals
    p["login_url"] = sanitize_login_url(  # إسناد نتيجة استدعاء sanitize_login_url (3 معاملات) إلى p['login_url']
        p.get("login_url", ""), p.get("user_field", "username"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
        p.get("pass_field", "password"))  # تكملة السطر السابق داخل القوس
    return p  # إرجاع p


# ---------------------------------------------------------------------------
# التخزين
# ---------------------------------------------------------------------------
class Store:  # تعريف الصنف Store
    def __init__(self):  # تعريف الدالة __init__(self)
        ensure_dirs()  # استدعاء ensure_dirs
        self.path = config.PROFILES_FILE  # إسناد config.PROFILES_FILE إلى self.path
        self._profiles = self._load()  # إسناد نتيجة استدعاء self._load إلى self._profiles
        self.settings = read_json(config.SETTINGS_FILE, {}) or {}  # دمج منطقي (أو) وإسناده إلى self.settings

    # -- البروفايلات ------------------------------------------------------
    def _load(self) -> dict:  # تعريف الدالة _load(self) ترجع dict
        raw = read_json(self.path, {})  # إسناد نتيجة استدعاء read_json (2 معاملات) إلى raw
        out = {}  # إسناد قاموس إلى out
        if isinstance(raw, dict) and "profiles" in raw:  # شرط مركّب (و)
            items = raw.get("profiles") or []  # دمج منطقي (أو) وإسناده إلى items
        elif isinstance(raw, list):  # شرط: نتيجة isinstance(raw, list)
            items = raw  # إسناد raw إلى items
        else:  # مفتاح else في القاموس
            items = [raw] if raw else []  # إسناد قائمة إن raw وإلا قائمة إلى items
        for item in items:  # دورة على items باسم item
            try:  # بدايةtry محمية (يليها except/finally)
                prof = migrate(item)  # إسناد نتيجة استدعاء migrate (معامل واحد) إلى prof
            except Exception:  # تكملة السطر السابق داخل القوس
                continue  # الانتقال إلى الدورة التالية
            name = clean(prof.get("name") or "")  # إسناد نتيجة استدعاء clean (معامل واحد) إلى name
            if not name or name == "profile":  # شرط مركّب (أو)
                name = clean(prof.get("login_url", "profile").split("//")[-1])  # إسناد نتيجة استدعاء clean (معامل واحد) إلى name
            prof["name"] = name  # إسناد name إلى prof['name']
            out[name] = prof  # إسناد prof إلى out[name]
        return out  # إرجاع out

    def save(self) -> None:  # تعريف الدالة save(self) ترجع None
        payload = {"schema": SCHEMA, "saved": time.strftime("%Y-%m-%d %H:%M:%S"),  # إسناد قاموس إلى payload
                   "profiles": list(self._profiles.values())}  # مفتاح profiles في القاموس
        atomic_write(self.path, json.dumps(payload, ensure_ascii=False, indent=2))  # استدعاء atomic_write (2 معاملات)

    def all(self) -> list:  # تعريف الدالة all(self) ترجع list
        return sorted(self._profiles.values(), key=lambda x: x.get("name", ""))  # إرجاع sorted(self._profiles.values(), key=دالة مجهولة)

    def get(self, name: str):  # تعريف الدالة get(self, name)
        return self._profiles.get(clean(name))  # إرجاع self._profiles.get(clean(name))

    def put(self, profile: dict) -> dict:  # تعريف الدالة put(self, profile) ترجع dict
        prof = migrate(profile)  # إسناد نتيجة استدعاء migrate (معامل واحد) إلى prof
        name = clean(prof.get("name") or  # إسناد نتيجة استدعاء clean (معامل واحد) إلى name
                     prof.get("login_url", "profile").split("//")[-1])  # تكملة السطر السابق داخل القوس
        if name == "profile":  # شرط: name يساوي 'profile'
            name = f"profile-{len(self._profiles) + 1}"  # بناء نص منسّق وإسناده إلى name
        prof["name"] = name  # إسناد name إلى prof['name']
        self._profiles[name] = prof  # إسناد prof إلى self._profiles[name]
        self.save()  # استدعاء self.save
        return prof  # إرجاع prof

    def delete(self, name: str) -> bool:  # تعريف الدالة delete(self, name) ترجع bool
        prof = self._profiles.pop(clean(name), None)  # إسناد نتيجة استدعاء self._profiles.pop (2 معاملات) إلى prof
        if prof:  # شرط: prof
            self.save()  # استدعاء self.save
            return True  # إرجاع True
        return False  # إرجاع False

    def get_setting(self, key, default=None):  # تعريف الدالة get_setting(self, key, default)
        return self.settings.get(key, default)  # إرجاع self.settings.get(key, default)

    def set_setting(self, key, value) -> None:  # تعريف الدالة set_setting(self, key, value) ترجع None
        self.settings[key] = value  # إسناد value إلى self.settings[key]
        atomic_write(config.SETTINGS_FILE, json.dumps(self.settings,  # استدعاء atomic_write (2 معاملات)
                                                      ensure_ascii=False, indent=2))  # المعامل المسمّى ensure_ascii

    # -- التقارير / صفحات المراجعة ----------------------------------------
    def save_review(self, seq: int, card: str, verdict: dict, body: str) -> dict:  # تعريف الدالة save_review(self, seq, card, verdict, body) ترجع dict
        ensure_dirs()  # استدعاء ensure_dirs
        name = f"{int(time.time())}_{seq:05d}_{clean(card, 24)}.html"  # بناء نص منسّق وإسناده إلى name
        path = os.path.join(config.REVIEW_DIR, name)  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى path
        try:  # بدايةtry محمية (يليها except/finally)
            with open(path, "w", encoding="utf-8") as fh:  # سياق مُدار: open(path, 'w', encoding='utf-8') باسم fh
                fh.write(redact_review_body(body or "")[:400000])  # استدعاء fh.write (معامل واحد)
        except OSError:  # تكملة السطر السابق داخل القوس
            return {}  # إرجاع قاموس
        try:  # بدايةtry محمية (يليها except/finally)
            index = read_json(os.path.join(config.REVIEW_DIR, "index.json"), [])  # إسناد نتيجة استدعاء read_json (2 معاملات) إلى index
            index.append({"file": name, "card": card,  # استدعاء index.append (معامل واحد)
                          "saved": time.strftime("%Y-%m-%d %H:%M:%S"),  # مفتاح saved في القاموس
                          **{k: verdict.get(k)  # تكملة السطر السابق داخل القوس
                             for k in ("code", "reason", "data")}})  # تكملة السطر السابق داخل القوس
            atomic_write(os.path.join(config.REVIEW_DIR, "index.json"),  # استدعاء atomic_write (2 معاملات)
                         json.dumps(index[-500:], ensure_ascii=False, indent=2))  # تكملة السطر السابق داخل القوس
        except OSError:  # تكملة السطر السابق داخل القوس
            pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
        return {"file": name, "card": card, "reason": verdict.get("reason"),  # إرجاع قاموس
                "data": verdict.get("data")}  # مفتاح data في القاموس

    def list_review(self) -> list:  # تعريف الدالة list_review(self) ترجع list
        index = read_json(os.path.join(config.REVIEW_DIR, "index.json"), [])  # إسناد نتيجة استدعاء read_json (2 معاملات) إلى index
        return list(reversed(index))  # إرجاع list(reversed(index))

    def read_review(self, name: str) -> str:  # تعريف الدالة read_review(self, name) ترجع str
        safe = os.path.basename(name)  # إسناد نتيجة استدعاء os.path.basename (معامل واحد) إلى safe
        path = os.path.join(config.REVIEW_DIR, safe)  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى path
        try:  # بدايةtry محمية (يليها except/finally)
            with open(path, "r", encoding="utf-8", errors="replace") as fh:  # سياق مُدار: open(path, 'r', encoding='utf-8', errors='replace') باسم fh
                return fh.read()  # إرجاع fh.read()
        except OSError:  # تكملة السطر السابق داخل القوس
            return ""  # إرجاع ''

    def save_run(self, report: dict) -> str:  # تعريف الدالة save_run(self, report) ترجع str
        ensure_dirs()  # استدعاء ensure_dirs
        self.cleanup_old_reports()  # استدعاء self.cleanup_old_reports
        name = time.strftime("%Y%m%d_%H%M%S") + "_" + clean(report.get("profile", "run"), 24)  # حساب جمع بين جمع وclean(report.get('profile', 'run'), 24) وإسناده إلى name
        path = os.path.join(config.RUN_DIR, name + ".json")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى path
        atomic_write(path, json.dumps(report, ensure_ascii=False, indent=2))  # استدعاء atomic_write (2 معاملات)
        return path  # إرجاع path

    def cleanup_old_reports(self, days: int = None) -> dict:  # تعريف الدالة cleanup_old_reports(self, days) ترجع dict
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Delete run reports older than `days` (default from config).

        Optional and never touches hits/profiles. Returns how many files went.
        """  # نهاية النص متعدد الأسطر
        retain = config.REPORT_RETENTION_DAYS if days is None else int(days)  # إسناد config.REPORT_RETENTION_DAYS إن مقارنة وإلا int(days) إلى retain
        if retain <= 0:  # شرط: retain أصغر أو يساوي 0
            return {"removed": 0, "freed_bytes": 0, "days": retain}  # إرجاع قاموس
        cutoff = time.time() - retain * 86400  # حساب طرح بين time.time() وضرب وإسناده إلى cutoff
        removed, freed = 0, 0  # إسناد مجموعة إلى مجموعة
        try:  # بدايةtry محمية (يليها except/finally)
            names = os.listdir(config.RUN_DIR)  # إسناد نتيجة استدعاء os.listdir (معامل واحد) إلى names
        except OSError:  # تكملة السطر السابق داخل القوس
            return {"removed": 0, "freed_bytes": 0, "days": retain}  # إرجاع قاموس
        for name in names:  # دورة على names باسم name
            if not name.endswith(".json"):  # شرط معكوس: ليس name.endswith('.json')
                continue  # الانتقال إلى الدورة التالية
            path = os.path.join(config.RUN_DIR, name)  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى path
            try:  # بدايةtry محمية (يليها except/finally)
                if os.path.getmtime(path) < cutoff:  # شرط: os.path.getmtime(path) أصغر من cutoff
                    size = os.path.getsize(path)  # إسناد نتيجة استدعاء os.path.getsize (معامل واحد) إلى size
                    os.remove(path)  # استدعاء os.remove (معامل واحد)
                    removed += 1  # تحديث removed بعملية جمع
                    freed += size  # تحديث freed بعملية جمع
            except OSError:  # تكملة السطر السابق داخل القوس
                continue  # الانتقال إلى الدورة التالية
        return {"removed": removed, "freed_bytes": freed, "days": retain}  # إرجاع قاموس

    def append_hit(self, line: str) -> None:  # تعريف الدالة append_hit(self, line) ترجع None
        ensure_dirs()  # استدعاء ensure_dirs
        with open(config.HITS_FILE, "a", encoding="utf-8") as fh:  # سياق مُدار: open(config.HITS_FILE, 'a', encoding='utf-8') باسم fh
            fh.write(line.rstrip() + "\n")  # استدعاء fh.write (معامل واحد)

    # -- الكاش ------------------------------------------------------------
    def cache_info(self) -> dict:  # تعريف الدالة cache_info(self) ترجع dict
        info = {"folders": {}, "files": {}, "total_bytes": 0}  # إسناد قاموس إلى info
        for label, folder in (("review", config.REVIEW_DIR),  # دورة على مجموعة باسم مجموعة
                              ("runs", config.RUN_DIR),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                              ("cache", config.CACHE_DIR),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                              ("logs", config.LOG_DIR)):  # تكملة تعريف متعدد الأسطر
            size, count = _dir_size(folder)  # إسناد نتيجة استدعاء _dir_size (معامل واحد) إلى مجموعة
            info["folders"][label] = {"files": count, "bytes": size,  # إسناد قاموس إلى info['folders'][label]
                                      "path": folder}  # مفتاح path في القاموس
            info["total_bytes"] += size  # تحديث info['total_bytes'] بعملية جمع
        for path in (config.HITS_FILE,) + config.LEGACY_FILES:  # دورة على جمع باسم path
            if os.path.exists(path):  # شرط: نتيجة os.path.exists(path)
                size = os.path.getsize(path)  # إسناد نتيجة استدعاء os.path.getsize (معامل واحد) إلى size
                info["files"][os.path.basename(path)] = size  # إسناد size إلى info['files'][os.path.basename(path)]
                info["total_bytes"] += size  # تحديث info['total_bytes'] بعملية جمع
        prof = config.PROFILES_FILE  # إسناد config.PROFILES_FILE إلى prof
        info["profiles"] = {"file": os.path.basename(prof),  # إسناد قاموس إلى info['profiles']
                            "count": len(self._profiles),  # مفتاح count في القاموس
                            "bytes": os.path.getsize(prof) if os.path.exists(prof) else 0}  # مفتاح bytes في القاموس
        return info  # إرجاع info

    def clear_cache(self, scope: str = "temp") -> dict:  # تعريف الدالة clear_cache(self, scope) ترجع dict
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """Delete tool data by scope.

        temp     -> saved review pages + cache folders (never the hits log)
        results  -> run reports, logs and hits.txt
        profiles -> profiles.json
        all      -> everything above + legacy files from the old version
        """  # نهاية النص متعدد الأسطر
        removed, freed = [], 0  # إسناد مجموعة إلى مجموعة
        targets = []  # إسناد قائمة إلى targets
        if scope in ("temp", "all"):  # شرط: scope ضمن مجموعة
            targets += [config.CACHE_DIR, config.REVIEW_DIR]  # تحديث targets بعملية جمع
        if scope in ("results", "all"):  # شرط: scope ضمن مجموعة
            # سجل الإصابات من النتائج، لا من تنظيف «المؤقت»:
            # مسح الكاش يجب ألا يحذف أبداً بطاقات وُجدت بصمت
            targets += [config.RUN_DIR, config.LOG_DIR, config.HITS_FILE]  # تحديث targets بعملية جمع
        always = []  # إسناد قائمة إلى always
        if scope == "all":  # شرط: scope يساوي 'all'
            always += list(config.LEGACY_FILES)  # تحديث always بعملية جمع
            targets += [config.DATA_DIR]  # تحديث targets بعملية جمع
        for path in targets + always:  # دورة على جمع باسم path
            if not os.path.exists(path):  # شرط معكوس: ليس os.path.exists(path)
                continue                      # لا تسرد ما لم يكن موجوداً
            freed += _remove_path(path)  # تحديث freed بعملية جمع
            removed.append(os.path.basename(path))  # استدعاء removed.append (معامل واحد)
        if scope in ("profiles", "all") and os.path.exists(config.PROFILES_FILE):  # شرط مركّب (و)
            try:  # بدايةtry محمية (يليها except/finally)
                os.remove(config.PROFILES_FILE)  # استدعاء os.remove (معامل واحد)
                removed.append(os.path.basename(config.PROFILES_FILE))  # استدعاء removed.append (معامل واحد)
                self._profiles = {}  # إسناد قاموس إلى self._profiles
            except OSError:  # تكملة السطر السابق داخل القوس
                pass  # سطر فارغ منطقياً (pass) — مطلوب صياغياً
        # كاشات البايت كود للأداة نفسها (نمطا glob
        # متداخلان — بدون هذه المجموعة كان نفس المجلد يُحسب مرتين
        # وكان رقم «المحرَّر» كذبة)
        seen_paths = set()  # إسناد نتيجة استدعاء set إلى seen_paths
        for pattern in ("**/__pycache__", "__pycache__"):  # دورة على مجموعة باسم pattern
            for path in glob.glob(os.path.join(config.BASE_DIR, pattern),  # دورة على glob.glob(os.path.join(config.BASE_DIR, pattern), recursive=True) باسم path
                                  recursive=True):  # المعامل المسمّى recursive
                key = os.path.normpath(path)  # إسناد نتيجة استدعاء os.path.normpath (معامل واحد) إلى key
                if key in seen_paths:  # شرط: key ضمن seen_paths
                    continue  # الانتقال إلى الدورة التالية
                seen_paths.add(key)  # استدعاء seen_paths.add (معامل واحد)
                size, _ = _dir_size(path)  # إسناد نتيجة استدعاء _dir_size (معامل واحد) إلى مجموعة
                shutil.rmtree(path, ignore_errors=True)  # استدعاء shutil.rmtree (معامل واحد، ignore_errors=…)
                freed += size  # تحديث freed بعملية جمع
                removed.append(os.path.relpath(path, config.BASE_DIR))  # استدعاء removed.append (معامل واحد)
        ensure_dirs()  # استدعاء ensure_dirs
        return {"scope": scope, "removed": sorted(set(removed)),  # إرجاع قاموس
                "freed_bytes": freed, "freed_human": human_size(freed)}  # مفتاح freed_bytes في القاموس


def _dir_size(path: str) -> tuple:  # تعريف الدالة _dir_size(path) ترجع tuple
    total, count = 0, 0  # إسناد مجموعة إلى مجموعة
    if not os.path.isdir(path):  # شرط معكوس: ليس os.path.isdir(path)
        return 0, 0  # إرجاع مجموعة
    for root, _dirs, files in os.walk(path):  # دورة على os.walk(path) باسم مجموعة
        for f in files:  # دورة على files باسم f
            try:  # بدايةtry محمية (يليها except/finally)
                total += os.path.getsize(os.path.join(root, f))  # تحديث total بعملية جمع
                count += 1  # تحديث count بعملية جمع
            except OSError:  # تكملة السطر السابق داخل القوس
                continue  # الانتقال إلى الدورة التالية
    return total, count  # إرجاع مجموعة


# يميّز الملف من المجلد ويرجع البايتات المحررة فعلاً.
# shutil.rmtree على ملف لا يفعل شيئاً بصمت — هكذا كانت hits.txt تُحسب محذوفة.
def _remove_path(path: str) -> int:  # تعريف الدالة _remove_path(path) ترجع int
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Delete a file or a folder and return the bytes really freed.

    `shutil.rmtree(..., ignore_errors=True)` silently does nothing when handed
    a *file* - which is how the old code managed to list hits.txt as "removed"
    without removing it.  This helper never lies about what it did.
    """  # نهاية النص متعدد الأسطر
    if os.path.isdir(path) and not os.path.islink(path):  # شرط مركّب (و)
        size, _ = _dir_size(path)  # إسناد نتيجة استدعاء _dir_size (معامل واحد) إلى مجموعة
        shutil.rmtree(path, ignore_errors=True)  # استدعاء shutil.rmtree (معامل واحد، ignore_errors=…)
        return size  # إرجاع size
    try:  # بدايةtry محمية (يليها except/finally)
        size = os.path.getsize(path)  # إسناد نتيجة استدعاء os.path.getsize (معامل واحد) إلى size
        os.remove(path)  # استدعاء os.remove (معامل واحد)
        return size  # إرجاع size
    except OSError:  # تكملة السطر السابق داخل القوس
        return 0  # إرجاع 0


# أنماط MAC / IPv4 المستخدمة عند تنقية HTML المراجعة قبل القرص.
_REVIEW_MAC_RE = re.compile(  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى _REVIEW_MAC_RE
    r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b")  # تكملة السطر السابق داخل القوس
_REVIEW_IP_RE = re.compile(  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى _REVIEW_IP_RE
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}"  # تكملة السطر السابق داخل القوس
    r"(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b")  # تكملة السطر السابق داخل القوس


# يحذف MAC وIPv4 من صفحات المراجعة قبل كتابتها على القرص.
def redact_review_body(body: str) -> str:  # تعريف الدالة redact_review_body(body) ترجع str
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Strip client MAC/IP addresses from review pages before saving.

    Review HTML can echo the guest device identity; keep the page shape for
    the operator without storing those identifiers on disk.
    """  # نهاية النص متعدد الأسطر
    text = body or ""  # دمج منطقي (أو) وإسناده إلى text
    text = _REVIEW_MAC_RE.sub("[mac-redacted]", text)  # إسناد نتيجة استدعاء _REVIEW_MAC_RE.sub (2 معاملات) إلى text
    text = _REVIEW_IP_RE.sub("[ip-redacted]", text)  # إسناد نتيجة استدعاء _REVIEW_IP_RE.sub (2 معاملات) إلى text
    return text  # إرجاع text


def human_size(num: int) -> str:  # تعريف الدالة human_size(num) ترجع str
    value = float(num)  # إسناد نتيجة استدعاء float (معامل واحد) إلى value
    for unit in ("B", "KB", "MB", "GB"):  # دورة على مجموعة باسم unit
        if value < 1024 or unit == "GB":  # شرط مركّب (أو)
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"  # إرجاع نص منسّق (f-string) إن مقارنة وإلا نص منسّق (f-string)
        value /= 1024.0  # تحديث value بعملية قسمة
    return f"{value:.1f} GB"  # إرجاع نص منسّق (f-string)


def load_legacy_profiles() -> list:  # تعريف الدالة load_legacy_profiles() ترجع list
    """Import profiles written by the old version, if any exist."""  # نص توثيقي (docstring) يشرح ما يليه
    out = []  # إسناد قائمة إلى out
    for path in (config.LEGACY_FILES[1], config.LEGACY_FILES[2]):  # دورة على مجموعة باسم path
        raw = read_json(path, None)  # إسناد نتيجة استدعاء read_json (2 معاملات) إلى raw
        if not raw:  # شرط معكوس: ليس raw
            continue  # الانتقال إلى الدورة التالية
        items = raw if isinstance(raw, list) else raw.get("profiles", [raw])  # إسناد raw إن isinstance(raw, list) وإلا raw.get('profiles', قائمة) إلى items
        for item in items or []:  # دورة على items أو قائمة باسم item
            try:  # بدايةtry محمية (يليها except/finally)
                out.append(migrate(item))  # استدعاء out.append (معامل واحد)
            except Exception:  # تكملة السطر السابق داخل القوس
                continue  # الانتقال إلى الدورة التالية
    return out  # إرجاع out
