# KiraPass 5 · كيراباس

أداة اختبار أمني للشبكات التي **تملكها** أو **لديك إذن كتابي** باختبارها:
تتحقّق من قوة أكواد كروت/بطاقات الدخول في شبكات الهوتسبوت (MikroTik وغيرها)
وتخبرك **بماذا ردّ الراوتر على كل محاولة وسبب الرد**.

> ⚠️ **قبل أي شيء:** استخدام الأداة على شبكة ليست لك أو بدون إذن كتابي من
> صاحبها مخالف للقانون. اقرأ [AUTHORIZED_USE_LICENSE.md](AUTHORIZED_USE_LICENSE.md).
> الأداة نفسها تطلب منك إقراراً بذلك قبل أن تبدأ.

---

## ما الجديد في هذه النسخة (ولماذا)

النسخة السابقة كانت **تعطّلت فعلياً** في شبكات POST: صفحة الرد فيها رمز جلسة
يتغيّر مع كل طلب، والأداة كانت تقارن صفحات بطريقة «الطول ±40 بايت»، فكانت
تعتبر أي رد مختلف «بطاقة ناجحة» وتتوقف، أو تفشل في تمييز النجاح الحقيقي.
كل التفاصيل والبراهين في [docs/WHY_IT_STOPPED_AR.md](docs/WHY_IT_STOPPED_AR.md).

هذه النسخة:

* **تقرأ صفحة الدخول بنفسها** (POST/GET، أسماء الحقول، الحقول المخفية، تشفير
  `md5.js` الخاص بميكروتيك) فلا توجد أسئلة عن أشياء يمكن قراءتها.
* **تتعلّم شكل صفحة الرفض** بإرسال بطاقات تجريبية، وتتجاهل الرموز المتغيّرة
  تلقائياً، فلا تخطئ أبداً بين «مرفوضة» و«ناجحة».
* **لا تسمّي أي بطاقة ناجحة إلا بدليل**: تحويل خارج البوابة، أو كلمات نجاح
  تعلّمتها من بطاقتك، أو **اختبار إنترنت حقيقي**.
* **تشرح كل نتيجة**: مقبولة، مرفوضة، محظور من الراوتر، تقييد طلبات، انقطاع
  اتصال، أو «رد غير واضح» تحفظه لك لتقرأه بنفسك.
* **تعمل من المتصفح**: الأداة باك-إند فقط، تطبع رابطاً محلياً وتفتحه وتجيب على
  كل شيء من الصفحة — لذلك تعمل على ويندوز وهاتف أندرويد (Termux/Pydroid) ولينكس
  وماك **بدون أي مكتبات خارجية** (لا تحتاج `pip install`).

---

## التشغيل في دقيقة

```bash
# 1) لا يحتاج أي تثبيت - بايثون فقط (3.8+)
python3 KiraPass.py
```

ستطبع الأداة رابطاً محلياً، مثال:

```
Open this link / افتح هذا الرابط:
    http://127.0.0.1:8770/
```

افتح الرابط في المتصفح، ثم أربع خطوات:

| الخطوة | ماذا تفعل |
|---|---|
| 1 · فحص الشبكة | الصق رابط صفحة دخول الهوتسبوت → «افحص الآن» |
| 2 · صيغة البطاقة | البادئة + الطول (المعاينة تُظهر عدد الاحتمالات) |
| 3 · التشغيل | اختر «عادي» أو «آمن» → ✅ إقرار الإذن → «ابدأ التخمين» |
| 4 · النتائج | راقب الأسباب لحظة بلحظة، وأوقف متى شئت |

### أوامر أخرى

```bash
python3 KiraPass.py --selftest        # اختبار ذاتي على راوتر وهمي محلي (لا يلمس شبكتك ولا بياناتك)
python3 KiraPass.py --clear-cache     # مسح الكاش وصفحات المراجعة
python3 KiraPass.py --check           # التأكد من البيئة والأذونات
python3 KiraPass.py --host 0.0.0.0    # للاستخدام من الهاتف على نفس الواي فاي (يرسل رمز دخول)
python3 KiraPass.py --port 9000       # تغيير المنفذ
python3 KiraPass.py --help            # كل الخيارات
```

### التجربة بأمان قبل شبكتك الحقيقية

يشغّل هذا الأمر «بوابة تدريب» وهمية على جهازك فقط، فتجرب الأداة وترى معنى كل
رسالة بدون أي مخاطرة. ثم وجّه الأداة إلى `http://127.0.0.1:8899/login`.

```bash
python3 tools/practice_portal.py --card 0201240007 --ban-after 300
```

**تجربة صغيرة تجد فيها البطاقة فعلاً** (1000 احتمال فقط بدل 10 ملايين):

```bash
# 1) بوابة تدريب صغيرة، والبطاقة الصحيحة داخل النطاق
python3 tools/practice_portal.py --port 8898 --card 020124042 --pass-mode empty --ban-after 5000

# 2) في طرفية أخرى: اختبار الإنترنت يستعمل بوابة التدريب نفسها
#    (لأن جهازك هنا لا يستطيع الوصول إلى مواقع الفحص الحقيقية)
KIRAPASS_INTERNET_CHECKS="http://127.0.0.1:8898/generate_204|204" python3 KiraPass.py

# 3) في الصفحة: البادئة 020124 والطول 9 → ابدأ
#    النتيجة المتوقعة خلال ثانية: مقبولة ومؤكّدة = 020124042
```

> على شبكة حقيقية لا تحتاج المتغيّر `KIRAPASS_INTERNET_CHECKS`؛ استخدمه فقط
> إذا كانت الشبكة تحجب مواقع الفحص الثلاثة المعروفة (google/msft/apple)،
> أو إن أردت أن يفحص الإنترنت عبر رابط يختاره صاحب الشبكة.

للتحقق الآلي من الرحلة كاملة (فحص ← صيغة ← تعلّم ← تشغيل ← نتيجة) بدون متصفح:

```bash
python3 tools/checks/web_e2e.py
```

---

## كيف تقرأ النتائج

| النتيجة | معناها | ما تفعله |
|---|---|---|
| **مقبولة ومؤكّدة** | الراوتر قبل البطاقة **والإنترنت يعمل فعلاً** | هذه بطاقة صالحة |
| **مقبولة** | الراوتر حوّل المتصفح خارج البوابة | تأكيد إضافي جيد |
| **قبلها الراوتر (تأكيد الإنترنت فشل)** | الراوتر قبل، لكن لم أستطع إثبات الإنترنت (شبكتك محجوبة أو جهازك متصل أصلاً) | افتح صفحة الحالة أو جرّب البطاقة في المتصفح |
| **مرفوضة** | رد مطابق تماماً لصفحة الرفض (بطاقة خاطئة) | اكمل التخمين |
| **رد غير واضح** | رد ليس رفضاً وليس نجاحاً مؤكّداً | محفوظ في «صفحات المراجعة» — افتحه واقرأه |
| **محظور من الراوتر** | ظهرت صفحة حجب/منع صريحة | غيّر IP (أعد تشغيل الراوتر أو أعد الاتصال) وقلّل المسارات |
| **تقييد طلبات** | الراوتر يبطّئك (429) | الأداة أبطأت تلقائياً وأخبرتك — أوقف ثم أعد بمسارات أقل |
| **خطأ اتصال** | لم يصل الطلب (قطع، رفض، مهلة) | يظهر نوع الخطأ بدقة، والأداة تعيد المحاولة |

السبب الدقيق مكتوب بجانب كل محاولة في السجل (مثلاً: «رد مطابق لصفحة الرفض»
أو «الراوتر قطع الاتصال فجأة»)، وكل توقّف يشرح **لماذا توقف**.

وفي أعلى صفحة النتائج جدول **«لماذا انتهت كل محاولة بهذه النتيجة؟»** يجمع
الأسباب مع عددها (مثال حقيقي من تدريب كامل:

```
رد مطابق لصفحة الرفض                 174
تحويل خارج البوابة + الإنترنت يعمل     1
```

ونفس الجدول محفوظ داخل ملف التقرير في `kirapass_data/runs/`، فتعرف بعد أسبوع
لماذا انتهت الجلسة كما انتهت.

### المتابعة بلا تكرار

كل تشغيل يحفظ موضعه داخل الملف التعريفي (`space_pos` مع مسار مشي مخلوط لا
يكرّر بطاقة). شغّل مرة ثانية وستكمل من حيث توقفت — تعطيل خيار «المتابعة من حيث
توقفت» يبدأ من البداية بمسار جديد. عدد ما جرّبته يظهر أمامك في قائمة الملفات
التعريفية وفي بطاقة المعاينة.

### إيقاف الأداة من الصفحة

زر **«إيقاف الأداة»** في أسفل الصفحة يوقفها تماماً (مفيد على الهاتف حيث لا
يوجد `Ctrl+C`).

---

## المسموح والممنوع (باختصار)

* ✅ شبكتك، أو شبكة صديق/عميل **بإذن كتابي** (منها شبكة صديقك الذي يبيع الكروت).
* ❌ شبكة جيرانك، شبكات عامة، أو أكواد ليست لك.
* ❌ استخدام الأداة لسرقة خدمة مدفوعة.

الترخيص الكامل: [AUTHORIZED_USE_LICENSE.md](AUTHORIZED_USE_LICENSE.md)

---

## التوثيق

| الملف | المحتوى |
|---|---|
| [docs/GUIDE_AR.md](docs/GUIDE_AR.md) | دليل الاستخدام بالتفصيل (عربي مبسّط) |
| [docs/GUIDE_EN.md](docs/GUIDE_EN.md) | Full user guide (simple English) |
| [docs/WHY_IT_STOPPED_AR.md](docs/WHY_IT_STOPPED_AR.md) | تشخيص الأعطال القديمة بالأدلة + كيف تأكدت |
| [docs/WHY_IT_STOPPED_EN.md](docs/WHY_IT_STOPPED_EN.md) | The old failures, explained with evidence |
| [docs/MAKE_PRIVATE.md](docs/MAKE_PRIVATE.md) | خطوات جعل المستودع خاصاً (عربي + English) |
| [docs/DEV_NOTES.md](docs/DEV_NOTES.md) | بنية الكود والاختبارات لمن يريد التطوير |
| [docs/CHANGES.md](docs/CHANGES.md) | ما أُصلح وما أُضيف في هذه المراجعة (سجل الإصلاحات) |

## الملفات التي تُنشئها الأداة

كل شيء داخل مجلد واحد: `kirapass_data/` (تقارير، سجل نتائج، صفحات مراجعة،
ملفات تعريفية). يمكنك حذفه كاملاً بأمر `--clear-cache all` أو من زر 🧹 في الصفحة.

---

<details>
<summary><b>English</b> (click)</summary>

# KiraPass 5

An authorized security-testing tool for captive-portal / hotspot networks you
own or have written permission to test. It measures how strong the guest access
codes are, and - most importantly - it tells you **what the router answered on
every attempt and why**.

> ⚠️ Using it on a network you do not own, or without the owner's written
> permission, is unlawful. See [AUTHORIZED_USE_LICENSE.md](AUTHORIZED_USE_LICENSE.md).

## Quick start

```bash
python3 KiraPass.py            # prints a local link, opens it, done
python3 KiraPass.py --selftest # proves it works using local mock routers only
python3 KiraPass.py --help     # all options
```

No `pip install` is needed: the standard library is enough, which is why it
runs on Windows, Linux, macOS and Android (Termux / Pydroid) alike. iPhone is
not supported (its browsers cannot reach a local server reliably).

The page has four steps: **scan** the login page, describe the **card format**,
**run**, watch the **results**. Every attempt is one of: accepted & verified,
accepted, unverified accept, rejected, unclear reply, blocked by the router,
rate limited, network error - each with a reason, and every stop is explained.

Runs **resume** instead of repeating: the position is kept in the profile, so a
second run continues where the first stopped (uncheck "continue where you
stopped" to start over). The footer has a **stop the tool** button for phones.
See [docs/CHANGES.md](docs/CHANGES.md) for the bugs this revision fixed.

A safe playground ships with the tool:

```bash
python3 tools/practice_portal.py --card 0201240007 --ban-after 300
```

More: [docs/GUIDE_EN.md](docs/GUIDE_EN.md),
[docs/WHY_IT_STOPPED_EN.md](docs/WHY_IT_STOPPED_EN.md),
[docs/MAKE_PRIVATE.md](docs/MAKE_PRIVATE.md).

</details>
