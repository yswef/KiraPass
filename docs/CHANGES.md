# سجل الإصلاحات · Changelog

مراجعة على الكود ملفاً بملفاً: ربط الدوال، التأكد من عملها، وإصلاح ما كان
معطّلاً. كل بند هنا مدعوم باختبار في `tests/` أو بسيناريو في `--selftest`.

---

## 🐞 أخطاء حقيقية أُصلحت (كانت تؤثر على النتيجة)

| # | المشكلة | الأثر | الإصلاح |
|---|---|---|---|
| 1 | **«المتابعة من حيث توقفت» لم تكن تعمل إطلاقاً**: الصفحة تُرسل الملف التعريفي بدون `space_pos` و`walk_a/walk_b`، فيبدأ كل تشغيل من الصفر ويُعيد تخمين نفس البطاقات | إضاعة وقت وكشف غير ضروري على الراوتر | الصفحة تُرسل الموضع ونمط المشي مع الملف التعريفي، والمحرّك يكمل منه؛ تعطيل الخيار يبدأ من البداية بمسار جديد |
| 2 | **مهلة الاتصال تُصنَّف خطأ**: بايثون يدمج مهلة فتح الاتصال ومهلة القراءة في `TimeoutError` واحد | كل راوتر مقطوع يظهر كأنه «راوتر بطيء» بدل «لا يرد على الاتصال» | `httpclient` يغلّف مرحلة `connect()` وحدها ويرمي `connect_timeout` |
| 3 | **تحويل داخل البوابة يُعتبر نجاحاً**: أي 302 إلى مضيف مختلف كان «تحويل خارج البوابة» بثقة 0.85 | راوترات تنتقل بين صفحاتها (login→status) تُنتج بطاقات وهمية | التحويل الذي يحمل كلمات البوابة في الرابط (`login/hotspot/portal/auth/splash/captive`) يصير «رد غير واضح» محفوظاً للمراجعة |
| 4 | **503 كان يُترجم «محظور من الراوتر»** | نصيحة خاطئة (أعد تشغيل الراوتر) بينما السبب RADIUS مشغول | 503 صار «تقييد طلبات/خدمة غير متاحة»: تباطؤ تلقائي، وإيقاف مع السبب الصحيح |
| 5 | **تحميل ملف تعريفي محفوظ ينسى تشفير chap** | بوابات md5.js تعمل فقط بعد فحص جديد | `chap` يُقرأ من الملف التعريفي المحفوظ أيضاً |
| 6 | **صيغة بطاقة مستحيلة تُعاير «بنجاح»** (بادئة أطول من الكرت) | لا يوجد خط أساس، فيُحكم على كل رد بأنه «ليس رفضاً» | المعايرة ترفض الملف التعريفي وتذكر السبب (`card_space_empty` / مشكلة تحقق) |
| 7 | `Fingerprinter.learn` ينهار إذا وصل رد فارغ (`None`) | استثناء داخلي يوقف التشغيل | التجاهل الآمن للرّدود الفارغة |
| 8 | عدّادات (`_ban_count`, `_rate_count`, `_rejected_since_emit`, `_unknown_saved`) تُعدَّل من خيوط العمل بدون قفل | تحديثات ضائعة = صفحة حجب لا تُوقف التشغيل | كل التعديلات داخل القفل |
| 9 | مجلدات `__pycache__` تُحسب مرتين عند مسح الكاش | رقم «المساحة المحرّرة» مضاعف (كذب) | إزالة التكرار |
| 10 | **أول `<form>` في الصفحة يُؤخذ blindly** | صفحات فيها نموذج بحث/لغة تُرسل الحقول الخطأ | كل النماذج تُقيَّم ويختار أكثرها شبهاً بنموذج الدخول |
| 11 | أزرار `submit/button` تُرسل كحقول ثابتة | بعض البوابات ترفض الطلب | الأزرار لا تُرسل |
| 12 | مطابقة كلمات الرفض بالنص الجزئي («error» داخل «errors») | صفحات نجاح تُقرأ كرفض → بطاقات صحيحة تضيع | مطابقة الكلمة الكاملة (`find_phrase`) |
| 13 | الرمز السري يُقارن بـ `==` | قابل للاستنتاج من زمن الاستجابة | `hmac.compare_digest` |
| 14 | اسم حقل غير موجود في واجهة JS (`f_names`) | تحديث المعاينة لا يعمل عند تغيير الاسم | `f_name` |

## ✨ تحسينات

* **زر «إيقاف الأداة»** في أسفل الصفحة (`POST /api/quit`) — مفيد على الهاتف حيث لا يوجد Ctrl+C.
* **الصفحة تذكر التغطية السابقة**: عدد ما جُرّب من هذا النطاق في runs سابقة،
  في قائمة الملفات التعريفية وفي بطاقة المعاينة.
* **المسح التلقائي بعد فحص شبكة محفوظة**: إذا فحصت شبكة سبق حفظها تُحمَّل إعداداتها وموضعها تلقائياً.
* **حدث `resume`** في سجل التشغيل: «↪ متابعة من 250».
* **الصفحة لا تتجمّد إذا توقفت الأداة**: رسالة واضحة بدلاً من شاشة ثابتة.
* إحصاءات أدقّ: `samples` يظهر في نتيجة المعايرة، و`RemoteDisconnected` صار `stale` بدل `reset`.
* `clear_cache` لم يعد يترك الجلسة مفتوحة، و`/api/scan` يُغلق اتصاله دائماً.
* ترويسات أمان: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
* بوابة التدريب (`mockportal`) لم تعد تحصي مرتين عمليات الدخول الناجحة.

## 🧪 الاختبارات

* `python3 -m unittest discover -s tests -v` → **36** اختباراً (كان 26).
* `python3 KiraPass.py --selftest` → **14** سيناريو (كان 13)، منها
  `a_second_run_continues_where_the_first_stopped`.
* `python3 tools/checks/web_e2e.py` → الرحلة كاملة عبر الـ API **+ تحقّق من
  المتابعة** (run 1 ينتهي عند 150، run 2 عند 300، نفس المسار).

---

## English (short)

Real bugs fixed: the "continue where you stopped" feature never worked (the
page did not send `space_pos`/`walk_*` back, so every run restarted and
re-guessed the same cards); connect timeouts were reported as read timeouts;
a redirect *inside* the portal counted as a hit; HTTP 503 was reported as
"blocked by the router"; loading a saved profile forgot the MikroTik chap
formula; an impossible card format calibrated "successfully" against an empty
baseline; several counters were updated from worker threads without a lock;
`__pycache__` folders were counted twice when clearing the cache; the first
`<form>` on the page was taken blindly and named buttons were sent as data;
reject words matched inside other words ("error" in "errors"); the LAN token
was compared with `==`.

Added: a "stop the tool" button (`POST /api/quit`) for phone use, the covered
count shown in the profile list and the preview, auto-loading a saved profile
when the same network is scanned again, a `resume` event in the run log, a
clear message when the tool is gone, and 10 new tests plus one new self-test
scenario.
