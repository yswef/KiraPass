/* ==========================================================================
   KiraPass · سكربت موقع التوثيق
   يبني الشريط العلوي + القائمة الجانبية + البحث، ويعمل بلا إنترنت وبلا مكتبات.
   ========================================================================== */
"use strict";

/* كل صفحات التوثيق في مكان واحد: أضف صفحتك الجديدة هنا فتظهر في القائمة فوراً */
var KP_PAGES = [
  { group: "ابدأ هنا", id: "index", href: "index.html", title: "بوابة التوثيق",
    sub: "خريطة الموقع وكيف تقرأه" },
  { group: "ابدأ هنا", id: "user", href: "user.html", title: "دليل المستخدم",
    sub: "طريقة الاستخدام خطوة بخطوة" },
  { group: "ابدأ هنا", id: "glossary", href: "glossary.html", title: "المصطلحات",
    sub: "كل كلمة غريبة في الأداة والتوثيق" },

  { group: "للمطوّر", id: "dev", href: "dev.html", title: "نظرة عامة للمطوّر",
    sub: "البنية، الطبقات، دورة الحياة" },
  { group: "للمطوّر", id: "architecture", href: "architecture.html", title: "المعمارية وتدفق البيانات",
    sub: "من الضغط على الزر حتى النتيجة" },
  { group: "للمطوّر", id: "files", href: "files/index.html", title: "صفحات الملفات",
    sub: "صفحة لكل ملف: دواله ومتغيراته واستدعاءاته" },
  { group: "للمطوّر", id: "callgraph", href: "callgraph.html", title: "خريطة الاستدعاءات",
    sub: "من ينادي من في كل المشروع" },
  { group: "للمطوّر", id: "api", href: "api.html", title: "واجهات API",
    sub: "كل مسار: مدخلاته ومخرجاته ومن يستدعيه" },
  { group: "للمطوّر", id: "data", href: "data.html", title: "بنيات البيانات",
    sub: "البروفايل، التقرير، الحدث، الحكم" },

  { group: "التعديل", id: "editing", href: "editing.html", title: "دليل التعديل وأسلوب الكتابة",
    sub: "ماذا أعدّل، كيف، وبأي أسلوب" },
  { group: "التعديل", id: "danger", href: "danger.html", title: "أماكن الخطر",
    sub: "الأسطر التي تكسر الأداة إن لُمست" },
  { group: "التعديل", id: "texts", href: "texts.html", title: "النصوص المعروضة وأماكنها",
    sub: "كل نص عربي/إنجليزي وملفه وسطره" },

  { group: "مراجع", id: "tests", href: "tests.html", title: "الاختبارات والتشغيل الآمن",
    sub: "بوابة التدريب، الاختبار الذاتي، e2e" },
  { group: "مراجع", id: "troubleshooting", href: "troubleshooting.html", title: "حل المشاكل",
    sub: "لماذا توقفت الأداة؟ وماذا أفعل" },
  { group: "مراجع", id: "env", href: "env.html", title: "الإعدادات ومتغيرات البيئة",
    sub: "كل رقم يمكن تغييره وأثره" }
];

/* ------------------------------------------------------------------ أدوات */
function kpBase() {
  /* الصفحات داخل files/ أو src/ أعمق بمستوى واحد، فنصحح المسارات النسبية */
  var p = location.pathname;
  if (p.indexOf("/files/") !== -1 || p.indexOf("/src/") !== -1) return "../";
  return "";
}

function kpCurrent() {
  var p = location.pathname.split("/").pop() || "index.html";
  if (p === "") p = "index.html";
  var dir = location.pathname.indexOf("/files/") !== -1 ? "files/" : "";
  return dir + p;
}

function kpEl(tag, cls, html) {
  var e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

/* ------------------------------------------------------------------ الشريط */
function kpBuildTopbar(current) {
  var base = kpBase();
  var bar = kpEl("div", "", "");
  bar.id = "kp-topbar";
  var page = null;
  for (var i = 0; i < KP_PAGES.length; i++) {
    if (KP_PAGES[i].href.replace(/^\.\.\//, "") === current ||
        KP_PAGES[i].href === current || KP_PAGES[i].href.split("/").pop() === current) {
      page = KP_PAGES[i]; break;
    }
  }
  bar.appendChild(kpEl("button", "btn", "☰ القائمة").cloneNode(false));
  var menuBtn = kpEl("button", "btn", "☰");
  menuBtn.id = "kp-menu-btn";
  bar.appendChild(menuBtn);
  bar.appendChild(kpEl("div", "brand",
    "<span class='logo'>K</span><span>KiraPass · التوثيق</span>"));
  bar.appendChild(kpEl("div", "crumb", page ? page.group + " ← " + page.title : ""));
  bar.appendChild(kpEl("div", "spacer"));
  var search = kpEl("input", "");
  search.id = "kp-search";
  search.type = "search";
  search.placeholder = "ابحث في هذه الصفحة وفي القائمة…";
  search.autocomplete = "off";
  bar.appendChild(search);
  var home = kpEl("a", "btn", "الصفحة الرئيسية");
  home.href = base + "index.html";
  bar.appendChild(home);
  document.body.insertBefore(bar, document.body.firstChild);

  menuBtn.addEventListener("click", function () {
    var nav = document.getElementById("kp-nav");
    if (nav) nav.classList.toggle("collapsed");
  });
  search.addEventListener("input", function () { kpFilter(search.value); });
  return bar;
}

/* ------------------------------------------------------------------ القائمة */
function kpBuildNav(current) {
  var base = kpBase();
  var nav = kpEl("nav", "", "");
  nav.id = "kp-nav";
  var groups = [];
  var i;
  for (i = 0; i < KP_PAGES.length; i++) {
    if (groups.indexOf(KP_PAGES[i].group) === -1) groups.push(KP_PAGES[i].group);
  }
  for (i = 0; i < groups.length; i++) {
    nav.appendChild(kpEl("h4", "", groups[i]));
    for (var j = 0; j < KP_PAGES.length; j++) {
      var p = KP_PAGES[j];
      if (p.group !== groups[i]) continue;
      var a = kpEl("a", "", p.title + "<small>" + (p.sub || "") + "</small>");
      a.href = base + p.href;
      a.dataset.title = (p.title + " " + (p.sub || "")).toLowerCase();
      if (p.href.replace(/^\.\.\//, "") === current || p.href === current) a.className = "active";
      nav.appendChild(a);
    }
  }
  /* روابط إضافية ثابتة */
  nav.appendChild(kpEl("h4", "", "خارج الموقع"));
  var extra = [
    ["README.md (المستودع)", "../../README.md"],
    ["دليل الاستخدام العربي docs/GUIDE_AR.md", "../GUIDE_AR.md"],
    ["ملاحظات المطوّر docs/DEV_NOTES.md", "../DEV_NOTES.md"],
    ["سجل التغييرات docs/CHANGES.md", "../CHANGES.md"],
    ["الترخيص AUTHORIZED_USE_LICENSE.md", "../../AUTHORIZED_USE_LICENSE.md"]
  ];
  for (i = 0; i < extra.length; i++) {
    var e = kpEl("a", "", extra[i][0]);
    e.href = base + extra[i][1];
    e.dataset.title = extra[i][0].toLowerCase();
    nav.appendChild(e);
  }
  var layout = document.getElementById("kp-layout");
  if (layout) layout.insertBefore(nav, layout.firstChild);
  else document.body.insertBefore(nav, document.body.querySelector("main") || null);
  return nav;
}

/* ------------------------------------------------------- البحث داخل الصفحة */
function kpFilter(q) {
  q = (q || "").trim().toLowerCase();
  /* 1) تصفية روابط القائمة */
  var links = document.querySelectorAll("#kp-nav a");
  for (var i = 0; i < links.length; i++) {
    var hit = !q || links[i].dataset.title.indexOf(q) !== -1 ||
              links[i].textContent.toLowerCase().indexOf(q) !== -1;
    links[i].classList.toggle("hide", !hit);
  }
  /* 2) تمييز المطابقات داخل نص الصفحة */
  var body = document.querySelector("main.doc");
  if (!body) return;
  var old = body.querySelectorAll("mark[data-kp]");
  for (i = 0; i < old.length; i++) {
    var parent = old[i].parentNode;
    parent.replaceChild(document.createTextNode(old[i].textContent), old[i]);
    parent.normalize();
  }
  if (q.length < 2) return;
  var walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
    acceptNode: function (n) {
      if (!n.nodeValue || n.nodeValue.toLowerCase().indexOf(q) === -1) return NodeFilter.FILTER_REJECT;
      var p = n.parentNode;
      if (!p || p.nodeName === "SCRIPT" || p.nodeName === "STYLE") return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  var nodes = [], n, guard = 0;
  while ((n = walker.nextNode()) && guard++ < 400) nodes.push(n);
  for (i = 0; i < nodes.length; i++) {
    var text = nodes[i].nodeValue, low = text.toLowerCase(), from = 0, frag = document.createDocumentFragment();
    while (true) {
      var at = low.indexOf(q, from);
      if (at === -1) { frag.appendChild(document.createTextNode(text.slice(from))); break; }
      frag.appendChild(document.createTextNode(text.slice(from, at)));
      var m = document.createElement("mark");
      m.setAttribute("data-kp", "1");
      m.textContent = text.slice(at, at + q.length);
      frag.appendChild(m);
      from = at + q.length;
    }
    nodes[i].parentNode.replaceChild(frag, nodes[i]);
  }
  var first = body.querySelector("mark[data-kp]");
  if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
}

/* ------------------------------------------------------------- التهيئة */
function KPInit(current) {
  current = current || kpCurrent();
  document.documentElement.lang = "ar";
  document.documentElement.dir = "rtl";
  kpBuildTopbar(current);
  kpBuildNav(current);
  /* فهرس داخلي تلقائي من عناوين h2 */
  var doc = document.querySelector("main.doc");
  if (doc) {
    var heads = doc.querySelectorAll("h2[id]");
    var toc = doc.querySelector(".toc-auto");
    if (toc && heads.length) {
      var ol = kpEl("ol", "", "");
      for (var i = 0; i < heads.length; i++) {
        ol.appendChild(kpEl("li", "", "<a href='#" + heads[i].id + "'>" + heads[i].textContent + "</a>"));
      }
      toc.appendChild(ol);
    }
    /* أرقام الأسطر في صناديق الكود data-lines */
    var pres = doc.querySelectorAll("pre[data-lines]");
    for (i = 0; i < pres.length; i++) {
      var lines = pres[i].textContent.split("\n");
      var start = parseInt(pres[i].getAttribute("data-lines"), 10) || 1;
      var out = "";
      for (var j = 0; j < lines.length; j++) {
        if (!lines[j] && j === lines.length - 1) continue;
        out += "<span class='ln'>" + (start + j) + "</span>" +
               lines[j].replace(/&/g, "&amp;").replace(/</g, "&lt;") + "\n";
      }
      pres[i].innerHTML = out;
    }
  }
}
