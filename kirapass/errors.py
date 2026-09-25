"""Turn any network exception into one clear, explainable answer.

The old version printed "Err: <python traceback>" or counted a card as
"tested" when nothing was actually tested. Here every failure gets:

    kind   -> a stable code the UI can colour and translate
    text   -> the raw message from the system (for experts)
    hint   -> a short plain-language explanation of what to check

`kind` values are deliberately few and meaningful.
"""

from __future__ import annotations

import errno
import socket
import ssl

# kind -> (retryable, arabic_short, english_short)
KINDS = {
    "dns": (False, "اسم العنوان لم يُترجم (DNS)", "host name could not be resolved"),
    "refused": (False, "الراوتر رفض الاتصال (البورت مغلق أو الحماية رفضتك)",
                "connection refused by the router"),
    "connect_timeout": (True, "لا يوجد رد عند فتح الاتصال (الشبكة مقطوعة أو الراوتر مشغول)",
                        "timeout while opening the connection"),
    "read_timeout": (True, "الاتصال نجح لكن الراوتر تأخر في الرد (ضغط أو RADIUS بطيء)",
                     "the router accepted the connection but never answered"),
    "reset": (True, "الراوتر قطع الاتصال فجأة (حماية أو عميل مطرود)",
              "the connection was reset in the middle"),
    "stale": (True, "اتصال قديم أُغلق من جهة الراوتر (يُعاد تلقائياً)",
              "keep-alive connection was closed by the router"),
    "tls": (False, "خطأ في شهادة TLS", "TLS/certificate error"),
    "unreachable": (False, "الشبكة غير قابلة للوصول (لست متصلاً بها)",
                    "network is unreachable"),
    "bad_response": (True, "رد غير مفهوم من الراوتر",
                     "the router sent an unreadable response"),
    "too_many_redirects": (False, "دوران لا نهائي في التحويل (redirect loop)",
                           "too many redirects"),
    "proto": (False, "بروتوكول غير مدعوم", "unsupported protocol"),
    "unknown": (True, "خطأ غير متوقع", "unexpected network error"),
}

# Errors that are usually just a dead keep-alive connection: retry silently.
RETRY_KINDS = ("stale", "reset", "read_timeout", "bad_response", "unknown")


class NetError(Exception):
    """One network failure with a machine code and a human hint."""

    def __init__(self, kind: str, text: str, url: str = ""):
        super().__init__(text)
        self.kind = kind
        self.text = text
        self.url = url

    @property
    def retryable(self) -> bool:
        return KINDS.get(self.kind, KINDS["unknown"])[0]

    @property
    def short(self) -> str:
        return KINDS.get(self.kind, KINDS["unknown"])[1]

    def as_dict(self) -> dict:
        return {"kind": self.kind, "text": self.text[:300], "url": self.url}


def classify(exc: BaseException, url: str = "") -> NetError:
    """Map a python exception to a NetError."""
    if isinstance(exc, NetError):
        return exc

    text = f"{type(exc).__name__}: {exc}"
    low = text.lower()

    if isinstance(exc, ssl.SSLError):
        kind = "tls"
    elif isinstance(exc, socket.gaierror):
        kind = "dns"
    elif isinstance(exc, socket.timeout):
        kind = "read_timeout"
    elif isinstance(exc, ConnectionRefusedError):
        kind = "refused"
    elif isinstance(exc, (ConnectionResetError, BrokenPipeError)):
        kind = "reset"
    elif isinstance(exc, ConnectionAbortedError):
        kind = "reset"
    elif isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENETUNREACH:
        kind = "unreachable"
    elif "remotedisconnected" in low or "remote end closed" in low \
            or "badstatusline" in low or "cannot read from timed out" in low:
        kind = "stale"
    elif "reset by peer" in low or "connection aborted" in low:
        kind = "reset"
    elif "refused" in low:
        kind = "refused"
    elif "timed out" in low or "timeout" in low:
        kind = "read_timeout"
    elif "name or service not known" in low or "nodename nor servname" in low \
            or "getaddrinfo" in low or "name resolution" in low:
        kind = "dns"
    elif "no route to host" in low or "network is unreachable" in low:
        kind = "unreachable"
    elif "incompleteread" in low or "chunked" in low or "invalid http" in low:
        kind = "bad_response"
    elif isinstance(exc, ValueError):
        kind = "proto"
    else:
        kind = "unknown"

    return NetError(kind, text, url)
