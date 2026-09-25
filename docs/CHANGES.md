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

## الجولة الثانية · «طلبت 100 محاولة فقال انتهى وما جرّب ولا مرة»

هذا بالضبط ما أبلغت عنه: التشغيل ينتهي فوراً (`stop_reason=calibration_failed`)
والصفحة تقول «التفاصيل في السجل» والسجل فارغ.

| # | المشكلة | الأثر | الإصلاح |
|---|---|---|---|
| 1 | **الصفحة تُخفي سبب التوقف**: تكتب «التفاصيل في السجل» والسجل لا يحتوي شيئاً لأنه لم تُجرَ أي محاولة | المستخدم لا يعرف ما فعله الراوتر ولا ما يفعله بعدها | بطاقة «لماذا توقف» تعرض الآن: عنوان السبب بالعربية (مثال: **الراوتر حاجب جهازك** / **الراوتر رفض الاتصال**) + سطر النصيحة (**→** ما تفعله بالضبط) + خطوات التعلّم ✔/✖ + سطر «المحاولات التي أُجريت فعلاً: **صفر**» |
| 2 | **راوترات ترد على البطاقة الخاطئة بتحويل (302 بلا صفحة)**: الردّ فارغ وخط الأساس فارغ، فاعتُبرا «مثل بعض» | **أي بطاقة صحيحة تُخفى تحت «مثل صفحة الرفض»** على هذا النوع من البوابات | المقارنة تعتمد مكان التحويل (المخطط+المضيف+المسار، بدون متغيّرات الرابط) ورمز الحالة، لا على جسم فارغ |
| 3 | البطاقة التي يحوّلها الراوتر إلى مكان آخر (`/status` بدل `/login?error=1`) لم تكن تُعدّ دليلاً | بطاقات صحيحة تُسجَّل «رد غير واضح» بلا تحقّق | صارت «نجاح» بثقة 0.7 (لا توقف التشغيل وحدها) ثم يتحقّق منها فحص الإنترنت |
| 4 | **كلمات الحجب تُطابق داخل الكلمات** (`"banned"` داخل أي نص، و503 وحده = حجب) | «الراوتر حاجبك» كاذب ⇒ صفر محاولة على شبكة سليمة | مطابقة كلمة كاملة (`find_phrase`)؛ و503 وحده لم يعد حجباً (راديوس مشغول) بل تباطؤ |
| 5 | بطاقة تجربة تصيب بالصدفة تُدخل **صفحة النجاح** داخل خط أساس الرفض | الأداة تتعلّم النجاح على أنه رفض | إعادة التعلّم من بقية العيّنات بدونها (`relearned_without_the_working_probe`) |
| 6 | عثرة واحدة في مرحلة التعلّم (سوكيت أُغلق، راوتر انشغل ثانية) تُنهي التشغيل بصفر محاولة | «قال انتهى وما جرّب» | محاولة تلقائية واحدة قبل التسليم (`stale/reset/read_timeout/connect_timeout/bad_response/unknown`) |
| 7 | بطاقة «التعلّم المستمر» كانت تكتب فوق بطاقة التوقف | سبب التوقف يختفي من الشاشة | لا تُعرض إلا أثناء التشغيل |

* الاختبارات: `38/38` في `tests/` (+2 للتحويلات) و`14/14` في `--selftest`.
* تحقّق حيّ على بوابة حاجبة: `stop=calibration_failed error=blocked_already
  attempts=0` مع الخطوة `rejection_baseline ✖ blocked_already
  {'status': [403,403,403], 'word': 'you are blocked'}` ⇒ تُعرض كلها في الصفحة.

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

Second round - "it said *finished* and never tried once": the stop card now
spells out, in Arabic, exactly what the router did (the network error, which
learning step failed, and what to do) instead of "details in the log" with an
empty log; portals that answer a wrong card with a **redirect** no longer hide
every real hit behind "same as the rejection page" (redirect target and status
are compared instead of an empty body); a card redirected somewhere else than a
rejected one is now positive evidence (0.7, verified by the internet check);
ban words match whole words only and a bare 503 is no longer "blocked"; a probe
that luckily hits is dropped from the rejection baseline; and one hiccup in the
learning phase is retried once instead of ending the run with zero attempts
(38 tests, 14/14 self-test).
