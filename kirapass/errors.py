# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Turn any network exception into one clear, explainable answer.

The old version printed "Err: <python traceback>" or counted a card as
"tested" when nothing was actually tested. Here every failure gets:

    kind   -> a stable code the UI can colour and translate
    text   -> the raw message from the system (for experts)
    hint   -> a short plain-language explanation of what to check

`kind` values are deliberately few and meaningful.
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import errno  # استيراد الوحدة errno من المكتبة
import http.client  # استيراد الوحدة http.client من المكتبة
import socket  # استيراد الوحدة socket من المكتبة
import ssl  # استيراد الوحدة ssl من المكتبة

# النوع ← (قابل للإعادة، وصف عربي قصير، وصف إنجليزي قصير)
KINDS = {  # إسناد قاموس إلى KINDS
    "dns": (False, "اسم العنوان لم يُترجم (DNS)", "host name could not be resolved"),  # مفتاح dns في القاموس
    "refused": (False, "الراوتر رفض الاتصال (البورت مغلق أو الحماية رفضتك)",  # مفتاح refused في القاموس
                "connection refused by the router"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "connect_timeout": (True, "لا يوجد رد عند فتح الاتصال (الشبكة مقطوعة أو الراوتر مشغول)",  # مفتاح connect_timeout في القاموس
                        "timeout while opening the connection"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "read_timeout": (True, "الاتصال نجح لكن الراوتر تأخر في الرد (ضغط أو RADIUS بطيء)",  # مفتاح read_timeout في القاموس
                     "the router accepted the connection but never answered"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "reset": (True, "الراوتر قطع الاتصال فجأة (حماية أو عميل مطرود)",  # مفتاح reset في القاموس
              "the connection was reset in the middle"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "stale": (True, "اتصال قديم أُغلق من جهة الراوتر (يُعاد تلقائياً)",  # مفتاح stale في القاموس
              "keep-alive connection was closed by the router"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "tls": (False, "خطأ في شهادة TLS", "TLS/certificate error"),  # مفتاح tls في القاموس
    "unreachable": (False, "الشبكة غير قابلة للوصول (لست متصلاً بها)",  # مفتاح unreachable في القاموس
                    "network is unreachable"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "bad_response": (True, "رد غير مفهوم من الراوتر",  # مفتاح bad_response في القاموس
                     "the router sent an unreadable response"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "too_many_redirects": (False, "دوران لا نهائي في التحويل (redirect loop)",  # مفتاح too_many_redirects في القاموس
                           "too many redirects"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
    "proto": (False, "بروتوكول غير مدعوم", "unsupported protocol"),  # مفتاح proto في القاموس
    "unknown": (True, "خطأ غير متوقع", "unexpected network error"),  # مفتاح unknown في القاموس
    # البوابة لم تعطِنا صفحة دخولها، فالإرسال سيرفض
    # فقط: البطاقة لم تُختبر، ونقول ذلك بدل التخمين
    "no_session": (True, "لم نستطع أخذ صفحة الدخول (لا جلسة) - الكرت لم يُجرَّب",  # مفتاح no_session في القاموس
                   "could not fetch the login page (no session) - card not tested"),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
}  # إغلاق القوس المفتوح في السطر السابق

# أخطاء غالباً مجرد اتصال keep-alive ميت: تُعاد بصمت.
RETRY_KINDS = ("stale", "reset", "read_timeout", "bad_response", "unknown")  # إسناد مجموعة إلى RETRY_KINDS


# خطأ شبكة واحد: kind (كود ثابت) + text (رسالة النظام) + url.
# retryable وshort خاصيتان محسوبتان من جدول KINDS.
class NetError(Exception):  # تعريف الصنف NetError يرث من Exception
    """One network failure with a machine code and a human hint."""  # نص توثيقي (docstring) يشرح ما يليه

    def __init__(self, kind: str, text: str, url: str = ""):  # تعريف الدالة __init__(self, kind, text, url)
        super().__init__(text)  # استدعاء super().__init__ (معامل واحد)
        self.kind = kind  # إسناد kind إلى self.kind
        self.text = text  # إسناد text إلى self.text
        self.url = url  # إسناد url إلى self.url

    @property  # مُزخرف (decorator) بـproperty
    def retryable(self) -> bool:  # تعريف الدالة retryable(self) ترجع bool
        return KINDS.get(self.kind, KINDS["unknown"])[0]  # إرجاع KINDS.get(self.kind, KINDS['unknown'])[0]

    @property  # مُزخرف (decorator) بـproperty
    def short(self) -> str:  # تعريف الدالة short(self) ترجع str
        return KINDS.get(self.kind, KINDS["unknown"])[1]  # إرجاع KINDS.get(self.kind, KINDS['unknown'])[1]

    def as_dict(self) -> dict:  # تعريف الدالة as_dict(self) ترجع dict
        return {"kind": self.kind, "text": self.text[:300], "url": self.url}  # إرجاع قاموس


# يحوّل أي استثناء بايثون إلى NetError واحد له كود ونص وتلميح.
# ترتيب الفروع مقصود: الأنواع الدقيقة أولاً، ثم مطابقة النص.
# في بايثون ≥3.10 socket.timeout هو TimeoutError نفسه ويرتفع للمرحلتين،
# لذلك مرحلة فتح الاتصال ملفوفة في httpclient._send_once وحدها.
def classify(exc: BaseException, url: str = "") -> NetError:  # تعريف الدالة classify(exc, url) ترجع NetError
    """Map a python exception to a NetError."""  # نص توثيقي (docstring) يشرح ما يليه
    if isinstance(exc, NetError):  # شرط: نتيجة isinstance(exc, NetError)
        return exc  # إرجاع exc

    text = f"{type(exc).__name__}: {exc}"  # بناء نص منسّق وإسناده إلى text
    low = text.lower()  # إسناد نتيجة استدعاء text.lower إلى low

    if isinstance(exc, ssl.SSLError):  # شرط: نتيجة isinstance(exc, ssl.SSLError)
        kind = "tls"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, socket.gaierror):  # شرط: نتيجة isinstance(exc, socket.gaierror)
        kind = "dns"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, (http.client.RemoteDisconnected,)):  # شرط: نتيجة isinstance(exc, مجموعة)
        # اتصال keep-alive أغلقه الراوتر بين طلبين
        kind = "stale"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, (http.client.IncompleteRead,  # شرط: نتيجة isinstance(exc, مجموعة)
                          http.client.LineTooLong)):  # تكملة تعريف متعدد الأسطر
        kind = "bad_response"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, socket.timeout):  # شرط: نتيجة isinstance(exc, socket.timeout)
        # بايثون ≥ 3.10: socket.timeout هو TimeoutError نفسه، وhttp.client
        # يرفعه للمرحلتين. العميل يلفّ مرحلة الاتصال
        # بنفسه (انظر httpclient.Session._send_once)، لذلك أي شيء
        # يصل إلى هنا كان فعلاً قراءة لم تكتمل.
        kind = "read_timeout"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, ConnectionRefusedError):  # شرط: نتيجة isinstance(exc, ConnectionRefusedError)
        kind = "refused"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, (ConnectionResetError, BrokenPipeError)):  # شرط: نتيجة isinstance(exc, مجموعة)
        kind = "reset"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, ConnectionAbortedError):  # شرط: نتيجة isinstance(exc, ConnectionAbortedError)
        kind = "reset"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENETUNREACH:  # شرط مركّب (و)
        kind = "unreachable"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, http.client.HTTPException):  # شرط: نتيجة isinstance(exc, http.client.HTTPException)
        kind = "bad_response"  # إسناد القيمة الثابتة kind
    # شرط مركّب (أو)
    elif "remotedisconnected" in low or "remote end closed" in low \
            or "badstatusline" in low or "cannot read from timed out" in low:  # تكملة تعريف متعدد الأسطر
        kind = "stale"  # إسناد القيمة الثابتة kind
    elif "reset by peer" in low or "connection aborted" in low:  # شرط مركّب (أو)
        kind = "reset"  # إسناد القيمة الثابتة kind
    elif "refused" in low:  # شرط: 'refused' ضمن low
        kind = "refused"  # إسناد القيمة الثابتة kind
    elif "timed out" in low or "timeout" in low:  # شرط مركّب (أو)
        kind = "read_timeout"  # إسناد القيمة الثابتة kind
    # شرط مركّب (أو)
    elif "name or service not known" in low or "nodename nor servname" in low \
            or "getaddrinfo" in low or "name resolution" in low:  # تكملة تعريف متعدد الأسطر
        kind = "dns"  # إسناد القيمة الثابتة kind
    elif "no route to host" in low or "network is unreachable" in low:  # شرط مركّب (أو)
        kind = "unreachable"  # إسناد القيمة الثابتة kind
    elif "incompleteread" in low or "chunked" in low or "invalid http" in low:  # شرط مركّب (أو)
        kind = "bad_response"  # إسناد القيمة الثابتة kind
    elif isinstance(exc, ValueError):  # شرط: نتيجة isinstance(exc, ValueError)
        kind = "proto"  # إسناد القيمة الثابتة kind
    else:  # مفتاح else في القاموس
        kind = "unknown"  # إسناد القيمة الثابتة kind

    return NetError(kind, text, url)  # إرجاع NetError(kind, text, url)
