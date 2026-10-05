#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مولّد صفحات التوثيق الآلية لموقع KiraPass.

ينتج (داخل docs/site/):
    files/index.html       فهرس كل ملفات المشروع
    files/<module>.html    صفحة لكل ملف: دواله، أصنافه، متغيراته، منادياته
    src/<module>.html      المصدر كاملاً مرقّماً بالأسطر مع تعليقاته العربية
    callgraph.html         خريطة الاستدعاءات (من ينادي من، ومن يُنادى)
    api.html               كل مسارات HTTP: مدخلاتها ومخرجاتها ومن يستدعيها
    texts.html             كل النصوص المعروضة: مفتاحها وملفها وسطرها ونصّها

الاستخدام:
    python3 tools/docs/build_docs.py            # ولّد كل شيء
    python3 tools/docs/build_docs.py --dry      # اطبع ما سيُكتب فقط

كل الصفحات تولّد بالعربية (RTL) وتستخدم نفس أوراق الأنماط assets/docs.css.
"""
from __future__ import annotations

import argparse
import ast
import html
import io
import json
import os
import re
import sys
import time
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "docs", "site")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------
# الملفات التي لها صفحة (الاسم، المعرّف، العنوان العربي، الدور)
# --------------------------------------------------------------------------
MODULES = [
    ("KiraPass.py", "kirapass-py", "KiraPass.py",
     "نقطة الدخول: يشغّل الأداة من سطر الأوامر"),
    ("kirapass/__init__.py", "init", "__init__.py",
     "تعريف الحزمة ورقم النسخة"),
    ("kirapass/__main__.py", "main-mod", "__main__.py",
     "تشغيل بـpython -m kirapass"),
    ("kirapass/version_helpers.py", "version-helpers", "version_helpers.py",
     "مساعدات قراءة رقم النسخة"),
    ("kirapass/cli.py", "cli", "cli.py",
     "سطر الأوامر: الخيارات، الطباعة، تشغيل السيرفر"),
    ("kirapass/config.py", "config", "config.py",
     "كل الثوابت والمسارات والكلمات والمتغيرات البيئية"),
    ("kirapass/errors.py", "errors", "errors.py",
     "تحويل أي استثناء شبكة إلى كود ونص وتلميح"),
    ("kirapass/httpclient.py", "httpclient", "httpclient.py",
     "عميل HTTP: الاتصال، الكوكيز، المهلات، التحويلات"),
    ("kirapass/verify.py", "verify", "verify.py",
     "فحص حالة الإنترنت وصفحة الحالة وتسجيل الخروج"),
    ("kirapass/portals.py", "portals", "portals.py",
     "قراءة صفحة البوابة واستخراج النموذج وبنائه"),
    ("kirapass/fingerprint.py", "fingerprint", "fingerprint.py",
     "البصمة والحَكَم: من الردّ إلى الحكم"),
    ("kirapass/store.py", "store", "store.py",
     "البروفايلات، الإعدادات، التقارير، المراجعة، المسح"),
    ("kirapass/engine.py", "engine", "engine.py",
     "المحرك: المعايرة، التشغيل، الخيوط، المراقب، التقرير"),
    ("kirapass/capture.py", "capture", "capture.py",
     "المسجّل اليدوي: اعتراض البوابة وتنقيح الأسرار"),
    ("kirapass/selftest.py", "selftest", "selftest.py",
     "15 سيناريو اختبار على راوترات وهمية"),
    ("kirapass/mockportal.py", "mockportal", "mockportal.py",
     "راوتر وهمي كامل للاختبارات"),
    ("kirapass/web/server.py", "server", "web/server.py",
     "سيرفر الويب: المسارات، التفويض، المهام"),
    ("kirapass/web/ui.html", "ui-html", "web/ui.html",
     "هيكل الصفحة: كل العناصر والمعرّفات"),
    ("kirapass/web/ui.js", "ui-js", "web/ui.js",
     "منطق الصفحة: الترجمة، الاستطلاع، المعالجات"),
    ("kirapass/web/ui.css", "ui-css", "web/ui.css",
     "التنسيقات: كل الأصناف والمتغيرات"),
]
BY_ID = {m[1]: m for m in MODULES}
ID_OF = {m[0]: m[1] for m in MODULES}

AR = re.compile(r"[\u0600-\u06FF]")
PAGE_CSS = "../assets/docs.css"
PAGE_JS = "../assets/docs.js"


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def lines_of(rel: str):
    return read(rel).split("\n")


def comment_of(lines, ln: int) -> str:
    """نص التعليق العربي في نهاية السطر (إن وُجد)."""
    if ln < 1 or ln > len(lines):
        return ""
    line = lines[ln - 1]
    if "#" in line:
        tail = line.split("#", 1)[1].strip()
        if AR.search(tail):
            return tail
    if "//" in line:
        tail = line.split("//", 1)[1].strip()
        if AR.search(tail):
            return tail
    return ""


def comments_above(lines, ln: int) -> list:
    """أسطر التعليق العربي التي تسبق السطر مباشرة."""
    out = []
    i = ln - 2
    while i >= 0:
        s = lines[i].strip()
        if s.startswith("#") and AR.search(s):
            out.append(s.lstrip("#").strip())
            i -= 1
            continue
        break
    return list(reversed(out))


# ==========================================================================
# 1) تحليل بايثون
# ==========================================================================
def py_symbols(rel: str) -> dict:
    """كل رمز في الملف: دوال، أصناف، متغيرات، ومناديات كل دالة."""
    src = read(rel)
    lines = src.split("\n")
    tree = ast.parse(src)
    out = {"file": rel, "docstring": ast.get_docstring(tree) or "",
           "lines": len(lines), "funcs": [], "classes": [], "vars": [],
           "imports": []}

    # متغيرات الوحدة
    for node in tree.body:
        if isinstance(node, ast.Assign):
            val = ""
            try:
                val = ast.unparse(node.value)[:70]
            except Exception:
                val = "…"
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out["vars"].append({
                        "name": t.id, "line": node.lineno, "value": val,
                        "comment": comment_of(lines, node.lineno)})
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out["vars"].append({"name": node.target.id, "line": node.lineno,
                                "value": "(مصرّح بنوع)",
                                "comment": comment_of(lines, node.lineno)})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ", ".join(a.name for a in node.names)
            out["imports"].append({
                "line": node.lineno,
                "text": (f"from {'.' * node.level}{node.module or ''} import {names}"
                         if isinstance(node, ast.ImportFrom) else f"import {names}"),
                "comment": comment_of(lines, node.lineno)})

    def walk(node, prefix, parent):
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = prefix + child.name
                calls, assigns, returns, raises = [], [], [], []
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Call):
                        nm = _call_name(sub)
                        if nm:
                            calls.append((nm, sub.lineno))
                    elif isinstance(sub, ast.Assign):
                        for t in sub.targets:
                            if isinstance(t, ast.Name):
                                assigns.append(t.id)
                            elif isinstance(t, ast.Attribute):
                                assigns.append("self." + t.attr
                                               if isinstance(t.value, ast.Name)
                                               and t.value.id == "self" else t.attr)
                    elif isinstance(sub, ast.Return) and sub.value is not None:
                        returns.append(sub.lineno)
                    elif isinstance(sub, ast.Raise):
                        raises.append(sub.lineno)
                out["funcs"].append({
                    "name": child.name, "qname": qname, "line": child.lineno,
                    "end": getattr(child, "end_lineno", child.lineno),
                    "args": _sig(child),
                    "ret": _ret(child), "decorators": [
                        _call_name(d) or "?" for d in child.decorator_list],
                    "docstring": (ast.get_docstring(child) or "").strip(),
                    "comment": comment_of(lines, child.lineno),
                    "above": comments_above(lines, child.lineno),
                    "calls": calls, "assigns": sorted(set(assigns)),
                    "returns": len(returns), "raises": len(raises),
                    "parent": parent})
                walk(child, qname + ".", qname)
            elif isinstance(child, ast.ClassDef):
                qname = prefix + child.name
                out["classes"].append({
                    "name": child.name, "qname": qname, "line": child.lineno,
                    "end": getattr(child, "end_lineno", child.lineno),
                    "bases": [_call_name(b) or "?" for b in child.bases],
                    "docstring": (ast.get_docstring(child) or "").strip(),
                    "comment": comment_of(lines, child.lineno),
                    "above": comments_above(lines, child.lineno),
                    "parent": parent})
                walk(child, qname + ".", qname)

    walk(tree, "", "")
    return out


def _call_name(node) -> str:
    """اسم المنادى بنقاطه: classify / store.decode_card / self._run / p.get."""
    try:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = _call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        if isinstance(node, ast.Call):
            return _call_name(node.func)
    except RecursionError:
        pass
    return ""


def _ret(node) -> str:
    if not node.returns:
        return ""
    try:
        return ast.unparse(node.returns)
    except Exception:
        return ""


def _sig(node) -> str:
    a = node.args
    parts = [x.arg for x in a.posonlyargs] + [x.arg for x in a.args]
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    parts += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return ", ".join(parts)


# ==========================================================================
# 2) تحليل JavaScript / CSS / HTML
# ==========================================================================
def js_symbols(rel: str) -> dict:
    lines = read(rel).split("\n")
    funcs, vars_, i18n = [], [], {"ar": {}, "en": {}}
    block = None
    depth = 0
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        m = re.match(r"^function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", s)
        if m:
            funcs.append({"name": m.group(1), "line": i, "args": m.group(2),
                          "comment": comment_of(lines, i)})
            continue
        m = re.match(r"^(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*(.{0,60})", s)
        if m:
            vars_.append({"name": m.group(1), "line": i, "value": m.group(2),
                          "comment": comment_of(lines, i)})
            if m.group(1) == "I18N":
                depth = i
        if s.startswith("ar:") and block is None and depth:
            block = "ar"
        elif s.startswith("en:") and block == "ar":
            block = "en"
        elif s.startswith("};") and block:
            block = None
        if block:
            for km in re.finditer(r"([A-Za-z_][\w]*)\s*:\s*\"((?:[^\"\\]|\\.)*)\"", s):
                i18n[block].setdefault(km.group(1), {"line": i, "text": km.group(2)})
    # مناديات داخل JS
    calls = {}
    names = {f["name"] for f in funcs}
    for i, raw in enumerate(lines, 1):
        for m in re.finditer(r"\b([A-Za-z_$][\w$]*)\s*\(", raw):
            nm = m.group(1)
            if nm in names and nm not in ("if", "for", "while", "switch",
                                          "function", "catch", "return"):
                calls.setdefault(nm, []).append(i)
    return {"file": rel, "lines": len(lines), "funcs": funcs, "vars": vars_,
            "calls": calls, "i18n": i18n}


def css_symbols(rel: str) -> dict:
    lines = read(rel).split("\n")
    selectors, props = [], {}
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith("/*"):
            continue
        if "{" in s or s.startswith("@media"):
            selectors.append({"sel": s.split("{")[0].strip() or s[:40], "line": i,
                              "comment": comment_of(lines, i)})
        m = re.match(r"^([-a-zA-Z]+)\s*:", s)
        if m:
            props[m.group(1)] = props.get(m.group(1), 0) + 1
    return {"file": rel, "lines": len(lines), "selectors": selectors,
            "props": props}


def html_symbols(rel: str) -> dict:
    lines = read(rel).split("\n")
    ids, i18n, inputs, buttons = [], [], [], []
    for i, raw in enumerate(lines, 1):
        for m in re.finditer(r'id="([^"]+)"', raw):
            ids.append({"id": m.group(1), "line": i})
        for m in re.finditer(r'data-i18n="([^"]+)"', raw):
            text = re.sub(r"<[^>]+>", "", raw).strip()
            i18n.append({"key": m.group(1), "line": i, "text": text})
        for m in re.finditer(r'<(input|select|textarea)\b([^>]*)', raw):
            mid = re.search(r'id="([^"]+)"', m.group(2))
            inputs.append({"tag": m.group(1), "line": i,
                           "id": mid.group(1) if mid else ""})
        for m in re.finditer(r'<button\b([^>]*)>([^<]*)', raw):
            mid = re.search(r'id="([^"]+)"', m.group(1))
            buttons.append({"line": i, "id": mid.group(1) if mid else "",
                            "text": m.group(2).strip()})
    return {"file": rel, "lines": len(lines), "ids": ids, "i18n": i18n,
            "inputs": inputs, "buttons": buttons}


# ==========================================================================
# 3) الاستدعاءات عبر المشروع
# ==========================================================================
# أسماء وحداتنا: اسم الوحدة ← ملفها (لحلّ مناديات store.x وverify.y …)
MOD_ALIAS = {}
for _rel, _mid, _name, _role in MODULES:
    if _rel.endswith(".py"):
        MOD_ALIAS[os.path.basename(_rel)[:-3]] = _rel
MOD_ALIAS["server"] = "kirapass/web/server.py"


def build_graph(py_data: dict) -> dict:
    """فهرس دقيق للاستدعاءات.

    لا نربط مناداة بمجرد تطابق الاسم: `p.get()` (قاموس) ليست `Session.get`.
    لذلك نُحلّل كل مناداة:
      * اسم مجرّد            ← يرتبط إن كان له تعريف واحد لا لبس فيه
      * self.x               ← يرتبط بدالة في نفس الصنف/الملف
      * module.x             ← يرتبط فقط إن كان module وحدة من وحداتنا
      * أي شيء آخر (كائن خارجي) ← لا رابط
    """
    defs = {}
    for rel, data in py_data.items():
        for f in data["funcs"]:
            defs.setdefault(f["name"], []).append((rel, f["line"], f["qname"]))
        for c in data["classes"]:
            defs.setdefault(c["name"], []).append((rel, c["line"], c["qname"]))

    edges = []                       # (من ملف، من دالة، إلى ملف، إلى دالة، سطر)
    unresolved = {}                  # اسم ← عدد المرات (للمناداة الخارجية)
    for rel, data in py_data.items():
        for f in data["funcs"]:
            cls = f["qname"].rsplit(".", 1)[0] if "." in f["qname"] else ""
            for dotted, ln in f["calls"]:
                parts = dotted.split(".")
                target = None
                if len(parts) == 1:
                    cand = defs.get(parts[0], [])
                    same = [c for c in cand if c[0] == rel]
                    pick = same[0] if same else (cand[0] if len(cand) == 1 else None)
                    if pick and pick[2] != f["qname"]:
                        target = pick
                elif parts[0] == "self":
                    cand = [c for c in defs.get(parts[-1], []) if c[0] == rel]
                    if cls:
                        pref = [c for c in cand if c[2].startswith(cls + ".")]
                        cand = pref or cand
                    if cand:
                        target = cand[0]
                elif parts[0] in MOD_ALIAS:
                    want = MOD_ALIAS[parts[0]]
                    cand = [c for c in defs.get(parts[-1], []) if c[0] == want]
                    if cand:
                        target = cand[0]
                if target:
                    edges.append((rel, f["qname"], target[0], target[2], ln))
                else:
                    unresolved[dotted] = unresolved.get(dotted, 0) + 1
    callers = {}
    for src_rel, src_q, dst_rel, dst_q, ln in edges:
        callers.setdefault((dst_rel, dst_q), []).append((src_rel, src_q, ln))
    calls_of = {}
    for src_rel, src_q, dst_rel, dst_q, ln in edges:
        calls_of.setdefault((src_rel, src_q), []).append((dst_rel, dst_q, ln))
    return {"defs": defs, "callers": callers, "calls_of": calls_of,
            "edges": edges, "unresolved": unresolved}


# ==========================================================================
# 4) قوالب الصفحات
# ==========================================================================
def page(title: str, page_id: str, body: str, base: str = "",
         extra_head: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · KiraPass</title>
<link rel="stylesheet" href="{base}assets/docs.css">
{extra_head}
</head>
<body>
<div id="kp-layout">
<main class="doc">
{body}
<footer class="docfoot">صفحة مولّدة آلياً من مصدر الكود · KiraPass —
<code>{esc(page_id)}</code> · {time.strftime('%Y-%m-%d %H:%M')}</footer>
</main>
</div>
<script src="{base}assets/docs.js"></script>
<script>KPInit("{esc(page_id)}");</script>
</body>
</html>
"""


def banner(base: str = "../") -> str:
    """لافتة «صفحة مولّدة آلياً» بمسارات صحيحة لمستوى الصفحة."""
    return (f'<div class="card info"><b>هذه الصفحة مولّدة آلياً</b> من مصدر الكود مباشرة '
            f'(<code>tools/docs/build_docs.py</code>). إن غيّرت الكود فأعد توليدها: '
            f'<code>python3 tools/docs/build_docs.py</code>. الشرح اليدوي الأوسع في '
            f'<a href="{base}architecture.html">المعمارية</a> و'
            f'<a href="{base}editing.html">دليل التعديل</a> و'
            f'<a href="{base}danger.html">أماكن الخطر</a>.</div>')


GEN_BANNER = banner("../")


def write(rel: str, content: str, dry: bool = False) -> None:
    path = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if dry:
        print(f"  سيُكتب {rel} ({len(content)//1024} ك.بايت)")
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  كُتب {rel} ({len(content)//1024} ك.بايت)")


# ==========================================================================
# 5) صفحة ملف واحد
# ==========================================================================
def module_page(mid: str, py_data, js_data, css_data, html_data, graph,
                dry=False) -> None:
    rel, _mid, name, role = BY_ID[mid]
    parts = [f"<h1>ملف <code>{esc(name)}</code></h1>",
             f'<p class="lead">{esc(role)} — <code>{esc(rel)}</code></p>',
             GEN_BANNER]

    if rel.endswith(".py"):
        d = py_data[rel]
        nf, nc = len(d["funcs"]), len(d["classes"])
        parts.append('<div class="grid3">'
                     f'<div class="card"><b>{d["lines"]}</b><br>سطراً</div>'
                     f'<div class="card"><b>{nf}</b><br>دالة</div>'
                     f'<div class="card"><b>{nc}</b><br>صنف</div></div>')
        if d["docstring"]:
            first = d["docstring"].strip().split("\n")[0]
            parts.append(f'<div class="note"><b>ملخّص المؤلف للملف (نصه الأصلي بالإنجليزية):</b> <span class="muted">{esc(first)}</span></div>')
        parts.append(f'<p><a class="btn primary" href="../src/{mid}.html">'
                     'افتح المصدر كاملاً مرقّماً</a></p>')

        if d["imports"]:
            parts.append("<h2 id=\"imports\">الاستيرادات</h2>"
                         '<table class="t compact"><thead><tr><th>السطر</th>'
                         '<th>الاستيراد</th><th>لماذا</th></tr></thead><tbody>')
            for im in d["imports"]:
                parts.append(f'<tr><td class="mono">{im["line"]}</td>'
                             f'<td class="mono">{esc(im["text"])}</td>'
                             f'<td>{esc(im["comment"])}</td></tr>')
            parts.append("</tbody></table>")

        if d["vars"]:
            parts.append("<h2 id=\"vars\">متغيرات وثوابت على مستوى الوحدة</h2>"
                         '<div class="scroll-x"><table class="t compact"><thead><tr>'
                         '<th>الاسم</th><th>السطر</th><th>القيمة</th>'
                         '<th>الشرح</th></tr></thead><tbody>')
            for v in d["vars"]:
                parts.append(
                    f'<tr><td class="mono"><span class="tag var">{esc(v["name"])}</span></td>'
                    f'<td class="mono"><a href="../src/{mid}.html#L{v["line"]}">'
                    f'{v["line"]}</a></td><td class="mono">{esc(v["value"])}</td>'
                    f'<td>{esc(v["comment"])}</td></tr>')
            parts.append("</tbody></table></div>")

        if d["classes"]:
            parts.append("<h2 id=\"classes\">الأصناف</h2>")
            for c in d["classes"]:
                bases = (" يرث من " + ", ".join(esc(b) for b in c["bases"])) if c["bases"] else ""
                methods = [f for f in d["funcs"]
                           if f["qname"].startswith(c["qname"] + ".")
                           and f["qname"].count(".") == c["qname"].count(".") + 1]
                parts.append(
                    f'<div class="sym head" id="c-{esc(c["qname"])}">'
                    f'<span class="tag mod">صنف</span> <b>{esc(c["qname"])}</b>{bases}'
                    f' <a class="tag api" href="../src/{mid}.html#L{c["line"]}">سطر {c["line"]}</a>'
                    f'<div>{esc(" ".join(c["above"])) or esc(c["comment"])}</div></div>')
                if methods:
                    parts.append('<div class="sym body">دواله: ' + " · ".join(
                        f'<a href="#f-{esc(m["qname"])}"><code>{esc(m["name"])}</code></a>'
                        for m in methods) + "</div>")

        if d["funcs"]:
            parts.append("<h2 id=\"funcs\">الدوال — واحدة واحدة</h2>")
            for f in d["funcs"]:
                parts.append(_func_block(f, mid, graph, rel))
    elif rel.endswith(".js"):
        d = js_data[rel]
        parts.append('<div class="grid3">'
                     f'<div class="card"><b>{d["lines"]}</b><br>سطراً</div>'
                     f'<div class="card"><b>{len(d["funcs"])}</b><br>دالة</div>'
                     f'<div class="card"><b>{len(d["vars"])}</b><br>متغير</div></div>')
        parts.append(f'<p><a class="btn primary" href="../src/{mid}.html">'
                     'افتح المصدر كاملاً مرقّماً</a></p>')
        parts.append("<h2 id=\"vars\">المتغيرات العامة</h2>"
                     '<div class="scroll-x"><table class="t compact"><thead><tr>'
                     '<th>الاسم</th><th>السطر</th><th>القيمة</th><th>الشرح</th>'
                     '</tr></thead><tbody>')
        for v in d["vars"]:
            parts.append(f'<tr><td class="mono"><span class="tag var">{esc(v["name"])}</span></td>'
                         f'<td class="mono"><a href="../src/{mid}.html#L{v["line"]}">'
                         f'{v["line"]}</a></td><td class="mono">{esc(v["value"])}</td>'
                         f'<td>{esc(v["comment"])}</td></tr>')
        parts.append("</tbody></table></div>")
        parts.append("<h2 id=\"funcs\">الدوال</h2>")
        for f in d["funcs"]:
            called = d["calls"].get(f["name"], [])
            sites = [x for x in called if x != f["line"]]
            parts.append(
                f'<div class="sym head" id="f-{esc(f["name"])}">'
                f'<span class="tag fn">دالة</span> <b>{esc(f["name"])}'
                f'({esc(f["args"])})</b> '
                f'<a class="tag api" href="../src/{mid}.html#L{f["line"]}">سطر {f["line"]}</a>'
                f'<div>{esc(f["comment"])}</div></div>'
                f'<div class="sym body"><div class="kv"><span>تُنادى في</span>'
                f'<b>{len(sites)}</b> موضعاً داخل الملف: '
                + (", ".join(str(x) for x in sites[:12]) + ("…" if len(sites) > 12 else "")
                   if sites else "لا تُنادى داخلياً (نقطة دخول)") + "</div></div>")
        parts.append('<h2 id="i18n">قاموس الترجمة</h2>'
                     '<p>كل نصوص الواجهة في <code>I18N</code> — انظر '
                     '<a href="../texts.html">صفحة النصوص</a>.</p>')
    elif rel.endswith(".css"):
        d = css_data[rel]
        parts.append('<div class="grid3">'
                     f'<div class="card"><b>{d["lines"]}</b><br>سطراً</div>'
                     f'<div class="card"><b>{len(d["selectors"])}</b><br>محدِّد</div>'
                     f'<div class="card"><b>{len(d["props"])}</b><br>خاصية مختلفة</div></div>')
        parts.append(f'<p><a class="btn primary" href="../src/{mid}.html">'
                     'افتح المصدر كاملاً مرقّماً</a></p>')
        parts.append("<h2 id=\"sel\">المحدِّدات</h2>"
                     '<div class="scroll-x"><table class="t compact"><thead><tr>'
                     '<th>المحدِّد</th><th>السطر</th><th>الشرح</th></tr></thead><tbody>')
        for s in d["selectors"]:
            parts.append(f'<tr><td class="mono">{esc(s["sel"])}</td>'
                         f'<td class="mono"><a href="../src/{mid}.html#L{s["line"]}">'
                         f'{s["line"]}</a></td><td>{esc(s["comment"])}</td></tr>')
        parts.append("</tbody></table></div>")
    else:                                   # ui.html
        d = html_data[rel]
        parts.append('<div class="grid3">'
                     f'<div class="card"><b>{d["lines"]}</b><br>سطراً</div>'
                     f'<div class="card"><b>{len(d["ids"])}</b><br>معرّف</div>'
                     f'<div class="card"><b>{len(d["i18n"])}</b><br>نص مترجم</div></div>')
        parts.append(f'<p><a class="btn primary" href="../src/{mid}.html">'
                     'افتح المصدر كاملاً مرقّماً</a></p>')
        parts.append("<h2 id=\"ids\">كل المعرّفات (ما يمسكه ui.js)</h2>"
                     '<div class="scroll-x"><table class="t compact"><thead><tr>'
                     '<th>المعرّف</th><th>السطر</th></tr></thead><tbody>')
        for x in d["ids"]:
            parts.append(f'<tr><td class="mono">{esc(x["id"])}</td>'
                         f'<td class="mono"><a href="../src/{mid}.html#L{x["line"]}">'
                         f'{x["line"]}</a></td></tr>')
        parts.append("</tbody></table></div>")
        parts.append("<h2 id=\"btns\">الأزرار وحقول الإدخال</h2>"
                     '<table class="t compact"><thead><tr><th>النوع</th><th>المعرّف</th>'
                     '<th>النص</th><th>السطر</th></tr></thead><tbody>')
        for b in d["buttons"]:
            parts.append(f'<tr><td>زر</td><td class="mono">{esc(b["id"])}</td>'
                         f'<td>{esc(b["text"])}</td><td class="mono">{b["line"]}</td></tr>')
        for x in d["inputs"]:
            parts.append(f'<tr><td>{esc(x["tag"])}</td><td class="mono">{esc(x["id"])}</td>'
                         f'<td>—</td><td class="mono">{x["line"]}</td></tr>')
        parts.append("</tbody></table>")

    body = "\n".join(parts)
    # معرّف التنقّل "files" حتى تُظلَّل خانة «صفحات الملفات» في القائمة الجانبية
    write(f"files/{mid}.html", page("ملف " + name, "files", body, "../"), dry)


def _func_block(f: dict, mid: str, graph, rel: str) -> str:
    """بطاقة دالة واحدة: توقيعها، شرحها، ما تفعله، من يناديها، أين تُنادى."""
    qname = f["qname"]
    out = [f'<div class="sym head" id="f-{esc(qname)}">'
           f'<span class="tag fn">دالة</span> <b>{esc(qname)}({esc(f["args"])})</b>']
    if f.get("ret"):
        out.append(f' <span class="muted">→ {esc(f["ret"])}</span>')
    if f["decorators"]:
        out.append(" " + " ".join(f'<span class="tag var">@{esc(d)}</span>'
                                  for d in f["decorators"]))
    out.append(f' <a class="tag api" href="../src/{mid}.html#L{f["line"]}">'
               f'سطر {f["line"]}–{f["end"]}</a>')
    expl = " ".join(f["above"]) or f["comment"] or ""
    if f["docstring"]:
        first = f["docstring"].strip().split("\n")[0]
        expl = (expl + " " if expl else "") + f'<span class="muted">(نص المؤلف الأصلي في docstring: {esc(first)})</span>'
    out.append(f"<div>{expl}</div></div>")
    rows = []
    if f["returns"]:
        rows.append(("قيمة إرجاع", f'{f["returns"]} موضع <code>return</code>'))
    if f["raises"]:
        rows.append(("يرفع استثناء", f'{f["raises"]} موضع <code>raise</code>'))
    if f["assigns"]:
        shown = ", ".join(esc(a) for a in f["assigns"][:16])
        more = "…" if len(f["assigns"]) > 16 else ""
        rows.append(("يُسند إلى", f"<code>{shown}{more}</code>"))
    calls = graph["calls_of"].get((rel, qname), [])
    if calls:
        agg = {}
        for drel, dq, ln in calls:
            agg.setdefault((drel, dq), []).append(ln)
        bits = []
        for (drel, dq), lns in sorted(agg.items(), key=lambda kv: -len(kv[1])):
            did = ID_OF.get(drel, "")
            same = " (نفس الملف)" if drel == rel else ""
            bits.append(f'<a href="../files/{did}.html#f-{esc(dq)}">'
                        f'<code>{esc(dq)}</code></a>'
                        f'<span class="muted">×{len(lns)} سطر {lns[0]}{same}</span>')
        rows.append(("ينادي من دوال المشروع", " · ".join(bits)))
    who = graph["callers"].get((rel, qname), [])
    if who:
        bits = []
        for wrel, wq, wln in sorted(who)[:14]:
            wid = ID_OF.get(wrel, "")
            bits.append(f'<a href="../files/{wid}.html#f-{esc(wq)}">'
                        f'<code>{esc(wq)}</code></a> <span class="muted">'
                        f'({esc(os.path.basename(wrel))}:{wln})</span>')
        if len(who) > 14:
            bits.append(f'<span class="muted">+{len(who) - 14} غيرها</span>')
        rows.append(("من يناديها", " ".join(bits)))
    else:
        rows.append(("من يناديها", '<span class="muted">لا تُنادى من داخل بايثون '
                                   '(نقطة دخول، أو تناديها الواجهة/الاختبارات)</span>'))
    out.append('<div class="sym body"><table class="kv">')
    for k, v in rows:
        out.append(f"<tr><th>{esc(k)}</th><td>{v}</td></tr>")
    out.append("</table></div>")
    return "\n".join(out)


# ==========================================================================
# 6) صفحة المصدر المرقّم
# ==========================================================================
def src_page(mid: str, dry=False) -> None:
    rel, _m, name, role = BY_ID[mid]
    lines = lines_of(rel)
    out = [f"<h1>مصدر <code>{esc(name)}</code></h1>",
           f'<p class="lead">{esc(role)} — {len(lines)} سطراً. '
           'كل سطر يحمل تعليقه العربي.</p>',
           banner("../"),
           f'<p><a class="btn" href="../files/{mid}.html">← صفحة الشرح</a> '
           '<label class="muted"> قفز إلى سطر: <input id="kp-jump" '
           'style="width:6rem" placeholder="123"></label></p>',
           '<details class="src" open><summary>المصدر كاملاً</summary>'
           '<pre data-lines="%d"><code>' % len(lines)]
    for i, raw in enumerate(lines, 1):
        out.append(f'<span class="ln" id="L{i}">{i}</span>{esc(raw) or " "}')
    out.append("</code></pre></details>")
    out.append("""<script>
document.getElementById("kp-jump").addEventListener("change", function (e) {
  var n = parseInt(e.target.value, 10);
  if (n > 0) { var el = document.getElementById("L" + n);
    if (el) el.scrollIntoView({block: "center"}); }
});
if (location.hash) { var el = document.querySelector(location.hash);
  if (el) setTimeout(function () { el.scrollIntoView({block: "center"}); }, 60); }
</script>""")
    write(f"src/{mid}.html",
          page("مصدر " + name, "files", "\n".join(out), "../"), dry)


# ==========================================================================
# 7) فهرس الملفات
# ==========================================================================
def files_index(py_data, js_data, css_data, html_data, dry=False) -> None:
    parts = ["<h1>صفحات الملفات</h1>",
             '<p class="lead">صفحة لكل ملف في المشروع: ما فيه من دوال وأصناف '
             'ومتغيرات، ومن ينادي كل دالة، ورابط إلى المصدر كاملاً مرقّماً.</p>',
             GEN_BANNER]
    total_lines = 0
    parts.append('<div class="scroll-x"><table class="t"><thead><tr>'
                 '<th>الملف</th><th>الدور</th><th>الأسطر</th><th>الدوال</th>'
                 '<th>الأصناف</th><th>المتغيرات</th><th>صفحات</th></tr></thead><tbody>')
    for rel, mid, name, role in MODULES:
        if rel.endswith(".py"):
            d = py_data[rel]
            nf, nc, nv, ln = len(d["funcs"]), len(d["classes"]), len(d["vars"]), d["lines"]
        elif rel.endswith(".js"):
            d = js_data[rel]
            nf, nc, nv, ln = len(d["funcs"]), 0, len(d["vars"]), d["lines"]
        elif rel.endswith(".css"):
            d = css_data[rel]
            nf, nc, nv, ln = 0, 0, len(d["selectors"]), d["lines"]
        else:
            d = html_data[rel]
            nf, nc, nv, ln = 0, 0, len(d["ids"]), d["lines"]
        total_lines += ln
        parts.append(
            f'<tr><td class="mono"><b>{esc(name)}</b><br>'
            f'<span class="muted">{esc(rel)}</span></td>'
            f'<td>{esc(role)}</td><td>{ln:,}</td><td>{nf}</td><td>{nc}</td>'
            f'<td>{nv}</td><td><a class="btn" href="{mid}.html">الشرح</a> '
            f'<a class="btn" href="../src/{mid}.html">المصدر</a></td></tr>')
    parts.append(f'</tbody><tfoot><tr><th colspan="2">المجموع</th>'
                 f'<th>{total_lines:,}</th><th colspan="4"></th></tr></tfoot></table></div>')
    parts.append('<div class="note"><b>كيف تقرأ صفحة ملف:</b> كل دالة لها بطاقة فيها '
                 'التوقيع، الشرح العربي، ما تُسنده وما تُرجعه، '
                 '<b>الدوال التي تناديها</b> (مرتبطة بصفحاتها)، '
                 '<b>ومن يناديها</b> مع الملف ورقم السطر.</div>')
    write("files/index.html", page("صفحات الملفات", "files", "\n".join(parts), "../"), dry)


# ==========================================================================
# 8) خريطة الاستدعاءات
# ==========================================================================
def callgraph_page(py_data, graph, dry=False) -> None:
    parts = ["<h1>خريطة الاستدعاءات</h1>",
             '<p class="lead">من ينادي من في كل المشروع — <b>%d</b> حافة استدعاء '
             'محلولة بين دوال المشروع (لا تُحسب مناديات المكتبات القياسية ولا '
             'طرائق الكائنات الخارجية حتى لا تختلط <code>p.get()</code> بـ'
             '<code>Session.get()</code>).</p>' % len(graph["edges"]),
             banner("")]
    callers = graph["callers"]
    hot = sorted(callers.items(), key=lambda kv: -len(kv[1]))[:30]
    parts.append("<h2 id=\"hot\">مفاصل النظام — الدوال الأكثر مناداةً</h2>")
    parts.append('<table class="t compact"><thead><tr><th>الدالة</th>'
                 '<th>مواضع المناداة</th><th>من يناديها</th></tr></thead><tbody>')
    for (drel, dq), who in hot:
        did = ID_OF.get(drel, "")
        by = " ".join(f'<a href="files/{ID_OF.get(w[0], "")}.html#f-{esc(w[1])}">'
                      f'<code>{esc(w[1].rsplit(".", 1)[-1])}</code></a>'
                      for w in sorted(set((w[0], w[1]) for w in who))[:8])
        parts.append(f'<tr><td><a href="files/{did}.html#f-{esc(dq)}">'
                     f'<code>{esc(dq)}</code></a> <span class="muted">'
                     f'{esc(os.path.basename(drel))}</span></td>'
                     f'<td>{len(who)}</td><td>{by}</td></tr>')
    parts.append("</tbody></table>")

    parts.append("<h2 id=\"all\">كل دوال المشروع — من يناديها ومن تنادي</h2>")
    for rel, mid, name, _role in MODULES:
        if not rel.endswith(".py"):
            continue
        d = py_data[rel]
        if not d["funcs"]:
            continue
        parts.append(f'<h3 id="g-{mid}"><code>{esc(name)}</code> '
                     f'<span class="muted">({len(d["funcs"])} دالة)</span></h3>')
        parts.append('<div class="scroll-x"><table class="t compact"><thead><tr>'
                     '<th>الدالة</th><th>السطر</th><th>تنادي</th>'
                     '<th>يناديها</th></tr></thead><tbody>')
        for f in d["funcs"]:
            calls = graph["calls_of"].get((rel, f["qname"]), [])
            agg = {}
            for drel, dq, ln in calls:
                agg.setdefault((drel, dq), 0)
                agg[(drel, dq)] += 1
            c_links = " ".join(
                f'<a href="files/{ID_OF.get(dr, "")}.html#f-{esc(dq)}">'
                f'<code>{esc(dq.rsplit(".", 1)[-1])}</code></a>'
                f'<span class="muted">×{n}</span>'
                for (dr, dq), n in sorted(agg.items(), key=lambda kv: -kv[1])[:10]) \
                or '<span class="muted">—</span>'
            who = callers.get((rel, f["qname"]), [])
            w_links = " ".join(
                f'<a href="files/{ID_OF.get(wr, "")}.html#f-{esc(wq)}">'
                f'<code>{esc(wq.rsplit(".", 1)[-1])}</code></a>'
                for wr, wq, _ln in sorted(set((w[0], w[1], 0) for w in who))[:8]) \
                or '<span class="muted">لا أحد (نقطة دخول)</span>'
            parts.append(
                f'<tr><td><a href="files/{mid}.html#f-{esc(f["qname"])}">'
                f'<code>{esc(f["qname"])}</code></a></td>'
                f'<td class="mono"><a href="src/{mid}.html#L{f["line"]}">{f["line"]}</a></td>'
                f'<td>{c_links}</td><td>{w_links}</td></tr>')
        parts.append("</tbody></table></div>")

    parts.append("""<h2 id=\"threads\">سلاسل الاستدعاء الرئيسية</h2>
<div class="card"><pre>
الإقلاع:  KiraPass.py:main → cli.main → server.serve → KiraServer → ThreadingHTTPServer
الفحص:     ui.js:scanNow → POST /api/scan → server.do_POST → engine.scan → portals.scan
                                                                    ↘ verify.probe_internet
المعايرة:  ui.js:calibrate → POST /api/calibrate → server.Job → engine.calibrate
                                                                    ↘ engine.warm_up / absorb_form
                                                                    ↘ engine.bench_cards
                                                                    ↘ fingerprint.Fingerprinter.learn
                                                                    ↘ engine._tune_with_known_card
التشغيل:   ui.js:startRun → POST /api/run/start → engine.Engine.start → Engine._run
                                                                    ↘ Engine._attempt (×خيوط)
                                                                        ↘ engine.send_login
                                                                        ↘ fingerprint.Judge.classify
                                                                        ↘ Engine._register_hit
                                                                            ↘ Engine._verify_hit
                                                                                ↘ verify.probe_internet
                                                                    ↘ Engine._start_watchdog
                                                                    ↘ Engine._save_report → store.save_run
</pre></div>""")
    write("callgraph.html", page("خريطة الاستدعاءات", "callgraph",
                                 "\n".join(parts)), dry)


# ==========================================================================
# 9) واجهات API
# ==========================================================================
API_DESC = {
    "/api/meta": ("GET", "هوية الأداة: النسخة، اللغة، المسارات، حدود الإعدادات، وهل يوجد رمز"),
    "/api/profiles": ("GET", "قائمة البروفايلات المحفوظة (بلا قيم سرّية)"),
    "/api/profiles/get": ("GET", "بروفايل واحد بالاسم"),
    "/api/run/status": ("GET", "حالة التشغيل + الأحداث الجديدة منذ seq"),
    "/api/job": ("GET", "استطلاع مهمة خلفية (معايرة/تشخيص/قياس حجب)"),
    "/api/review": ("GET", "فهرس صفحات المراجعة"),
    "/api/review/file": ("GET", "نص صفحة مراجعة واحدة (باسم ملفها)"),
    "/api/cache": ("GET", "أحجام المجلدات والملفات على القرص"),
    "/api/report": ("GET", "تقرير تشغيل واحد أو تنزيله"),
    "/api/reports": ("GET", "قائمة تقارير التشغيل"),
    "/api/capture/status": ("GET", "حالة جلسة المسجّل الحالية"),
    "/api/capture/report": ("GET", "تقرير المسجّل المنقّح (أو تنزيله)"),
    "/api/scan": ("POST", "قراءة صفحة الدخول + فحص حالة الإنترنت"),
    "/api/format/preview": ("POST", "معاينة الفضاء والعينات ومشاكل الصيغة"),
    "/api/profiles/save": ("POST", "حفظ بروفايل (يرحلّه ثم يكتبه)"),
    "/api/profiles/delete": ("POST", "حذف بروفايل بالاسم"),
    "/api/profiles/export": ("POST", "تصدير بروفايل منقّح كنص"),
    "/api/profiles/import": ("POST", "استيراد بروفايل (يمسح pass_fixed)"),
    "/api/diagnose": ("POST", "تشخيص «لماذا يتصرف هكذا» بعينات محدودة"),
    "/api/calibrate": ("POST", "بدء معايرة كمهمة خلفية"),
    "/api/lockout": ("POST", "قياس مدى تسامح الراوتر (محدود وبإذن صريح)"),
    "/api/run/start": ("POST", "بدء التخمين"),
    "/api/run/stop": ("POST", "إيقاف التخمين"),
    "/api/cache/clear": ("POST", "مسح البيانات بنطاق: temp/results/profiles/all"),
    "/api/cache/cleanup-old": ("POST", "حذف تقارير أقدم من n يوم"),
    "/api/settings": ("POST", "حفظ اللغة/رابط الفحص/المهلات"),
    "/api/probe-link": ("POST", "طلب GET واحد للرابط لعرضه بلا تخمين"),
    "/api/capture/start": ("POST", "بدء جلسة تسجيل على رابط بوابة"),
    "/api/capture/step": ("POST", "إعادة إرسال طلب مسجّل بجلسة خاضعة للرقابة"),
    "/api/capture/mark": ("POST", "تعليم صفحة كنجاح/حالة (مرفوض إن كان فيها نموذج دخول)"),
    "/api/capture/finish": ("POST", "إنهاء الجلسة وبناء البروفايل المقترح"),
    "/api/quit": ("POST", "إغلاق الأداة (من خيط منفصل حتى لا يعلق)"),
}
STATIC = {"/": "صفحة الواجهة ui.html", "/ui.js": "منطق الواجهة",
          "/ui.css": "تنسيقات الواجهة", "/favicon.ico": "أيقونة",
          "/capture/view": "عرض البوابة المسجَّلة في إطار معزول (يتطلب تفويضاً)"}


def api_page(dry=False) -> None:
    srv = lines_of("kirapass/web/server.py")
    js = lines_of("kirapass/web/ui.js")
    parts = ["<h1>واجهات API</h1>",
             '<p class="lead">كل مسار HTTP في الأداة: وظيفته، من يستدعيه من الواجهة، '
             'وأين يُعالَج في <code>web/server.py</code>.</p>', banner(""),
             '<div class="card warn"><b>التفويض:</b> كل مسار يتطلب رمزاً '
             '(<code>?token=</code> أو ترويسة <code>X-KiraPass-Token</code>) '
             'باستثناء المسارات الثابتة الأربعة الأولى التي تُخدم قبل التفويض عمداً '
             'حتى تستطيع الصفحة أن تطلب الرمز. العميل المحلي (<code>127.0.0.1</code>/'
             '<code>::1</code>) مسموح دائماً. المقارنة بـ<code>hmac.compare_digest</code>.</div>']

    used = {}
    for i, raw in enumerate(js, 1):
        for m in re.finditer(r'["\'](/api/[a-z0-9/_-]+)', raw):
            used.setdefault(m.group(1), []).append(i)
    where = {}
    for i, raw in enumerate(srv, 1):
        for m in re.finditer(r'route == "(/api/[a-z0-9/_-]+)"', raw):
            where[m.group(1)] = i

    parts.append("<h2 id=\"http\">مسارات JSON</h2>")
    parts.append('<div class="scroll-x"><table class="t"><thead><tr><th>المسار</th>'
                 '<th>الأسلوب</th><th>الوظيفة</th><th>معالَج في server.py</th>'
                 '<th>يُستدعى من ui.js</th></tr></thead><tbody>')
    for path, (method, desc) in sorted(API_DESC.items(),
                                       key=lambda kv: (kv[1][0], kv[0])):
        w = where.get(path)
        u = used.get(path, [])
        wlink = (f'<a href="src/server.html#L{w}" class="mono">{w}</a>' if w
                 else '<span class="muted">—</span>')
        ulink = (", ".join(f'<a href="src/ui-js.html#L{x}" class="mono">{x}</a>'
                           for x in u[:8]) or '<span class="muted">لا يُستدعى مباشرة</span>')
        parts.append(f'<tr><td class="mono"><b>{esc(path)}</b></td>'
                     f'<td><span class="tag {method.lower()}">{method}</span></td>'
                     f'<td>{esc(desc)}</td><td>{wlink}</td><td>{ulink}</td></tr>')
    parts.append("</tbody></table></div>")

    found = sorted(set(where) - set(API_DESC))
    if found:
        parts.append('<div class="card warn"><b>مسارات في الكود لم تُوثَّق هنا:</b> '
                     + ", ".join(f"<code>{esc(x)}</code>" for x in found) + "</div>")

    parts.append("<h2 id=\"static\">المسارات الثابتة</h2><table class=\"t compact\">"
                 "<thead><tr><th>المسار</th><th>ما يخدمه</th><th>قبل التفويض؟</th>"
                 "</tr></thead><tbody>")
    for path, desc in STATIC.items():
        auth = "نعم (يُخدم بلا رمز)" if path != "/capture/view" else "لا — يتطلب رمزاً"
        parts.append(f'<tr><td class="mono">{esc(path)}</td><td>{esc(desc)}</td>'
                     f'<td>{auth}</td></tr>')
    parts.append("</tbody></table>")

    parts.append("""<h2 id="shapes">أشكال الحمولات</h2>
<div class="grid2">
<div class="card"><b>POST /api/run/start</b><pre>{
  "profile": { …بروفايل كامل… },
  "attempts": 2000,      // 1 … 20,000,000
  "threads": 12,         // 1 … 200
  "delay_ms": 0,
  "verify": true,        // فحص إنترنت بعد كل إصابة
  "auto_stop": true,
  "resume": true,        // تابع من space_pos
  "known_card": "0201242548",
  "preflight_only": false
}</pre></div>
<div class="card"><b>GET /api/run/status?since=N</b><pre>{
  "status": { state, counters, reason_counts,
              net_kinds, progress, speed,
              latency, throttle, calibration,
              hits, review, stop_reason,
              ban_evidence, plan, seq },
  "events": [ { seq, t, kind, data } ]
}</pre></div>
<div class="card"><b>POST /api/scan</b><pre>{ "url": "http://10.5.50.1/login" }
→ { ok, ms, portal: { status, url,
      form: { action, method, user_field,
              pass_field, chap, inputs,
              extra_fields, dst_field,
              dst_value } },
    internet: { state, detail },
    problems: [...] }</pre></div>
<div class="card"><b>POST /api/cache/clear</b><pre>{ "scope": "temp" }   // أو results|profiles|all
→ { ok, cleared: { scope, removed[],
      freed_bytes, freed_human },
    cache: { folders, files, total_bytes } }</pre></div>
</div>""")
    parts.append("""<h2 id="errors">أشكال الأخطاء</h2>
<p>كل فشل يرجع <code>{"ok": false, "error": "&lt;مفتاح آلية&gt;"}</code> بحالة HTTP
مناسبة (400 لمدخلات خاطئة، 401 بلا رمز، 404 لمفقود، 409 لتشغيل جارٍ).
المفاتيح الشائعة: <code>already_running</code> · <code>profile_invalid</code> ·
<code>bad_scope</code> · <code>profile_not_found</code> · <code>bad_json</code> ·
<code>server_gone</code> (من جهة الواجهة عندما ينقطع السيرفر).</p>""")
    write("api.html", page("واجهات API", "api", "\n".join(parts)), dry)


# ==========================================================================
# 10) صفحة النصوص المعروضة
# ==========================================================================
def texts_page(py_data, js_data, html_data, dry=False) -> None:
    js = js_data["kirapass/web/ui.js"]
    htm = html_data["kirapass/web/ui.html"]
    parts = ["""<h1>النصوص المعروضة وأماكنها</h1>
<p class="lead">كل نص يراه المستخدم، وأين يسكن، وكيف تغيّره. القاعدة الذهبية:
<b>النصوص الثابتة في <code>ui.html</code></b> (مع مفتاح <code>data-i18n</code>)،
<b>والنصوص الديناميكية في <code>I18N</code> داخل <code>ui.js</code></b>،
<b>والمفاتيح الآلية في بايثون</b> (لا تُترجم هناك — تُترجم في الواجهة).</p>""",
             banner("")]
    ar = js["i18n"].get("ar", {})
    en = js["i18n"].get("en", {})
    parts.append('<div class="grid3">'
                 f'<div class="card"><b>{len(ar)}</b><br>مفتاح ترجمة عربي في ui.js</div>'
                 f'<div class="card"><b>{len(en)}</b><br>مفتاح ترجمة إنجليزي</div>'
                 f'<div class="card"><b>{len(htm["i18n"])}</b><br>نص ثابت في ui.html</div>'
                 '</div>')

    parts.append("""<div class="card ok"><b>ثلاث قواعد لا تُكسر:</b>
<ol>
<li>كل مفتاح يُضاف إلى <code>data-i18n</code> في <code>ui.html</code> <b>يجب</b> أن يكون له
نصّان في <code>I18N</code> (ar وen) — وإلا سقط اختبار
<code>UIIntegrityTests.test_ui_ids_are_unique_and_static_translations_exist</code>.</li>
<li>لا تُعرّب المفاتيح الآلية في بايثون: <code>v_*</code> و<code>stop_*</code> و<code>r_*</code>
و<code>net_*</code> تبقى بالإنجليزية وتترجمها الواجهة. تغييرها يكسر التقارير القديمة.</li>
<li>الكلمات التي تُطابق صفحات الراوتر (<code>REJECT_WORDS</code>/<code>BAN_WORDS</code>/
<code>ACCEPT_WORDS</code>) ليست نصوصاً معروضة: هي <b>أدوات كشف</b>، وتُطابق كلمة كاملة.
أضف إليها بحذر واختبر.</li>
</ol></div>""")

    # --- نصوص ui.html الثابتة
    parts.append('<h2 id="static">١) النصوص الثابتة في ui.html</h2>'
                 '<p>كل عنصر يحمل <code>data-i18n</code>: النص العربي مكتوب مباشرة في '
                 'العنصر، والمفتاح يربطه بترجمته الإنجليزية في <code>I18N.en</code>.</p>'
                 '<div class="scroll-x"><table class="t compact"><thead><tr>'
                 '<th>المفتاح</th><th>النص العربي المعروض</th><th>السطر</th>'
                 '<th>الإنجليزي</th></tr></thead><tbody>')
    for x in htm["i18n"]:
        ent = en.get(x["key"])
        parts.append(f'<tr><td class="mono">{esc(x["key"])}</td>'
                     f'<td>{esc(x["text"][:110])}</td>'
                     f'<td class="mono"><a href="src/ui-html.html#L{x["line"]}">'
                     f'{x["line"]}</a></td>'
                     f'<td>{esc(ent["text"][:80]) if ent else "—"}</td></tr>')
    parts.append("</tbody></table></div>")

    # --- I18N
    parts.append('<h2 id="i18n">٢) قاموس الترجمة I18N في ui.js</h2>'
                 '<p>النصوص الديناميكية: رسائل، أسباب توقف، أحكام، أزرار تُبنى من '
                 'مفاتيح آلية. <b>المفتاح + النص العربي + السطر</b>:</p>'
                 '<div class="scroll-x"><table class="t compact"><thead><tr>'
                 '<th>المفتاح</th><th>العربي</th><th>السطر</th><th>الإنجليزي</th>'
                 '</tr></thead><tbody>')
    for key in sorted(ar):
        e = ar[key]
        ent = en.get(key)
        parts.append(f'<tr><td class="mono">{esc(key)}</td>'
                     f'<td>{esc(e["text"][:150])}</td>'
                     f'<td class="mono"><a href="src/ui-js.html#L{e["line"]}">'
                     f'{e["line"]}</a></td>'
                     f'<td>{esc(ent["text"][:90]) if ent else "—"}</td></tr>')
    parts.append("</tbody></table></div>")
    missing = sorted(set(en) - set(ar))
    if missing:
        parts.append('<div class="card bad"><b>مفاتيح بالإنجليزية بلا عربي:</b> '
                     + ", ".join(esc(m) for m in missing[:40]) + "</div>")

    # --- المفاتيح الآلية
    parts.append("""<h2 id="machine">٣) المفاتيح الآلية في بايثون (لا تُترجم هناك)</h2>
<div class="scroll-x"><table class="t compact"><thead><tr><th>العائلة</th>
<th>أين تولَّد</th><th>أين تُترجم</th><th>القيم</th></tr></thead><tbody>
<tr><td>الأحكام <code>v_*</code></td><td><code>fingerprint.Judge.classify</code></td>
<td><code>I18N.verdict_*</code></td>
<td class="mono">ACCEPTED_VERIFIED · ACCEPTED · ACCEPTED_UNVERIFIED · REJECTED ·
UNKNOWN · BANNED · RATE_LIMITED · CHALLENGE · NET_ERROR · INTERNAL_ERROR</td></tr>
<tr><td>أسباب التوقف <code>stop_*</code></td><td><code>engine.Engine.stop</code></td>
<td><code>I18N.stop_*</code></td>
<td class="mono">found_verified · found_strong_evidence · user_stop ·
banned_by_router · rate_limited_by_router · target_unreachable · captcha_challenge ·
internet_opened · attempts_done · space_done · calibration_failed · engine_error</td></tr>
<tr><td>أسباب الحكم <code>r_*</code></td><td><code>Judge.classify</code></td>
<td><code>I18N.reason_*</code></td>
<td class="mono">same_as_rejection_page_exact/shape/similar/empty/redirect ·
redirect_out_of_portal · redirect_differs_from_rejection · success_url_contains ·
learned_success_words · rejection_wording · reply_differs_not_proven · ban_page ·
http_403/429/503 · captcha_present · accepted_internet_already_open · …</td></tr>
<tr><td>أنواع أخطاء الشبكة <code>net_*</code></td><td><code>errors.classify</code></td>
<td><code>errors.KINDS</code> (عربي جاهز)</td>
<td class="mono">dns · refused · connect_timeout · read_timeout · reset · stale ·
tls · unreachable · bad_response · too_many_redirects · proto · unknown · no_session</td></tr>
<tr><td>مشاكل الصيغة</td><td><code>store.validate</code></td>
<td><code>I18N.problem_*</code></td>
<td class="mono">url_missing_or_invalid · user_field_missing ·
length_not_bigger_than_prefix_and_suffix · charset_too_small · unknown_pass_mode ·
fixed_password_empty · needs_browser_js · space_is_astronomically_big</td></tr>
<tr><td>أخطاء المعايرة</td><td><code>engine.calibrate</code></td>
<td><code>I18N.cal_*</code></td>
<td class="mono">profile_valid · reach_login_page · internet_state · rejection_probe ·
rejection_baseline · probe_looked_accepted · known_card_preflight · shape_tuned ·
blocked_already · captcha_challenge · request_shape_rejected · no_rejection_baseline ·
card_space_empty · known_card_out_of_format · known_card_not_proven · logout_unconfirmed</td></tr>
</tbody></table></div>""")

    # --- نصوص عربية داخل بايثون
    parts.append('<h2 id="pytext">٤) نصوص عربية مكتوبة داخل بايثون</h2>'
                 '<p>هذه <b>معروضة للمستخدم مباشرة</b> (لا تمرّ بالواجهة):</p>')
    cfg = py_data["kirapass/config.py"]
    parts.append('<table class="t compact"><thead><tr><th>الثابت</th><th>السطر</th>'
                 '<th>الاستخدام</th></tr></thead><tbody>')
    for v in cfg["vars"]:
        if v["name"] in ("REJECT_WORDS", "BAN_WORDS", "ACCEPT_WORDS"):
            use = {"REJECT_WORDS": "كلمات تُطابق صفحة «بطاقة خاطئة»",
                   "BAN_WORDS": "كلمات تُطابق صفحة حجب (عربية/إنجليزية/فرنسية)",
                   "ACCEPT_WORDS": "كلمات تُطابق صفحة نجاح"}[v["name"]]
            parts.append(f'<tr><td class="mono">{esc(v["name"])}</td>'
                         f'<td class="mono"><a href="src/config.html#L{v["line"]}">'
                         f'{v["line"]}</a></td><td>{esc(use)}</td></tr>')
    err = py_data["kirapass/errors.py"]
    for v in err["vars"]:
        if v["name"] == "KINDS":
            parts.append(f'<tr><td class="mono">KINDS</td>'
                         f'<td class="mono"><a href="src/errors.html#L{v["line"]}">'
                         f'{v["line"]}</a></td><td>وصف عربي قصير لكل نوع خطأ شبكة '
                         '(العمود الثاني في كل مدخل)</td></tr>')
    parts.append("</tbody></table>")

    parts.append("""<h2 id="howto">٥) كيف أغيّر نصّاً؟</h2>
<table class="t"><thead><tr><th>أريد أن…</th><th>أذهب إلى</th><th>الخطوات</th></tr></thead>
<tbody>
<tr><td>أغيّر نصاً ثابتاً في الصفحة</td><td><code>ui.html</code> + <code>I18N</code></td>
<td>غيّر النص داخل العنصر (العربي)، ثم غيّر <code>I18N.en.&lt;المفتاح&gt;</code>.
لا تغيّر <code>data-i18n</code> نفسه إلا إن غيّرت الاثنين.</td></tr>
<tr><td>أغيّر رسالة ديناميكية</td><td><code>I18N.ar/en</code> في <code>ui.js</code></td>
<td>ابحث عن المفتاح، غيّر النصّين. لا تضف مفاتيح في جهة واحدة.</td></tr>
<tr><td>أضيف مفتاحاً جديداً</td><td>الاثنان معاً</td>
<td>أضف في <code>I18N.ar</code> و<code>I18N.en</code>، ثم استخدمه بـ<code>t(key)</code>
أو <code>data-i18n</code>، ثم شغّل <code>UIIntegrityTests</code>.</td></tr>
<tr><td>أضيف كلمة كشف (رفض/حجب/نجاح)</td><td><code>config.py</code></td>
<td>أضف الكلمة <b>ككلمة كاملة</b>، ثم شغّل <code>PhraseTests</code> و
<code>MaskingTests</code>. انظر <a href="editing.html#recipe3">وصفة 3</a>.</td></tr>
<tr><td>أغيّر وصفاً عربياً لخطأ شبكة</td><td><code>errors.KINDS</code></td>
<td>العمود الثاني من كل مدخل. لا تغيّر <code>kind</code> نفسه (مفتاح آلي).</td></tr>
<tr><td>أترجم مفتاحاً آلياً جديداً</td><td><code>I18N</code></td>
<td>أضف <code>stop_&lt;الجديد&gt;</code> أو <code>r_&lt;الجديد&gt;</code> في
<code>ar</code> و<code>en</code>. المفتاح غير المترجم يظهر كما هو (لا ينهار).</td></tr>
</tbody></table>""")
    write("texts.html", page("النصوص المعروضة", "texts", "\n".join(parts)), dry)


# ==========================================================================
# 11) التشغيل
# ==========================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true", help="لا يكتب شيئاً")
    args = ap.parse_args(argv)

    py_data, js_data, css_data, html_data = {}, {}, {}, {}
    for rel, mid, _name, _role in MODULES:
        if rel.endswith(".py"):
            py_data[rel] = py_symbols(rel)
        elif rel.endswith(".js"):
            js_data[rel] = js_symbols(rel)
        elif rel.endswith(".css"):
            css_data[rel] = css_symbols(rel)
        else:
            html_data[rel] = html_symbols(rel)
    graph = build_graph(py_data)

    print("  توليد صفحات الملفات…")
    for rel, mid, _n, _r in MODULES:
        module_page(mid, py_data, js_data, css_data, html_data, graph, args.dry)
    print("  توليد صفحات المصدر…")
    for rel, mid, _n, _r in MODULES:
        src_page(mid, args.dry)
    print("  توليد الفهرس وخريطة الاستدعاءات وAPI والنصوص…")
    files_index(py_data, js_data, css_data, html_data, args.dry)
    callgraph_page(py_data, graph, args.dry)
    api_page(args.dry)
    texts_page(py_data, js_data, html_data, args.dry)
    print("\n  انتهى. افتح docs/site/index.html في المتصفح.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
