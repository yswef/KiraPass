# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Paths, defaults and constants for KiraPass.

Everything the tool writes on disk lives in one of the folders below, so the
"clear cache" button can clean the whole tool in one shot and nothing is
scattered around the project.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import os  # استيراد الوحدة os من المكتبة

APP_NAME = "KiraPass"  # إسناد القيمة الثابتة APP_NAME
VERSION = "5.9.0"  # إسناد القيمة الثابتة VERSION

# --------------------------------------------------------------------------
# المجلدات
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # إسناد نتيجة استدعاء os.path.dirname (معامل واحد) إلى BASE_DIR

DATA_DIR = os.path.join(BASE_DIR, "kirapass_data")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى DATA_DIR
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى PROFILES_FILE
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى SETTINGS_FILE
HITS_FILE = os.path.join(DATA_DIR, "hits.txt")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى HITS_FILE
RUN_DIR = os.path.join(DATA_DIR, "runs")          # تقرير واحد لكل تشغيل
REVIEW_DIR = os.path.join(DATA_DIR, "review")     # صفحات لم نستطع الحكم عليها
CACHE_DIR = os.path.join(DATA_DIR, "cache")       # صفحات متعلَّمة / مؤقتة
LOG_DIR = os.path.join(DATA_DIR, "logs")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى LOG_DIR

ALL_DIRS = (DATA_DIR, RUN_DIR, REVIEW_DIR, CACHE_DIR, LOG_DIR)  # إسناد مجموعة إلى ALL_DIRS


def set_data_dir(path: str) -> str:  # تعريف الدالة set_data_dir(path) ترجع str
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Point every file the tool writes at another folder.

    The self-test uses this so `KiraPass.py --selftest` can never mix its
    practice cards into the user's real profiles, hits or reports.
    """  # نهاية النص متعدد الأسطر
    global DATA_DIR, PROFILES_FILE, SETTINGS_FILE, HITS_FILE  # إعلان أن DATA_DIR, PROFILES_FILE, SETTINGS_FILE, HITS_FILE متغير عام (لا محلي)
    global RUN_DIR, REVIEW_DIR, CACHE_DIR, LOG_DIR, ALL_DIRS  # إعلان أن RUN_DIR, REVIEW_DIR, CACHE_DIR, LOG_DIR, ALL_DIRS متغير عام (لا محلي)
    DATA_DIR = os.path.abspath(path)  # إسناد نتيجة استدعاء os.path.abspath (معامل واحد) إلى DATA_DIR
    PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى PROFILES_FILE
    SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى SETTINGS_FILE
    HITS_FILE = os.path.join(DATA_DIR, "hits.txt")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى HITS_FILE
    RUN_DIR = os.path.join(DATA_DIR, "runs")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى RUN_DIR
    REVIEW_DIR = os.path.join(DATA_DIR, "review")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى REVIEW_DIR
    CACHE_DIR = os.path.join(DATA_DIR, "cache")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى CACHE_DIR
    LOG_DIR = os.path.join(DATA_DIR, "logs")  # إسناد نتيجة استدعاء os.path.join (2 معاملات) إلى LOG_DIR
    ALL_DIRS = (DATA_DIR, RUN_DIR, REVIEW_DIR, CACHE_DIR, LOG_DIR)  # إسناد مجموعة إلى ALL_DIRS
    os.makedirs(DATA_DIR, exist_ok=True)  # استدعاء os.makedirs (معامل واحد، exist_ok=…)
    return DATA_DIR  # إرجاع DATA_DIR

# ملفات النسخة القديمة — يحذفها «مسح البيانات».
LEGACY_FILES = (  # إسناد مجموعة إلى LEGACY_FILES
    os.path.join(BASE_DIR, "kirapass_hits.txt"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    os.path.join(BASE_DIR, "mikrotikbf_profiles.json"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    os.path.join(BASE_DIR, "kirapass_profiles.json"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
)  # إغلاق القوس المفتوح في السطر السابق

# --------------------------------------------------------------------------
# افتراضيات الشبكة
# --------------------------------------------------------------------------
USER_AGENT = (  # إسناد القيمة الثابتة USER_AGENT
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "  # تكملة السطر السابق داخل القوس
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"  # تكملة السطر السابق داخل القوس
)  # إغلاق القوس المفتوح في السطر السابق

BASE_HEADERS = {  # إسناد قاموس إلى BASE_HEADERS
    "User-Agent": USER_AGENT,  # مفتاح User-Agent في القاموس
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",  # مفتاح Accept في القاموس
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",  # مفتاح Accept-Language في القاموس
    "Upgrade-Insecure-Requests": "1",  # مفتاح Upgrade-Insecure-Requests في القاموس
}  # إغلاق القوس المفتوح في السطر السابق

# يمكن رفع المهلات لراوترات RADIUS بطيئة جداً عبر متغيرات البيئة:
# KIRAPASS_CONNECT_TIMEOUT=8
# KIRAPASS_READ_TIMEOUT=15
def _env_float(name: str, default: float) -> float:  # تعريف الدالة _env_float(name, default) ترجع float
    raw = os.environ.get(name, "")  # إسناد نتيجة استدعاء os.environ.get (2 معاملات) إلى raw
    if not raw:  # شرط معكوس: ليس raw
        return default  # إرجاع default
    try:  # بدايةtry محمية (يليها except/finally)
        value = float(raw)  # إسناد نتيجة استدعاء float (معامل واحد) إلى value
    except ValueError:  # تكملة السطر السابق داخل القوس
        return default  # إرجاع default
    return max(0.5, min(value, 120.0))  # إرجاع max(0.5, min(value, 120.0))


CONNECT_TIMEOUT = _env_float("KIRAPASS_CONNECT_TIMEOUT", 4.0)  # إسناد نتيجة استدعاء _env_float (2 معاملات) إلى CONNECT_TIMEOUT
READ_TIMEOUT = _env_float("KIRAPASS_READ_TIMEOUT", 8.0)  # إسناد نتيجة استدعاء _env_float (2 معاملات) إلى READ_TIMEOUT
ATTACK_READ_TIMEOUT = _env_float("KIRAPASS_ATTACK_READ_TIMEOUT", 5.0)  # إسناد نتيجة استدعاء _env_float (2 معاملات) إلى ATTACK_READ_TIMEOUT
VERIFY_TLS = False         # بوابات الأسر تستخدم شهادات موقّعة ذاتياً

DEFAULT_THREADS = 12  # إسناد القيمة الثابتة DEFAULT_THREADS
MIN_THREADS = 1  # إسناد القيمة الثابتة MIN_THREADS
MAX_THREADS = 200  # إسناد القيمة الثابتة MAX_THREADS
DEFAULT_ATTEMPTS = 2000  # إسناد القيمة الثابتة DEFAULT_ATTEMPTS
MAX_ATTEMPTS = 20_000_000  # إسناد القيمة الثابتة MAX_ATTEMPTS
DEFAULT_DELAY_MS = 0  # إسناد القيمة الثابتة DEFAULT_DELAY_MS

# كم طلباً متتالياً يجوز أن يفشل (بلا رد HTTP إطلاقاً) قبل أن نتوقف
# ونقول للمستخدم إن الرابط انقطع بدل الادعاء بأن تلك البطاقات
# اختُبرت.
SLOW_DIAG_AFTER = 8.0  # ثوانٍ: فوق هذا يُحسب الراوتر بطيئاً
BURST_LIMIT = 20  # إسناد القيمة الثابتة BURST_LIMIT
# توقّف مبكراً بعد إخفاقات نقل متكررة. لا إعادة اتصال ولا انتظار
# ولا تغيير هوية بعد هذا التوقف؛ على المستخدم مراجعة مسؤول الشبكة.
CONSECUTIVE_TRANSPORT_FAILURE_LIMIT = 3  # إسناد القيمة الثابتة CONSECUTIVE_TRANSPORT_FAILURE_LIMIT
SILENCE_SECONDS = 6.0  # إسناد القيمة الثابتة SILENCE_SECONDS

# --------------------------------------------------------------------------
# فحوص «هل الضيف متصل فعلاً؟»
# --------------------------------------------------------------------------
# بوابة الأسر تردّ على هذه بتحويل إلى صفحة الدخول.
# وعندما تعمل البطاقة نحصل على الرد المتوقع بدلاً من ذلك.
#
# بعض الشبكات تحجب مواقع الفحص الثلاثة عمداً. عندها ضع
# روابط فحصك في متغير بيئة، والمداخل مفصولة بفواصل:
#
# KIRAPASS_INTERNET_CHECKS="http://example.com/generate_204|204"
# KIRAPASS_INTERNET_CHECKS="http://a.test/ok|200|OK,http://b.test/204|204"
#
# الصيغة:  الرابط|الحالة المتوقعة|النص المتوقع (اختياري)
def _parse_internet_checks(raw: str) -> tuple:  # تعريف الدالة _parse_internet_checks(raw) ترجع tuple
    out = []  # إسناد قائمة إلى out
    for item in (raw or "").split(","):  # دورة على raw أو ''.split(',') باسم item
        item = item.strip()  # إسناد نتيجة استدعاء item.strip إلى item
        if not item:  # شرط معكوس: ليس item
            continue  # الانتقال إلى الدورة التالية
        bits = item.split("|")  # إسناد نتيجة استدعاء item.split (معامل واحد) إلى bits
        url = bits[0].strip()  # إسناد نتيجة استدعاء bits[0].strip إلى url
        if not url:  # شرط معكوس: ليس url
            continue  # الانتقال إلى الدورة التالية
        try:  # بدايةtry محمية (يليها except/finally)
            status = int(bits[1]) if len(bits) > 1 and bits[1].strip() else 204  # إسناد int(bits[1]) إن مقارنة و bits[1].strip() وإلا 204 إلى status
        except ValueError:  # تكملة السطر السابق داخل القوس
            status = 204  # إسناد القيمة الثابتة status
        text = bits[2].strip() if len(bits) > 2 and bits[2].strip() else None  # إسناد bits[2].strip() إن مقارنة و bits[2].strip() وإلا None إلى text
        out.append((url, status, text, "custom"))  # استدعاء out.append (معامل واحد)
    return tuple(out)  # إرجاع tuple(out)


INTERNET_CHECKS = _parse_internet_checks(  # دمج منطقي (أو) وإسناده إلى INTERNET_CHECKS
    os.environ.get("KIRAPASS_INTERNET_CHECKS", "")) or (  # تكملة السطر السابق داخل القوس
    # (الرابط، الحالة المتوقعة، النص المتوقع أو None، التسمية)
    ("http://connectivitycheck.gstatic.com/generate_204", 204, None, "google204"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    ("http://www.msftconnecttest.com/connecttest.txt", 200, "Microsoft Connect Test", "msft"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    ("http://captive.apple.com/hotspot-detect.html", 200, "Success", "apple"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
)  # إغلاق القوس المفتوح في السطر السابق

# مضيفات إضافية تعني «البوابة أخرجتنا» عندما تظهر في Location.
EXIT_HOST_MARKERS = (  # إسناد مجموعة إلى EXIT_HOST_MARKERS
    "msftconnecttest", "gstatic", "captive.apple", "generate_204",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "connectivitycheck", "detectportal", "google.com", "icloud",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
)  # إغلاق القوس المفتوح في السطر السابق

# صفحة ردّ تحمل هذه الكلمات تعني شبه دائماً «بطاقة خاطئة».
REJECT_WORDS = (  # إسناد مجموعة إلى REJECT_WORDS
    "invalid username or password", "invalid password", "wrong password",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "invalid user", "unknown user", "user not found", "authentication failed",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "login failed", "failed to log in", "access denied", "not authorized",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "incorrect", "try again", "error", "denied", "expired", "already used",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "no valid profile", "voucher not found", "code not found", "صلاحية",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "غير صحيح", "خطأ", "منتهي",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
)  # إغلاق القوس المفتوح في السطر السابق

# صفحات/ردود تحمل هذه الكلمات تعني «الراوتر بدأ يحجبنا».
# أبقِ العبارات العربية/الفرنسية قصيرة حتى تعمل مطابقة الكلمة الكاملة،
# ولا تعتمد على كشف الحجب وحده ما دام نموذج الدخول ظاهراً (انظر
# engine._is_protective_reply) حتى لا يصير نص الرفض العادي حجباً كاذباً.
BAN_WORDS = (  # إسناد مجموعة إلى BAN_WORDS
    "you are blocked", "your ip is blocked", "ip has been blocked",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "address is blocked", "access blocked", "<title>blocked", "blocked.html",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "too many attempts", "too many login attempts", "too many failed",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "banned", "temporarily blocked", "rate limit", "slow down",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "device is blocked", "client is blocked", "mac is blocked",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "mac address blocked", "session blocked", "login attempts exceeded",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "maximum login attempts", "try again later", "access temporarily denied",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    # صفحات حجب بوابات الأسر بالعربية
    "محظور", "تم حظر", "تم حظرك", "الحظر", "محجوب", "تم حجبك",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "جهازك محظور", "تم حظر الجهاز", "تم حظر عنوان", "محظور مؤقتا",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "تجاوزت عدد المحاولات", "محاولات كثيرة", "حاول لاحقا",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    # صفحات حجب بوابات الأسر بالفرنسية
    "vous êtes bloqué", "vous etes bloque", "accès bloqué", "acces bloque",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "ip bloquée", "ip bloquee", "temporairement bloqué", "temporairement bloque",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "trop de tentatives", "tentatives de connexion",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
)  # إغلاق القوس المفتوح في السطر السابق

# كلمات إيجابية: البطاقة مقبولة
ACCEPT_WORDS = (  # إسناد مجموعة إلى ACCEPT_WORDS
    "you are logged in", "logged in successfully", "login successful",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "welcome", "status", "remaining time", "time left", "uptime",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "logout", "log out", "disconnect", "session started", "تم الدخول",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "مرحبا", "المتبقي",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
)  # إغلاق القوس المفتوح في السطر السابق

# كم بطاقة خاطئة نرسلها لنتعلّم صفحة الرفض. كل واحدة منها
# فشل دخول عند الراوتر، لذلك نُبقّيها صغيرة: راوتر يُقفل بعد
# فشلين سيقفل بسبب تعلّمنا نفسه.
CALIBRATION_PROBES = 3  # إسناد القيمة الثابتة CALIBRATION_PROBES
# البطاقة المعروفة الصالحة تُستخدم فقط لفحص شكل طلب صغير ومحدود.
# وإن لم تُثبت، توقّف واطلب من المسؤول مراجعة البوابة
# بدل التنقل بين عشرات محاولات الدخول والمخاطرة بقفل.
KNOWN_CARD_TRIAL_LIMIT = 8  # إسناد القيمة الثابتة KNOWN_CARD_TRIAL_LIMIT
# اترك الراوتر يطبّق دخول البطاقة المعروفة قبل فحص الوصول الخارجي.
KNOWN_CARD_VERIFY_DELAY_SECONDS = 1.0  # إسناد القيمة الثابتة KNOWN_CARD_VERIFY_DELAY_SECONDS
# تشخيص الحجب الاختياري محدود ويتوقف عند أول رد حجب.
LOCKOUT_PROBE_MAX_FAILURES = 8  # إسناد القيمة الثابتة LOCKOUT_PROBE_MAX_FAILURES
# تشخيص الشبكة يستخدم عيّنات صغيرة ويتوقف عند أول رد حجب.
DIAGNOSTIC_SAMPLE_LIMIT = 8  # إسناد القيمة الثابتة DIAGNOSTIC_SAMPLE_LIMIT

# دع التشغيل يجد وتيرته: ادفع حتى يشتكي الراوتر ثم
# تراجع (زيادة جمعية / نقصان مضاعف). AUTO_PACE=0 يُبقي
# الأداة بالضبط على الوتيرة التي كتبها المستخدم.
AUTO_PACE = os.environ.get("KIRAPASS_AUTO_PACE", "1") not in ("0", "no", "off")  # مقارنة (ليس ضمن) وإسناد النتيجة المنطقية إلى AUTO_PACE
PACE_WINDOW_SECONDS = 3.0     # انظر ما الذي رجع كل 3 ثوانٍ
PACE_BAD_RATIO = 0.02         # فوق 2% أخطاء/تقييد: هذا الراوتر اكتفى
PACE_MAX_DELAY_MS = 4000      # لا أبطأ من هذا من تلقاء نفسها
PACE_MAX_THREADS = 32         # سقف صارم لعدد الأيدي التي تضيفها بنفسها

# اطلب صفحة الدخول مجدداً كل هذا العدد من المحاولات لكل عامل، حتى
# يبقى كوكي الجلسة والحقول المخفية طازجة كما يُبقيها
# المتصفح. 0 = اطلب مرة واحدة ولا تعد.
WARMUP_EVERY = max(0, int(os.environ.get("KIRAPASS_WARMUP_EVERY", "25")))  # إسناد نتيجة استدعاء max (2 معاملات) إلى WARMUP_EVERY

# كم مرة يُسأل مجدداً عن بطاقة لم نحصل لها على إجابة إطلاقاً. الطلب قد
# يموت في الطريق (الراوتر يغلق المقبس، أو يصل الرد بعد
# مهلتنا) بينما الراوتر أخذه فعلاً — كهذه البطاقة ليست «مُختبَرة»، و
# تشغيل يجب ألا ينتهي بتخطّي البطاقة الوحيدة التي تعمل. فقط الطلبات
# بلا إجابة إطلاقاً تُعاد؛ وردّ REJECTED هو إجابة.
MAX_CARD_RETRIES = 2  # إسناد القيمة الثابتة MAX_CARD_RETRIES

# بعض الراوترات تُدخل الضيف وما تزال تردّ بصفحة الرفض. عندها
# الإشارة الوحيدة الصادقة هي الإنترنت نفسه: أثناء التشغيل نسأل
# «هل ما زلنا خلف الجدار؟» كل بضع ثوانٍ. وعندما ينقلب الجواب إلى
# «متصل»، فإحدى البطاقات التي أرسلناها لتوّنا فعلتها — تلك البطاقات هي
# المشتبه بها التي نسلّمها للمستخدم بدل أن نضيّعها.
WATCH_INTERNET = True  # إسناد القيمة الثابتة WATCH_INTERNET
WATCH_EVERY_SECONDS = 3.0  # إسناد القيمة الثابتة WATCH_EVERY_SECONDS
WATCH_SUSPECTS = 40  # إسناد القيمة الثابتة WATCH_SUSPECTS

# مضيفات نعتبرها «داخل البوابة» (فالتحويل إليها ليس خروجاً).
PORTAL_HINT_WORDS = ("login", "hotspot", "portal", "welcome", "splash", "auth")  # إسناد مجموعة إلى PORTAL_HINT_WORDS

# تحويل يحمل واحدة من هذه في رابطه ما زال البوابة — ليس
# دليلاً أن الضيف خرج (بعض الراوترات تقفز بك بين صفحاتها
# هي: /login ← /status ← /login، وكل قفزة كانت تبدو إصابة).
PORTAL_URL_WORDS = ("login", "hotspot", "portal", "splash", "auth", "captive")  # إسناد مجموعة إلى PORTAL_URL_WORDS

DEFAULT_PREFIX = ""  # إسناد القيمة الثابتة DEFAULT_PREFIX

# عتبات تُستخدم عندما تحتاج الأداة أن تتحدث عن حجم الفضاء.
BIG_SPACE = 10 ** 12  # حساب أسّ بين 10 و12 وإسناده إلى BIG_SPACE
# تحذيرات ليّنة في الواجهة (لا تمنع أبداً): الفضاءات الكبيرة وأعداد الخيوط
# الشرسة ترفع احتمال قفل الراوتر في الاختبارات المصرّح بها.
WARN_SPACE = 10 ** 9  # حساب أسّ بين 10 و9 وإسناده إلى WARN_SPACE
WARN_THREADS = 50  # إسناد القيمة الثابتة WARN_THREADS
# تنظيف اختياري تلقائي لتقارير التشغيل الأقدم من هذا العدد من الأيام.
# 0 يعطّله. يمكن تجاوزه بـKIRAPASS_REPORT_RETENTION_DAYS.
REPORT_RETENTION_DAYS = max(0, int(os.environ.get(  # إسناد نتيجة استدعاء max (2 معاملات) إلى REPORT_RETENTION_DAYS
    "KIRAPASS_REPORT_RETENTION_DAYS", "30") or "0"))  # تكملة السطر السابق داخل القوس
