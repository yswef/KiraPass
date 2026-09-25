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

## الجولة الثالثة · سبب «الحظر» وكيف يزول

صورة المستخدم تظهر الحظر. الحظر في الأداة يعني: **الراوتر يرفض هذا الجهاز قبل
أي محاولة** (صفحة حجب أو `403/429`). والآن الأداة تفرّق بين سببين مختلفين تماماً:

| الحالة | كيف تعرفها | ما تفعله |
|---|---|---|
| **حظر سابق** (`blocked_before_probes`) — صفحة الدخول نفسها صفحة حجب | الأداة **لا تُضيّع أي بطاقة تجربة**، تكتشفه من أول GET | أعد الاتصال بالشبكة لتغيير الـ IP (أو فعّل «عنوان MAC عشوائي/خاص» لهذه الشبكة في إعدادات الهاتف)، أو أعد تشغيل الراوتر إن كنت مديره، ثم ابدأ من جديد |
| **حظر نحن سببه** (`blocked_by_our_probes`) — بطاقات التجربة نفسها ملأت عداد المحاولات الفاشلة | الأداة تقارن: صفحة الدخول كانت سليمة قبل التجربة | **الأداة تنتظر ٤٥ ثانية ثم تعيد التعلّم ببطاقتي تجربة بدل ثلاث** تلقائياً؛ وإن تكرّر: قلّل الخيوط (2-4) وأضف مهلة بين المحاولات |

* الأزرار الجديدة في بطاقة التوقف: **«أعد المحاولة الآن»** و**«أعد المحاولة بعد ٤٥ ثانية»** (عدّ تنازلي على الشاشة).
* المهلة قابلة للتغيير بدون تعديل الكود: `KIRAPASS_BLOCK_WAIT=120 python3 KiraPass.py`.
* للتدرّب على الحالة محلياً: `python3 tools/practice_portal.py --ban-after 2 --ban-seconds 8`
  (يحجب بعد محاولتين و**يفك الحظر بعد ٨ ثوان**) — الأداة تتعافى منه وحدها:
  `calibration ok=True, samples=2` ثم يبدأ التشغيل، وعدّاد `BANNED` يوضح أن
  الراوتر يحجب كل محاولتين (أي: على راوتر كهذا لا يوجد تخمين ممكن بدون مهلة
  طويلة بين المحاولات).
* اختباران جديدان: `40/40` في `tests/` و`14/14` في `--selftest`.

**لتجربة أن التخمين يعمل أصلاً:** استخدم البوابة المحلية الشغّالة (بدون حظر)
على `http://127.0.0.1:8898/login` والكرت `020124042` — تصل إليه في نحو ألف
محاولة ويظهر في الصفحة كـ «نجاح مؤكد بالإنترنت».

---

## الجولة الرابعة · «لازالت تنحظر» — كان تشخيصاً خاطئاً

بطاقة التوقف التي أرسلتها كانت تقول:

```
✔ الوصول إلى صفحة الدخول: الصفحة ردت بشكل سليم
✖ الوصول إلى صفحة الدخول: صفحة الحجب ظهرت قبل أن نجرّب أي بطاقة
```

سطران متناقضان لنفس الخطوة، وفيهما المشكلة كلها:

| # | المشكلة | الإصلاح |
|---|---|---|
| 1 | **صفحة الدخول تُعتبر صفحة حجب لمجرّد أن نصها فيه كلمة حجب** («banned»/«محظور»/«slow down» في سطر تحذير أو Footer). الصفحة فيها نموذج الدخول وترد 200 — أي ليست صفحة حجب | «حجب» الآن = `403/429` **أو** (كلمة حجب **و** الصفحة بلا نموذج دخول). صفحة فيها النموذج تُقبل، ويُكتب سبب ذلك في الخطوة: `http_ok_word_ignored` مع الكلمة التي وُجدت |
| 2 | نفس الخطوة تُعرض مرتين (✔ ثم ✖) | تُسجَّل مرة واحدة فقط |
| 3 | لا يُعرض دليل الحكم | البطاقة تعرض الآن الكلمة المطابقة ورمز الحالة وعدد بطاقات التجربة: `«banned» · HTTP 403 · 3 بطاقات تجربة` |

**دليل حيّ** على بوابة صفحتها فيها كلمة «banned» وفيها النموذج:
```
OK   reach_login_page -> http_ok_word_ignored {'word': 'banned'}
stop=attempts_done  tried=100  counters={'REJECTED': 100}
```
قبل الإصلاح نفس الصفحة كانت تعطي `blocked_before_probes` و**صفر محاولة**.

### والحظر إن كان حقيقياً: صبر بدل الطرق
بدل أن يوقف التشغيل عند ثالث ردّ حظر، الأداة الآن **تجلس مدة الحظر مرة واحدة**
(٤٥ ثانية، `KIRAPASS_BLOCK_WAIT`) ثم تكمل ببطء (مهلة ٣ ثوان بين المحاولات).
إن عاد الحظر توقّف مع `banned_by_router` — لأن الراوتر يقول بوضوح: «أبطئ».

### لماذا لا نغيّر MAC/IP في كل طلب؟
طلبك كان «خليها تغيّر الـ MAC والـ IP في كل طلب». هذا غير مطبّق، وثلاثة أسباب:

1. **غير ممكن بالمعدّل المطلوب**: تغيير الـ MAC يعني فصل الارتباط عن نقطة الوصول،
   ثم إعادة الارتباط وطلب DHCP — ثوانٍ لكل محاولة، بينما التخمين يحتاج مئات
   المحاولات في الدقيقة. وتغيير الـ IP يحتاج إعادة الاتصال نفسها.
2. **يقطع شبكتك أنت**: كل تغيير يفصل جهازك عن الشبكة، وإن فشل DHCP تبقى خارجها.
3. **هو تهرّب من حماية**: على شبكة تملكها الحل من داخل الراوتر نفسه (استثناء
   جهازك / رفع حدّ المحاولات / تخفيف مهلة الدخول) لا من كسر الحماية؛ وعلى شبكة
   لا تملكها فهو خارج نطاق الأداة (`AUTHORIZED_USE_LICENSE.md`).

البديل اليدوي المشروع على جهازك أنت: **«عنوان MAC عشوائي/خاص»** في إعدادات الهاتف
لهذه الشبكة (أندرويد: Private Wi-Fi address · iOS: Private Address) — تغيّره مرة
واحدة وتكمل الاختبار، دون أن نبرمجه كتهرّب تلقائي داخل الأداة.

* اختبارات: `43/43` (+3 للتشخيص الخاطئ) و`14/14` في `--selftest`.

---

## الجولة الخامسة · «النت اشتغل بس ما قال لي في كرت صح» + «١٤ حظر»

### 1. كرت صحيح والراوتر يرد «رفض»
بعض الراوترات تُدخل الضيف فعلاً ثم ترد **بنفس صفحة الرفض**. فلا يوجد رد يُعلن النجاح،
والتخمين يستمر بلا نتيجة. الحل: **الإنترنت نفسه لا يكذب**.

* أثناء التشغيل يسأل الأداة كل ٣ ثوان: «هل ما زلنا خلف الجدار؟» (`WATCH_EVERY_SECONDS`).
* إذا تحوّل الجواب إلى «متصل» ⇒ **أحد الكروت التي أُرسلت للتو هو الصحيح**: يوقف التشغيل
  بسبب `internet_opened` ويعرض قائمة **المشتبهين** (كل كرت أُرسل منذ آخر فحص، مع الوقت)،
  ويحفظها في التقرير (`internet_opened.suspects`).
* البطاقة في الصفحة: **«الإنترنت فتح أثناء التشغيل - أحد هذه الكروت هو الصحيح»** +
  الكروت + شرح: أوقف الجلسة وجرّبها واحداً واحداً.

دليل حيّ على بوابة «نجاح مخفي» (تفتح النت وترد `invalid username or password`):
```
stop_reason : internet_opened
attempts    : 5  counters: {'REJECTED': 5}   hits: []   ← لم يُعرف من الرد
suspects    : ['020124042', '020124052', '020124062', '020124072']
                    ↑ هو الصحيح وهو أول المشتبهين
```
> تنبيه مهم: «النت اشتغل» **ليس دائماً** دليلاً على كرت صحيح (بيانات الجوال، جلسة قديمة،
> راوتر يمنح فترة تجريبية). لذلك الأداة تسجّل حالة الإنترنت قبل التشغيل، وإن كنت متصلاً
> أصلاً فهي تقول ذلك صراحة (`internet_online_verification_limited`) ولا تدّعي تحققاً.

للتدرّب: `MockPortal(..., hide_success=True)` (أضفته للبوابة التجريبية) = راوتر يدخلك ويرد رفضاً.

### 2. أربعة عشر حظراً ثم إيقاف
| المشكلة | الإصلاح |
|---|---|
| الكرت الذي يرد الراوتر عليه بصفحة حظر يُحسب «مُجرَّباً» ويُحسب ضمن التغطية - أي يُستبعد لاحقاً وهو **لم يُختبر أصلاً** | صفحة الحظر/التقييد ليست إجابة: الكرت لا يُحسب لا في `covered` ولا في موضع المتابعة، فيُعاد تجريبه لاحقاً |
| التشغيل يستمر في الطرق بعد الحظر | عند ثالث رد حظر: **جلوس مرة واحدة** مدة الحظر (`KIRAPASS_BLOCK_WAIT`) ثم متابعة بمهلة ٣ ثوان |

* نصيحة عملية من تجربتك: راوتر يحجب بعد محاولتين = **لا يوجد تخمين ممكن** عليه بأي سرعة؛
  إما مهلة طويلة (٣٠–٦٠ ثانية) وخيط واحد، أو تعديل الإعداد من الراوتر نفسه إن كنت مديره.

* اختبارات: `45/45` (+2 للمراقب والتغطية) و`14/14` في `--selftest`.

---

## الجولة السادسة · «كل طلب من IP/متصفح مختلف؟» + «قِس حدّ الحظر»

### هل فكرة «طلب لكل IP/متصفح» تنجح؟ لا — وسببها فيزياء الشبكة

| الفكرة | لماذا لا تنجح |
|---|---|
| **تغيير IP المصدر في كل طلب** | عنوان المصدر يحدّده الراوتر (DHCP). إن زوّرته: الراوتر يرد على ذلك العنوان فيسأل عنه بـ ARP ولا أحد يجيب، والواي فاي في وضع «عميل» يمرّر إطارات MAC جهازك فقط ⇒ **الرد لا يعود أبداً** ⇒ لا TCP ولا HTTP ⇒ **صفر محاولات** |
| **«متصفح مختلف» / User-Agent / كوكيز** | الراوتر يحجب على **MAC + IP** (طبقة ٢ و٣)؛ المتصفح لا يراه أصلاً ولا يهمّه. تغييره تجميل لا أكثر |
| **بروكسي/VPN متعدد المخارج** | الطلب يخرج من خارج شبكة البوابة، فالراوتر لا يراه ولا يصادق جهازك، والضيف الذي يُفتح له هو IP البروكسي لا أنت |
| **تغيير MAC (الطريقة الوحيدة التي تغيّر الهوية فعلاً)** | تعمل تقنياً، لكن كل دورة = فصل ارتباط + إعادة ربط + DHCP = **ثوانٍ**؛ فبدل ٢٠٠ محاولة/دقيقة تصير محاولة كل ٥ ثوان = **أبطأ من التباطؤ**. وتحتاج root، وتقطع شبكتك، ويسجّلها الراوتر كإنذار MAC flooding، وهي تهرّب من حماية |

> الخلاصة: المحاولة تحتاج **عشرات المحاولات على نفس الهوية** لا هوية لكل محاولة.
> التبديل يكثر الهويات لا المحاولات المفيدة، وبسرعة أقل بكثير.

### البديل المطبّق: **قِس الحظر بدل كسره**
زر جديد **«قِس حدّ الحظر»** (`POST /api/lockout` → `engine.probe_lockout`):

1. يرسل كروتاً خاطئة **واحدة واحدة وبهوادة** حتى يرفضها الراوتر ⇒ `ban_after` = كم محاولة يسامحها.
2. ينتظر ويسأل كل ١٠ ثوان (بصفحة الدخول **وبكرت تجربة**، لأن بعض الراوترات تُظهر الحظر عند المحاولة فقط) حتى يرجع ⇒ `clears_after` = كم يطول الحظر.
3. يحسب **أسرع وتيرة آمنة**: `clears_after ÷ ban_after` ⇒ «محاولة كل ٣٫٣ ثانية».

مثال حيّ (بوابة مضبوطة على: حظر بعد ٣، يزول بعد ٨ ثوان):
```
ban_after   : 3        ← طابق إعداد الراوتر بالضبط
clears_after: 10 ثانية
safe_delay  : 3333 ms  ← «محاولة كل ٣٫٣ ثانية»
```
وإن كان الراوتر لا يفك الحظر أصلاً ⇒ يقولها صراحة: «لا يمكن التخمين على هذا الراوتر
دون حظر متكرر: إما مهلة طويلة جداً، أو تعديل الإعداد من الراوتر نفسه».

هذه نتيجة اختبار مشروعة تكتبها في تقريرك: «البوابة تقفل بعد N محاولة وتفتح بعد M ثانية»
(أو: «لا تقفل أبداً» — وهي ملاحظة أمنية بحد ذاتها).

* اختبارات: `48/48` (+3 للقياس) و`14/14` في `--selftest`.

---

## الجولة السابعة · «الكرت المعروف ما أثبت نفسه»

الرسالة `✖ ضبط شكل الطلب باستخدام البطاقة المعروفة: لم أستطع إثبات أن البطاقة
المعروفة تعمل بهذه الإعدادات` كانت بلا سبب ولا دليل. الآن ثلاث تحسينات:

| # | المشكلة | الإصلاح |
|---|---|---|
| 1 | **لا يُقال لماذا فشل** | الخطوة تعرض **جدولاً** بكل شكل جرّبناه (كلمة المرور: فارغة/نفس الكرت/محذوفة/chap/md5 × الرابط dst) مع رمز الحالة ونوع الحكم **ونصّ ردّ الراوتر**: `empty · HTTP 200 · رفض · «invalid username or password»` |
| 2 | **الكرت قد لا يطابق الصيغة أصلاً** (أكثر سبب شيوعاً) | فحص قبل أي طلب: الطول ≠ الطول المضبوط / لا يبدأ بالبادئة / لا ينتهي باللاحقة / فيه رموز خارج الأبجدية ⇒ `known_card_out_of_format` مع السبب بالتحديد — **بلا أي محاولة فاشلة على الراوتر** |
| 3 | **نصوص ناقصة تظهر كمفاتيح خام** (`internet_walled`، `internet_`) | أضيفت ترجمة `cal_internet_*`، وإضافة «حالة الإنترنت» لا تُطبع إلا إن وُجدت فعلاً |

مخرجات حقيقية من نفس الأداة على بوابة التدريب:
```
كرت يعمل          → OK   shape_tuned  known_card_works      {"mode":"empty","evidence":1.0,"verified":true}
كرت لا يعمل       → FAIL shape_tuned  known_card_not_proven  جُرّب ١٢ شكلاً؛ مثال: [empty] HTTP 200 «invalid username or password»
كرت بصيغة أخرى    → FAIL shape_tuned  known_card_out_of_format  {"reason":"length_mismatch",...}
```

**كيف تقرأ الجدول إن فشل كرتك:**
* كل الأشكال رجعت «مثل صفحة الرفض» ⇒ الكرت **منتهٍ/مستخدم**، أو كلمة المرور/أحد الحقول
  ناقص ⇒ افتح صفحة الدخول في المتصفح، سجّل دخولاً ناجحاً، وقارن الحقول المرسَلة.
* رجع «محجوب» ⇒ أعد الاتصال لتغيير الـ IP ثم أعد المحاولة.
* رجع «الكرت لا يطابق الصيغة» ⇒ صحّح **الطول والبادئة** في نموذج البطاقة (مثال: كرت من
  ١٠ خانات يحتاج «الطول = ١٠»).

* اختبارات: `51/51` (+3 للكرت المعروف) و`14/14` في `--selftest`.

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

Third round - the block itself: the tool now tells the two cases apart. A block
page that was already there (`blocked_before_probes`) is detected on the first
GET, without wasting a single test card, and the advice is a new IP (reconnect,
or the phone's per-network randomized/private MAC) or a router restart. A block
our own learning cards caused (`blocked_by_our_probes`) is waited out
automatically - 45s (override with `KIRAPASS_BLOCK_WAIT=...`), then the
learning is retried with two cards instead of three. The stop card offers
"try again now" and "try again after 45s" buttons. The practice portal grew
`--ban-seconds` so the whole cycle can be rehearsed locally (40 tests,
14/14 self-test).

Fourth round - "still blocked": the block was a misdiagnosis. A login page
that merely MENTIONS blocking ("... is banned" in a footnote) while still
offering the form was called a block page, which stopped every run with zero
attempts - the page even printed the same step twice, once ok and once failed.
A block is now 403/429, or a ban word on a page that has NO login form; the
step is recorded once, and the card shows the evidence (matched word, status,
number of test cards). When a block is real the run no longer dies at the third
ban reply: it sits out the lockout once (45s, KIRAPASS_BLOCK_WAIT) and then
continues at 3s per attempt instead of hammering a router that asked us to slow
down. Automatic MAC/IP rotation per request is deliberately NOT implemented -
it needs root, tears down the operator's own association (deauth + DHCP per
attempt, so hundreds of attempts per minute become seconds each), and it
circumvents a protection instead of testing with permission (43 tests,
14/14 self-test).

Fifth round - "the internet worked but it never told me a card was correct":
some routers log the guest in and still answer with the rejection page, so no
verdict ever looks like a hit. The tool now asks "are we still behind the
wall?" every 3s while a run is going; when the answer flips to online it stops
with stop_reason=internet_opened and lists every card sent since the previous
check as suspects (also saved in the report). Rehearse it with
MockPortal(..., hide_success=True). And a card the router answered with a block
or rate-limit page is no longer counted as tested: it is excluded from the
covered count and from the resume position, so it is retried instead of being
skipped forever - which is what turned 14 bans into "covered" cards that were
never really tried (45 tests, 14/14 self-test).

Sixth round - "can each request come from a different IP/browser?": no, and
not for policy reasons. A spoofed source IP never gets an answer (the router
ARPs for it, and a Wi-Fi client may only send frames from its own MAC), so
TCP never completes; the router blocks on MAC+IP at layers 2-3 and never sees
a User-Agent; a proxy pool puts the traffic outside the portal so your device
is never authenticated; and MAC rotation - the only thing that really changes
identity - costs seconds per cycle (disassociate + DHCP) and needs root, which
is slower than simply backing off. What is added instead is a "measure the
lock-out" button (engine.probe_lockout, POST /api/lockout): it sends wrong
cards one at a time until the router refuses, then watches when the door opens
again (checking with a real trial card too, since some routers only show the
block page on a login attempt) and reports ban_after, clears_after and the
fastest pace that stays under the limit - or states plainly that guessing on
this router is not possible (48 tests, 14/14 self-test).

Seventh round - the known-good card step: "could not prove this card works"
now comes with the evidence. Every request shape we tried (password empty /
same as card / omitted / chap / md5 x each dst value) is reported with its
status, verdict and the router's own words, so "the card is used up", "a field
is missing" and "you are blocked" can be told apart. Before any request the
card is checked against the format - wrong length, prefix, suffix or charset
is reported as known_card_out_of_format without spending a single failed login
on the router (the most common cause: a 10-digit card in a 9-digit profile).
Two raw translation keys that leaked into the Arabic page (internet_walled and
a bare "internet_") are fixed (51 tests, 14/14 self-test).