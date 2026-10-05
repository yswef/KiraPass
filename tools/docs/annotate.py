#!/usr/bin/env python3
"""إضافة تعليق عربي بعد كل سطر من أسطر ملفات KiraPass الأساسية.

الاستخدام:
    python3 tools/docs/annotate.py                 # كل الملفات الأساسية
    python3 tools/docs/annotate.py kirapass/store.py
    python3 tools/docs/annotate.py --check         # لا يكتب، يطبع ما سيفعله
    python3 tools/docs/annotate.py --revert        # يحذف التعليقات التي أضافتها الأداة

القواعد التي تحترمها الأداة:
  * لا يُضاف تعليق داخل نص متعدد الأسطر (docstring أو قالب HTML/JS داخل بايثون):
    الأسطر داخل الثلاث علامات ليست كوداً، والتعليق فيها يفسد النص.
    بدلاً من ذلك يُضاف تعليق على سطر الفتح وسطر الإغلاق + سطر توضيحي فوقها.
  * لا يُضاف تعليق بعد سطر ينتهي بشرطة مائلة (\\) لأنها سطر مكمّل حرفياً.
  * لا يُلمس سطر فيه `# noqa` أو `# type:` (تُضاف الملاحظة فوقه بدل ذلك).
  * الأسطر الفارغة تُترك فارغة (فواصل بصرية مقصودة - انظر editing.html §4).
  * كل تعليق تضيفه الأداة يبدأ بـ `#` (أو `//` أو `/* */` أو `<!-- -->`)
    ويحتوي حرفاً عربياً واحداً على الأقل، وهذا ما يجعل --revert آمناً.
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AR = re.compile(r"[\u0600-\u06FF]")

# الملفات الأساسية التي يشملها التعليق (حسب طلب المستخدم: kirapass/ + KiraPass.py)
PY_FILES = [
    "KiraPass.py",
    "kirapass/__init__.py",
    "kirapass/__main__.py",
    "kirapass/version_helpers.py",
    "kirapass/cli.py",
    "kirapass/config.py",
    "kirapass/errors.py",
    "kirapass/verify.py",
    "kirapass/httpclient.py",
    "kirapass/portals.py",
    "kirapass/store.py",
    "kirapass/fingerprint.py",
    "kirapass/engine.py",
    "kirapass/capture.py",
    "kirapass/selftest.py",
    "kirapass/mockportal.py",
    "kirapass/web/server.py",
]
JS_FILES = ["kirapass/web/ui.js"]
CSS_FILES = ["kirapass/web/ui.css"]
HTML_FILES = ["kirapass/web/ui.html"]

# ============================================================================
# 1) تحليل الأسطر: أي سطر داخل نص متعدد الأسطر؟ وأي سطر فيه تعليق أصلاً؟
# ============================================================================
def scan_python(src: str) -> dict:
    """يُرجع خريطة عن كل سطر: هل هو داخل نص، هل فيه تعليق، هل ينتهي بشرطة مائلة."""
    lines = src.split("\n")
    info = {i: {"in_string": False, "has_comment": False, "noqa": False,
                "backslash": False, "string_open": False, "string_close": False}
            for i in range(1, len(lines) + 1)}
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        toks = []
    for tok in toks:
        if tok.type == tokenize.STRING:
            start, end = tok.start[0], tok.end[0]
            if end > start:                       # نص متعدد الأسطر
                for ln in range(start, end + 1):
                    if ln in info:
                        info[ln]["in_string"] = True
                info[start]["string_open"] = True
                info[end]["string_close"] = True
            else:
                # نص في سطر واحد: السطر نفسه ليس "داخل نص"
                pass
        elif tok.type == tokenize.COMMENT:
            ln = tok.start[0]
            if ln in info:
                info[ln]["has_comment"] = True
                if "noqa" in tok.string or tok.string.startswith("# type:"):
                    info[ln]["noqa"] = True
    for i, line in enumerate(lines, 1):
        if i in info and line.rstrip().endswith("\\"):
            info[i]["backslash"] = True
    return info


# ============================================================================
# 2) توليد التعليق التلقائي من شجرة AST
# ============================================================================
BIN = {ast.Add: "جمع", ast.Sub: "طرح", ast.Mult: "ضرب", ast.Div: "قسمة",
       ast.FloorDiv: "قسمة صحيحة", ast.Mod: "باقي القسمة", ast.Pow: "أسّ",
       ast.BitOr: "أو بتّي", ast.BitAnd: "و بتّي", ast.BitXor: "xor بتّي",
       ast.LShift: "إزاحة يسار", ast.RShift: "إزاحة يمين"}
CMP = {ast.Eq: "يساوي", ast.NotEq: "لا يساوي", ast.Lt: "أصغر من",
       ast.LtE: "أصغر أو يساوي", ast.Gt: "أكبر من", ast.GtE: "أكبر أو يساوي",
       ast.In: "ضمن", ast.NotIn: "ليس ضمن", ast.Is: "هو نفسه",
       ast.IsNot: "ليس نفسه"}


def _name(node) -> str:
    """اسم مقروء لأي عقدة (بلا أخطاء إن كانت مجهولة)."""
    try:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Call):
            inner = ", ".join(_name(a) for a in node.args[:3])
            inner += ", " if inner and node.keywords else ""
            inner += ", ".join((k.arg or "**") + "=" + _name(k.value)
                               for k in node.keywords[:3])
            if len(node.args) > 3 or len(node.keywords) > 3:
                inner += ", …"
            return f"{_name(node.func)}({inner})"
        if isinstance(node, ast.Subscript):
            return f"{_name(node.value)}[{_name(node.slice)[:24]}]"
        if isinstance(node, ast.IfExp):
            return f"{_name(node.body)} إن {_name(node.test)} وإلا {_name(node.orelse)}"
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.List):
            return "قائمة"
        if isinstance(node, ast.Tuple):
            return "مجموعة"
        if isinstance(node, ast.Dict):
            return "قاموس"
        if isinstance(node, ast.Set):
            return "مجموعة فريدة"
        if isinstance(node, ast.Lambda):
            return "دالة مجهولة"
        if isinstance(node, ast.JoinedStr):
            return "نص منسّق (f-string)"
        if isinstance(node, ast.BinOp):
            return BIN.get(type(node.op), "عملية")
        if isinstance(node, ast.BoolOp):
            joiner = " و " if isinstance(node.op, ast.And) else " أو "
            return joiner.join(_name(v) for v in node.values[:3])
        if isinstance(node, ast.UnaryOp):
            return "نفي/سالب"
        if isinstance(node, ast.Compare):
            return "مقارنة"
        if isinstance(node, ast.Starred):
            return "تفكيك قائمة"
        if isinstance(node, ast.Await):
            return "انتظار"
        if isinstance(node, ast.GeneratorExp):
            return "مولّد"
        if isinstance(node, ast.ListComp):
            return "اشتقاق قائمة"
        if isinstance(node, ast.DictComp):
            return "اشتقاق قاموس"
        if isinstance(node, ast.SetComp):
            return "اشتقاق مجموعة"
    except RecursionError:
        return "…"
    return ""


def _args_sig(node) -> str:
    """توقيع المعاملات بشكل قصير: self, a, b=1, *args, **kw."""
    a = node.args
    out = [x.arg for x in a.posonlyargs] + [x.arg for x in a.args]
    if a.vararg:
        out.append("*" + a.vararg.arg)
    out += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        out.append("**" + a.kwarg.arg)
    return ", ".join(out)


def _call_desc(node: ast.Call) -> str:
    fn = _name(node.func)
    parts = []
    if len(node.args) == 1:
        parts.append("معامل واحد")
    elif node.args:
        parts.append("%d معاملات" % len(node.args))
    parts += [(kw.arg or "**") + "=…" for kw in node.keywords]
    tail = (" (" + "، ".join(parts) + ")") if parts else ""
    return f"استدعاء {fn}{tail}"


def auto_python(node, line: str) -> str:
    """تعليق عربي تلقائي لعقدة AST تبدأ في هذا السطر."""
    if isinstance(node, (ast.Import,)):
        names = ", ".join(a.name for a in node.names)
        return f"استيراد الوحدة {names} من المكتبة"
    if isinstance(node, ast.ImportFrom):
        names = ", ".join(a.name for a in node.names)
        mod = node.module or "."
        if names == "*":
            return f"استيراد كل أسماء الوحدة {mod}"
        return f"استيراد {names} من الوحدة {mod}"
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
        ret = f" ترجع {_name(node.returns)}" if node.returns else ""
        return f"تعريف الدالة {node.name}({_args_sig(node)}){ret}"
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(_name(b) for b in node.bases)
        tail = f" يرث من {bases}" if bases else ""
        return f"تعريف الصنف {node.name}{tail}"
    if isinstance(node, ast.Return):
        if node.value is None:
            return "إنهاء الدالة بلا قيمة (ترجع None ضمناً)"
        return f"إرجاع {_name(node.value)}"
    if isinstance(node, ast.Assign):
        tg = ", ".join(_name(t) for t in node.targets)
        val = node.value
        if isinstance(val, ast.Call):
            return f"إسناد نتيجة {_call_desc(val)} إلى {tg}"
        if isinstance(val, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            return f"بناء {_name(val)} وإسناده إلى {tg}"
        if isinstance(val, ast.DictComp):
            return f"بناء قاموس بالاشتقاق وإسناده إلى {tg}"
        if isinstance(val, ast.BinOp):
            op = BIN.get(type(val.op), "عملية")
            return f"حساب {op} بين {_name(val.left)} و{_name(val.right)} وإسناده إلى {tg}"
        if isinstance(val, ast.Compare):
            return f"مقارنة ({CMP.get(type(val.ops[0]), '؟')}) وإسناد النتيجة المنطقية إلى {tg}"
        if isinstance(val, ast.BoolOp):
            return f"دمج منطقي ({'و' if isinstance(val.op, ast.And) else 'أو'}) وإسناده إلى {tg}"
        if isinstance(val, ast.Constant):
            return f"إسناد القيمة الثابتة {tg}"
        if isinstance(val, ast.JoinedStr):
            return f"بناء نص منسّق وإسناده إلى {tg}"
        return f"إسناد {_name(val)} إلى {tg}"
    if isinstance(node, ast.AugAssign):
        op = BIN.get(type(node.op), "عملية")
        return f"تحديث {_name(node.target)} بعملية {op}"
    if isinstance(node, ast.AnnAssign):
        return f"إسناد مع تصريح نوع إلى {_name(node.target)}"
    if isinstance(node, ast.Expr):
        v = node.value
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            if v.end_lineno and v.end_lineno > v.lineno:
                return "بداية نص توثيقي (docstring) متعدد الأسطر"
            return "نص توثيقي (docstring) يشرح ما يليه"
        if isinstance(v, ast.Call):
            return _call_desc(v)
        if isinstance(v, ast.Await):
            return f"انتظار نتيجة {_name(v.value)}"
        return f"تقييم {_name(v)} (بلا إسناد)"
    if isinstance(node, ast.If):
        cond = node.test
        if isinstance(cond, ast.Compare):
            return f"شرط: {_name(cond.left)} {CMP.get(type(cond.ops[0]), '؟')} {_name(cond.comparators[0])}"
        if isinstance(cond, ast.UnaryOp) and isinstance(cond.op, ast.Not):
            return f"شرط معكوس: ليس {_name(cond.operand)}"
        if isinstance(cond, ast.BoolOp):
            return f"شرط مركّب ({'و' if isinstance(cond.op, ast.And) else 'أو'})"
        if isinstance(cond, ast.Call):
            return f"شرط: نتيجة {_name(cond)}"
        return f"شرط: {_name(cond)}"
    if isinstance(node, ast.For):
        return f"دورة على {_name(node.iter)} باسم {_name(node.target)}"
    if isinstance(node, ast.While):
        return f"حلقة ما دام {_name(node.test)}"
    if isinstance(node, ast.With):
        items = ", ".join(
            (_name(i.context_expr) + (f" باسم {_name(i.optional_vars)}"
                                      if i.optional_vars else ""))
            for i in node.items)
        return f"سياق مُدار: {items}"
    if isinstance(node, ast.Try):
        return "بدايةtry محمية (يليها except/finally)"
    if isinstance(node, ast.ExceptHandler):
        name = f" باسم {node.name}" if node.name else ""
        typ = _name(node.type) if node.type else "أي استثناء"
        return f"التقاط {typ}{name}"
    if isinstance(node, ast.Raise):
        if node.exc is None:
            return "إعادة رفع الاستثناء الحالي"
        return f"رفع {_name(node.exc)}"
    if isinstance(node, ast.Assert):
        return f"تأكيد (assert): {_name(node.test)}"
    if isinstance(node, ast.Delete):
        return "حذف " + ", ".join(_name(t) for t in node.targets)
    if isinstance(node, ast.Pass):
        return "سطر فارغ منطقياً (pass) — مطلوب صياغياً"
    if isinstance(node, ast.Break):
        return "قطع الحلقة فوراً"
    if isinstance(node, ast.Continue):
        return "الانتقال إلى الدورة التالية"
    if isinstance(node, ast.Global):
        return "إعلان أن " + ", ".join(node.names) + " متغير عام (لا محلي)"
    if isinstance(node, ast.Nonlocal):
        return "إعلان أن " + ", ".join(node.names) + " من النطاق المحيط"
    return ""


# ============================================================================
# 3) تعليقات الأسطر المكمّلة (داخل الأقواس) والأسطر الآلية البسيطة
# ============================================================================
CLOSE_ONLY = re.compile(r"^[\s\)\]\},;]+$")
KWARGS = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
DICT_KEY = re.compile(r"""^\s*(?:"([^"]{1,40})"|'([^']{1,40})'"""
                      r"""|([A-Za-z_][\w.\-]*))\s*:""")


def auto_continuation(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if CLOSE_ONLY.match(line) and any(c in line for c in ")]}"):
        return "إغلاق القوس المفتوح في السطر السابق"
    mkey = DICT_KEY.match(line)
    if mkey:
        key = mkey.group(1) or mkey.group(2) or mkey.group(3)
        return f"مفتاح {key} في القاموس"
    m = KWARGS.match(line)
    if m:
        return f"المعامل المسمّى {m.group(1)}"
    if stripped.startswith("@"):
        return f"مُزخرف (decorator) بـ{stripped[1:]}"
    if stripped.startswith("#"):
        return ""
    if stripped in (")", "]", "}", "),", "],", "},"):
        return "إغلاق القوس المفتوح في السطر السابق"
    if stripped.endswith(","):
        return "عنصر في القائمة/المعاملات (يتبعه المزيد)"
    if stripped.startswith(("\"", "'")) and stripped.endswith(("),", "]", "}")):
        return "تكملة قيمة المفتاح/العنصر السابق"
    if stripped.endswith(":") and not stripped.startswith(("if", "for", "while",
                                                          "with", "def", "class",
                                                          "elif", "else", "try",
                                                          "except", "finally")):
        return "تكملة تعريف متعدد الأسطر"
    if stripped.startswith(("elif ", "elif(")):
        return "شرط بديل (elif)"
    if stripped == "else:":
        return "فرع else: يُنفَّذ إن لم يتحقق الشرط السابق"
    if stripped == "finally:":
        return "فرع finally: يُنفَّذ دائماً بعد try"
    if stripped == "try:":
        return "بدايةtry محمية"
    return "تكملة السطر السابق داخل القوس"


def _collect_defs(node, prefix: str, out: dict) -> None:
    """يجمع أسطر بداية الدوال/الأصناف بمفتاح مؤهَّل: ClassName.method."""
    for child in getattr(node, "body", []) if isinstance(node, ast.ClassDef) else []:
        pass
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        key = f"{prefix}{node.name}"
        out[node.lineno] = (key, node)
        inner_prefix = key + "."
        for child in node.body:
            _collect_defs(child, inner_prefix, out)


# ============================================================================
# 4) تطبيق التعليقات على ملف بايثون
# ============================================================================
def annotate_python(path: str, notes: dict, func_notes: dict, dry: bool = False):
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    info = scan_python(src)
    tree = ast.parse(src)

    # عقدة البداية لكل سطر
    stmt_line = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            ln = node.lineno
            stmt_line.setdefault(ln, node)
    # أسطر البداية لدوال/أصناف (لتعليقات الدالة الكاملة) بمفتاح مؤهَّل
    def_line = {}
    for top in tree.body:
        _collect_defs(top, "", def_line)

    trailing = {}     # lineno -> نص يُضاف بعد السطر
    above = {}        # lineno -> [أسطر تعليق تُدرج فوقه]

    for ln in range(1, len(lines) + 1):
        raw = lines[ln - 1]
        if not raw.strip():
            continue                                   # الأسطر الفارغة فواصل مقصودة
        if ln == 1 and raw.startswith("#!"):
            continue                                   # سطر shebang لا يُلمس أبداً
        text = None
        if ln in def_line:
            key, node = def_line[ln]
            text = notes.get(ln) or auto_python(node, raw)
            if key in func_notes:
                above.setdefault(ln, []).extend(func_notes[key])
        elif ln in notes:
            text = notes[ln]
        elif ln in stmt_line:
            text = auto_python(stmt_line[ln], raw)
        if not text:
            text = auto_continuation(raw)
        if not text:
            continue

        meta = info.get(ln, {})
        if meta.get("in_string"):
            # داخل نص متعدد الأسطر: تعليق فوق السطر الافتتاحي وفوق سطر الإغلاق
            if meta.get("string_open"):
                above.setdefault(ln, []).append(
                    "بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً")
            elif meta.get("string_close"):
                trailing[ln] = "نهاية النص متعدد الأسطر"
            continue
        if meta.get("backslash") or meta.get("noqa"):
            above.setdefault(ln, []).append(text)
            continue
        if meta.get("has_comment"):
            continue                                   # لا نكتب فوق تعليق المؤلف
        trailing[ln] = text

    # بناء الملف الجديد (الإدراج من الأعلى، والترقيم يتغير لكننا نكتب مرة واحدة)
    out = []
    for ln in range(1, len(lines) + 1):
        raw = lines[ln - 1]
        for block in above.get(ln, []):
            indent = re.match(r"\s*", raw).group(0)
            out.append(f"{indent}# {block}")
        if ln in trailing and raw.strip():
            out.append(raw.rstrip() + "  # " + trailing[ln])
        else:
            out.append(raw)
    new = "\n".join(out)
    if new == src:
        return 0
    if not dry:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
    return sum(1 for v in trailing.values() if v) + sum(len(v) for v in above.values())


# ============================================================================
# 5) JavaScript: تعليق // بعد كل سطر (لا توجد نصوص متعددة الأسطر في ui.js)
# ============================================================================
def annotate_js(path: str, notes: dict, dry: bool = False):
    lines = open(path, encoding="utf-8").read().split("\n")
    out, count = [], 0
    in_block = False
    in_string = False
    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if in_block:
            out.append(raw)
            if "*/" in stripped:
                in_block = False
            continue
        if not stripped:
            out.append(raw)
            continue
        if stripped.startswith("/*"):
            out.append(raw)
            if "*/" not in stripped:
                in_block = True
            continue
        if stripped.startswith("//"):
            out.append(raw)
            continue
        text = notes.get(i) or js_auto(stripped)
        if text:
            out.append(raw.rstrip() + "  // " + text)
            count += 1
        else:
            out.append(raw)
        # تحديث حالة النص متعدد الأسطر (نادر جداً لكن نحمي أنفسنا)
        if stripped.count("'") % 2 or stripped.count('"') % 2:
            in_string = not in_string
    if not dry:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
    return count


JS_PATTERNS = [
    (re.compile(r'^"use strict";?$'), lambda m: "الوضع الصارم: يمنع أخطاء JS الصامتة في كل الملف"),
    (re.compile(r"^([A-Za-z_$][\w$]*)\s*:\s*(.+?),?$"),
     lambda m: f"مفتاح {m.group(1)} في الكائن = {_js_val(m.group(2))}"),
    (re.compile(r"^var\s+([A-Za-z_$][\w$]*)\s*=\s*(.+?);?$"),
     lambda m: f"تعريف المتغير {m.group(1)} وإسناد {_js_val(m.group(2))} إليه"),
    (re.compile(r"^let\s+([A-Za-z_$][\w$]*)\s*=\s*(.+?);?$"),
     lambda m: f"تعريف المتغير القابل للتغيير {m.group(1)} = {_js_val(m.group(2))}"),
    (re.compile(r"^const\s+([A-Za-z_$][\w$]*)\s*=\s*(.+?);?$"),
     lambda m: f"تعريف الثابت {m.group(1)} = {_js_val(m.group(2))}"),
    (re.compile(r"^function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)"),
     lambda m: f"تعريف الدالة {m.group(1)}({m.group(2)})"),
    (re.compile(r"^if\s*\((.+)\)\s*\{?$"), lambda m: f"شرط: {m.group(1)[:70]}"),
    (re.compile(r"^else\s+if\s*\((.+)\)\s*\{?$"), lambda m: f"شرط بديل: {m.group(1)[:70]}"),
    (re.compile(r"^}?\s*else\s*\{?$"), lambda m: "فرع else"),
    (re.compile(r"^for\s*\((.+)\)\s*\{?$"), lambda m: f"حلقة تكرار: {m.group(1)[:70]}"),
    (re.compile(r"^while\s*\((.+)\)\s*\{?$"), lambda m: f"حلقة ما دام: {m.group(1)[:70]}"),
    (re.compile(r"^try\s*\{?$"), lambda m: "بداية try محمية"),
    (re.compile(r"^}\s*catch\s*\((\w+)\)\s*\{?$"), lambda m: f"التقاط الخطأ في {m.group(1)}"),
    (re.compile(r"^}\s*finally\s*\{?$"), lambda m: "فرع finally: يُنفَّذ دائماً"),
    (re.compile(r"^return\b(.*)$"), lambda m: "إرجاع " + (m.group(1).strip()[:60] or "بلا قيمة")),
    (re.compile(r"^([\w$.]+)\s*=\s*(.+?);?$"),
     lambda m: f"إسناد {_js_val(m.group(2))} إلى {m.group(1)}"),
    (re.compile(r"^([\w$.]+)\((.*)\);?$"),
     lambda m: f"استدعاء الدالة {m.group(1)}({m.group(2)[:40]})"),
    (re.compile(r"^\}\s*[;,]?$"), lambda m: "إغلاق الكتلة السابقة"),
    (re.compile(r"^\{\s*$"), lambda m: "بداية كتلة"),
    (re.compile(r"^[}\])]+[,;]?\s*$"), lambda m: "إغلاق القوس المفتوح في السطر السابق"),
    (re.compile(r"^\"([^\"]+)\"\s*:\s*(.+?),?$"),
     lambda m: f"مدخل في القاموس: المفتاح {m.group(1)}"),
]


def _js_val(text: str) -> str:
    t = text.strip().rstrip(";").strip()
    if t.startswith("{"):
        return "كائن"
    if t.startswith("["):
        return "مصفوفة"
    if t.startswith(("'", '"')):
        return "نص"
    if t.startswith("function"):
        return "دالة"
    if re.match(r"^-?\d", t):
        return "رقم"
    if t in ("true", "false"):
        return "قيمة منطقية"
    if t == "null":
        return "null"
    if "(" in t and t.endswith(")"):
        return "نتيجة استدعاء"
    return "قيمة"


def js_auto(stripped: str) -> str:
    for pat, fn in JS_PATTERNS:
        m = pat.match(stripped)
        if m:
            try:
                return fn(m)
            except IndexError:
                continue
    if stripped.endswith(","):
        return "عنصر في القائمة/الكائن (يتبعه المزيد)"
    if stripped.endswith(";"):
        return "تنفيذ التعليمة السابقة"
    return "تكملة السطر السابق"


# ============================================================================
# 6) CSS: تعليق /* */ بعد كل سطر
# ============================================================================
CSS_PROP = {
    "color": "لون النص", "background": "الخلفية", "background-color": "لون الخلفية",
    "background-image": "صورة الخلفية", "border": "الحدود", "border-radius": "استدارة الزوايا",
    "padding": "الحشوة الداخلية", "margin": "الهامش الخارجي", "display": "طريقة العرض",
    "flex": "المرونة", "flex-direction": "اتجاه المحور", "gap": "المسافة بين العناصر",
    "grid-template-columns": "أعمدة الشبكة", "font-size": "حجم الخط",
    "font-family": "نوع الخط", "font-weight": "سماكة الخط", "line-height": "ارتفاع السطر",
    "text-align": "محاذاة النص", "width": "العرض", "height": "الارتفاع",
    "max-width": "أقصى عرض", "min-width": "أدنى عرض", "max-height": "أقصى ارتفاع",
    "min-height": "أدنى ارتفاع", "overflow": "التعامل مع الفائض",
    "overflow-y": "الفائض الرأسي", "overflow-x": "الفائض الأفقي",
    "position": "نوع التموضع", "top": "المسافة من الأعلى", "bottom": "المسافة من الأسفل",
    "left": "المسافة من اليسار", "right": "المسافة من اليمين", "z-index": "طبقة الترتيب",
    "box-shadow": "ظل الصندوق", "text-shadow": "ظل النص", "opacity": "الشفافية",
    "cursor": "شكل المؤشر", "transition": "الانتقال الحركي", "transform": "التحويل",
    "white-space": "التعامل مع المسافات", "word-break": "كسر الكلمة",
    "direction": "اتجاه النص", "list-style": "شكل القائمة", "outline": "الحد الخارجي",
    "box-sizing": "طريقة حساب الأبعاد", "user-select": "إمكانية التحديد",
    "scroll-behavior": "سلوك التمرير", "letter-spacing": "تباعد الحروف",
    "text-decoration": "زخرفة النص", "vertical-align": "المحاذاة الرأسية",
    "align-items": "محاذاة العناصر", "justify-content": "توزيع المحتوى",
    "flex-wrap": "التفاف العناصر", "order": "ترتيب العنصر",
    "border-collapse": "دمج حدود الجدول", "table-layout": "تخطيط الجدول",
    "content": "المحتوى المولَّد", "pointer-events": "استجابة الأحداث",
    "visibility": "الظهور", "filter": "المرشّح", "resize": "إمكانية تغيير الحجم",
    "font-variant-numeric": "شكل الأرقام", "text-overflow": "اقتطاع النص",
}


def css_auto(stripped: str) -> str:
    if stripped.startswith("@media"):
        return "استعلام وسائط: قواعد تُطبَّق في هذا العرض/الحالة فقط"
    if stripped.startswith("@keyframes"):
        return "تعريف حركة (keyframes)"
    if stripped.startswith("@font-face"):
        return "تعريف خط"
    if stripped.startswith("@"):
        return "قاعدة at-rule"
    if stripped.startswith(":root"):
        return "جذر المستند: متغيرات CSS العامة"
    if "{" in stripped and "}" in stripped:
        sel = stripped.split("{")[0].strip()
        return f"قاعدة كاملة في سطر واحد على المحدِّد {sel[:40]}"
    if "{" in stripped:
        return f"محدِّد (selector) {stripped.split('{')[0].strip()[:40]}: القواعد التالية تُطبَّق عليه"
    if stripped in ("}", "};"):
        return "إغلاق الكتلة السابقة"
    if stripped.endswith("}") and ":" in stripped:
        return "نهاية قاعدة فرعية"
    m = re.match(r"^([-\w]+)\s*:\s*([^:{]+?)\s*;?$", stripped)
    if m:
        prop, val = m.group(1), m.group(2)
        label = CSS_PROP.get(prop, prop)
        return f"{label}: {val[:40]}"
    if stripped.startswith("/*"):
        return ""
    if stripped.endswith(","):
        return "محدِّد إضافي لنفس الكتلة"
    return "تكملة القاعدة السابقة"


def annotate_css(path: str, notes: dict, dry: bool = False):
    lines = open(path, encoding="utf-8").read().split("\n")
    out, count, in_block = [], 0, False
    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if in_block:
            out.append(raw)
            if "*/" in stripped:
                in_block = False
            continue
        if not stripped or stripped.startswith("/*"):
            out.append(raw)
            if stripped.startswith("/*") and "*/" not in stripped:
                in_block = True
            continue
        text = notes.get(i) or css_auto(stripped)
        if text and not stripped.endswith("*/"):
            out.append(raw.rstrip() + " /* " + text + " */")
            count += 1
        else:
            out.append(raw)
    if not dry:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
    return count


# ============================================================================
# 7) HTML: تعليق <!-- --> فوق كل سطر (الإدراج آمن دائماً، الإلحاق ليس كذلك)
# ============================================================================
def html_auto(stripped: str) -> str:
    m = re.match(r"^<([a-zA-Z][\w-]*)", stripped)
    if m:
        tag = m.group(1).lower()
        labels = {
            "div": "حاوية (div)", "section": "قسم", "header": "ترويسة",
            "footer": "تذييل", "main": "المحتوى الرئيسي", "nav": "شريط تنقّل",
            "form": "نموذج", "input": "حقل إدخال", "select": "قائمة اختيار",
            "option": "خيار في القائمة", "button": "زر", "label": "تسمية حقل",
            "table": "جدول", "thead": "رأس الجدول", "tbody": "جسم الجدول",
            "tr": "صف جدول", "th": "خلية عنوان", "td": "خلية بيانات",
            "span": "جزء نصي", "p": "فقرة", "h1": "عنوان مستوى 1",
            "h2": "عنوان مستوى 2", "h3": "عنوان مستوى 3", "h4": "عنوان مستوى 4",
            "ul": "قائمة نقطية", "ol": "قائمة رقمية", "li": "عنصر قائمة",
            "a": "رابط", "img": "صورة", "script": "سكربت", "style": "تنسيقات",
            "link": "ربط ملف خارجي", "meta": "وصف للمستند", "title": "عنوان الصفحة",
            "br": "سطر جديد", "hr": "فاصل أفقي", "code": "نص برمجي",
            "pre": "نص محافظ على التنسيق", "strong": "توكيد قوي", "b": "توكيد",
            "small": "نص صغير", "details": "تفاصيل قابلة للطي",
            "summary": "عنوان التفاصيل", "progress": "شريط تقدم",
            "output": "مخرج", "fieldset": "مجموعة حقول", "legend": "عنوان المجموعة",
            "textarea": "مربع نص متعدد الأسطر", "iframe": "إطار داخلي",
            "aside": "هامش", "article": "مقال", "template": "قالب",
        }
        label = labels.get(tag, f"عنصر {tag}")
        mid = re.search(r'id="([^"]+)"', stripped)
        cls = re.search(r'class="([^"]+)"', stripped)
        extra = ""
        if mid:
            extra += f" بمعرّف {mid.group(1)}"
        if cls:
            extra += f" وصنف {cls.group(1)[:40]}"
        return label + extra
    if stripped.startswith("</"):
        return "إغلاق العنصر السابق"
    if stripped.startswith("<!DOCTYPE"):
        return "إعلان نوع المستند (HTML5)"
    if stripped.startswith("<!--"):
        return ""
    return "تكملة العنصر السابق"


def _html_tag_state(lines):
    """لكل سطر: هل يبدأ داخل وسم غير مغلق؟ (التعليق داخل وسم يكسر HTML)."""
    inside = {}
    state = False
    for i, raw in enumerate(lines, 1):
        inside[i] = state
        text = re.sub(r"<!--.*?-->", "", raw)
        for ch in text:
            if ch == "<":
                state = True
            elif ch == ">":
                state = False
    return inside


def _html_attrs(lines, start: int):
    """يلخّص ما يحمله السطر التالي من خصائص (لدمجه في تعليق سطر فتح الوسم)."""
    extra = []
    for raw in lines[start:]:
        stripped = raw.strip()
        if not stripped:
            break
        extra += re.findall(r"([\w:@.-]+)=", stripped)
        if ">" in stripped:
            break
    return extra


def annotate_html(path: str, notes: dict, dry: bool = False):
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    inside = _html_tag_state(lines)
    out, count, in_comment = [], 0, False
    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if in_comment:
            out.append(raw)
            if "-->" in stripped:
                in_comment = False
            continue
        if not stripped:
            out.append(raw)
            continue
        if inside.get(i):
            # سطر داخل وسم مفتوح: لا تعليق فوقه ولا بعده (يكسر HTML)،
            # ووصفه مدمج في تعليق سطر فتح الوسم
            out.append(raw)
            continue
        text = notes.get(i) or html_auto(stripped)
        if text and inside.get(i + 1):   # الوسم يستمر في السطر التالي
            attrs = _html_attrs(lines, i)
            if attrs:
                text += " — ويستمر في السطر التالي بخصائص: " + ", ".join(attrs[:8])
        if text:
            indent = re.match(r"\s*", raw).group(0)
            out.append(f"{indent}<!-- {text} -->")
            count += 1
        out.append(raw)
        if stripped.startswith("<!--") and "-->" not in stripped:
            in_comment = True
    if not dry:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
    return count


# ============================================================================
# 7ب) ترجمة التعليقات الإنجليزية الموجودة إلى عربية (في مكانها، بلا أسطر جديدة)
# ============================================================================
def translate_python(path: str, tr: dict, dry: bool = False) -> int:
    """يستبدل نص التعليق الإنجليزي بترجمته العربية على نفس السطر.

    لا يضيف ولا يحذف أسطراً، فأرقام الأسطر — وبالتالي خريطة الترجمة —
    تبقى صالحة.
    """
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return 0
    done = 0
    for tok in toks:
        if tok.type != tokenize.COMMENT:
            continue
        ln, col = tok.start
        if ln not in tr:
            continue
        line = lines[ln - 1]
        if line[col:col + 1] != "#":
            continue                                   # تغيّر العمود: لا نخمّن
        lines[ln - 1] = line[:col] + "# " + tr[ln] + line[tok.end[1]:]
        done += 1
    if done and not dry:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    return done


# ============================================================================
# 8) التراجع: حذف كل تعليق عربي أضافته الأداة
# ============================================================================
def revert(path: str, dry: bool = False) -> int:
    src = open(path, encoding="utf-8").read()
    out, removed = [], 0
    for raw in src.split("\n"):
        line = raw
        # تعليق كامل السطر فيه عربي
        if re.match(r"^\s*(#|//)\s", line) and AR.search(line):
            removed += 1
            continue
        if re.match(r"^\s*<!--.*-->\s*$", line) and AR.search(line):
            removed += 1
            continue
        # تعليق في آخر السطر
        for pat in (r"\s+#\s[^#]*$", r"\s+//\s[^/]*$", r"\s+/\*\s[^*]*\*/\s*$"):
            new = re.sub(pat, "", line)
            if new != line and AR.search(line[len(new):]):
                line = new
                removed += 1
                break
        out.append(line)
    if not dry:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
    return removed


# ============================================================================
# 9) نقطة الدخول
# ============================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="ملفات محددة (افتراضياً كل الملفات الأساسية)")
    ap.add_argument("--check", action="store_true", help="لا يكتب شيئاً")
    ap.add_argument("--revert", action="store_true", help="يحذف التعليقات العربية المضافة")
    ap.add_argument("--translate", action="store_true",
                    help="يترجم التعليقات الإنجليزية الموجودة إلى عربية")
    args = ap.parse_args(argv)

    from notes import PY_NOTES, PY_FUNC_NOTES, JS_NOTES, CSS_NOTES, HTML_NOTES
    from translations import PY_TR

    targets = args.files or (PY_FILES + JS_FILES + CSS_FILES + HTML_FILES)
    total = 0
    for rel in targets:
        path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print(f"  !! مفقود: {rel}")
            continue
        if args.translate:
            n = translate_python(path, PY_TR.get(rel, {}), args.check)
            verb = "سيُترجَم" if args.check else "تُرجم"
            print(f"  {rel:<32} {verb} {n} تعليقاً")
            total += n
            continue
        if args.revert:
            n = revert(path, args.check)
        elif rel.endswith(".py"):
            n = annotate_python(path, PY_NOTES.get(rel, {}),
                                PY_FUNC_NOTES.get(rel, {}), args.check)
        elif rel.endswith(".js"):
            n = annotate_js(path, JS_NOTES.get(rel, {}), args.check)
        elif rel.endswith(".css"):
            n = annotate_css(path, CSS_NOTES.get(rel, {}), args.check)
        elif rel.endswith(".html"):
            n = annotate_html(path, HTML_NOTES.get(rel, {}), args.check)
        else:
            print(f"  ؟ نوع غير معروف: {rel}")
            continue
        verb = "سيُحذف" if args.revert else ("سيُضاف" if args.check else "أُضيف")
        print(f"  {rel:<32} {verb} {n} تعليقاً")
        total += n
    print(f"\n  المجموع: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
