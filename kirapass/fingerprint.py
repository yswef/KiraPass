# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""Decide what a router's answer means - without guessing.

The old version had two ways to judge a reply:

    1. byte-compare after masking  -> failed as soon as the page carried a
       session token / echoed card / timestamp the mask did not know about
    2. "if the length differs from the failure page by more than 40 bytes,
       call it a DIFFERENT page and stop as a suspected match"

Rule 2 is why wrong cards were reported as hits (see kirapass_hits.txt in the
history: eight wrong cards, all "DIFFERENT page len=8575"), and why the tool
could not recognise a *real* success that redirected to the internet.

This module does it the way a network engineer would:

    * send two deliberately-wrong probes and learn WHICH parts of the page
      change on their own (tokens, mac echo, timestamps ...) -> mask them
    * a reply identical to that masked rejection page = REJECTED
    * a reply is only ACCEPTED on positive evidence (redirect out of the
      portal, learned success words, or a real internet check)
    * anything else = UNKNOWN, reported honestly instead of being called a hit
"""  # نهاية النص متعدد الأسطر

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import difflib  # استيراد الوحدة difflib من المكتبة
import hashlib  # استيراد الوحدة hashlib من المكتبة
import html  # استيراد الوحدة html من المكتبة
import re  # استيراد الوحدة re من المكتبة

from . import config  # استيراد config من الوحدة .

TOKEN_RE = re.compile(r"[A-Za-z0-9_@.\-]+|[^\sA-Za-z0-9_]")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى TOKEN_RE
SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى SCRIPT_RE
TAG_RE = re.compile(r"<[^>]+>")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى TAG_RE
WS_RE = re.compile(r"[ \t\r\n]+")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى WS_RE

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى UUID_RE
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")  # تكملة السطر السابق داخل القوس
LONGHEX_RE = re.compile(r"\b[0-9a-fA-F]{12,}\b")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى LONGHEX_RE
LONGNUM_RE = re.compile(r"\b\d{4,}\b")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى LONGNUM_RE
MAC_RE = re.compile(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى MAC_RE
# رموز تبدو جلسة/nonce: 6 محارف فأكثر من hex/alnum تخلط حروفاً وأرقاماً
# («faded» أو «0201242548» لا تُخفى، و«5f30507b» تُخفى).
TOKENLIKE_RE = re.compile(r"[0-9A-Za-z]{6,}")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى TOKENLIKE_RE
HEXLIKE_RE = re.compile(r"^[0-9a-fA-F]+$")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى HEXLIKE_RE
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")  # إسناد نتيجة استدعاء re.compile (معامل واحد) إلى IP_RE


# ---------------------------------------------------------------------------
# مساعدات نصية
# ---------------------------------------------------------------------------
def visible_text(body: str) -> str:  # تعريف الدالة visible_text(body) ترجع str
    """What the guest actually sees: no <script>/<style>, no tags."""  # نص توثيقي (docstring) يشرح ما يليه
    if not body:  # شرط معكوس: ليس body
        return ""  # إرجاع ''
    text = SCRIPT_RE.sub(" ", body)  # إسناد نتيجة استدعاء SCRIPT_RE.sub (2 معاملات) إلى text
    text = TAG_RE.sub(" ", text)  # إسناد نتيجة استدعاء TAG_RE.sub (2 معاملات) إلى text
    text = html.unescape(text)  # إسناد نتيجة استدعاء html.unescape (معامل واحد) إلى text
    return WS_RE.sub(" ", text).strip()  # إرجاع WS_RE.sub(' ', text).strip()


def tokens(text: str) -> list:  # تعريف الدالة tokens(text) ترجع list
    return TOKEN_RE.findall(text or "")  # إرجاع TOKEN_RE.findall(text أو '')


def _nonce_like(tok: str) -> bool:  # تعريف الدالة _nonce_like(tok) ترجع bool
    if len(tok) < 6:  # شرط: len(tok) أصغر من 6
        return False  # إرجاع False
    has_digit = any(c.isdigit() for c in tok)  # إسناد نتيجة استدعاء any (معامل واحد) إلى has_digit
    has_alpha = any(c.isalpha() for c in tok)  # إسناد نتيجة استدعاء any (معامل واحد) إلى has_alpha
    return has_digit and has_alpha  # إرجاع has_digit و has_alpha


# يستبدل القيم المتغيّرة والأنماط المتعلَّمة بـ# حتى تصير المقارنة عادلة.
def mask_text(text: str, literals=(), generic: bool = True, patterns=()) -> str:  # تعريف الدالة mask_text(text, literals, generic, patterns) ترجع str
    """Replace values that legitimately change between two identical requests."""  # نص توثيقي (docstring) يشرح ما يليه
    out = text or ""  # دمج منطقي (أو) وإسناده إلى out
    for lit in literals:  # دورة على literals باسم lit
        if lit and len(str(lit)) >= 3:  # شرط مركّب (و)
            out = out.replace(str(lit), "#")  # إسناد نتيجة استدعاء out.replace (2 معاملات) إلى out
    for pattern in patterns:  # دورة على patterns باسم pattern
        try:  # بدايةtry محمية (يليها except/finally)
            out = re.sub(pattern, "#", out)  # إسناد نتيجة استدعاء re.sub (3 معاملات) إلى out
        except re.error:  # تكملة السطر السابق داخل القوس
            continue  # الانتقال إلى الدورة التالية
    if generic:  # شرط: generic
        out = TOKENLIKE_RE.sub(lambda m: "#" if _nonce_like(m.group(0))  # إسناد نتيجة استدعاء TOKENLIKE_RE.sub (2 معاملات) إلى out
                               else m.group(0), out)  # تكملة السطر السابق داخل القوس
        out = UUID_RE.sub("#", out)  # إسناد نتيجة استدعاء UUID_RE.sub (2 معاملات) إلى out
        out = LONGHEX_RE.sub("#", out)  # إسناد نتيجة استدعاء LONGHEX_RE.sub (2 معاملات) إلى out
        out = MAC_RE.sub("#", out)  # إسناد نتيجة استدعاء MAC_RE.sub (2 معاملات) إلى out
        out = IP_RE.sub("#", out)  # إسناد نتيجة استدعاء IP_RE.sub (2 معاملات) إلى out
        out = LONGNUM_RE.sub("#", out)  # إسناد نتيجة استدعاء LONGNUM_RE.sub (2 معاملات) إلى out
    return out  # إرجاع out


# «شكل» الصفحة: تسلسل الرموز بعد تحويل كل رقم إلى # — للمقارنة التقريبية.
def struct_tokens(text: str, literals=(), generic: bool = True, patterns=()) -> list:  # تعريف الدالة struct_tokens(text, literals, generic, patterns) ترجع list
    """A shape-only view of the page, used when exact compare is impossible."""  # نص توثيقي (docstring) يشرح ما يليه
    masked = mask_text(text, literals, generic, patterns)  # إسناد نتيجة استدعاء mask_text (4 معاملات) إلى masked
    out = []  # إسناد قائمة إلى out
    for tok in tokens(masked):  # دورة على tokens(masked) باسم tok
        if tok.isdigit():  # شرط: نتيجة tok.isdigit()
            out.append("#")  # استدعاء out.append (معامل واحد)
        else:  # مفتاح else في القاموس
            out.append(tok.lower())  # استدعاء out.append (معامل واحد)
    return out  # إرجاع out


def ratio(a, b) -> float:  # تعريف الدالة ratio(a, b) ترجع float
    if not a and not b:  # شرط مركّب (و)
        return 1.0  # إرجاع 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()  # إرجاع difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def diff_words(page: str, reference: str, limit: int = 12) -> dict:  # تعريف الدالة diff_words(page, reference, limit) ترجع dict
    """Words that appear in `page` but not in `reference`, and vice-versa."""  # نص توثيقي (docstring) يشرح ما يليه
    def words(t):  # تعريف الدالة words(t)
        return set(re.findall(r"[A-Za-z\u0600-\u06FF]{3,}", visible_text(t).lower()))  # إرجاع set(re.findall('[A-Za-z\\u0600-\\u06FF]{3,}', visible_text(t).lower()))

    pw, rw = words(page), words(reference)  # إسناد مجموعة إلى مجموعة
    return {  # إرجاع قاموس
        "new_words": sorted(pw - rw, key=len, reverse=True)[:limit],  # مفتاح new_words في القاموس
        "missing_words": sorted(rw - pw, key=len, reverse=True)[:limit],  # مفتاح missing_words في القاموس
    }  # إغلاق القوس المفتوح في السطر السابق


def sha(text: str) -> str:  # تعريف الدالة sha(text) ترجع str
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]  # إرجاع hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()[]


# ---------------------------------------------------------------------------
# مطابقة العبارات
# ---------------------------------------------------------------------------
# عبارة من قوائم الكلمات يجب أن تطابق كلمة كاملة، لا أي جزء:
# «error» يجب ألا تشتعل على «no errors found in the terminal»، وإلا فكل
# صفحة حالة ستبدو رفضاً. العبارات المتعلَّمة القصيرة (التي كتبها
# المستخدم) ما تزال تُطابق بمرونة — فهي كلماته هو.
_PHRASE_CACHE = {}  # إسناد قاموس إلى _PHRASE_CACHE


def _phrase_re(phrase: str):  # تعريف الدالة _phrase_re(phrase)
    pat = _PHRASE_CACHE.get(phrase)  # إسناد نتيجة استدعاء _PHRASE_CACHE.get (معامل واحد) إلى pat
    if pat is None:  # شرط: pat هو نفسه None
        pat = re.compile(r"(?<![\w\-])" + re.escape(phrase) + r"(?![\w\-])",  # إسناد نتيجة استدعاء re.compile (2 معاملات) إلى pat
                         re.I)  # تكملة السطر السابق داخل القوس
        _PHRASE_CACHE[phrase] = pat  # إسناد pat إلى _PHRASE_CACHE[phrase]
    return pat  # إرجاع pat


def find_phrase(haystack: str, phrases) -> str:  # تعريف الدالة find_phrase(haystack, phrases) ترجع str
    """-> the first whole-word phrase found in `haystack`, else ''."""  # نص توثيقي (docstring) يشرح ما يليه
    for phrase in phrases or ():  # دورة على phrases أو مجموعة باسم phrase
        if not phrase:  # شرط معكوس: ليس phrase
            continue  # الانتقال إلى الدورة التالية
        if _phrase_re(phrase).search(haystack or ""):  # شرط: نتيجة _phrase_re(phrase).search(haystack أو '')
            return phrase  # إرجاع phrase
    return ""  # إرجاع ''


# ---------------------------------------------------------------------------
# تعلّم الأجزاء المتغيّرة في الصفحة
# ---------------------------------------------------------------------------
def differing_tokens(a: str, b: str, limit: int = 40) -> list:  # تعريف الدالة differing_tokens(a, b, limit) ترجع list
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Raw list of the values that change between two same-shape replies.

    Reported to the user ("this page changes by itself in N places"); the
    masking engine below is what actually neutralises them.
    """  # نهاية النص متعدد الأسطر
    if not a or not b:  # شرط مركّب (أو)
        return []  # إرجاع قائمة
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)  # إسناد نتيجة استدعاء difflib.SequenceMatcher (3 معاملات، autojunk=…) إلى sm
    out, seen = [], set()  # إسناد مجموعة إلى مجموعة
    for tag, i1, i2, j1, j2 in sm.get_opcodes():  # دورة على sm.get_opcodes() باسم مجموعة
        if tag == "equal":  # شرط: tag يساوي 'equal'
            continue  # الانتقال إلى الدورة التالية
        for piece in (a[i1:i2], b[j1:j2]):  # دورة على مجموعة باسم piece
            for tok in tokens(piece):  # دورة على tokens(piece) باسم tok
                if len(tok) >= 3 and tok not in seen:  # شرط مركّب (و)
                    seen.add(tok)  # استدعاء seen.add (معامل واحد)
                    out.append(tok)  # استدعاء out.append (معامل واحد)
                    if len(out) >= limit:  # شرط: len(out) أكبر أو يساوي limit
                        return out  # إرجاع out
    return out  # إرجاع out


# يحوّل القيم المتغيّرة إلى أنماط عامة بدل حفظ كل قيمة على حدة.
def learn_patterns(samples, max_patterns: int = 6) -> list:  # تعريف الدالة learn_patterns(samples, max_patterns) ترجع list
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Turn "this span changes" into "a token like this changes".

    A session token of 8 hex characters is different on every reply, so
    remembering the value is useless.  Seeing that the value LOOKED like
    `[0-9a-fA-F]{8}` is what lets us ignore it forever.
    """  # نهاية النص متعدد الأسطر
    samples = [x for x in samples if x]  # بناء اشتقاق قائمة وإسناده إلى samples
    if len(samples) < 2:  # شرط: len(samples) أصغر من 2
        return []  # إرجاع قائمة
    out, seen = [], set()  # إسناد مجموعة إلى مجموعة
    base = samples[0]  # إسناد samples[0] إلى base
    for other in samples[1:]:  # دورة على samples[] باسم other
        sm = difflib.SequenceMatcher(None, base, other, autojunk=False)  # إسناد نتيجة استدعاء difflib.SequenceMatcher (3 معاملات، autojunk=…) إلى sm
        for tag, i1, i2, j1, j2 in sm.get_opcodes():  # دورة على sm.get_opcodes() باسم مجموعة
            if tag == "equal":  # شرط: tag يساوي 'equal'
                continue  # الانتقال إلى الدورة التالية
            for piece in (base[i1:i2], other[j1:j2]):  # دورة على مجموعة باسم piece
                for tok in tokens(piece):  # دورة على tokens(piece) باسم tok
                    if not _nonce_like(tok) or len(tok) > 64:  # شرط مركّب (أو)
                        continue  # الانتقال إلى الدورة التالية
                    if HEXLIKE_RE.match(tok):  # شرط: نتيجة HEXLIKE_RE.match(tok)
                        pattern = r"\b[0-9a-fA-F]{%d}\b" % len(tok)  # حساب باقي القسمة بين '\\b[0-9a-fA-F]{%d}\\b' وlen(tok) وإسناده إلى pattern
                    else:  # مفتاح else في القاموس
                        pattern = r"\b[0-9A-Za-z]{%d}\b" % len(tok)  # حساب باقي القسمة بين '\\b[0-9A-Za-z]{%d}\\b' وlen(tok) وإسناده إلى pattern
                    if pattern not in seen:  # شرط: pattern ليس ضمن seen
                        seen.add(pattern)  # استدعاء seen.add (معامل واحد)
                        out.append(pattern)  # استدعاء out.append (معامل واحد)
                        if len(out) >= max_patterns:  # شرط: len(out) أكبر أو يساوي max_patterns
                            return out  # إرجاع out
    return out  # إرجاع out


# يكتشف القيم التي تتغير وحدها بين ردّين متطابقين (رمز جلسة، وقت، صدى البطاقة).
def learn_dynamic(samples, rounds: int = 4) -> set:  # تعريف الدالة learn_dynamic(samples, rounds) ترجع set
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """Return the literal values that differ between two same-shape replies.

    Two wrong cards sent in a row normally produce the same page, except for
    the session token, the echoed card, timestamps... Those are exactly the
    values we must ignore, and we learn them instead of listing them by hand.
    """  # نهاية النص متعدد الأسطر
    literals = set()  # إسناد نتيجة استدعاء set إلى literals
    samples = [s for s in samples if s]  # بناء اشتقاق قائمة وإسناده إلى samples
    if len(samples) < 2:  # شرط: len(samples) أصغر من 2
        return literals  # إرجاع literals

    for _ in range(rounds):  # دورة على range(rounds) باسم _
        masked = [mask_text(s, literals) for s in samples]  # بناء اشتقاق قائمة وإسناده إلى masked
        if all(m == masked[0] for m in masked):  # شرط: نتيجة all(مولّد)
            break  # قطع الحلقة فوراً
        base = masked[0]  # إسناد masked[0] إلى base
        gained = False  # إسناد القيمة الثابتة gained
        for other in samples[1:]:  # دورة على samples[] باسم other
            sm = difflib.SequenceMatcher(None, base, other, autojunk=False)  # إسناد نتيجة استدعاء difflib.SequenceMatcher (3 معاملات، autojunk=…) إلى sm
            for tag, i1, i2, j1, j2 in sm.get_opcodes():  # دورة على sm.get_opcodes() باسم مجموعة
                if tag == "equal":  # شرط: tag يساوي 'equal'
                    continue  # الانتقال إلى الدورة التالية
                for piece in (base[i1:i2], other[j1:j2]):  # دورة على مجموعة باسم piece
                    for tok in tokens(piece):  # دورة على tokens(piece) باسم tok
                        # شرط مركّب (أو)
                        if len(tok) >= 3 and not tok.isdigit() or \
                                (tok.isdigit() and len(tok) >= 5):  # تكملة تعريف متعدد الأسطر
                            if tok not in literals:  # شرط: tok ليس ضمن literals
                                literals.add(tok)  # استدعاء literals.add (معامل واحد)
                                gained = True  # إسناد القيمة الثابتة gained
        if not gained:  # شرط معكوس: ليس gained
            break  # قطع الحلقة فوراً
    return literals  # إرجاع literals


# ---------------------------------------------------------------------------
# الأحكام
# ---------------------------------------------------------------------------
# حكم واحد: code + reason + confidence + data + evidence.
# is_hit: أي كود يبدأ بـACCEPTED. is_final: مؤكد أو ثقة ≥0.85.
class Verdict:  # تعريف الصنف Verdict
    """One answer about one reply."""  # نص توثيقي (docstring) يشرح ما يليه

    __slots__ = ("code", "confidence", "reason", "data", "evidence")  # إسناد مجموعة إلى __slots__

    def __init__(self, code, reason, confidence=0.0, data=None, evidence=None):  # تعريف الدالة __init__(self, code, reason, confidence, data, evidence)
        self.code = code  # إسناد code إلى self.code
        self.reason = reason  # إسناد reason إلى self.reason
        self.confidence = confidence  # إسناد confidence إلى self.confidence
        self.data = data or {}  # دمج منطقي (أو) وإسناده إلى self.data
        self.evidence = evidence or {}  # دمج منطقي (أو) وإسناده إلى self.evidence

    @property  # مُزخرف (decorator) بـproperty
    def is_hit(self) -> bool:  # تعريف الدالة is_hit(self) ترجع bool
        return self.code.startswith("ACCEPTED")  # إرجاع self.code.startswith('ACCEPTED')

    @property  # مُزخرف (decorator) بـproperty
    def is_final(self) -> bool:  # تعريف الدالة is_final(self) ترجع bool
        """High-confidence hits stop the run; UNKNOWN never does."""  # نص توثيقي (docstring) يشرح ما يليه
        return self.code == "ACCEPTED_VERIFIED" or (  # إرجاع مقارنة أو مقارنة و مقارنة
            self.code == "ACCEPTED" and self.confidence >= 0.85)  # تكملة السطر السابق داخل القوس

    def as_dict(self) -> dict:  # تعريف الدالة as_dict(self) ترجع dict
        return {"code": self.code, "reason": self.reason,  # إرجاع قاموس
                "confidence": round(self.confidence, 2),  # مفتاح confidence في القاموس
                "data": self.data, "evidence": self.evidence}  # مفتاح data في القاموس


class Fingerprinter:  # تعريف الصنف Fingerprinter
    """Knows what the *rejection* page looks like, and how to compare."""  # نص توثيقي (docstring) يشرح ما يليه

    def __init__(self):  # تعريف الدالة __init__(self)
        self.literals = set()  # إسناد نتيجة استدعاء set إلى self.literals
        self.patterns = []  # إسناد قائمة إلى self.patterns
        self.exact = False  # إسناد القيمة الثابتة self.exact
        self.reject_masked_sha = ""  # إسناد القيمة الثابتة self.reject_masked_sha
        self.reject_tokens = []  # إسناد قائمة إلى self.reject_tokens
        self.reject_status = 0  # إسناد القيمة الثابتة self.reject_status
        self.reject_len = 0  # إسناد القيمة الثابتة self.reject_len
        self.reject_text = ""  # إسناد القيمة الثابتة self.reject_text
        # إلى أين تُحوَّل بطاقة خاطئة (فارغ = ليس تحويلاً، أو أنه
        # يتغير وحده فلا يمكن مقارنته)
        self.reject_location_key = ()  # إسناد مجموعة إلى self.reject_location_key
        self.login_text = ""  # إسناد القيمة الثابتة self.login_text
        self.samples = 0  # إسناد القيمة الثابتة self.samples
        self.note = ""  # إسناد القيمة الثابتة self.note
        self.dynamic_count = 0      # قيم تتغير وحدها

    # -- التعلّم ---------------------------------------------------------
    @classmethod  # مُزخرف (decorator) بـclassmethod
    # يبني «شكل صفحة الرفض» من ردود بطاقات خاطئة جيدة الصيغة.
    # عيّنة فاشلة شبكياً تصل None فتُستبعد ولا تكسر التعلّم.
    def learn(cls, reject_replies, login_reply=None) -> "Fingerprinter":  # تعريف الدالة learn(cls, reject_replies, login_reply) ترجع 'Fingerprinter'
        """`reject_replies` = list of Replies to wrong-but-well-formed cards."""  # نص توثيقي (docstring) يشرح ما يليه
        fp = cls()  # إسناد نتيجة استدعاء cls إلى fp
        # عيّنة فشلت بخطأ شبكي تصل None — ليست
        # صفحة نستطيع التعلّم منها، ويجب ألا تُسقط التشغيل أيضاً
        replies = [r for r in (reject_replies or []) if r is not None]  # بناء اشتقاق قائمة وإسناده إلى replies
        bodies = [r.text for r in replies]  # بناء اشتقاق قائمة وإسناده إلى bodies
        if login_reply is not None:  # شرط: login_reply ليس نفسه None
            fp.login_text = login_reply.text[:40000]  # إسناد login_reply.text[] إلى fp.login_text
        if not bodies:  # شرط معكوس: ليس bodies
            fp.note = "no rejection baseline"  # إسناد القيمة الثابتة fp.note
            return fp  # إرجاع fp

        fp.samples = len(bodies)  # إسناد نتيجة استدعاء len (معامل واحد) إلى fp.samples
        fp.reject_status = replies[0].status  # إسناد replies[0].status إلى fp.reject_status
        fp.reject_len = len(bodies[0])  # إسناد نتيجة استدعاء len (معامل واحد) إلى fp.reject_len
        fp.reject_text = bodies[0][:40000]  # إسناد bodies[0][] إلى fp.reject_text
        # قابل للاستخدام فقط عندما كانت كل عيّنة تحويلاً إلى نفس المكان: إن
        # كان بعضها فقط، فخط الأساس مختلط ولا مقارنة
        # آمنة (إحدى العيّنات قد تكون البطاقة العاملة).
        if replies and all(r.is_redirect() for r in replies):  # شرط مركّب (و)
            locs = {_loc_key(r.location) for r in replies}  # بناء اشتقاق مجموعة وإسناده إلى locs
            fp.reject_location_key = locs.pop() if len(locs) == 1 else ()  # إسناد locs.pop() إن مقارنة وإلا مجموعة إلى fp.reject_location_key
        fp.literals = learn_dynamic(bodies)  # إسناد نتيجة استدعاء learn_dynamic (معامل واحد) إلى fp.literals
        fp.patterns = learn_patterns(bodies)  # إسناد نتيجة استدعاء learn_patterns (معامل واحد) إلى fp.patterns
        # إسناد len(differing_tokens(bodies[0], bodies[1])) إن مقارنة وإلا 0 إلى fp.dynamic_count
        fp.dynamic_count = len(differing_tokens(bodies[0], bodies[1])) \
            if len(bodies) > 1 else 0  # تكملة السطر السابق داخل القوس

        masked = [mask_text(b, fp.literals, patterns=fp.patterns)  # بناء اشتقاق قائمة وإسناده إلى masked
                  for b in bodies]  # تكملة السطر السابق داخل القوس
        fp.exact = all(m == masked[0] for m in masked)  # إسناد نتيجة استدعاء all (معامل واحد) إلى fp.exact
        if fp.exact:  # شرط: fp.exact
            fp.reject_masked_sha = sha(masked[0])  # إسناد نتيجة استدعاء sha (معامل واحد) إلى fp.reject_masked_sha
            fp.note = "exact comparison ready"  # إسناد القيمة الثابتة fp.note
        else:  # مفتاح else في القاموس
            fp.reject_tokens = struct_tokens(bodies[0], fp.literals,  # إسناد نتيجة استدعاء struct_tokens (2 معاملات، patterns=…) إلى fp.reject_tokens
                                             patterns=fp.patterns)  # المعامل المسمّى patterns
            fp.note = "page changes on its own - comparing by shape"  # إسناد القيمة الثابتة fp.note
        return fp  # إرجاع fp

    # -- المقارنة -------------------------------------------------------
    # المقارنة بثلاث درجات: exact (SHA بعد الإخفاء) ← shape ← similar.
    # الردّان الفارغان لا يعنيان تطابقاً: يُقارن مفتاح التحويل ثم الحالة.
    def same_as_reject(self, resp, extra_literals=()) -> tuple:  # تعريف الدالة same_as_reject(self, resp, extra_literals) ترجع tuple
        # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
        """-> (is_rejected, how, similarity)

        `extra_literals` are the values we just sent (card, password, dst):
        a portal that echoes them back must not look like a different page.
        """  # نهاية النص متعدد الأسطر
        body = resp.text or ""  # دمج منطقي (أو) وإسناده إلى body
        literals = tuple(self.literals) + tuple(extra_literals or ())  # حساب جمع بين tuple(self.literals) وtuple(extra_literals أو مجموعة) وإسناده إلى literals
        if not body and not self.reject_text:  # شرط مركّب (و)
            # كلا الردّين صفحتان فارغتان — وهذا وحده لا يعني شيئاً. الراوتر
            # الذي يحوّل عند بطاقة خاطئة يعيدنا إلى صفحة الدخول؛
            # والبطاقة التي تعمل تذهب إلى مكان آخر. تجاهل ذلك كان
            # يخفي كل إصابة حقيقية خلف «مثل صفحة الرفض».
            if self.reject_location_key and resp.is_redirect():  # شرط مركّب (و)
                same = _loc_key(resp.location) == self.reject_location_key  # مقارنة (يساوي) وإسناد النتيجة المنطقية إلى same
                return same, "redirect", 1.0 if same else 0.0  # إرجاع مجموعة
            if self.reject_status and resp.status != self.reject_status:  # شرط مركّب (و)
                return False, "empty_status_differs", 0.0  # إرجاع مجموعة
            return True, "empty", 1.0  # إرجاع مجموعة

        masked = mask_text(body, literals, patterns=self.patterns)  # إسناد نتيجة استدعاء mask_text (2 معاملات، patterns=…) إلى masked
        if self.exact:  # شرط: self.exact
            if sha(masked) == self.reject_masked_sha:  # شرط: sha(masked) يساوي self.reject_masked_sha
                return True, "exact", 1.0  # إرجاع مجموعة
        if self.reject_tokens:  # شرط: self.reject_tokens
            sim = ratio(struct_tokens(body, literals, patterns=self.patterns),  # إسناد نتيجة استدعاء ratio (2 معاملات) إلى sim
                        self.reject_tokens)  # تكملة السطر السابق داخل القوس
            if sim >= 0.995:  # شرط: sim أكبر أو يساوي 0.995
                return True, "shape", sim  # إرجاع مجموعة
            return False, "shape", sim  # إرجاع مجموعة

        # لا خط أساس دقيق: نرجع إلى الحالة + تشابه الشكل
        sim = ratio(struct_tokens(body, literals, patterns=self.patterns),  # إسناد نتيجة استدعاء ratio (2 معاملات) إلى sim
                    struct_tokens(self.reject_text, literals,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                  patterns=self.patterns))  # المعامل المسمّى patterns
        if resp.status == self.reject_status and sim >= 0.97:  # شرط مركّب (و)
            return True, "similar", sim  # إرجاع مجموعة
        return False, "similar", sim  # إرجاع مجموعة


class Judge:  # تعريف الصنف Judge
    """Turns one reply into one Verdict with a reason a human can read."""  # نص توثيقي (docstring) يشرح ما يليه

    def __init__(self, fingerprint: Fingerprinter, login_url: str,  # تعريف الدالة __init__(self, fingerprint, login_url, success_words, success_url_contains, exit_host_markers)
                 success_words=(), success_url_contains="",  # المعامل المسمّى success_words
                 exit_host_markers=config.EXIT_HOST_MARKERS):  # المعامل المسمّى exit_host_markers
        self.fp = fingerprint  # إسناد fingerprint إلى self.fp
        self.login_url = login_url  # إسناد login_url إلى self.login_url
        self.success_words = [w.lower() for w in (success_words or []) if w]  # بناء اشتقاق قائمة وإسناده إلى self.success_words
        self.success_url_contains = (success_url_contains or "").lower()  # إسناد نتيجة استدعاء success_url_contains أو ''.lower إلى self.success_url_contains
        self.exit_markers = tuple(exit_host_markers)  # إسناد نتيجة استدعاء tuple (معامل واحد) إلى self.exit_markers
        self.portal_host = _host(login_url)  # إسناد نتيجة استدعاء _host (معامل واحد) إلى self.portal_host

        from urllib.parse import urlsplit  # استيراد urlsplit من الوحدة urllib.parse
        self.portal_host = urlsplit(login_url).hostname or ""  # دمج منطقي (أو) وإسناده إلى self.portal_host

        reject_text = (fingerprint.reject_text or "").lower()  # إسناد نتيجة استدعاء fingerprint.reject_text أو ''.lower إلى reject_text
        login_text = (fingerprint.login_text or "").lower()  # إسناد نتيجة استدعاء fingerprint.login_text أو ''.lower إلى login_text

        # الكلمات تُحسب فقط عندما لا تكون موجودة أصلاً في صفحة الرفض/الدخول
        # — وإلا فكل صفحة ستبدو فشلاً.
        self.reject_phrases = [w for w in config.REJECT_WORDS  # بناء اشتقاق قائمة وإسناده إلى self.reject_phrases
                               if w in reject_text or w not in login_text]  # تكملة السطر السابق داخل القوس
        self.accept_phrases = [w for w in config.ACCEPT_WORDS  # بناء اشتقاق قائمة وإسناده إلى self.accept_phrases
                               if w not in reject_text and w not in login_text]  # تكملة السطر السابق داخل القوس

    # -- مساعدات ---------------------------------------------------------
    @staticmethod  # مُزخرف (decorator) بـstaticmethod
    def _has_any(haystack: str, needles) -> str:  # تعريف الدالة _has_any(haystack, needles) ترجع str
        """Loose (substring) match - for words the user gave us himself."""  # نص توثيقي (docstring) يشرح ما يليه
        for n in needles:  # دورة على needles باسم n
            if n and n in haystack:  # شرط مركّب (و)
                return n  # إرجاع n
        return ""  # إرجاع ''

    @staticmethod  # مُزخرف (decorator) بـstaticmethod
    def _has_phrase(haystack: str, needles) -> str:  # تعريف الدالة _has_phrase(haystack, needles) ترجع str
        """Whole-word match - for the built-in reject/accept/ban phrases."""  # نص توثيقي (docstring) يشرح ما يليه
        return find_phrase(haystack, needles)  # إرجاع find_phrase(haystack, needles)

    # -- القرار ----------------------------------------------------
    # قلب الأداة: ردّ واحد ⇒ حكم واحد.
    # الترتيب هو القرار: (1) الحجب/الكابتشا (2) مطابقة صفحة الرفض
    # (3) الأدلة الإيجابية: تحويل خارج البوابة، كلمات نجاح، رابط نجاح
    # (4) UNKNOWN لكل ما لا يُثبت. لا يُسمّى شيء نجاحاً بلا دليل.
    def classify(self, resp, submitted=None) -> Verdict:  # تعريف الدالة classify(self, resp, submitted) ترجع Verdict
        body = resp.text or ""  # دمج منطقي (أو) وإسناده إلى body
        text = visible_text(body)  # إسناد نتيجة استدعاء visible_text (معامل واحد) إلى text
        low = text.lower()  # إسناد نتيجة استدعاء text.lower إلى low
        raw_low = body.lower()  # إسناد نتيجة استدعاء body.lower إلى raw_low
        loc = resp.location  # إسناد resp.location إلى loc
        sub = [str(s) for s in (submitted or []) if s]  # بناء اشتقاق قائمة وإسناده إلى sub

        # --- الراوتر يحجبنا (يُفحص أولاً: إن كان خط الأساس قد
        # تُعلّم ونحن محجوبون أصلاً، فقد تبدو صفحة الحجب
        # رفضاً عادياً) ----------------------------------
        # دمج منطقي (أو) وإسناده إلى ban
        ban = self._has_phrase(raw_low, config.BAN_WORDS) or \
            self._has_phrase(low, config.BAN_WORDS)  # تكملة السطر السابق داخل القوس
        if ban or resp.status in (403, 429, 503):  # شرط مركّب (أو)
            if resp.status == 429 or (ban and ("rate limit" in ban  # شرط مركّب (أو)
                                               or "slow down" in ban)):  # تكملة تعريف متعدد الأسطر
                return Verdict("RATE_LIMITED", "ban_page" if ban else "http_429",  # إرجاع Verdict('RATE_LIMITED', 'ban_page' إن ban وإلا 'http_429', 0.9, data=قاموس, evidence=resp.as_dict())
                               0.9, data={"word": ban, "status": resp.status},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                               evidence=resp.as_dict())  # المعامل المسمّى evidence
            if resp.status == 503 and not ban:  # شرط مركّب (و)
                # «service unavailable» راوتر/RADIUS يغرق —
                # وإخبار المستخدم أنه محجوب سيرسله ليعيد تشغيل
                # الراوتر بلا سبب. تُعامل كتقييد طلبات: أبطئ،
                # وتوقّف إن استمر.
                return Verdict("RATE_LIMITED", "http_503", 0.9,  # إرجاع Verdict('RATE_LIMITED', 'http_503', 0.9, data=قاموس, evidence=resp.as_dict())
                               data={"status": resp.status},  # المعامل المسمّى data
                               evidence=resp.as_dict())  # المعامل المسمّى evidence
            return Verdict("BANNED", "ban_page" if ban else f"http_{resp.status}",  # إرجاع Verdict('BANNED', 'ban_page' إن ban وإلا نص منسّق (f-string), 0.9, data=قاموس, evidence=resp.as_dict())
                           0.9, data={"word": ban, "status": resp.status},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                           evidence=resp.as_dict())  # المعامل المسمّى evidence

        rejected, how, sim = self.fp.same_as_reject(resp, extra_literals=sub)  # إسناد نتيجة استدعاء self.fp.same_as_reject (معامل واحد، extra_literals=…) إلى مجموعة
        if rejected and how != "redirect" and resp.is_redirect():  # شرط مركّب (و)
            # لا يمكن أن يكون الردّ «مثل صفحة الرفض» ويخرج بالمتصفح
            # من البوابة في الوقت نفسه: الراوتر يردّ بشيء آخر
            # على هذه البطاقة. تسمية ذلك رفضاً عادياً هي كيف تضيع
            # بطاقة عاملة، لذلك تذهب إلى المراجعة
            # — مع السبب والوجهة مكتوبين.
            host = _host(loc)  # إسناد نتيجة استدعاء _host (معامل واحد) إلى host
            if host and host != self.portal_host:  # شرط مركّب (و)
                return Verdict("UNKNOWN",  # إرجاع Verdict('UNKNOWN', 'redirect_out_of_portal_but_page_matches', 0.0, data=قاموس, evidence=resp.as_dict())
                               "redirect_out_of_portal_but_page_matches",  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                               0.0,  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                               data={"location": loc[:200], "how": how,  # المعامل المسمّى data
                                     "similarity": round(sim, 3)},  # مفتاح similarity في القاموس
                               evidence=resp.as_dict())  # المعامل المسمّى evidence
        if rejected:  # شرط: rejected
            seen_ok = [w for w in self.success_words if w in low or w in raw_low]  # بناء اشتقاق قائمة وإسناده إلى seen_ok
            if seen_ok and how != "exact":  # شرط مركّب (و)
                # الصفحة تطابق شكل الرفض، لكن كلمات تعلّمناها
                # من بطاقة عاملة موجودة ⇒ دَع إنساناً ينظر إليها
                return Verdict("UNKNOWN", "looks_rejected_but_success_words_found",  # إرجاع Verdict('UNKNOWN', 'looks_rejected_but_success_words_found', 0.0, data=قاموس, evidence=resp.as_dict())
                               0.0, data={"words": seen_ok[:6]},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                               evidence=resp.as_dict())  # المعامل المسمّى evidence
            return Verdict("REJECTED", f"same_as_rejection_page_{how}", 1.0,  # إرجاع Verdict('REJECTED', نص منسّق (f-string), 1.0, data=قاموس, evidence=resp.as_dict())
                           data={"similarity": round(sim, 3)},  # المعامل المسمّى data
                           evidence=resp.as_dict())  # المعامل المسمّى evidence

        # --- أُضيف كابتشا / تحد ---------------------------
        if any(w in raw_low for w in ("captcha", "g-recaptcha", "hcaptcha")):  # شرط: نتيجة any(مولّد)
            return Verdict("CHALLENGE", "captcha_present", 0.6,  # إرجاع Verdict('CHALLENGE', 'captcha_present', 0.6, evidence=resp.as_dict())
                           evidence=resp.as_dict())  # المعامل المسمّى evidence

        # --- دليل إيجابي: البوابة أخرجتنا ---------------------
        if resp.is_redirect():  # شرط: نتيجة resp.is_redirect()
            host = _host(loc)  # إسناد نتيجة استدعاء _host (معامل واحد) إلى host
            if host and host != self.portal_host:  # شرط مركّب (و)
                marker = self._has_any(loc.lower(), self.exit_markers)  # إسناد نتيجة استدعاء self._has_any (2 معاملات) إلى marker
                if not marker and self._has_any(loc.lower(),  # شرط مركّب (و)
                                                config.PORTAL_URL_WORDS):  # تكملة تعريف متعدد الأسطر
                    # صفحة أخرى من نفس البوابة — ليس خروجاً، وليس
                    # شيئاً يجوز أن نسميه بطاقة عاملة أيضاً
                    return Verdict("UNKNOWN", "redirect_to_another_portal_page",  # إرجاع Verdict('UNKNOWN', 'redirect_to_another_portal_page', 0.0, data=قاموس, evidence=resp.as_dict())
                                   0.0, data={"location": loc[:200]},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                   evidence=resp.as_dict())  # المعامل المسمّى evidence
                confident = 0.95 if marker else 0.85  # إسناد 0.95 إن marker وإلا 0.85 إلى confident
                return Verdict("ACCEPTED", "redirect_out_of_portal", confident,  # إرجاع Verdict('ACCEPTED', 'redirect_out_of_portal', confident, data=قاموس, evidence=resp.as_dict())
                               data={"location": loc[:200]},  # المعامل المسمّى data
                               evidence=resp.as_dict())  # المعامل المسمّى evidence
            # الراوتر يرسلنا إلى مكان غير الذي يرسل إليه بطاقة
            # خاطئة — هذا دليل حقيقي، حتى لو كانت الوجهة صفحة
            # حالته هو (لا يكفي وحده أبداً لإيقاف تشغيل)
            if self.fp.reject_location_key and resp.is_redirect():  # شرط مركّب (و)
                if _loc_key(loc) != self.fp.reject_location_key:  # شرط: _loc_key(loc) لا يساوي self.fp.reject_location_key
                    return Verdict("ACCEPTED", "redirect_differs_from_rejection",  # إرجاع Verdict('ACCEPTED', 'redirect_differs_from_rejection', 0.7, data=قاموس, evidence=resp.as_dict())
                                   0.7, data={"location": loc[:200]},  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                                   evidence=resp.as_dict())  # المعامل المسمّى evidence
            if self.success_url_contains and self.success_url_contains in loc.lower():  # شرط مركّب (و)
                return Verdict("ACCEPTED", "success_url_contains", 0.9,  # إرجاع Verdict('ACCEPTED', 'success_url_contains', 0.9, data=قاموس, evidence=resp.as_dict())
                               data={"location": loc[:200]},  # المعامل المسمّى data
                               evidence=resp.as_dict())  # المعامل المسمّى evidence

        # --- دليل إيجابي: كلمات نجاح متعلَّمة ---------------------
        seen = [w for w in self.success_words if w in low or w in raw_low]  # بناء اشتقاق قائمة وإسناده إلى seen
        if len(seen) >= 1 and not self._has_phrase(low, self.reject_phrases):  # شرط مركّب (و)
            return Verdict("ACCEPTED", "learned_success_words",  # إرجاع Verdict('ACCEPTED', 'learned_success_words', min(0.9, جمع), data=قاموس, evidence=resp.as_dict())
                           min(0.9, 0.6 + 0.1 * len(seen)),  # عنصر في القائمة/المعاملات (يتبعه المزيد)
                           data={"words": seen[:6]}, evidence=resp.as_dict())  # المعامل المسمّى data

        if self.success_url_contains and self.success_url_contains in resp.url.lower():  # شرط مركّب (و)
            return Verdict("ACCEPTED", "success_url_contains", 0.9,  # إرجاع Verdict('ACCEPTED', 'success_url_contains', 0.9, data=قاموس, evidence=resp.as_dict())
                           data={"url": resp.url[:200]}, evidence=resp.as_dict())  # المعامل المسمّى data

        # --- كلمات إيجابية خاصة بصفحة *جيدة* -----------
        accept_hit = self._has_phrase(low, self.accept_phrases)  # إسناد نتيجة استدعاء self._has_phrase (2 معاملات) إلى accept_hit
        reject_hit = self._has_phrase(low, self.reject_phrases)  # إسناد نتيجة استدعاء self._has_phrase (2 معاملات) إلى reject_hit
        if accept_hit and not reject_hit:  # شرط مركّب (و)
            return Verdict("ACCEPTED", "welcome_words", 0.7,  # إرجاع Verdict('ACCEPTED', 'welcome_words', 0.7, data=قاموس, evidence=resp.as_dict())
                           data={"word": accept_hit}, evidence=resp.as_dict())  # المعامل المسمّى data

        # --- ليست صفحة الرفض، وليست نجاحاً مثبتاً --------------
        diff = diff_words(body, self.fp.reject_text)  # إسناد نتيجة استدعاء diff_words (2 معاملات) إلى diff
        if reject_hit:  # شرط: reject_hit
            # صفحة رفض متغيّرة لا نستطيع مقارنتها بدقة
            return Verdict("REJECTED", "rejection_wording", 0.75,  # إرجاع Verdict('REJECTED', 'rejection_wording', 0.75, data=قاموس, evidence=resp.as_dict())
                           data={"word": reject_hit}, evidence=resp.as_dict())  # المعامل المسمّى data

        return Verdict("UNKNOWN", "reply_differs_not_proven", 0.0,  # إرجاع Verdict('UNKNOWN', 'reply_differs_not_proven', 0.0, data=قاموس, evidence=resp.as_dict())
                       data={"diff": diff, "similarity": round(sim, 3),  # المعامل المسمّى data
                             "status": resp.status, "length": resp.length},  # مفتاح status في القاموس
                       evidence=resp.as_dict())  # المعامل المسمّى evidence


def _loc_key(url: str) -> tuple:  # تعريف الدالة _loc_key(url) ترجع tuple
    # بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
    """The stable part of a redirect target: scheme + host + path.

    A router that answers "wrong card" with a redirect usually appends a
    changing token or the guest's own dst to the query string - comparing the
    whole URL would call every reply different.
    """  # نهاية النص متعدد الأسطر
    from urllib.parse import urlsplit  # استيراد urlsplit من الوحدة urllib.parse
    try:  # بدايةtry محمية (يليها except/finally)
        parts = urlsplit(url or "")  # إسناد نتيجة استدعاء urlsplit (معامل واحد) إلى parts
    except Exception:  # تكملة السطر السابق داخل القوس
        return ()  # إرجاع مجموعة
    if not parts.netloc and not parts.path:  # شرط مركّب (و)
        return ()  # إرجاع مجموعة
    return (parts.scheme, parts.netloc.lower(), parts.path or "/")  # إرجاع مجموعة


def _host(url: str) -> str:  # تعريف الدالة _host(url) ترجع str
    from urllib.parse import urlsplit  # استيراد urlsplit من الوحدة urllib.parse
    try:  # بدايةtry محمية (يليها except/finally)
        return (urlsplit(url).hostname or "").lower()  # إرجاع urlsplit(url).hostname أو ''.lower()
    except Exception:  # تكملة السطر السابق داخل القوس
        return ""  # إرجاع ''
